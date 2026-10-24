import csv, io
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, Field, EmailStr
from core import db, now_iso, new_id, clean, require, audit, next_seq, crud, student_query, teacher_ctx, get_settings, today
from routes_auth import create_user_record, strong

router = APIRouter(prefix="/api")

class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    photo_file_id: Optional[str] = None
    dob: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    gender: str
    class_id: str
    section: str
    academic_year: str
    admission_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    blood_group: Optional[str] = None
    address: str = Field("", max_length=300)
    phone: Optional[str] = None
    email: Optional[str] = None
    guardian_name: str = Field(min_length=1)
    guardian_phone: str = Field(min_length=6, max_length=20)
    guardian_email: Optional[str] = None
    emergency_contact: Optional[str] = None
    previous_school: Optional[str] = None
    status: str = Field("active", pattern="^(active|inactive|transferred|graduated|archived)$")
    parent_ids: List[str] = []
    _login_password: Optional[str] = None

class TeacherIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    photo_file_id: Optional[str] = None
    email: EmailStr
    phone: str = Field(min_length=6, max_length=20)
    address: str = ""
    designation: str = "Teacher"
    department: str = ""
    specialization: str = ""
    joining_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: str = Field("active", pattern="^(active|on_leave|resigned|archived)$")
    qualification: str = ""
    experience_years: float = Field(0, ge=0, le=60)
    salary: Optional[float] = Field(None, ge=0)

class ParentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=20)
    address: str = ""
    occupation: str = ""
    relation: str = "Guardian"
    student_ids: List[str] = []

async def validate_class(class_id, section):
    c = await db.classes.find_one({"id": class_id, "archived": {"$ne": True}}, {"_id": 0})
    if not c: raise HTTPException(422, "Selected class does not exist")
    sec = next((s for s in c.get("sections", []) if s["name"] == section), None)
    if not sec: raise HTTPException(422, f"Section {section} does not exist in {c['name']}")
    return c, sec

async def student_before(data, user, old):
    c, sec = await validate_class(data["class_id"], data["section"])
    if not old or (old["class_id"], old["section"]) != (data["class_id"], data["section"]):
        cnt = await db.students.count_documents({"class_id": data["class_id"], "section": data["section"], "status": "active"})
        if sec.get("capacity") and cnt >= int(sec["capacity"]): raise HTTPException(409, f"{c['name']}-{data['section']} is at full capacity ({sec['capacity']})")
    data["class_name"] = c["name"]
    if old is None:
        yr = data["admission_date"][:4]
        data["admission_no"] = await next_seq(f"adm{yr}", f"ADM{yr}", 4)
        data["history"] = [{"date": now_iso(), "event": "admitted", "class_name": c["name"], "section": data["section"], "academic_year": data["academic_year"]}]
    else:
        data["admission_no"] = old["admission_no"]
        data["history"] = old.get("history", [])
        if (old["class_id"], old["section"]) != (data["class_id"], data["section"]):
            data["history"].append({"date": now_iso(), "event": "class_changed", "class_name": c["name"], "section": data["section"], "academic_year": data["academic_year"]})
    await sync_parents(data.get("parent_ids", []), old.get("parent_ids", []) if old else [], old["id"] if old else None)
    return data

async def sync_parents(new, old, sid):
    if sid:
        for p in set(old) - set(new): await db.parents.update_one({"id": p}, {"$pull": {"student_ids": sid}})
        for p in set(new): await db.parents.update_one({"id": p}, {"$addToSet": {"student_ids": sid}})

async def student_after(data, user, extra):
    for p in data.get("parent_ids", []): await db.parents.update_one({"id": p}, {"$addToSet": {"student_ids": data["id"]}})

def staff_hide(user): return [] if user["role"] == "admin" else ["salary", "address", "phone"]
def student_hide(user): return [] if user["role"] in ("admin", "teacher") else []

async def teacher_scope(user):
    if user["role"] in ("admin", "teacher"): return {}
    sq = await student_query(user)
    studs = await db.students.find(sq, {"_id": 0, "class_id": 1, "section": 1}).to_list(50)
    tids = set()
    for s in studs:
        async for a in db.assignments.find({"class_id": s["class_id"], "section": s["section"]}, {"_id": 0}): tids.add(a["teacher_id"])
    return {"id": {"$in": list(tids)}}

async def teacher_before(data, user, old):
    data["employee_id"] = old["employee_id"] if old else await next_seq("emp", "EMP", 4)
    data["email"] = data["email"].lower()
    return data

async def parent_scope(user):
    if user["role"] == "admin": return {}
    if user["role"] == "parent": return {"id": user.get("profile_id")}
    sq = await student_query(user)
    pids = {p for s in await db.students.find(sq, {"_id": 0, "parent_ids": 1}).to_list(5000) for p in s.get("parent_ids", [])}
    return {"id": {"$in": list(pids)}}

async def parent_before(data, user, old):
    data["email"] = data["email"].lower()
    if old:
        for s in set(old.get("student_ids", [])) - set(data["student_ids"]): await db.students.update_one({"id": s}, {"$pull": {"parent_ids": old["id"]}})
        for s in data["student_ids"]: await db.students.update_one({"id": s}, {"$addToSet": {"parent_ids": old["id"]}})
    return data

async def parent_after(data, user, extra):
    for s in data["student_ids"]: await db.students.update_one({"id": s}, {"$addToSet": {"parent_ids": data["id"]}})

# ---- student extras (registered before crud so static paths win) ----
class PromoteIn(BaseModel):
    student_ids: List[str]
    to_class_id: str
    to_section: str
    to_academic_year: str

@router.post("/students/promote")
async def promote(body: PromoteIn, user=Depends(require("admin"))):
    c, _ = await validate_class(body.to_class_id, body.to_section)
    n = 0
    for sid in body.student_ids:
        st = await db.students.find_one({"id": sid, "status": "active"})
        if not st: continue
        await db.students.update_one({"id": sid}, {"$set": {"class_id": c["id"], "class_name": c["name"], "section": body.to_section, "academic_year": body.to_academic_year},
                                                   "$push": {"history": {"date": now_iso(), "event": "promoted", "from": f"{st.get('class_name')}-{st['section']} ({st['academic_year']})",
                                                                         "class_name": c["name"], "section": body.to_section, "academic_year": body.to_academic_year}}})
        n += 1
    await audit(user, "promote", "students", None, {"count": n, "to": f"{c['name']}-{body.to_section}", "year": body.to_academic_year})
    return {"promoted": n}

class TransferIn(BaseModel):
    section: str

@router.post("/students/{sid}/transfer")
async def transfer(sid: str, body: TransferIn, user=Depends(require("admin"))):
    st = await db.students.find_one({"id": sid}, {"_id": 0})
    if not st: raise HTTPException(404, "Student not found")
    c, sec = await validate_class(st["class_id"], body.section)
    cnt = await db.students.count_documents({"class_id": st["class_id"], "section": body.section, "status": "active"})
    if sec.get("capacity") and cnt >= int(sec["capacity"]): raise HTTPException(409, "Target section is full")
    await db.students.update_one({"id": sid}, {"$set": {"section": body.section}, "$push": {"history": {"date": now_iso(), "event": "section_transfer", "from": st["section"], "class_name": c["name"], "section": body.section, "academic_year": st["academic_year"]}}})
    await audit(user, "transfer", "students", sid, {"from": st["section"], "to": body.section})
    return {"ok": True}

@router.post("/students/import")
async def import_students(file: UploadFile = File(...), user=Depends(require("admin"))):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(422, "Upload a .csv file")
    raw = await file.read()
    if len(raw) > 2_000_000: raise HTTPException(422, "CSV too large (max 2MB)")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    classes = {c["name"].lower(): c for c in await db.classes.find({"archived": {"$ne": True}}, {"_id": 0}).to_list(500)}
    s = await get_settings()
    created, errors = 0, []
    for i, r in enumerate(rows, start=2):
        try:
            c = classes.get((r.get("class") or "").strip().lower())
            if not c: raise ValueError(f"unknown class '{r.get('class')}'")
            data = StudentIn(name=r.get("name", "").strip(), dob=r.get("dob", "").strip(), gender=r.get("gender", "").strip() or "Other", class_id=c["id"],
                             section=(r.get("section") or "").strip(), academic_year=r.get("academic_year") or s["academic_year"],
                             admission_date=r.get("admission_date") or await today(), address=r.get("address", ""), guardian_name=r.get("guardian_name", "").strip(),
                             guardian_phone=r.get("guardian_phone", "").strip(), guardian_email=r.get("guardian_email") or None, blood_group=r.get("blood_group") or None).model_dump()
            data = await student_before(data, user, None)
            data.update({"id": new_id(), "created_at": now_iso(), "updated_at": now_iso(), "archived": False})
            await db.students.insert_one(data); created += 1
        except Exception as e:
            msg = e.detail if isinstance(e, HTTPException) else (e.errors()[0]["msg"] + f" ({e.errors()[0]['loc'][0]})" if hasattr(e, "errors") else str(e))
            errors.append({"row": i, "error": msg})
    await audit(user, "import", "students", None, {"created": created, "errors": len(errors)})
    return {"created": created, "errors": errors}

STUDENT_CSV = [("admission_no", "Admission No"), ("name", "Name"), ("class_name", "Class"), ("section", "Section"), ("academic_year", "Academic Year"),
               ("gender", "Gender"), ("dob", "DOB"), ("guardian_name", "Guardian"), ("guardian_phone", "Guardian Phone"), ("status", "Status")]

crud(router, "/students", "students", StudentIn, read_roles=("admin", "teacher", "student", "parent"), search=("name", "admission_no", "guardian_name"),
     filters=("class_id", "section", "academic_year", "status", "gender"), csv_cols=STUDENT_CSV,
     hooks={"scope": student_query, "before_save": student_before, "after_create": student_after, "hide": student_hide})
crud(router, "/teachers", "teachers", TeacherIn, read_roles=("admin", "teacher", "student", "parent"), search=("name", "employee_id", "email", "department", "specialization"),
     filters=("department", "status", "designation"), hooks={"scope": teacher_scope, "before_save": teacher_before, "hide": staff_hide},
     csv_cols=[("employee_id", "Employee ID"), ("name", "Name"), ("email", "Email"), ("phone", "Phone"), ("designation", "Designation"), ("department", "Department"),
               ("specialization", "Specialization"), ("joining_date", "Joining Date"), ("status", "Status")])
crud(router, "/parents", "parents", ParentIn, read_roles=("admin", "teacher", "parent"), search=("name", "email", "phone"),
     hooks={"scope": parent_scope, "before_save": parent_before, "after_create": parent_after},
     csv_cols=[("name", "Name"), ("email", "Email"), ("phone", "Phone"), ("relation", "Relation"), ("occupation", "Occupation")])

class LoginCreateIn(BaseModel):
    password: str = Field(min_length=8)
    email: Optional[str] = None

@router.post("/{kind}/{pid}/create-login")
async def create_login(kind: str, pid: str, body: LoginCreateIn, user=Depends(require("admin"))):
    role = {"teachers": "teacher", "students": "student", "parents": "parent"}.get(kind)
    if not role: raise HTTPException(404, "Unknown profile type")
    strong(body.password)
    p = await db[kind].find_one({"id": pid}, {"_id": 0})
    if not p: raise HTTPException(404, "Profile not found")
    email = body.email or p.get("email")
    if not email: raise HTTPException(422, "An email is required for the login")
    u = await create_user_record(email, p["name"], role, body.password, pid)
    await audit(user, "create_login", kind, pid)
    return u
