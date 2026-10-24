from typing import Optional, List
from datetime import date as Date, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from core import (db, now_iso, new_id, clean, require, audit, crud, teacher_ctx, student_query, assert_student, assert_section_access,
                  get_settings, today, notify, get_current_user)

router = APIRouter(prefix="/api")

class YearIn(BaseModel):
    name: str = Field(pattern=r"^\d{4}-\d{2}$")
    start_date: str
    end_date: str
    terms: List[dict] = []
    current: bool = False

class SectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=10)
    capacity: int = Field(40, ge=1, le=200)
    class_teacher_id: Optional[str] = None
    room: str = ""

class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    grade_level: int = Field(ge=0, le=14)
    sections: List[SectionIn] = []

class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    code: str = Field(min_length=1, max_length=12)
    type: str = "Theory"
    class_ids: List[str] = []

async def year_before(data, user, old):
    if data["end_date"] <= data["start_date"]: raise HTTPException(422, "End date must be after start date")
    if data["current"]:
        await db.academic_years.update_many({}, {"$set": {"current": False}})
        await db.settings.update_one({"id": "school"}, {"$set": {"academic_year": data["name"]}}, upsert=True)
    return data

async def class_before(data, user, old):
    names = [s["name"].upper() for s in data["sections"]]
    if len(names) != len(set(names)): raise HTTPException(422, "Duplicate section names")
    for s in data["sections"]: s["name"] = s["name"].upper()
    dup = await db.classes.find_one({"name": data["name"], "archived": {"$ne": True}, **({"id": {"$ne": old["id"]}} if old else {})})
    if dup: raise HTTPException(409, "A class with this name already exists")
    if old:
        removed = {s["name"] for s in old.get("sections", [])} - set(names)
        for r in removed:
            if await db.students.count_documents({"class_id": old["id"], "section": r, "status": "active"}):
                raise HTTPException(409, f"Section {r} still has active students; transfer them first")
    return data

async def subject_before(data, user, old):
    data["code"] = data["code"].upper()
    dup = await db.subjects.find_one({"code": data["code"], "archived": {"$ne": True}, **({"id": {"$ne": old["id"]}} if old else {})})
    if dup: raise HTTPException(409, "Subject code already exists")
    return data

crud(router, "/academic-years", "academic_years", YearIn, hooks={"before_save": year_before}, search=("name",))
crud(router, "/classes", "classes", ClassIn, search=("name",), hooks={"before_save": class_before})
crud(router, "/subjects", "subjects", SubjectIn, search=("name", "code"), filters=("class_ids",), hooks={"before_save": subject_before})

@router.get("/classes-overview")
async def classes_overview(user=Depends(get_current_user)):
    classes = await db.classes.find({"archived": {"$ne": True}}, {"_id": 0}).sort("grade_level", 1).to_list(200)
    teachers = {t["id"]: t["name"] for t in await db.teachers.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(2000)}
    pipeline = [{"$match": {"status": "active", "archived": {"$ne": True}}}, {"$group": {"_id": {"c": "$class_id", "s": "$section"}, "n": {"$sum": 1}}}]
    counts = {(r["_id"]["c"], r["_id"]["s"]): r["n"] async for r in db.students.aggregate(pipeline)}
    for c in classes:
        for s in c.get("sections", []):
            s["student_count"] = counts.get((c["id"], s["name"]), 0)
            s["class_teacher_name"] = teachers.get(s.get("class_teacher_id"))
    return classes

# ---- teacher-subject-section assignments ----
class AssignIn(BaseModel):
    teacher_id: str
    class_id: str
    section: str
    subject_id: str

@router.get("/assignments")
async def list_assignments(teacher_id: str = "", class_id: str = "", user=Depends(get_current_user)):
    q = {}
    if user["role"] == "teacher": q["teacher_id"] = user["profile_id"]
    elif teacher_id: q["teacher_id"] = teacher_id
    if class_id: q["class_id"] = class_id
    if user["role"] in ("student", "parent"):
        studs = await db.students.find(await student_query(user), {"_id": 0}).to_list(20)
        q["$or"] = [{"class_id": s["class_id"], "section": s["section"]} for s in studs] or [{"id": "__none__"}]
    items = await db.assignments.find(q, {"_id": 0}).to_list(2000)
    return await enrich(items)

async def enrich(items):
    cls = {c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    sub = {s["id"]: s["name"] for s in await db.subjects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    tch = {t["id"]: t["name"] for t in await db.teachers.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(2000)}
    for i in items:
        i["class_name"] = cls.get(i.get("class_id")); i["subject_name"] = sub.get(i.get("subject_id")); i["teacher_name"] = tch.get(i.get("teacher_id"))
    return items

@router.post("/assignments")
async def create_assignment(body: AssignIn, user=Depends(require("admin"))):
    c = await db.classes.find_one({"id": body.class_id}, {"_id": 0})
    if not c or body.section not in [s["name"] for s in c.get("sections", [])]: raise HTTPException(422, "Invalid class/section")
    if not await db.teachers.find_one({"id": body.teacher_id, "archived": {"$ne": True}}): raise HTTPException(422, "Invalid teacher")
    if not await db.subjects.find_one({"id": body.subject_id}): raise HTTPException(422, "Invalid subject")
    ex = await db.assignments.find_one({"class_id": body.class_id, "section": body.section, "subject_id": body.subject_id}, {"_id": 0})
    if ex: raise HTTPException(409, "This subject already has a teacher assigned for this section")
    doc = {"id": new_id(), **body.model_dump(), "created_at": now_iso()}
    await db.assignments.insert_one(dict(doc))
    await audit(user, "assign", "assignments", doc["id"], body.model_dump())
    return clean(doc)

@router.delete("/assignments/{aid}")
async def delete_assignment(aid: str, user=Depends(require("admin"))):
    a = await db.assignments.find_one_and_delete({"id": aid})
    if not a: raise HTTPException(404, "Not found")
    clean(a); await db.assignment_history.insert_one({**a, "removed_at": now_iso()})
    await audit(user, "unassign", "assignments", aid)
    return {"ok": True}

# ---- timetable ----
class SlotIn(BaseModel):
    class_id: str
    section: str
    day: str = Field(pattern="^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)$")
    period_no: int = Field(ge=1, le=20)
    subject_id: str
    teacher_id: str
    room: str = ""

@router.get("/timetable")
async def get_timetable(class_id: str = "", section: str = "", teacher_id: str = "", student_id: str = "", user=Depends(get_current_user)):
    q = {}
    if user["role"] in ("student", "parent"):
        studs = await db.students.find(await student_query(user), {"_id": 0}).to_list(20)
        st = next((s for s in studs if s["id"] == student_id), studs[0] if studs else None)
        if not st: return {"entries": [], "periods": (await get_settings())["periods"]}
        q = {"class_id": st["class_id"], "section": st["section"]}
    elif teacher_id or (user["role"] == "teacher" and not class_id):
        q = {"teacher_id": teacher_id or user["profile_id"]}
    else:
        if not class_id: raise HTTPException(422, "Choose a class")
        q = {"class_id": class_id, "section": section}
    s = await get_settings()
    return {"entries": await enrich(await db.timetable.find(q, {"_id": 0}).to_list(500)), "periods": s["periods"], "working_days": s["working_days"]}

@router.post("/timetable")
async def save_slot(body: SlotIn, user=Depends(require("admin"))):
    s = await get_settings()
    p = next((p for p in s["periods"] if p["no"] == body.period_no), None)
    if not p or p["type"] != "class": raise HTTPException(422, "That period is a break or does not exist")
    if body.day not in s["working_days"]: raise HTTPException(422, f"{body.day} is not a working day")
    c = await db.classes.find_one({"id": body.class_id}, {"_id": 0})
    if not c or body.section not in [x["name"] for x in c.get("sections", [])]: raise HTTPException(422, "Invalid class/section")
    if not await db.assignments.find_one({"class_id": body.class_id, "section": body.section, "subject_id": body.subject_id, "teacher_id": body.teacher_id}):
        raise HTTPException(422, "This teacher is not assigned to teach this subject in this section (see Subjects → Teacher assignments)")
    base = {"day": body.day, "period_no": body.period_no}
    existing = await db.timetable.find_one({**base, "class_id": body.class_id, "section": body.section})
    exid = existing["id"] if existing else None
    t = await db.timetable.find_one({**base, "teacher_id": body.teacher_id, "id": {"$ne": exid}}, {"_id": 0})
    if t:
        c = await db.classes.find_one({"id": t["class_id"]})
        raise HTTPException(409, f"Teacher conflict: already teaching {c['name'] if c else ''}-{t['section']} at this time")
    if body.room:
        r = await db.timetable.find_one({**base, "room": body.room, "id": {"$ne": exid}}, {"_id": 0})
        if r: raise HTTPException(409, f"Room conflict: room {body.room} is already booked at this time")
    data = body.model_dump()
    if existing:
        await db.timetable.update_one({"id": exid}, {"$set": data}); data["id"] = exid
    else:
        data["id"] = new_id(); await db.timetable.insert_one(dict(data))
    await audit(user, "timetable_save", "timetable", data["id"], data)
    return clean(data)

@router.delete("/timetable/{tid}")
async def delete_slot(tid: str, user=Depends(require("admin"))):
    await db.timetable.delete_one({"id": tid}); await audit(user, "timetable_delete", "timetable", tid)
    return {"ok": True}

# ---- student attendance ----
STATUSES = ("present", "absent", "late", "excused")

class AttEntry(BaseModel):
    student_id: str
    status: str = Field(pattern="^(present|absent|late|excused)$")
    remark: str = ""

class AttIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    class_id: str
    section: str
    entries: List[AttEntry]

@router.get("/attendance/sheet")
async def att_sheet(date: str, class_id: str, section: str, user=Depends(require("admin", "teacher"))):
    await assert_section_access(user, class_id, section)
    studs = await db.students.find({"class_id": class_id, "section": section, "status": "active"}, {"_id": 0, "id": 1, "name": 1, "admission_no": 1, "photo_file_id": 1}).sort("name", 1).to_list(500)
    recs = {r["student_id"]: r for r in await db.attendance.find({"date": date, "class_id": class_id, "section": section}, {"_id": 0}).to_list(500)}
    for s in studs:
        r = recs.get(s["id"]); s["status"] = r["status"] if r else None; s["remark"] = r.get("remark", "") if r else ""
    return {"students": studs, "already_marked": bool(recs), "date": date}

@router.post("/attendance/sheet")
async def save_att(body: AttIn, user=Depends(require("admin", "teacher"))):
    await assert_section_access(user, body.class_id, body.section)
    t = await today(); s = await get_settings()
    if body.date > t: raise HTTPException(422, "Cannot mark attendance for a future date")
    if user["role"] == "teacher" and body.date != t and not s.get("teacher_edit_past_attendance"):
        if await db.attendance.count_documents({"date": body.date, "class_id": body.class_id, "section": body.section}):
            raise HTTPException(403, "Only administrators can correct past attendance")
    valid = {x["id"] for x in await db.students.find({"class_id": body.class_id, "section": body.section, "status": "active"}, {"_id": 0, "id": 1}).to_list(500)}
    saved, corrected = 0, 0
    for e in body.entries:
        if e.student_id not in valid: raise HTTPException(422, "A student does not belong to this section")
        old = await db.attendance.find_one({"date": body.date, "student_id": e.student_id}, {"_id": 0})
        if old and old["status"] == e.status and old.get("remark", "") == e.remark: continue
        await db.attendance.update_one({"date": body.date, "student_id": e.student_id},
                                       {"$set": {"status": e.status, "remark": e.remark, "class_id": body.class_id, "section": body.section, "marked_by": user["id"], "updated_at": now_iso()},
                                        "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}, upsert=True)
        if old:
            corrected += 1
            await db.attendance_history.insert_one({"id": new_id(), "student_id": e.student_id, "date": body.date, "from": old["status"], "to": e.status, "by": user["name"], "at": now_iso()})
        saved += 1
    await audit(user, "attendance_save", "attendance", None, {"date": body.date, "class_id": body.class_id, "section": body.section, "saved": saved, "corrections": corrected})
    return {"saved": saved, "corrections": corrected}

def pct(c):
    denom = c.get("present", 0) + c.get("late", 0) + c.get("absent", 0)
    return round((c.get("present", 0) + c.get("late", 0)) * 100 / denom, 1) if denom else None

async def summarize(match):
    out = {}
    async for r in db.attendance.aggregate([{"$match": match}, {"$group": {"_id": {"s": "$student_id", "st": "$status"}, "n": {"$sum": 1}}}]):
        out.setdefault(r["_id"]["s"], {k: 0 for k in STATUSES})[r["_id"]["st"]] = r["n"]
    return out

@router.get("/attendance/summary")
async def att_summary(class_id: str = "", section: str = "", date_from: str = "", date_to: str = "", user=Depends(require("admin", "teacher"))):
    sq = {"status": "active"}
    if class_id: sq["class_id"] = class_id
    if section: sq["section"] = section
    if user["role"] == "teacher":
        if not class_id: raise HTTPException(422, "Choose a class")
        await assert_section_access(user, class_id, section)
    studs = await db.students.find(sq, {"_id": 0, "id": 1, "name": 1, "admission_no": 1, "class_name": 1, "section": 1}).sort("name", 1).to_list(5000)
    m = {"student_id": {"$in": [s["id"] for s in studs]}}
    if date_from or date_to: m["date"] = {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}
    summ = await summarize(m); thr = (await get_settings())["low_attendance_threshold"]
    for s in studs:
        c = summ.get(s["id"], {k: 0 for k in STATUSES}); s.update(c); s["percentage"] = pct(c)
        s["low"] = s["percentage"] is not None and s["percentage"] < thr
    return {"students": studs, "threshold": thr}

@router.get("/attendance/student/{sid}")
async def att_student(sid: str, date_from: str = "", date_to: str = "", user=Depends(get_current_user)):
    await assert_student(user, sid)
    m = {"student_id": sid}
    if date_from or date_to: m["date"] = {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}
    recs = await db.attendance.find(m, {"_id": 0}).sort("date", -1).to_list(1000)
    c = {k: sum(1 for r in recs if r["status"] == k) for k in STATUSES}
    hist = await db.attendance_history.find({"student_id": sid}, {"_id": 0}).sort("at", -1).to_list(50) if user["role"] == "admin" else []
    return {"records": recs, "counts": c, "percentage": pct(c), "corrections": hist}

@router.get("/attendance/trend")
async def att_trend(days: int = 14, user=Depends(require("admin"))):
    start = (Date.fromisoformat(await today()) - timedelta(days=days)).isoformat()
    out = {}
    async for r in db.attendance.aggregate([{"$match": {"date": {"$gte": start}}}, {"$group": {"_id": {"d": "$date", "s": "$status"}, "n": {"$sum": 1}}}]):
        out.setdefault(r["_id"]["d"], {k: 0 for k in STATUSES})[r["_id"]["s"]] = r["n"]
    return [{"date": d, **c, "percentage": pct(c)} for d, c in sorted(out.items())]

# ---- staff attendance ----
class StaffAttIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    entries: List[dict]

@router.get("/staff-attendance")
async def staff_att(date: str, user=Depends(require("admin"))):
    staff = await db.teachers.find({"archived": {"$ne": True}, "status": {"$ne": "resigned"}}, {"_id": 0, "id": 1, "name": 1, "employee_id": 1, "designation": 1}).sort("name", 1).to_list(1000)
    recs = {r["teacher_id"]: r for r in await db.staff_attendance.find({"date": date}, {"_id": 0}).to_list(1000)}
    for s in staff: s["status"] = recs.get(s["id"], {}).get("status")
    return {"staff": staff}

@router.post("/staff-attendance")
async def save_staff_att(body: StaffAttIn, user=Depends(require("admin"))):
    if body.date > await today(): raise HTTPException(422, "Cannot mark a future date")
    for e in body.entries:
        if e.get("status") not in ("present", "absent", "late", "on_leave", "half_day"): raise HTTPException(422, "Invalid status")
        await db.staff_attendance.update_one({"date": body.date, "teacher_id": e["teacher_id"]}, {"$set": {"status": e["status"], "by": user["id"], "updated_at": now_iso()}, "$setOnInsert": {"id": new_id()}}, upsert=True)
    await audit(user, "staff_attendance_save", "staff_attendance", None, {"date": body.date, "count": len(body.entries)})
    return {"saved": len(body.entries)}
