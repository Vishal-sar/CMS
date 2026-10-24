from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from core import (db, now_iso, new_id, clean, require, audit, teacher_ctx, student_query, assert_student, assert_section_access,
                  get_settings, notify, audience_user_ids, get_current_user, paginate, class_teacher_pairs)
from routes_academic import pct, STATUSES

router = APIRouter(prefix="/api")

class ExamSubject(BaseModel):
    subject_id: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    max_marks: float = Field(gt=0, le=1000)
    pass_marks: float = Field(ge=0)

class ExamIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(pattern="^(Unit Test|Mid-Term|Final Examination|Practical|Other)$")
    academic_year: str
    term: str
    class_id: str
    sections: List[str]
    subjects: List[ExamSubject]
    weight: float = Field(100, ge=0, le=100)

def grade_for(p, grading):
    for g in sorted(grading, key=lambda x: -x["min"]):
        if p >= g["min"]: return g["grade"]
    return "-"

async def exam_scope(user):
    if user["role"] == "admin": return {}
    if user["role"] == "teacher":
        _, pairs, _ = await teacher_ctx(user)
        return {"$or": [{"class_id": c, "sections": s} for c, s in pairs]} if pairs else {"id": "__none__"}
    studs = await db.students.find(await student_query(user), {"_id": 0}).to_list(20)
    return {"$or": [{"class_id": s["class_id"], "sections": s["section"]} for s in studs] or [{"id": "__none__"}]}

@router.get("/exams")
async def list_exams(class_id: str = "", status: str = "", academic_year: str = "", page: int = 1, page_size: int = 50, user=Depends(get_current_user)):
    q = {"archived": {"$ne": True}}
    if class_id: q["class_id"] = class_id
    if status: q["status"] = status
    if academic_year: q["academic_year"] = academic_year
    res = await paginate(db.exams, {"$and": [q, await exam_scope(user)]}, page, page_size, "-created_at")
    cls = {c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    sub = {s["id"]: s["name"] for s in await db.subjects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    for e in res["items"]:
        e["class_name"] = cls.get(e["class_id"])
        for s in e["subjects"]: s["subject_name"] = sub.get(s["subject_id"])
    return res

@router.get("/exams/{eid}")
async def get_exam(eid: str, user=Depends(get_current_user)):
    e = await db.exams.find_one({"$and": [{"id": eid}, await exam_scope(user)]}, {"_id": 0})
    if not e: raise HTTPException(404, "Exam not found")
    sub = {s["id"]: s["name"] for s in await db.subjects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    for s in e["subjects"]: s["subject_name"] = sub.get(s["subject_id"])
    c = await db.classes.find_one({"id": e["class_id"]}, {"_id": 0}); e["class_name"] = c["name"] if c else ""
    return e

async def validate_exam(body):
    c = await db.classes.find_one({"id": body.class_id}, {"_id": 0})
    if not c: raise HTTPException(422, "Invalid class")
    secs = {s["name"] for s in c.get("sections", [])}
    if not body.sections or not set(body.sections) <= secs: raise HTTPException(422, "Invalid sections")
    ids = [s.subject_id for s in body.subjects]
    if not ids or len(ids) != len(set(ids)): raise HTTPException(422, "Add each subject once")
    for s in body.subjects:
        if s.pass_marks > s.max_marks: raise HTTPException(422, "Passing marks cannot exceed maximum marks")

@router.post("/exams")
async def create_exam(body: ExamIn, user=Depends(require("admin"))):
    await validate_exam(body)
    doc = {"id": new_id(), **body.model_dump(), "status": "draft", "archived": False, "created_at": now_iso()}
    await db.exams.insert_one(dict(doc)); await audit(user, "create", "exams", doc["id"])
    return clean(doc)

@router.put("/exams/{eid}")
async def update_exam(eid: str, body: ExamIn, user=Depends(require("admin"))):
    e = await db.exams.find_one({"id": eid})
    if not e: raise HTTPException(404, "Not found")
    if e["status"] == "published": raise HTTPException(409, "Unpublish the exam before changing its setup")
    await validate_exam(body)
    await db.exams.update_one({"id": eid}, {"$set": body.model_dump()}); await audit(user, "update", "exams", eid)
    return {"ok": True}

@router.delete("/exams/{eid}")
async def archive_exam(eid: str, user=Depends(require("admin"))):
    await db.exams.update_one({"id": eid}, {"$set": {"archived": True}}); await audit(user, "archive", "exams", eid)
    return {"ok": True}

@router.post("/exams/{eid}/publish")
async def publish(eid: str, publish: bool = True, user=Depends(require("admin"))):
    e = await db.exams.find_one({"id": eid}, {"_id": 0})
    if not e: raise HTTPException(404, "Not found")
    await db.exams.update_one({"id": eid}, {"$set": {"status": "published" if publish else "draft", "published_at": now_iso() if publish else None}})
    await audit(user, "publish" if publish else "unpublish", "exams", eid)
    if publish:
        uids = await audience_user_ids(["student", "parent"], [e["class_id"]], e["sections"])
        await notify(uids, f"Results published: {e['name']}", "View the report card in Results.", "/results")
    return {"ok": True}

class MarkEntry(BaseModel):
    student_id: str
    marks: Optional[float] = None
    absent: bool = False

class MarksIn(BaseModel):
    section: str
    subject_id: str
    entries: List[MarkEntry]
    submit: bool = False

@router.get("/exams/{eid}/marks")
async def get_marks(eid: str, section: str, subject_id: str, user=Depends(require("admin", "teacher"))):
    e = await db.exams.find_one({"id": eid}, {"_id": 0})
    if not e: raise HTTPException(404, "Exam not found")
    await assert_section_access(user, e["class_id"], section, subject_id)
    es = next((s for s in e["subjects"] if s["subject_id"] == subject_id), None)
    if not es: raise HTTPException(422, "Subject is not part of this exam")
    studs = await db.students.find({"class_id": e["class_id"], "section": section, "status": "active"}, {"_id": 0, "id": 1, "name": 1, "admission_no": 1}).sort("name", 1).to_list(500)
    mk = {m["student_id"]: m for m in await db.marks.find({"exam_id": eid, "subject_id": subject_id}, {"_id": 0}).to_list(1000)}
    for s in studs:
        m = mk.get(s["id"]); s["marks"] = m.get("marks") if m else None; s["absent"] = m.get("absent", False) if m else False; s["mark_status"] = m.get("status") if m else None
    return {"students": studs, "max_marks": es["max_marks"], "pass_marks": es["pass_marks"], "exam_status": e["status"]}

@router.post("/exams/{eid}/marks")
async def save_marks(eid: str, body: MarksIn, user=Depends(require("admin", "teacher"))):
    e = await db.exams.find_one({"id": eid}, {"_id": 0})
    if not e: raise HTTPException(404, "Exam not found")
    await assert_section_access(user, e["class_id"], body.section, body.subject_id)
    if e["status"] == "published" and user["role"] != "admin": raise HTTPException(403, "Results are published; only administrators can correct marks")
    es = next((s for s in e["subjects"] if s["subject_id"] == body.subject_id), None)
    if not es: raise HTTPException(422, "Subject is not part of this exam")
    valid = {x["id"] for x in await db.students.find({"class_id": e["class_id"], "section": body.section, "status": "active"}, {"_id": 0, "id": 1}).to_list(500)}
    for en in body.entries:
        if en.student_id not in valid: raise HTTPException(422, "Student not in this section")
        if not en.absent and en.marks is not None and not (0 <= en.marks <= es["max_marks"]):
            raise HTTPException(422, f"Marks must be between 0 and {es['max_marks']}")
    status = "submitted" if body.submit else "draft"
    for en in body.entries:
        old = await db.marks.find_one({"exam_id": eid, "student_id": en.student_id, "subject_id": body.subject_id}, {"_id": 0})
        if en.marks is None and not en.absent:
            if old:
                await db.marks.delete_one({"id": old["id"]})
                await audit(user, "marks_cleared", "marks", old["id"], {"student_id": en.student_id, "from": old.get("marks")})
            continue
        upd = {"$set": {"marks": None if en.absent else en.marks, "absent": en.absent, "status": status, "entered_by": user["id"], "updated_at": now_iso()},
               "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}
        if old and e["status"] == "published" and (old.get("marks") != en.marks or old.get("absent") != en.absent):
            upd["$push"] = {"history": {"from": old.get("marks"), "to": en.marks, "absent": en.absent, "by": user["name"], "at": now_iso()}}
            await audit(user, "marks_correction", "marks", old["id"], {"student_id": en.student_id, "from": old.get("marks"), "to": en.marks})
        await db.marks.update_one({"exam_id": eid, "student_id": en.student_id, "subject_id": body.subject_id}, upd, upsert=True)
    await audit(user, "marks_" + status, "exams", eid, {"section": body.section, "subject_id": body.subject_id, "count": len(body.entries)})
    return {"ok": True, "status": status}

async def compute_result(e, student_id, settings, sub_names):
    marks = {m["subject_id"]: m for m in await db.marks.find({"exam_id": e["id"], "student_id": student_id}, {"_id": 0}).to_list(100)}
    rows, total, maxt, all_pass, complete = [], 0, 0, True, True
    for es in e["subjects"]:
        m = marks.get(es["subject_id"]); val = None if not m or m.get("absent") else m.get("marks")
        absent = bool(m and m.get("absent"))
        if not m: complete = False
        passed = val is not None and val >= es["pass_marks"]
        if not passed: all_pass = False
        total += val or 0; maxt += es["max_marks"]
        rows.append({"subject_id": es["subject_id"], "subject_name": sub_names.get(es["subject_id"]), "max_marks": es["max_marks"], "pass_marks": es["pass_marks"],
                     "marks": val, "absent": absent, "grade": grade_for(val * 100 / es["max_marks"], settings["grading"]) if val is not None else ("AB" if absent else "-"), "passed": passed})
    p = round(total * 100 / maxt, 2) if maxt else 0
    return {"subjects": rows, "total": total, "max_total": maxt, "percentage": p, "grade": grade_for(p, settings["grading"]),
            "result": ("PASS" if all_pass and p >= settings["pass_percent"] else "FAIL") if complete else "INCOMPLETE"}

@router.get("/exams/{eid}/results")
async def exam_results(eid: str, section: str = "", user=Depends(require("admin", "teacher"))):
    e = await db.exams.find_one({"$and": [{"id": eid}, await exam_scope(user)]}, {"_id": 0})
    if not e: raise HTTPException(404, "Exam not found")
    s = await get_settings(); sub = {x["id"]: x["name"] for x in await db.subjects.find({}, {"_id": 0}).to_list(1000)}
    q = {"class_id": e["class_id"], "section": {"$in": [section] if section else e["sections"]}, "status": {"$ne": "archived"}, "archived": {"$ne": True}}
    studs = await db.students.find(q, {"_id": 0, "id": 1, "name": 1, "admission_no": 1, "section": 1}).to_list(1000)
    out = []
    for st in studs: out.append({**st, **(await compute_result(e, st["id"], s, sub))})
    out.sort(key=lambda r: -r["percentage"])
    for i, r in enumerate(out): r["rank"] = i + 1
    subj_stats = []
    for es in e["subjects"]:
        vals = [x["marks"] for r in out for x in r["subjects"] if x["subject_id"] == es["subject_id"] and x["marks"] is not None]
        subj_stats.append({"subject_name": sub.get(es["subject_id"]), "average": round(sum(vals) / len(vals), 1) if vals else 0, "max_marks": es["max_marks"],
                           "highest": max(vals) if vals else 0, "pass_rate": round(sum(1 for v in vals if v >= es["pass_marks"]) * 100 / len(vals), 1) if vals else 0})
    return {"exam": e, "results": out, "subject_stats": subj_stats}

class RemarkIn(BaseModel):
    student_id: str
    remark: str = Field(max_length=500)

@router.put("/exams/{eid}/remarks")
async def set_remark(eid: str, body: RemarkIn, user=Depends(require("admin", "teacher"))):
    st = await assert_student(user, body.student_id)
    if user["role"] == "teacher" and (st["class_id"], st["section"]) not in await class_teacher_pairs(user["profile_id"]):
        _, _, subj = await teacher_ctx(user)
        if not any(c == st["class_id"] and s == st["section"] for c, s, _ in subj): raise HTTPException(403, "Not permitted")
    await db.exam_remarks.update_one({"exam_id": eid, "student_id": body.student_id}, {"$set": {"remark": body.remark, "by": user["name"], "at": now_iso()}}, upsert=True)
    return {"ok": True}

@router.get("/report-card/{eid}/{sid}")
async def report_card(eid: str, sid: str, user=Depends(get_current_user)):
    st = await assert_student(user, sid)
    e = await db.exams.find_one({"id": eid, "class_id": st["class_id"], "sections": st["section"]}, {"_id": 0})
    if not e: raise HTTPException(404, "Exam not found for this student")
    if user["role"] in ("student", "parent") and e["status"] != "published": raise HTTPException(403, "Results are not published yet")
    s = await get_settings(); sub = {x["id"]: x["name"] for x in await db.subjects.find({}, {"_id": 0}).to_list(1000)}
    res = await compute_result(e, sid, s, sub)
    counts = {k: 0 for k in STATUSES}
    async for r in db.attendance.aggregate([{"$match": {"student_id": sid}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]): counts[r["_id"]] = r["n"]
    rem = await db.exam_remarks.find_one({"exam_id": eid, "student_id": sid}, {"_id": 0})
    c = await db.classes.find_one({"id": st["class_id"]}, {"_id": 0})
    sec = next((x for x in (c or {}).get("sections", []) if x["name"] == st["section"]), {})
    ct = await db.teachers.find_one({"id": sec.get("class_teacher_id")}, {"_id": 0, "name": 1}) if sec.get("class_teacher_id") else None
    return {"school": {k: s[k] for k in ("school_name", "address", "phone", "email", "website", "logo_file_id", "tagline")},
            "student": {k: st.get(k) for k in ("id", "name", "admission_no", "class_name", "section", "dob", "guardian_name", "photo_file_id")},
            "exam": {k: e[k] for k in ("id", "name", "type", "academic_year", "term", "status")}, **res,
            "attendance": {**counts, "percentage": pct(counts)}, "remark": rem.get("remark") if rem else "", "class_teacher": ct["name"] if ct else ""}

@router.get("/results/student/{sid}")
async def student_results(sid: str, user=Depends(get_current_user)):
    st = await assert_student(user, sid)
    q = {"class_id": st["class_id"], "sections": st["section"], "archived": {"$ne": True}}
    if user["role"] in ("student", "parent"): q["status"] = "published"
    s = await get_settings(); sub = {x["id"]: x["name"] for x in await db.subjects.find({}, {"_id": 0}).to_list(1000)}
    out = []
    for e in await db.exams.find(q, {"_id": 0}).sort("created_at", -1).to_list(100):
        r = await compute_result(e, sid, s, sub)
        out.append({"exam_id": e["id"], "name": e["name"], "type": e["type"], "term": e["term"], "status": e["status"], **{k: r[k] for k in ("percentage", "grade", "result", "total", "max_total")}, "subjects": r["subjects"]})
    return out
