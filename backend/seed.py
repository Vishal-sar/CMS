import random
from datetime import date as Date, timedelta
from core import db, new_id, now_iso, hash_password, DEFAULT_SETTINGS, today

random.seed(42)
FIRST_M = ["Aarav", "Vivaan", "Aditya", "Arjun", "Reyansh", "Kabir", "Ishaan", "Rohan", "Dhruv", "Krish", "Aryan", "Shaurya", "Atharv", "Yash", "Rudra"]
FIRST_F = ["Ananya", "Diya", "Saanvi", "Aadhya", "Myra", "Kiara", "Ira", "Anika", "Navya", "Riya", "Meera", "Tara", "Zara", "Pari", "Avni"]
LAST = ["Sharma", "Verma", "Iyer", "Reddy", "Nair", "Gupta", "Patel", "Mehta", "Rao", "Kulkarni", "Joshi", "Menon", "Singh", "Das", "Bose"]
SUBJECTS = [("English", "ENG"), ("Mathematics", "MATH"), ("Science", "SCI"), ("Social Studies", "SST"), ("Hindi", "HIN"), ("Computer Science", "CS")]
TEACHERS = [("Dr. Kavita Rao", "English"), ("Rahul Menon", "English"), ("Sunita Iyer", "Mathematics"), ("Vikram Shah", "Mathematics"), ("Dr. Neha Kapoor", "Science"),
            ("Arvind Pillai", "Science"), ("Meenakshi Das", "Social Studies"), ("Sanjay Kulkarni", "Social Studies"), ("Pooja Mishra", "Hindi"), ("Rakesh Tiwari", "Hindi"),
            ("Anjali Nair", "Computer Science"), ("Farhan Qureshi", "Computer Science")]
D = {"demo": True}

def ins(coll, doc): return db[coll].insert_one({**doc, **D, "created_at": doc.get("created_at", now_iso()), "archived": False})

async def seed_demo():
    s = await db.settings.find_one({"id": "school"})
    if s and s.get("demo_seeded"): return
    await db.settings.update_one({"id": "school"}, {"$set": {**DEFAULT_SETTINGS, "demo_seeded": True}}, upsert=True)
    t = Date.fromisoformat(await today()); yr = "2026-27"
    await ins("academic_years", {"id": new_id(), "name": yr, "start_date": "2026-04-01", "end_date": "2027-03-31", "current": True,
                                 "terms": [{"name": "Term 1", "start": "2026-04-01", "end": "2026-09-30"}, {"name": "Term 2", "start": "2026-10-01", "end": "2027-03-31"}]})
    subj = []
    for n, c in SUBJECTS:
        d = {"id": new_id(), "name": n, "code": c, "type": "Theory", "class_ids": []}; subj.append(d)
    teachers = []
    for i, (n, sp) in enumerate(TEACHERS):
        d = {"id": new_id(), "employee_id": f"EMP{str(i + 1).zfill(4)}", "name": n, "email": f"{n.split()[-1].lower()}.{i + 1}@eduprime.demo", "phone": f"98450{10000 + i}",
             "address": "Bengaluru", "designation": "Senior Teacher" if i % 2 == 0 else "Teacher", "department": sp, "specialization": sp, "joining_date": f"20{15 + i % 8}-06-01",
             "status": "active", "qualification": "M.Sc, B.Ed" if i % 2 else "M.A, B.Ed", "experience_years": 4 + i, "salary": 45000 + i * 2500}
        teachers.append(d); await ins("teachers", d)
    await db.counters.update_one({"id": "emp"}, {"$set": {"v": len(teachers)}}, upsert=True)
    classes, sections = [], []
    for g in range(6, 11):
        c = {"id": new_id(), "name": f"Grade {g}", "grade_level": g, "sections": []}
        for k, sn in enumerate(["A", "B"]):
            idx = len(sections)
            c["sections"].append({"name": sn, "capacity": 40, "class_teacher_id": teachers[idx % 12]["id"], "room": f"{g}0{k + 1}"})
            sections.append((c, sn, idx))
        classes.append(c)
    for sj in subj:
        sj["class_ids"] = [c["id"] for c in classes]; await ins("subjects", sj)
    for c in classes: await ins("classes", c)
    asg = {}
    for c, sn, k in sections:
        for j, sj in enumerate(subj):
            tch = teachers[j * 2 + (0 if k < 5 else 1)]
            asg[(c["id"], sn, sj["id"])] = tch["id"]
            await ins("assignments", {"id": new_id(), "teacher_id": tch["id"], "class_id": c["id"], "section": sn, "subject_id": sj["id"]})
    busy = set()
    for c, sn, k in sections:
        for di, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]):
            for pi, p in enumerate([1, 2, 4, 5, 7, 8]):
                sj = subj[(pi + di + k) % 6]; tid = asg[(c["id"], sn, sj["id"])]
                if (tid, day, p) in busy: continue
                busy.add((tid, day, p))
                await db.timetable.insert_one({"id": new_id(), "class_id": c["id"], "section": sn, "day": day, "period_no": p, "subject_id": sj["id"], "teacher_id": tid, "room": f"{c['grade_level']}0{1 if sn == 'A' else 2}", **D})
    students, parents, n = [], [], 0
    for c, sn, k in sections:
        for i in range(6):
            n += 1; female = (n % 2 == 0)
            first = (FIRST_F if female else FIRST_M)[(n * 7) % 15]; last = LAST[(n * 3 + k) % 15]
            adm_month = ["2025-04", "2025-06", "2026-01", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"][n % 10]
            pid = new_id()
            st = {"id": new_id(), "admission_no": f"ADM{adm_month[:4]}{str(n).zfill(4)}", "name": f"{first} {last}", "photo_file_id": None,
                  "dob": f"{2026 - c['grade_level'] - 6}-{str(1 + n % 12).zfill(2)}-{str(1 + n % 27).zfill(2)}", "gender": "Female" if female else "Male",
                  "class_id": c["id"], "class_name": c["name"], "section": sn, "academic_year": yr, "admission_date": f"{adm_month}-{str(1 + n % 25).zfill(2)}",
                  "blood_group": ["A+", "B+", "O+", "AB+", "O-"][n % 5], "address": f"{10 + n}, MG Road, Bengaluru", "phone": None, "email": None,
                  "guardian_name": f"{['Rajesh', 'Suresh', 'Priya', 'Lakshmi', 'Mahesh'][n % 5]} {last}", "guardian_phone": f"99000{20000 + n}",
                  "guardian_email": f"parent{n}@eduprime.demo", "emergency_contact": f"98860{30000 + n}", "previous_school": None, "status": "active", "parent_ids": [pid],
                  "history": [{"date": now_iso(), "event": "admitted", "class_name": c["name"], "section": sn, "academic_year": yr}]}
            students.append(st)
            parents.append({"id": pid, "name": st["guardian_name"], "email": st["guardian_email"], "phone": st["guardian_phone"], "address": st["address"], "occupation": "Professional", "relation": "Parent", "student_ids": [st["id"]]})
    for st in students: await ins("students", st)
    for p in parents: await ins("parents", p)
    for y in ("2025", "2026"):
        await db.counters.update_one({"id": f"adm{y}"}, {"$set": {"v": len(students)}}, upsert=True)
    # attendance: last 25 days (Mon-Sat), today only for first 3 grades
    d = t - timedelta(days=30)
    while d <= t:
        if d.weekday() < 6:
            docs = []
            for st in students:
                if d == t and st["class_name"] not in ("Grade 6", "Grade 7", "Grade 8"): continue
                r = random.random(); bias = 0.15 if st["admission_no"].endswith(("05", "17")) else 0
                status = "absent" if r < 0.06 + bias else "late" if r < 0.1 + bias else "excused" if r < 0.12 + bias else "present"
                docs.append({"id": new_id(), "date": d.isoformat(), "student_id": st["id"], "class_id": st["class_id"], "section": st["section"], "status": status, "remark": "", "marked_by": "seed", "created_at": now_iso(), **D})
            if docs: await db.attendance.insert_many(docs)
        d += timedelta(days=1)
    for tch in teachers:
        await db.staff_attendance.insert_one({"id": new_id(), "date": (t - timedelta(days=1)).isoformat(), "teacher_id": tch["id"], "status": "present", **D})
    # exams
    for c in classes:
        mid = {"id": new_id(), "name": "Mid-Term Examination", "type": "Mid-Term", "academic_year": yr, "term": "Term 1", "class_id": c["id"], "sections": ["A", "B"],
               "subjects": [{"subject_id": sj["id"], "date": f"2026-09-{str(14 + j).zfill(2)}", "max_marks": 50 if sj["code"] == "CS" else 100, "pass_marks": 17 if sj["code"] == "CS" else 35} for j, sj in enumerate(subj)],
               "weight": 40, "status": "published", "published_at": now_iso()}
        await ins("exams", mid)
        await ins("exams", {"id": new_id(), "name": "Unit Test 2", "type": "Unit Test", "academic_year": yr, "term": "Term 2", "class_id": c["id"], "sections": ["A", "B"],
                            "subjects": [{"subject_id": sj["id"], "date": f"2026-11-{str(16 + j).zfill(2)}", "max_marks": 25, "pass_marks": 9} for j, sj in enumerate(subj[:4])], "weight": 10, "status": "draft"})
        for st in [s for s in students if s["class_id"] == c["id"]]:
            base = random.uniform(0.45, 0.95)
            for es in mid["subjects"]:
                absent = random.random() < 0.02
                mk = None if absent else round(min(es["max_marks"], max(0, es["max_marks"] * (base + random.uniform(-0.12, 0.1)))))
                await db.marks.insert_one({"id": new_id(), "exam_id": mid["id"], "student_id": st["id"], "subject_id": es["subject_id"], "marks": mk, "absent": absent, "status": "submitted", "entered_by": "seed", **D})
            await db.exam_remarks.insert_one({"exam_id": mid["id"], "student_id": st["id"], "remark": "Consistent effort. Keep it up!" if base > 0.7 else "Needs more practice in core subjects.", "by": "Class Teacher", **D})
    # fees
    fs = [("Tuition Fee - Term 1", "Tuition", 25000, "2026-07-15", "Installment 1"), ("Examination Fee", "Examination", 1500, "2026-08-31", "Full"),
          ("Tuition Fee - Term 2", "Tuition", 25000, "2026-11-15", "Installment 2"), ("Transport Fee - Annual", "Transport", 8000, "2026-08-15", "Full")]
    fsd = []
    for n_, ft, amt, due, ins_ in fs:
        x = {"id": new_id(), "name": n_, "fee_type": ft, "class_id": "all", "academic_year": yr, "amount": amt, "due_date": due, "installment": ins_}; fsd.append(x); await ins("fee_structures", x)
    inv_n = rc_n = 0
    for i, st in enumerate(students):
        for f in fsd[:3]:
            inv_n += 1; total = f["amount"]
            disc = 2500 if (i % 13 == 0 and f["fee_type"] == "Tuition") else 0
            total -= disc
            roll = random.random() if f["due_date"] < t.isoformat() else 2
            paid = total if roll < 0.7 else (round(total / 2) if roll < 0.85 else 0)
            if f is fsd[2]: paid = total if i % 7 == 0 else 0
            status = "paid" if paid >= total else "partial" if paid else "unpaid"
            inv = {"id": new_id(), "invoice_no": f"INV2026-{str(inv_n).zfill(5)}", "student_id": st["id"], "student_name": st["name"], "admission_no": st["admission_no"], "class_id": st["class_id"],
                   "class_name": st["class_name"], "section": st["section"], "items": [{"name": f["name"], "amount": f["amount"]}], "subtotal": f["amount"], "discount": disc,
                   "discount_reason": "Merit scholarship" if disc else "", "late_fee": 0, "total": total, "paid": paid, "balance": total - paid, "due_date": f["due_date"], "status": status,
                   "academic_year": yr, "structure_id": f["id"], "created_by": "seed", "created_at": f"2026-0{6 if f is fsd[0] else 7}-01T09:00:00+00:00"}
            await ins("invoices", inv)
            if paid:
                rc_n += 1; pd = (Date.fromisoformat(f["due_date"]) - timedelta(days=random.randint(1, 20))).isoformat()
                if pd > t.isoformat(): pd = t.isoformat()
                await ins("payments", {"id": new_id(), "receipt_no": f"RCPT2026-{str(rc_n).zfill(6)}", "invoice_id": inv["id"], "invoice_no": inv["invoice_no"], "student_id": st["id"],
                                       "student_name": st["name"], "admission_no": st["admission_no"], "class_id": st["class_id"], "class_name": st["class_name"], "amount": paid,
                                       "method": random.choice(["Cash", "Bank Transfer", "UPI", "Card"]), "reference": f"TXN{random.randint(100000, 999999)}", "date": pd, "status": "success", "recorded_by": "seed", "created_at": f"{pd}T10:00:00+00:00"})
    await db.counters.update_one({"id": "inv"}, {"$set": {"v": inv_n}}, upsert=True)
    await db.counters.update_one({"id": "rcpt2026"}, {"$set": {"v": rc_n}}, upsert=True)
    # homework
    for (c, sn, k) in sections[:6]:
        for j, sj in enumerate(subj[:3]):
            hid = new_id(); due = (t + timedelta(days=j * 3 - 2)).isoformat()
            await ins("homework", {"id": hid, "title": f"{sj['name']} worksheet {j + 1}", "description": f"Complete the {sj['name'].lower()} practice worksheet from chapter {j + 3}.", "instructions": "Show all working. Submit as text or upload a PDF/photo.",
                                   "class_id": c["id"], "section": sn, "subject_id": sj["id"], "teacher_id": asg[(c["id"], sn, sj["id"])], "due_date": due, "attachments": [], "status": "published", "max_score": 10})
            for st in [s for s in students if s["class_id"] == c["id"] and s["section"] == sn][:3 - j]:
                await db.submissions.insert_one({"id": new_id(), "homework_id": hid, "student_id": st["id"], "student_name": st["name"], "admission_no": st["admission_no"], "text": "Completed all questions.", "files": [],
                                                 "submitted_at": now_iso(), "late": False, "status": "graded" if j == 0 else "submitted", "grade": 8 if j == 0 else None, "feedback": "Good work" if j == 0 else "", **D})
    # library
    books = [("Wings of Fire", "A.P.J. Abdul Kalam", "9788173711466", "Biography"), ("The Story of My Experiments with Truth", "M.K. Gandhi", "9780807059098", "Biography"),
             ("Malgudi Days", "R.K. Narayan", "9780143039655", "Fiction"), ("The Jungle Book", "Rudyard Kipling", "9780141325293", "Fiction"), ("A Brief History of Time", "Stephen Hawking", "9780553380163", "Science"),
             ("NCERT Mathematics Class 10", "NCERT", "9788174506375", "Textbook"), ("Concise Physics", "Selina", "9789388594123", "Textbook"), ("Panchatantra", "Vishnu Sharma", "9788129103441", "Fiction"),
             ("The Discovery of India", "Jawaharlal Nehru", "9780143031031", "History"), ("Harry Potter and the Philosopher's Stone", "J.K. Rowling", "9780747532699", "Fiction")]
    bk = []
    for i, (ti, au, isbn, cat) in enumerate(books):
        x = {"id": new_id(), "accession_no": f"ACC{str(i + 1).zfill(5)}", "title": ti, "author": au, "isbn": isbn, "category": cat, "publisher": "", "total_copies": 3, "available_copies": 3, "shelf": f"S{i % 4 + 1}"}
        bk.append(x)
    for i, st in enumerate(students[:6]):
        b = bk[i]; b["available_copies"] -= 1
        due = (t - timedelta(days=3)).isoformat() if i < 2 else (t + timedelta(days=7)).isoformat()
        await db.book_issues.insert_one({"id": new_id(), "book_id": b["id"], "book_title": b["title"], "accession_no": b["accession_no"], "borrower_type": "student", "borrower_id": st["id"], "borrower_name": st["name"],
                                         "issue_date": (Date.fromisoformat(due) - timedelta(days=14)).isoformat(), "due_date": due, "status": "issued", "fine": 0, "created_at": now_iso(), **D})
    for b in bk: await ins("books", b)
    await db.counters.update_one({"id": "acc"}, {"$set": {"v": len(bk)}}, upsert=True)
    # transport
    vs = []
    for i, (reg, cap, drv) in enumerate([("KA-01-AB-1234", 40, "Ramesh Kumar"), ("KA-01-CD-5678", 32, "Mohan Lal"), ("KA-05-EF-9012", 24, "Basavaraj")]):
        v = {"id": new_id(), "reg_no": reg, "model": "Tata Starbus", "capacity": cap, "driver_name": drv, "driver_phone": f"97400{40000 + i}", "attendant_name": "Lakshmamma", "attendant_phone": f"97400{50000 + i}"}
        vs.append(v); await ins("vehicles", v)
    rts = []
    for i, (nm, stops) in enumerate([("Route 1 - Indiranagar", ["100 Feet Road", "CMH Road", "Domlur"]), ("Route 2 - Jayanagar", ["4th Block", "South End Circle", "Lalbagh West Gate"]), ("Route 3 - Whitefield", ["ITPL", "Hope Farm", "Marathahalli"])]):
        r = {"id": new_id(), "name": nm, "vehicle_id": vs[i]["id"], "stops": [{"name": s_, "time": f"07:{10 + j * 12}"} for j, s_ in enumerate(stops)], "fee": 8000}
        rts.append(r); await ins("routes", r)
    for i, st in enumerate(students[::4]):
        r = rts[i % 3]
        await db.students.update_one({"id": st["id"]}, {"$set": {"transport": {"route_id": r["id"], "route_name": r["name"], "stop": r["stops"][i % 3]["name"]}}})
    # events, announcements, leaves
    for ti, ty, a, b, desc in [("Diwali Holidays", "holiday", "2026-11-07", "2026-11-11", "School closed for Diwali."), ("Parent-Teacher Meeting", "ptm", "2026-10-31", "2026-10-31", "Term 1 progress discussion, 9 AM – 1 PM."),
                               ("Annual Sports Day", "event", "2026-12-05", "2026-12-05", "Inter-house athletics at the main ground."), ("Children's Day Celebration", "event", "2026-11-14", "2026-11-14", "Cultural programme by teachers."),
                               ("Gandhi Jayanti", "holiday", "2026-10-02", "2026-10-02", "National holiday.")]:
        await ins("events", {"id": new_id(), "title": ti, "type": ty, "start_date": a, "end_date": b, "description": desc, "class_id": None})
    for ti, body, roles in [("Welcome to the 2026-27 academic year", "We are excited to welcome all students and families. Please review the updated school handbook.", []),
                            ("Unit Test 2 schedule released", "Unit Test 2 begins on 16 November. Timetables are available in the Examinations section.", ["student", "parent", "teacher"]),
                            ("Staff meeting on Saturday", "All teaching staff are requested to attend the curriculum review meeting at 11 AM.", ["teacher"])]:
        await ins("announcements", {"id": new_id(), "title": ti, "body": body, "roles": roles, "class_ids": [], "category": "General", "pinned": False, "created_by": "seed", "author": "Principal's Office"})
    return {"students": students, "teachers": teachers, "parents": parents}

async def seed_demo_logins(data=None):
    if await db.users.find_one({"email": "teacher@eduprime.demo"}): return
    st = await db.students.find_one({"demo": True, "admission_no": {"$regex": "0001$"}}, {"_id": 0})
    if not st: return
    par = await db.parents.find_one({"id": st["parent_ids"][0]}, {"_id": 0})
    cls = await db.classes.find_one({"id": st["class_id"]})
    tch = await db.teachers.find_one({"id": cls["sections"][0]["class_teacher_id"]}, {"_id": 0})
    for email, name, role, pw, pid in [("teacher@eduprime.demo", tch["name"], "teacher", "Teacher@123", tch["id"]), ("student@eduprime.demo", st["name"], "student", "Student@123", st["id"]),
                                       ("parent@eduprime.demo", par["name"], "parent", "Parent@123", par["id"])]:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({"id": new_id(), "email": email, "name": name, "role": role, "password_hash": hash_password(pw), "profile_id": pid, "active": True, "pv": 0, "created_at": now_iso(), "demo": True})
    await db.leaves.insert_one({"id": new_id(), "leave_type": "Sick", "from_date": (Date.fromisoformat(await today()) + timedelta(days=3)).isoformat(), "to_date": (Date.fromisoformat(await today()) + timedelta(days=4)).isoformat(),
                                "reason": "Medical appointment", "student_id": None, "requester_id": (await db.users.find_one({"email": "teacher@eduprime.demo"}))["id"], "requester_name": tch["name"],
                                "requester_role": "teacher", "kind": "staff", "status": "pending", "created_at": now_iso(), **D})
