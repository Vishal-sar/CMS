import re
from datetime import date as Date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from core import db, require, get_current_user, teacher_ctx, student_query, get_settings, today, to_csv, audit
from routes_academic import pct, STATUSES

router = APIRouter(prefix="/api")

async def sum_field(coll, match, field):
    r = [x async for x in db[coll].aggregate([{"$match": match}, {"$group": {"_id": None, "s": {"$sum": f"${field}"}}}])]
    return r[0]["s"] if r else 0

async def admin_dash():
    t = await today(); s = await get_settings()
    act = {"status": "active", "archived": {"$ne": True}}
    att = {r["_id"]: r["n"] async for r in db.attendance.aggregate([{"$match": {"date": t}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    classes = await db.classes.find({"archived": {"$ne": True}}, {"_id": 0}).sort("grade_level", 1).to_list(200)
    dist = {r["_id"]: r["n"] async for r in db.students.aggregate([{"$match": act}, {"$group": {"_id": "$class_id", "n": {"$sum": 1}}}])}
    enroll = {}
    async for r in db.students.aggregate([{"$match": {"archived": {"$ne": True}}}, {"$group": {"_id": {"$substr": ["$admission_date", 0, 7]}, "n": {"$sum": 1}}}]): enroll[r["_id"]] = r["n"]
    months = sorted(enroll)[-12:]
    start = (Date.fromisoformat(t) - timedelta(days=21)).isoformat()
    trend = {}
    async for r in db.attendance.aggregate([{"$match": {"date": {"$gte": start}}}, {"$group": {"_id": {"d": "$date", "s": "$status"}, "n": {"$sum": 1}}}]):
        trend.setdefault(r["_id"]["d"], {k: 0 for k in STATUSES})[r["_id"]["s"]] = r["n"]
    fee_month = {}
    async for r in db.payments.aggregate([{"$match": {"status": "success"}}, {"$group": {"_id": {"$substr": ["$date", 0, 7]}, "s": {"$sum": "$amount"}}}]): fee_month[r["_id"]] = r["s"]
    collected = await sum_field("payments", {"status": "success"}, "amount")
    pending = await sum_field("invoices", {"status": {"$in": ["unpaid", "partial"]}}, "balance")
    overdue = await sum_field("invoices", {"status": {"$in": ["unpaid", "partial"]}, "due_date": {"$lt": t}}, "balance")
    exams = await db.exams.find({"archived": {"$ne": True}}, {"_id": 0}).to_list(500)
    upcoming = sorted([{"exam": e["name"], "exam_id": e["id"], "date": min(x["date"] for x in e["subjects"]), "class_id": e["class_id"]} for e in exams if e["subjects"] and max(x["date"] for x in e["subjects"]) >= t], key=lambda x: x["date"])[:5]
    cname = {c["id"]: c["name"] for c in classes}
    for u in upcoming: u["class_name"] = cname.get(u["class_id"])
    perf = []
    for e in [e for e in exams if e["status"] == "published"][:6]:
        mx = {x["subject_id"]: x["max_marks"] for x in e["subjects"]}
        ms = await db.marks.find({"exam_id": e["id"], "absent": False, "marks": {"$ne": None}}, {"_id": 0}).to_list(5000)
        if ms: perf.append({"exam": f"{e['name']} ({cname.get(e['class_id'])})", "average": round(sum(m["marks"] * 100 / mx.get(m["subject_id"], 100) for m in ms) / len(ms), 1)})
    present = att.get("present", 0) + att.get("late", 0)
    return {
        "stats": {"students": await db.students.count_documents(act), "teachers": await db.teachers.count_documents({"archived": {"$ne": True}, "status": "active"}),
                  "parents": await db.parents.count_documents({"archived": {"$ne": True}}), "classes": len(classes), "sections": sum(len(c.get("sections", [])) for c in classes),
                  "present_today": present, "absent_today": att.get("absent", 0), "attendance_pct": pct(att), "marked_today": sum(att.values()),
                  "fees_collected": collected, "fees_pending": pending, "fees_overdue": overdue, "upcoming_exams": len(upcoming),
                  "pending_leaves": await db.leaves.count_documents({"status": "pending"}), "overdue_books": await db.book_issues.count_documents({"status": "issued", "due_date": {"$lt": t}})},
        "enrollment": [{"month": m, "students": enroll[m]} for m in months],
        "attendance_trend": [{"date": d[5:], **c, "percentage": pct(c)} for d, c in sorted(trend.items())],
        "fees": [{"month": m, "collected": v} for m, v in sorted(fee_month.items())[-8:]],
        "fee_split": [{"name": "Collected", "value": collected}, {"name": "Outstanding", "value": pending}],
        "class_distribution": [{"class": c["name"], "students": dist.get(c["id"], 0)} for c in classes],
        "exam_performance": perf, "upcoming_exams": upcoming,
        "recent_admissions": await db.students.find({"archived": {"$ne": True}}, {"_id": 0, "id": 1, "name": 1, "admission_no": 1, "class_name": 1, "section": 1, "admission_date": 1}).sort("created_at", -1).limit(5).to_list(5),
        "recent_payments": await db.payments.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5),
        "events": await db.events.find({"end_date": {"$gte": t}, "archived": {"$ne": True}}, {"_id": 0}).sort("start_date", 1).limit(5).to_list(5),
        "announcements": await db.announcements.find({"archived": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).limit(4).to_list(4),
        "activity": await db.audit_logs.find({"action": {"$ne": "login"}}, {"_id": 0}).sort("created_at", -1).limit(8).to_list(8),
    }

async def teacher_dash(user):
    t = await today(); tid, pairs, subj = await teacher_ctx(user)
    dow = Date.fromisoformat(t).strftime("%a")
    from routes_academic import enrich
    sched = await enrich(await db.timetable.find({"teacher_id": tid, "day": dow}, {"_id": 0}).sort("period_no", 1).to_list(20))
    cname = {c["id"]: c["name"] for c in await db.classes.find({}, {"_id": 0}).to_list(500)}
    secs = []
    for c, s in sorted(pairs):
        n = await db.students.count_documents({"class_id": c, "section": s, "status": "active"})
        marked = await db.attendance.count_documents({"date": t, "class_id": c, "section": s})
        secs.append({"class_id": c, "class_name": cname.get(c), "section": s, "students": n, "marked_today": marked > 0})
    hw = await db.homework.find({"teacher_id": tid, "status": "published"}, {"_id": 0}).sort("due_date", -1).limit(5).to_list(5)
    for h in hw: h["submissions"] = await db.submissions.count_documents({"homework_id": h["id"]}); h["ungraded"] = await db.submissions.count_documents({"homework_id": h["id"], "grade": None})
    return {"sections": secs, "today_schedule": sched, "homework": hw, "subjects": len(subj),
            "pending_leaves": await db.leaves.count_documents({"requester_id": user["id"], "status": "pending"}),
            "events": await db.events.find({"end_date": {"$gte": t}, "archived": {"$ne": True}}, {"_id": 0}).sort("start_date", 1).limit(5).to_list(5)}

async def student_card(sid, t):
    st = await db.students.find_one({"id": sid}, {"_id": 0})
    counts = {k: 0 for k in STATUSES}
    async for r in db.attendance.aggregate([{"$match": {"student_id": sid}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]): counts[r["_id"]] = r["n"]
    today_rec = await db.attendance.find_one({"student_id": sid, "date": t}, {"_id": 0})
    due = await db.invoices.find({"student_id": sid, "status": {"$in": ["unpaid", "partial"]}}, {"_id": 0}).to_list(50)
    hw = await db.homework.find({"class_id": st["class_id"], "section": st["section"], "status": "published", "due_date": {"$gte": t}}, {"_id": 0}).sort("due_date", 1).to_list(10)
    pending_hw = [h for h in hw if not await db.submissions.find_one({"homework_id": h["id"], "student_id": sid})]
    return {"student": {k: st.get(k) for k in ("id", "name", "admission_no", "class_name", "section", "photo_file_id", "academic_year", "class_id")},
            "attendance": {**counts, "percentage": pct(counts), "today": today_rec["status"] if today_rec else None},
            "fees_due": sum(i["balance"] for i in due), "overdue_invoices": sum(1 for i in due if i["due_date"] < t), "homework_pending": pending_hw[:5]}

async def family_dash(user):
    t = await today()
    studs = await db.students.find(await student_query(user), {"_id": 0, "id": 1}).to_list(20)
    from routes_misc import ann_scope
    anns = await db.announcements.find({"$and": [await ann_scope(user), {"archived": {"$ne": True}}]}, {"_id": 0}).sort("created_at", -1).limit(4).to_list(4)
    return {"children": [await student_card(s["id"], t) for s in studs], "announcements": anns,
            "events": await db.events.find({"end_date": {"$gte": t}, "archived": {"$ne": True}}, {"_id": 0}).sort("start_date", 1).limit(5).to_list(5)}

@router.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    if user["role"] == "admin": return await admin_dash()
    if user["role"] == "teacher": return await teacher_dash(user)
    return await family_dash(user)

@router.get("/search")
async def search(q: str, user=Depends(get_current_user)):
    if len(q.strip()) < 2: return {"results": []}
    rx = {"$regex": re.escape(q.strip()), "$options": "i"}; out = []
    sq = await student_query(user)
    for s in await db.students.find({"$and": [sq, {"$or": [{"name": rx}, {"admission_no": rx}]}]}, {"_id": 0, "id": 1, "name": 1, "admission_no": 1, "class_name": 1, "section": 1}).limit(6).to_list(6):
        out.append({"type": "student", "id": s["id"], "title": s["name"], "subtitle": f"{s['admission_no']} · {s.get('class_name')}-{s['section']}", "link": f"/students/{s['id']}"})
    if user["role"] == "admin":
        for t in await db.teachers.find({"$or": [{"name": rx}, {"employee_id": rx}]}, {"_id": 0, "id": 1, "name": 1, "employee_id": 1, "designation": 1}).limit(5).to_list(5):
            out.append({"type": "teacher", "id": t["id"], "title": t["name"], "subtitle": f"{t['employee_id']} · {t['designation']}", "link": "/teachers"})
        for i in await db.invoices.find({"invoice_no": rx}, {"_id": 0, "id": 1, "invoice_no": 1, "student_name": 1}).limit(4).to_list(4):
            out.append({"type": "invoice", "id": i["id"], "title": i["invoice_no"], "subtitle": i["student_name"], "link": "/fees"})
    for b in await db.books.find({"$or": [{"title": rx}, {"author": rx}, {"isbn": rx}], "archived": {"$ne": True}}, {"_id": 0, "id": 1, "title": 1, "author": 1}).limit(4).to_list(4):
        out.append({"type": "book", "id": b["id"], "title": b["title"], "subtitle": b["author"], "link": "/library"})
    return {"results": out}

# ---------- reports ----------
REPORTS = {
    "enrollment": "Student enrollment", "class_list": "Class-wise student list", "attendance_daily": "Daily attendance", "attendance_monthly": "Monthly attendance",
    "low_attendance": "Low attendance", "staff": "Teacher & staff", "exam_performance": "Examination performance", "subject_marks": "Subject-wise marks",
    "fee_collection": "Fee collection", "outstanding": "Outstanding fees", "transactions": "Payment transactions", "library_inventory": "Library inventory",
    "library_overdue": "Overdue books", "transport": "Transport allocation", "leave_summary": "Leave summary",
}

@router.get("/reports")
async def report_list(user=Depends(require("admin"))):
    return [{"key": k, "name": v} for k, v in REPORTS.items()]

@router.get("/reports/{key}")
async def run_report(key: str, class_id: str = "", section: str = "", academic_year: str = "", date_from: str = "", date_to: str = "", status: str = "",
                     exam_id: str = "", subject_id: str = "", method: str = "", format: str = "", user=Depends(require("admin"))):
    if key not in REPORTS: raise HTTPException(404, "Unknown report")
    t = await today(); s = await get_settings()
    sq = {"archived": {"$ne": True}}
    if class_id: sq["class_id"] = class_id
    if section: sq["section"] = section
    if academic_year: sq["academic_year"] = academic_year
    dr = {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}
    cols, rows = [], []
    if key in ("enrollment", "class_list"):
        if status: sq["status"] = status
        if key == "enrollment" and dr: sq["admission_date"] = dr
        rows = await db.students.find(sq, {"_id": 0}).sort([("class_name", 1), ("section", 1), ("name", 1)]).to_list(20000)
        cols = [("admission_no", "Admission No"), ("name", "Name"), ("class_name", "Class"), ("section", "Section"), ("gender", "Gender"), ("admission_date", "Admitted"), ("guardian_name", "Guardian"), ("guardian_phone", "Phone"), ("status", "Status")]
    elif key in ("attendance_daily", "attendance_monthly", "low_attendance"):
        m = {k: v for k, v in sq.items() if k in ("class_id", "section")}
        if key == "attendance_daily": m["date"] = date_from or t
        elif dr: m["date"] = dr
        agg = {}
        async for r in db.attendance.aggregate([{"$match": m}, {"$group": {"_id": {"s": "$student_id", "st": "$status"}, "n": {"$sum": 1}}}]):
            agg.setdefault(r["_id"]["s"], {k: 0 for k in STATUSES})[r["_id"]["st"]] = r["n"]
        studs = {x["id"]: x for x in await db.students.find({"id": {"$in": list(agg)}}, {"_id": 0}).to_list(20000)}
        for sid, c in agg.items():
            st = studs.get(sid, {}); p = pct(c)
            if key == "low_attendance" and (p is None or p >= s["low_attendance_threshold"]): continue
            rows.append({"admission_no": st.get("admission_no"), "name": st.get("name"), "class_name": st.get("class_name"), "section": st.get("section"), **c, "percentage": p})
        rows.sort(key=lambda r: (r["class_name"] or "", r["section"] or "", r["name"] or ""))
        cols = [("admission_no", "Admission No"), ("name", "Name"), ("class_name", "Class"), ("section", "Section"), ("present", "Present"), ("late", "Late"), ("absent", "Absent"), ("excused", "Excused"), ("percentage", "Attendance %")]
    elif key == "staff":
        q = {"archived": {"$ne": True}}
        if status: q["status"] = status
        rows = await db.teachers.find(q, {"_id": 0}).sort("name", 1).to_list(5000)
        cols = [("employee_id", "Employee ID"), ("name", "Name"), ("designation", "Designation"), ("department", "Department"), ("specialization", "Subject"), ("joining_date", "Joined"), ("status", "Status"), ("salary", "Salary")]
    elif key in ("exam_performance", "subject_marks"):
        from routes_exams import exam_results
        if not exam_id: raise HTTPException(422, "Choose an exam")
        r = await exam_results(exam_id, section, user)
        if key == "exam_performance":
            rows = [{k: x[k] for k in ("rank", "admission_no", "name", "section", "total", "max_total", "percentage", "grade", "result")} for x in r["results"]]
            cols = [("rank", "Rank"), ("admission_no", "Admission No"), ("name", "Name"), ("section", "Section"), ("total", "Total"), ("max_total", "Max"), ("percentage", "%"), ("grade", "Grade"), ("result", "Result")]
        else:
            for x in r["results"]:
                for sj in x["subjects"]:
                    if subject_id and sj["subject_id"] != subject_id: continue
                    rows.append({"admission_no": x["admission_no"], "name": x["name"], "section": x["section"], "subject": sj["subject_name"], "marks": "AB" if sj["absent"] else sj["marks"], "max_marks": sj["max_marks"], "grade": sj["grade"], "passed": "Yes" if sj["passed"] else "No"})
            cols = [("admission_no", "Admission No"), ("name", "Name"), ("section", "Section"), ("subject", "Subject"), ("marks", "Marks"), ("max_marks", "Max"), ("grade", "Grade"), ("passed", "Pass")]
    elif key in ("fee_collection", "transactions"):
        q = {}
        if dr: q["date"] = dr
        if class_id: q["class_id"] = class_id
        if method: q["method"] = method
        q["status"] = status or "success" if key == "fee_collection" else (status or {"$exists": True})
        rows = await db.payments.find(q, {"_id": 0}).sort("date", -1).to_list(20000)
        cols = [("receipt_no", "Receipt"), ("date", "Date"), ("student_name", "Student"), ("admission_no", "Admission No"), ("class_name", "Class"), ("invoice_no", "Invoice"), ("method", "Method"), ("reference", "Reference"), ("amount", "Amount"), ("status", "Status")]
    elif key == "outstanding":
        q = {"status": {"$in": ["unpaid", "partial"]}}
        if class_id: q["class_id"] = class_id
        if academic_year: q["academic_year"] = academic_year
        if status == "overdue": q["due_date"] = {"$lt": t}
        rows = await db.invoices.find(q, {"_id": 0}).sort("due_date", 1).to_list(20000)
        for r in rows: r["overdue"] = "Yes" if r["due_date"] < t else "No"
        cols = [("invoice_no", "Invoice"), ("student_name", "Student"), ("admission_no", "Admission No"), ("class_name", "Class"), ("section", "Section"), ("total", "Total"), ("paid", "Paid"), ("balance", "Balance"), ("due_date", "Due"), ("overdue", "Overdue")]
    elif key == "library_inventory":
        rows = await db.books.find({"archived": {"$ne": True}}, {"_id": 0}).sort("title", 1).to_list(20000)
        cols = [("accession_no", "Accession"), ("title", "Title"), ("author", "Author"), ("isbn", "ISBN"), ("category", "Category"), ("total_copies", "Total"), ("available_copies", "Available")]
    elif key == "library_overdue":
        rows = await db.book_issues.find({"status": "issued", "due_date": {"$lt": t}}, {"_id": 0}).sort("due_date", 1).to_list(20000)
        for r in rows: r["days_overdue"] = (Date.fromisoformat(t) - Date.fromisoformat(r["due_date"])).days; r["est_fine"] = r["days_overdue"] * s["library_fine_per_day"]
        cols = [("accession_no", "Accession"), ("book_title", "Book"), ("borrower_name", "Borrower"), ("borrower_type", "Type"), ("issue_date", "Issued"), ("due_date", "Due"), ("days_overdue", "Days Overdue"), ("est_fine", "Fine")]
    elif key == "transport":
        q = {**sq, "transport.route_id": {"$exists": True}}
        for r in await db.students.find(q, {"_id": 0}).sort("transport.route_name", 1).to_list(20000):
            rows.append({"route": r["transport"].get("route_name"), "stop": r["transport"].get("stop"), "admission_no": r["admission_no"], "name": r["name"], "class_name": r.get("class_name"), "section": r["section"], "guardian_phone": r.get("guardian_phone")})
        cols = [("route", "Route"), ("stop", "Stop"), ("admission_no", "Admission No"), ("name", "Name"), ("class_name", "Class"), ("section", "Section"), ("guardian_phone", "Guardian Phone")]
    elif key == "leave_summary":
        q = {}
        if status: q["status"] = status
        if dr: q["from_date"] = dr
        rows = await db.leaves.find(q, {"_id": 0}).sort("from_date", -1).to_list(20000)
        cols = [("requester_name", "Requested By"), ("requester_role", "Role"), ("student_name", "Student"), ("leave_type", "Type"), ("from_date", "From"), ("to_date", "To"), ("status", "Status"), ("reviewer", "Reviewer")]
    if format == "csv":
        await audit(user, "export_report", "reports", key, {"rows": len(rows)})
        return to_csv(rows, cols, key)
    return {"title": REPORTS[key], "columns": [{"key": k, "label": l} for k, l in cols], "rows": rows[:2000], "total": len(rows)}
