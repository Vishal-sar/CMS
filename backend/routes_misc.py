import re, json
from typing import Optional, List
from datetime import date as Date, timedelta
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from pydantic import BaseModel, Field
from core import (db, now_iso, new_id, clean, require, audit, crud, teacher_ctx, student_query, assert_student, assert_section_access, get_settings,
                  today, notify, audience_user_ids, get_current_user, paginate, next_seq, put_object, get_object, to_csv, send_email, email_template, class_teacher_pairs)
import os

router = APIRouter(prefix="/api")

# ---------- files ----------
ALLOWED = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "pdf": "application/pdf", "txt": "text/plain",
           "doc": "application/msword", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
IMAGE_CTX = ("photo", "logo")

@router.post("/files")
async def upload(file: UploadFile = File(...), context: str = Form("homework"), user=Depends(get_current_user)):
    if context not in ("photo", "logo", "homework", "submission"): raise HTTPException(422, "Invalid upload context")
    if context == "logo" and user["role"] != "admin": raise HTTPException(403, "Not permitted")
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED or (context in IMAGE_CTX and not ALLOWED[ext].startswith("image/")): raise HTTPException(422, f"File type .{ext} is not allowed")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024: raise HTTPException(422, "File exceeds the 5 MB limit")
    fid = new_id()
    res = await put_object(f"{os.environ['APP_NAME']}/{context}/{user['id']}/{fid}.{ext}", data, ALLOWED[ext])
    doc = {"id": fid, "storage_path": res["path"], "original_filename": file.filename[:200], "content_type": ALLOWED[ext], "size": len(data), "context": context,
           "owner_id": user["id"], "is_deleted": False, "created_at": now_iso()}
    await db.files.insert_one(dict(doc))
    return clean(doc)

@router.get("/files/{fid}")
async def download(fid: str, user=Depends(get_current_user)):
    f = await db.files.find_one({"id": fid, "is_deleted": False}, {"_id": 0})
    if not f: raise HTTPException(404, "File not found")
    if f["context"] == "submission" and user["role"] not in ("admin", "teacher") and f["owner_id"] != user["id"]:
        sub = await db.submissions.find_one({"files.id": fid}, {"_id": 0})
        if not sub: raise HTTPException(403, "Not permitted")
        await assert_student(user, sub["student_id"])
    data, _ = await get_object(f["storage_path"])
    return Response(content=data, media_type=f["content_type"], headers={"Content-Disposition": f'inline; filename="{f["original_filename"]}"', "Cache-Control": "private, max-age=3600"})

# ---------- homework ----------
class HomeworkIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field("", max_length=4000)
    instructions: str = Field("", max_length=4000)
    class_id: str
    section: str
    subject_id: str
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    attachments: List[dict] = []
    status: str = Field("published", pattern="^(draft|published|archived)$")
    max_score: float = Field(10, gt=0, le=1000)

async def names():
    return ({c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)},
            {s["id"]: s["name"] for s in await db.subjects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)})

@router.get("/homework")
async def list_homework(status: str = "", student_id: str = "", page: int = 1, page_size: int = 50, user=Depends(get_current_user)):
    t = await today(); q = {}
    studs = []
    if user["role"] == "teacher": q = {"teacher_id": user["profile_id"]}
    elif user["role"] in ("student", "parent"):
        studs = await db.students.find(await student_query(user), {"_id": 0}).to_list(20)
        if student_id: studs = [s for s in studs if s["id"] == student_id]
        q = {"$or": [{"class_id": s["class_id"], "section": s["section"]} for s in studs] or [{"id": "__none__"}], "status": "published"}
    if status and user["role"] in ("admin", "teacher"): q["status"] = status
    q = {"$and": [q, {"archived": {"$ne": True}, "status": {"$ne": "archived"}}]}
    res = await paginate(db.homework, q, page, page_size, "-due_date")
    cls, sub = await names()
    for h in res["items"]:
        h["class_name"] = cls.get(h["class_id"]); h["subject_name"] = sub.get(h["subject_id"]); h["overdue"] = h["due_date"] < t
        if studs:
            st = next((s for s in studs if s["class_id"] == h["class_id"] and s["section"] == h["section"]), None)
            h["student_name"] = st["name"] if st else None
            h["my_submission"] = await db.submissions.find_one({"homework_id": h["id"], "student_id": st["id"]}, {"_id": 0}) if st else None
        else:
            h["submission_count"] = await db.submissions.count_documents({"homework_id": h["id"]})
    return res

async def hw_before(data, user, old):
    if user["role"] == "teacher":
        if old and old["teacher_id"] != user["profile_id"]: raise HTTPException(403, "You can only edit your own assignments")
        await assert_section_access(user, data["class_id"], data["section"], data["subject_id"])
        data["teacher_id"] = user["profile_id"]
    else:
        a = await db.assignments.find_one({"class_id": data["class_id"], "section": data["section"], "subject_id": data["subject_id"]})
        data["teacher_id"] = old["teacher_id"] if old else (a["teacher_id"] if a else None)
    if not old and data["due_date"] < await today(): raise HTTPException(422, "Due date cannot be in the past")
    return data

async def hw_after(data, user, extra):
    if data["status"] == "published":
        uids = await audience_user_ids(["student", "parent"], [data["class_id"]], [data["section"]])
        await notify(uids, f"New homework: {data['title']}", f"Due {data['due_date']}", "/homework")

async def hw_owner(old, user):
    if user["role"] == "teacher" and old.get("teacher_id") != user["profile_id"]: raise HTTPException(403, "You can only change your own assignments")

crud(router, "/homework-items", "homework", HomeworkIn, read_roles=("admin", "teacher"), write_roles=("admin", "teacher"), hooks={"before_save": hw_before, "after_create": hw_after, "owner_check": hw_owner})

class SubmitIn(BaseModel):
    text: str = Field("", max_length=8000)
    files: List[dict] = []

@router.post("/homework/{hid}/submit")
async def submit(hid: str, body: SubmitIn, user=Depends(require("student"))):
    h = await db.homework.find_one({"id": hid, "status": "published", "archived": {"$ne": True}}, {"_id": 0})
    st = await db.students.find_one({"id": user["profile_id"]}, {"_id": 0})
    if not h or not st or (st["class_id"], st["section"]) != (h["class_id"], h["section"]): raise HTTPException(404, "Homework not found")
    if not body.text.strip() and not body.files: raise HTTPException(422, "Add text or attach a file")
    for f in body.files:
        if not await db.files.find_one({"id": f.get("id"), "owner_id": user["id"]}): raise HTTPException(422, "Invalid attachment")
    old = await db.submissions.find_one({"homework_id": hid, "student_id": st["id"]})
    if old and old.get("grade") is not None: raise HTTPException(409, "Already graded; resubmission is closed")
    late = await today() > h["due_date"]
    await db.submissions.update_one({"homework_id": hid, "student_id": st["id"]}, {"$set": {"text": body.text, "files": body.files, "submitted_at": now_iso(), "late": late, "status": "submitted"},
                                                                                  "$setOnInsert": {"id": new_id(), "student_name": st["name"], "admission_no": st["admission_no"]}}, upsert=True)
    return {"ok": True, "late": late}

@router.get("/homework/{hid}/submissions")
async def submissions(hid: str, user=Depends(require("admin", "teacher"))):
    h = await db.homework.find_one({"id": hid}, {"_id": 0})
    if not h: raise HTTPException(404, "Not found")
    if user["role"] == "teacher" and h["teacher_id"] != user["profile_id"]: await assert_section_access(user, h["class_id"], h["section"], h["subject_id"])
    studs = await db.students.find({"class_id": h["class_id"], "section": h["section"], "status": "active"}, {"_id": 0, "id": 1, "name": 1, "admission_no": 1}).sort("name", 1).to_list(500)
    subs = {s["student_id"]: s for s in await db.submissions.find({"homework_id": hid}, {"_id": 0}).to_list(500)}
    return {"homework": h, "students": [{**s, "submission": subs.get(s["id"])} for s in studs]}

class GradeIn(BaseModel):
    grade: float = Field(ge=0)
    feedback: str = Field("", max_length=2000)

@router.put("/submissions/{sid}/grade")
async def grade(sid: str, body: GradeIn, user=Depends(require("admin", "teacher"))):
    s = await db.submissions.find_one({"id": sid}, {"_id": 0})
    if not s: raise HTTPException(404, "Submission not found")
    h = await db.homework.find_one({"id": s["homework_id"]}, {"_id": 0})
    if user["role"] == "teacher" and h["teacher_id"] != user["profile_id"]: raise HTTPException(403, "Not your assignment")
    if body.grade > h.get("max_score", 10): raise HTTPException(422, f"Score cannot exceed {h.get('max_score', 10)}")
    await db.submissions.update_one({"id": sid}, {"$set": {"grade": body.grade, "feedback": body.feedback, "status": "graded", "graded_at": now_iso(), "graded_by": user["name"]}})
    u = await db.users.find_one({"profile_id": s["student_id"], "role": "student"})
    if u: await notify([u["id"]], f"Homework graded: {h['title']}", f"Score {body.grade}/{h.get('max_score', 10)}", "/homework")
    return {"ok": True}

# ---------- library ----------
class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=150)
    isbn: str = Field("", max_length=20)
    category: str = ""
    publisher: str = ""
    total_copies: int = Field(1, ge=1, le=1000)
    shelf: str = ""

async def book_before(data, user, old):
    if old:
        issued = old["total_copies"] - old["available_copies"]
        if data["total_copies"] < issued: raise HTTPException(422, f"{issued} copies are currently issued")
        data["available_copies"] = data["total_copies"] - issued; data["accession_no"] = old["accession_no"]
    else:
        data["available_copies"] = data["total_copies"]; data["accession_no"] = await next_seq("acc", "ACC", 5)
    return data

crud(router, "/books", "books", BookIn, read_roles=("admin", "teacher", "student", "parent"), search=("title", "author", "isbn", "accession_no"), filters=("category",),
     hooks={"before_save": book_before}, csv_cols=[("accession_no", "Accession"), ("title", "Title"), ("author", "Author"), ("isbn", "ISBN"), ("category", "Category"), ("total_copies", "Total"), ("available_copies", "Available")])

class IssueIn(BaseModel):
    book_id: str
    borrower_type: str = Field(pattern="^(student|teacher)$")
    borrower_id: str
    due_date: Optional[str] = None

@router.post("/library/issue")
async def issue(body: IssueIn, user=Depends(require("admin"))):
    coll = "students" if body.borrower_type == "student" else "teachers"
    b = await db[coll].find_one({"id": body.borrower_id, "archived": {"$ne": True}}, {"_id": 0})
    if not b or b.get("status") not in ("active", None): raise HTTPException(422, "Borrower is not eligible")
    if await db.book_issues.count_documents({"borrower_id": body.borrower_id, "status": "issued"}) >= 5: raise HTTPException(409, "Borrower already has 5 books issued")
    book = await db.books.find_one_and_update({"id": body.book_id, "available_copies": {"$gt": 0}, "archived": {"$ne": True}}, {"$inc": {"available_copies": -1}})
    if not book: raise HTTPException(409, "No copies available")
    s = await get_settings(); t = await today()
    due = body.due_date or (Date.fromisoformat(t) + timedelta(days=s["library_loan_days"])).isoformat()
    doc = {"id": new_id(), "book_id": book["id"], "book_title": book["title"], "accession_no": book["accession_no"], "borrower_type": body.borrower_type, "borrower_id": body.borrower_id,
           "borrower_name": b["name"], "issue_date": t, "due_date": due, "status": "issued", "fine": 0, "created_at": now_iso()}
    await db.book_issues.insert_one(dict(doc)); await audit(user, "issue_book", "books", book["id"], {"to": b["name"]})
    return clean(doc)

@router.post("/library/issues/{iid}/return")
async def return_book(iid: str, user=Depends(require("admin"))):
    t = await today(); s = await get_settings()
    i = await db.book_issues.find_one({"id": iid, "status": "issued"}, {"_id": 0})
    if not i: raise HTTPException(404, "Issue record not found or already returned")
    late = max(0, (Date.fromisoformat(t) - Date.fromisoformat(i["due_date"])).days)
    fine = late * s["library_fine_per_day"]
    r = await db.book_issues.update_one({"id": iid, "status": "issued"}, {"$set": {"status": "returned", "return_date": t, "fine": fine, "days_late": late}})
    if r.modified_count: await db.books.update_one({"id": i["book_id"]}, {"$inc": {"available_copies": 1}})
    await audit(user, "return_book", "books", i["book_id"], {"fine": fine})
    return {"ok": True, "fine": fine, "days_late": late}

@router.get("/library/issues")
async def issues(status: str = "", borrower_id: str = "", page: int = 1, page_size: int = 20, user=Depends(get_current_user)):
    t = await today(); q = {}
    if user["role"] in ("student", "parent"):
        q["borrower_id"] = {"$in": [s["id"] for s in await db.students.find(await student_query(user), {"_id": 0, "id": 1}).to_list(20)]}
    elif user["role"] == "teacher": q["borrower_id"] = user["profile_id"]
    elif borrower_id: q["borrower_id"] = borrower_id
    if status == "overdue": q.update({"status": "issued", "due_date": {"$lt": t}})
    elif status: q["status"] = status
    res = await paginate(db.book_issues, q, page, page_size, "-created_at")
    for i in res["items"]: i["overdue"] = i["status"] == "issued" and i["due_date"] < t
    return res

# ---------- transport ----------
class VehicleIn(BaseModel):
    reg_no: str = Field(min_length=2, max_length=20)
    model: str = ""
    capacity: int = Field(ge=1, le=100)
    driver_name: str = ""
    driver_phone: str = ""
    attendant_name: str = ""
    attendant_phone: str = ""

class RouteIn(BaseModel):
    name: str = Field(min_length=1)
    vehicle_id: Optional[str] = None
    stops: List[dict] = []
    fee: float = Field(0, ge=0)

def driver_hide(user): return [] if user["role"] in ("admin", "teacher") else ["driver_phone", "attendant_phone"]
crud(router, "/vehicles", "vehicles", VehicleIn, read_roles=("admin", "teacher", "student", "parent"), search=("reg_no", "driver_name"), hooks={"hide": driver_hide})
crud(router, "/routes", "routes", RouteIn, search=("name",))

class TAssignIn(BaseModel):
    student_id: str
    route_id: Optional[str] = None
    stop: str = ""

@router.post("/transport/assign")
async def t_assign(body: TAssignIn, user=Depends(require("admin"))):
    st = await db.students.find_one({"id": body.student_id}, {"_id": 0})
    if not st: raise HTTPException(404, "Student not found")
    if body.route_id:
        r = await db.routes.find_one({"id": body.route_id}, {"_id": 0})
        if not r: raise HTTPException(404, "Route not found")
        if body.stop and body.stop not in [s.get("name") for s in r.get("stops", [])]: raise HTTPException(422, "Stop not on this route")
        v = await db.vehicles.find_one({"id": r.get("vehicle_id")}, {"_id": 0})
        cnt = await db.students.count_documents({"transport.route_id": body.route_id, "id": {"$ne": body.student_id}, "status": "active"})
        if v and cnt >= v["capacity"]: raise HTTPException(409, f"Vehicle {v['reg_no']} is at full capacity ({v['capacity']})")
        await db.students.update_one({"id": body.student_id}, {"$set": {"transport": {"route_id": body.route_id, "route_name": r["name"], "stop": body.stop}}})
    else:
        await db.students.update_one({"id": body.student_id}, {"$unset": {"transport": ""}})
    await db.transport_history.insert_one({"id": new_id(), "student_id": body.student_id, "student_name": st["name"], "route_id": body.route_id, "stop": body.stop, "by": user["name"], "at": now_iso()})
    await audit(user, "transport_assign", "students", body.student_id, {"route_id": body.route_id})
    return {"ok": True}

@router.get("/transport/overview")
async def t_overview(user=Depends(require("admin", "teacher"))):
    routes = await db.routes.find({"archived": {"$ne": True}}, {"_id": 0}).to_list(200)
    vs = {v["id"]: v for v in await db.vehicles.find({}, {"_id": 0}).to_list(200)}
    for r in routes:
        r["vehicle"] = vs.get(r.get("vehicle_id"))
        r["students"] = await db.students.find({"transport.route_id": r["id"], "status": "active"}, {"_id": 0, "id": 1, "name": 1, "admission_no": 1, "class_name": 1, "section": 1, "transport": 1, "guardian_phone": 1}).to_list(200)
    hist = await db.transport_history.find({}, {"_id": 0}).sort("at", -1).to_list(30)
    return {"routes": routes, "history": hist}

# ---------- events / calendar ----------
class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = ""
    type: str = Field(pattern="^(holiday|closure|exam|ptm|event|academic)$")
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    class_id: Optional[str] = None

async def ev_before(data, user, old):
    if data["end_date"] < data["start_date"]: raise HTTPException(422, "End date must be on or after start date")
    if not data.get("class_id"): data["class_id"] = None
    return data

async def ev_scope(user):
    if user["role"] == "admin": return {}
    if user["role"] == "teacher":
        _, pairs, _ = await teacher_ctx(user); cids = list({c for c, _ in pairs})
    else: cids = [s["class_id"] for s in await db.students.find(await student_query(user), {"_id": 0}).to_list(20)]
    return {"$or": [{"class_id": None}, {"class_id": {"$in": cids}}]}

crud(router, "/events", "events", EventIn, hooks={"before_save": ev_before, "scope": ev_scope}, filters=("type",))

@router.get("/calendar")
async def calendar(month: str, user=Depends(get_current_user)):
    if not re.match(r"^\d{4}-\d{2}$", month): raise HTTPException(422, "month must be YYYY-MM")
    start, end = f"{month}-01", f"{month}-31"
    evs = await db.events.find({"$and": [await ev_scope(user), {"archived": {"$ne": True}, "start_date": {"$lte": end}, "end_date": {"$gte": start}}]}, {"_id": 0}).to_list(500)
    from routes_exams import exam_scope
    for e in await db.exams.find({"$and": [await exam_scope(user), {"archived": {"$ne": True}}]}, {"_id": 0}).to_list(200):
        for s in e["subjects"]:
            if start <= s["date"] <= end: evs.append({"id": f"{e['id']}-{s['subject_id']}", "title": f"{e['name']}", "type": "exam", "start_date": s["date"], "end_date": s["date"], "auto": True})
    hw = (await list_homework(user=user, page_size=200))["items"] if user["role"] != "admin" else []
    for h in hw:
        if start <= h["due_date"] <= end: evs.append({"id": h["id"], "title": f"Due: {h['title']}", "type": "deadline", "start_date": h["due_date"], "end_date": h["due_date"], "auto": True})
    return evs

# ---------- leave ----------
class LeaveIn(BaseModel):
    leave_type: str = Field(pattern="^(Sick|Casual|Earned|Personal|Medical|Family|Other)$")
    from_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str = Field(min_length=3, max_length=1000)
    student_id: Optional[str] = None

class ReviewIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    note: str = ""

@router.post("/leaves")
async def apply_leave(body: LeaveIn, user=Depends(require("teacher", "parent"))):
    if body.to_date < body.from_date: raise HTTPException(422, "End date must be on or after start date")
    doc = {"id": new_id(), **body.model_dump(), "requester_id": user["id"], "requester_name": user["name"], "requester_role": user["role"], "status": "pending", "created_at": now_iso()}
    if user["role"] == "parent":
        if not body.student_id: raise HTTPException(422, "Choose your child")
        st = await assert_student(user, body.student_id)
        doc.update({"student_name": st["name"], "class_id": st["class_id"], "section": st["section"], "kind": "student"})
    else:
        doc.update({"kind": "staff", "student_id": None})
    overlap = await db.leaves.find_one({"requester_id": user["id"], "student_id": doc["student_id"], "status": {"$ne": "rejected"}, "from_date": {"$lte": body.to_date}, "to_date": {"$gte": body.from_date}})
    if overlap: raise HTTPException(409, "You already have a leave request for these dates")
    await db.leaves.insert_one(dict(doc))
    await notify([u["id"] for u in await db.users.find({"role": "admin", "active": True}, {"_id": 0, "id": 1}).to_list(50)], f"New leave request from {user['name']}", body.reason[:80], "/leave")
    return clean(doc)

async def can_review(user, lv):
    if user["role"] == "admin": return True
    if user["role"] == "teacher" and lv["kind"] == "student" and (await get_settings())["student_leave_approver"] == "class_teacher":
        return (lv["class_id"], lv["section"]) in await class_teacher_pairs(user["profile_id"])
    return False

@router.get("/leaves")
async def list_leaves(status: str = "", kind: str = "", page: int = 1, page_size: int = 20, user=Depends(get_current_user)):
    q = {}
    if user["role"] == "student": q["student_id"] = user["profile_id"]
    elif user["role"] != "admin":
        q["$or"] = [{"requester_id": user["id"]}]
        if user["role"] == "teacher" and (await get_settings())["student_leave_approver"] == "class_teacher":
            q["$or"] += [{"kind": "student", "class_id": c, "section": s} for c, s in await class_teacher_pairs(user["profile_id"])]
    if status: q["status"] = status
    if kind: q["kind"] = kind
    return await paginate(db.leaves, q, page, page_size, "-created_at")

@router.put("/leaves/{lid}/review")
async def review(lid: str, body: ReviewIn, user=Depends(require("admin", "teacher"))):
    lv = await db.leaves.find_one({"id": lid}, {"_id": 0})
    if not lv or not await can_review(user, lv): raise HTTPException(404, "Leave request not found")
    if lv["status"] != "pending": raise HTTPException(409, "This request has already been decided")
    await db.leaves.update_one({"id": lid}, {"$set": {"status": body.status, "review_note": body.note, "reviewer": user["name"], "reviewed_at": now_iso()}})
    if body.status == "approved" and lv["kind"] == "student" and (await get_settings())["auto_excuse_on_leave"]:
        d = Date.fromisoformat(lv["from_date"])
        while d <= Date.fromisoformat(lv["to_date"]):
            await db.attendance.update_one({"date": d.isoformat(), "student_id": lv["student_id"]}, {"$set": {"status": "excused", "remark": "Approved leave", "class_id": lv["class_id"], "section": lv["section"], "marked_by": user["id"], "updated_at": now_iso()},
                                                                                                  "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}, upsert=True)
            d += timedelta(days=1)
    await notify([lv["requester_id"]], f"Leave request {body.status}", f"{lv['from_date']} to {lv['to_date']}" + (f" - {body.note}" if body.note else ""), "/leave")
    req = await db.users.find_one({"id": lv["requester_id"]}, {"_id": 0})
    if req and (await get_settings())["email_notifications"]:
        await send_email(req["email"], f"Leave request {body.status}", email_template(f"Your leave request was {body.status}", [f"Hi {req['name']},", f"Dates: {lv['from_date']} to {lv['to_date']}.", f"Note: {body.note or '-'}"]))
    await audit(user, "leave_" + body.status, "leaves", lid)
    return {"ok": True}

# ---------- announcements & notifications ----------
class AnnIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=5000)
    roles: List[str] = []
    class_ids: List[str] = []
    category: str = "General"
    pinned: bool = False

async def ann_scope(user):
    if user["role"] == "admin": return {}
    q = [{"roles": {"$size": 0}}, {"roles": user["role"]}]
    if user["role"] == "teacher":
        _, pairs, _ = await teacher_ctx(user); cids = list({c for c, _ in pairs})
        return {"$or": [{"created_by": user["id"]}, {"$and": [{"$or": q}, {"$or": [{"class_ids": {"$size": 0}}, {"class_ids": {"$in": cids}}]}]}]}
    cids = [s["class_id"] for s in await db.students.find(await student_query(user), {"_id": 0}).to_list(20)]
    return {"$and": [{"$or": q}, {"$or": [{"class_ids": {"$size": 0}}, {"class_ids": {"$in": cids}}]}]}

async def ann_before(data, user, old):
    if user["role"] == "teacher":
        _, pairs, _ = await teacher_ctx(user); mine = {c for c, _ in pairs}
        if not data["class_ids"] or not set(data["class_ids"]) <= mine: raise HTTPException(403, "Teachers can only post to their own classes")
        if old and old.get("created_by") != user["id"]: raise HTTPException(403, "Not your announcement")
    if not old: data["created_by"] = user["id"]; data["author"] = user["name"]
    else: data["created_by"] = old["created_by"]; data["author"] = old.get("author")
    return data

async def ann_after(data, user, extra):
    uids = await audience_user_ids(data["roles"], data["class_ids"] or None)
    await notify([u for u in uids if u != user["id"]], f"Announcement: {data['title']}", data["body"][:120], "/announcements")

async def ann_owner(old, user):
    if user["role"] == "teacher" and old.get("created_by") != user["id"]: raise HTTPException(403, "You can only change your own announcements")

crud(router, "/announcements", "announcements", AnnIn, write_roles=("admin", "teacher"), search=("title", "body"), filters=("category",),
     hooks={"scope": ann_scope, "before_save": ann_before, "after_create": ann_after, "owner_check": ann_owner})

@router.get("/notifications")
async def my_notifs(user=Depends(get_current_user)):
    items = await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(30)
    return {"items": items, "unread": await db.notifications.count_documents({"user_id": user["id"], "read": False})}

@router.post("/notifications/{nid}/read")
async def read_n(nid: str, user=Depends(get_current_user)):
    q = {"user_id": user["id"]} if nid == "all" else {"user_id": user["id"], "id": nid}
    await db.notifications.update_many(q, {"$set": {"read": True}})
    return {"ok": True}

# ---------- audit ----------
@router.get("/audit-logs")
async def audit_logs(q: str = "", entity: str = "", action: str = "", page: int = 1, page_size: int = 30, user=Depends(require("admin"))):
    query = {}
    if entity: query["entity"] = entity
    if action: query["action"] = action
    if q: query["user_name"] = {"$regex": re.escape(q), "$options": "i"}
    return await paginate(db.audit_logs, query, page, page_size, "-created_at")

# ---------- settings ----------
@router.get("/settings/public")
async def public_settings():
    s = await get_settings()
    return {k: s[k] for k in ("school_name", "tagline", "logo_file_id", "address", "email", "phone", "website", "academic_year", "currency", "currency_symbol")}

@router.get("/settings")
async def settings_get(user=Depends(get_current_user)):
    s = await get_settings()
    if user["role"] != "admin": s = {k: s[k] for k in ("school_name", "academic_year", "terms", "currency_symbol", "periods", "working_days", "genders", "grading", "pass_percent", "low_attendance_threshold", "payment_methods", "logo_file_id", "address", "phone", "email")}
    s["integrations"] = {"email": bool(os.environ.get("EMERGENT_EMAIL_KEY")), "razorpay": bool(os.environ.get("RAZORPAY_KEY_ID")), "cashfree": bool(os.environ.get("CASHFREE_CLIENT_ID")), "sms": False, "whatsapp": False, "gps": False}
    return s

@router.put("/settings")
async def settings_put(body: dict, user=Depends(require("admin"))):
    defaults = await get_settings()
    allowed = set(defaults.keys()) - {"id", "integrations", "demo_seeded"}
    data = {k: v for k, v in body.items() if k in allowed}
    for k, v in data.items():
        d = defaults.get(k)
        if isinstance(d, bool) and not isinstance(v, bool): raise HTTPException(422, f"{k} must be true or false")
        if isinstance(d, (int, float)) and not isinstance(d, bool):
            try: data[k] = float(v) if isinstance(d, float) else int(v)
            except (TypeError, ValueError): raise HTTPException(422, f"{k} must be a number")
        if isinstance(d, list) and not isinstance(v, list): raise HTTPException(422, f"{k} must be a list")
        if isinstance(d, str) and d and not isinstance(v, str): raise HTTPException(422, f"{k} must be text")
    for k in ("pass_percent", "low_attendance_threshold"):
        if k in data and not (0 <= data[k] <= 100): raise HTTPException(422, f"{k} must be between 0 and 100")
    for k in ("late_fee_amount", "library_fine_per_day", "library_loan_days", "retention_years"):
        if k in data and data[k] < 0: raise HTTPException(422, f"{k} cannot be negative")
    if "fee_reminder_days_before" in data and not (0 <= data["fee_reminder_days_before"] <= 30): raise HTTPException(422, "Reminder days must be between 0 and 30")
    if "session_minutes" in data and not (5 <= int(data["session_minutes"]) <= 720): raise HTTPException(422, "Session timeout must be 5–720 minutes")
    if "grading" in data:
        for g in data["grading"]:
            if not isinstance(g.get("min"), (int, float)) or not g.get("grade"): raise HTTPException(422, "Invalid grading rule")
    old = await get_settings()
    await db.settings.update_one({"id": "school"}, {"$set": data}, upsert=True)
    await audit(user, "update_settings", "settings", "school", {k: [old.get(k), v] for k, v in data.items() if old.get(k) != v})
    return await get_settings()

@router.get("/settings/backup")
async def backup(user=Depends(require("admin"))):
    out = {}
    for c in ("settings", "academic_years", "classes", "subjects", "assignments", "students", "teachers", "parents", "attendance", "timetable", "exams", "marks",
              "fee_structures", "invoices", "payments", "homework", "submissions", "books", "book_issues", "vehicles", "routes", "events", "leaves", "announcements"):
        out[c] = await db[c].find({}, {"_id": 0, "password_hash": 0}).to_list(100000)
    out["users"] = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100000)
    await audit(user, "backup_export", "settings")
    return Response(json.dumps(out, default=str), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="school-backup.json"'})

@router.post("/settings/clear-demo")
async def clear_demo(user=Depends(require("admin"))):
    n = 0
    for c in await db.list_collection_names():
        if c in ("users",):
            r = await db.users.delete_many({"demo": True, "id": {"$ne": user["id"]}})
        else:
            r = await db[c].delete_many({"demo": True})
        n += r.deleted_count
    await audit(user, "clear_demo_data", "settings", None, {"deleted": n})
    return {"deleted": n}
