# School Management System - backend regression suite (auth, RBAC, people, academics, exams, fees, misc)
import os, uuid, pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
CREDS = {
    "admin": ("meetup2456bro@gmail.com", "Admin@12345"),
    "teacher": ("teacher@eduprime.demo", "Teacher@123"),
    "student": ("student@eduprime.demo", "Student@123"),
    "parent": ("parent@eduprime.demo", "Parent@123"),
}
TODAY = "2026-10-24"
TAG = "TEST_" + uuid.uuid4().hex[:6]
STATE = {}
import random
LD = f"20{random.randint(30,89)}-0{random.randint(1,9)}-1{random.randint(0,9)}"


def _login(role):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    e, p = CREDS[role]
    r = s.post(f"{API}/auth/login", json={"email": e, "password": p, "remember": True})
    if r.status_code != 200:
        pytest.skip(f"login {role} failed {r.status_code} {r.text}")
    s.me = r.json()
    return s


@pytest.fixture(scope="session")
def admin(): return _login("admin")
@pytest.fixture(scope="session")
def teacher(): return _login("teacher")
@pytest.fixture(scope="session")
def student(): return _login("student")
@pytest.fixture(scope="session")
def parent(): return _login("parent")


@pytest.fixture(scope="session")
def ctx(admin):
    classes = admin.get(f"{API}/classes", params={"page_size": 100}).json()["items"]
    subs = admin.get(f"{API}/subjects", params={"page_size": 100}).json()["items"]
    c = {x["name"]: x for x in classes}
    s = {x["code"]: x for x in subs}
    return {"g6": c["Grade 6"], "g9": c["Grade 9"], "g10": c["Grade 10"], "ENG": s["ENG"], "MATH": s["MATH"], "SCI": s["SCI"]}


# ---------- auth ----------
class TestAuth:
    def test_login_cookies_httponly(self):
        r = requests.post(f"{API}/auth/login", json={"email": CREDS["admin"][0], "password": CREDS["admin"][1]})
        assert r.status_code == 200
        sc = r.headers.get("set-cookie", "")
        assert "access_token" in sc and "refresh_token" in sc
        assert "httponly" in sc.lower()
        assert r.json()["role"] == "admin" and "password_hash" not in r.json()

    def test_invalid_login(self):
        r = requests.post(f"{API}/auth/login", json={"email": f"{TAG.lower()}@x.com", "password": "Wrong123"})
        assert r.status_code == 401

    def test_me_and_refresh(self, teacher):
        r = teacher.get(f"{API}/auth/me")
        assert r.status_code == 200 and r.json()["role"] == "teacher"
        assert teacher.post(f"{API}/auth/refresh").status_code == 200

    def test_unauth(self):
        assert requests.get(f"{API}/students").status_code == 401

    def test_csrf_origin_guard(self, admin):
        r = admin.post(f"{API}/auth/refresh", headers={"Origin": "https://evil.example.com"})
        assert r.status_code == 403


# ---------- RBAC ----------
class TestRBAC:
    def test_teacher_invoices_403(self, teacher):
        assert teacher.get(f"{API}/invoices").status_code == 403

    def test_parent_students_only_child(self, parent):
        d = parent.get(f"{API}/students").json()
        ids = parent.me["profile"]["student_ids"]
        assert d["total"] >= 1 and all(x["id"] in ids for x in d["items"])

    def test_student_cannot_post_attendance(self, student, ctx):
        r = student.post(f"{API}/attendance/sheet", json={"date": TODAY, "class_id": ctx["g6"]["id"], "section": "A", "entries": []})
        assert r.status_code == 403

    def test_teacher_attendance_unassigned_section(self, teacher, ctx):
        r = teacher.post(f"{API}/attendance/sheet", json={"date": TODAY, "class_id": ctx["g10"]["id"], "section": "B", "entries": []})
        assert r.status_code == 403

    def test_teacher_settings_403(self, teacher):
        assert teacher.put(f"{API}/settings", json={"tagline": "x"}).status_code == 403

    def test_teacher_cannot_archive_others_announcement(self, admin, teacher):
        a = admin.post(f"{API}/announcements", json={"title": f"{TAG} ann admin", "body": "hello", "roles": ["teacher"]}).json()
        STATE["ann_id"] = a["id"]
        r = teacher.delete(f"{API}/announcements/{a['id']}")
        assert r.status_code == 403, f"teacher archived admin announcement: {r.status_code}"


# ---------- people ----------
class TestPeople:
    def test_student_crud(self, admin, ctx):
        body = {"name": f"{TAG} Student", "dob": "2014-05-05", "gender": "Male", "class_id": ctx["g9"]["id"], "section": "A",
                "academic_year": "2026-27", "admission_date": TODAY, "guardian_name": "G", "guardian_phone": "9999999999"}
        r = admin.post(f"{API}/students", json=body)
        assert r.status_code == 200, r.text
        st = r.json(); STATE["stu"] = st
        assert st["admission_no"].startswith("ADM2026")
        body["name"] = f"{TAG} Student Edited"
        r = admin.put(f"{API}/students/{st['id']}", json=body)
        assert r.status_code == 200 and r.json()["name"] == body["name"] and r.json()["admission_no"] == st["admission_no"]
        d = admin.get(f"{API}/students", params={"q": TAG, "class_id": ctx["g9"]["id"]}).json()
        assert any(x["id"] == st["id"] for x in d["items"])
        assert admin.delete(f"{API}/students/{st['id']}").status_code == 200
        d = admin.get(f"{API}/students", params={"q": TAG}).json()
        assert not any(x["id"] == st["id"] for x in d["items"])
        assert admin.post(f"{API}/students/{st['id']}/restore").status_code == 200
        assert admin.get(f"{API}/students/{st['id']}").json()["archived"] is False

    def test_student_csv_export(self, admin):
        r = admin.get(f"{API}/students", params={"format": "csv"})
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"] and "Admission" in r.text.splitlines()[0]

    def test_teacher_parent_create_login(self, admin):
        t = admin.post(f"{API}/teachers", json={"name": f"{TAG} Teacher", "email": f"{TAG.lower()}.t@example.com", "phone": "9876543210", "joining_date": TODAY})
        assert t.status_code == 200, t.text
        STATE["tch"] = t.json(); assert t.json()["employee_id"].startswith("EMP")
        p = admin.post(f"{API}/parents", json={"name": f"{TAG} Parent", "email": f"{TAG.lower()}.p@example.com", "phone": "9876543211", "student_ids": [STATE["stu"]["id"]]})
        assert p.status_code == 200, p.text
        STATE["par"] = p.json()
        assert p.json()["id"] in admin.get(f"{API}/students/{STATE['stu']['id']}").json()["parent_ids"]
        r = admin.post(f"{API}/teachers/{t.json()['id']}/create-login", json={"password": "TestPass123"})
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "teacher"


# ---------- classes ----------
class TestClasses:
    def test_create_and_duplicate(self, admin):
        body = {"name": f"{TAG} Class", "grade_level": 12, "sections": [{"name": "a", "capacity": 2}, {"name": "b", "capacity": 2}]}
        r = admin.post(f"{API}/classes", json=body)
        assert r.status_code == 200 and r.json()["sections"][0]["name"] == "A"
        STATE["cls"] = r.json()
        assert admin.post(f"{API}/classes", json=body).status_code == 409


# ---------- attendance ----------
class TestAttendance:
    def test_mark_g9a_and_summary(self, admin, ctx):
        cid = ctx["g9"]["id"]
        sh = admin.get(f"{API}/attendance/sheet", params={"date": TODAY, "class_id": cid, "section": "A"}).json()
        ents = [{"student_id": s["id"], "status": s["status"] or "present", "remark": s.get("remark", "")} for s in sh["students"]]
        r = admin.post(f"{API}/attendance/sheet", json={"date": TODAY, "class_id": cid, "section": "A", "entries": ents})
        assert r.status_code == 200, r.text
        sm = admin.get(f"{API}/attendance/summary", params={"class_id": cid, "section": "A"})
        assert sm.status_code == 200
        STATE["att_summary"] = str(sm.json())[:300]

    def test_future_date_rejected(self, admin, ctx):
        r = admin.post(f"{API}/attendance/sheet", json={"date": "2026-10-30", "class_id": ctx["g9"]["id"], "section": "A", "entries": []})
        assert r.status_code == 422


# ---------- timetable ----------
class TestTimetable:
    def test_assign_and_conflict(self, admin, ctx):
        tid = STATE["tch"]["id"]
        # find a free slot in Grade 10-A
        cid = STATE["cls"]["id"]
        d, p = "Mon", 1
        # iteration 2: timetable requires teacher assignment for subject/section
        for sec in ("A", "B"):
            a = admin.post(f"{API}/assignments", json={"teacher_id": tid, "class_id": cid, "section": sec, "subject_id": ctx["SCI"]["id"]})
            assert a.status_code == 200, a.text
        r = admin.post(f"{API}/timetable", json={"class_id": cid, "section": "A", "day": d, "period_no": p, "subject_id": ctx["SCI"]["id"], "teacher_id": tid})
        assert r.status_code == 200, r.text
        STATE["slot"] = r.json()["id"]
        r2 = admin.post(f"{API}/timetable", json={"class_id": cid, "section": "B", "day": d, "period_no": p, "subject_id": ctx["SCI"]["id"], "teacher_id": tid})
        assert r2.status_code == 409 and "conflict" in r2.json()["detail"].lower()
        admin.delete(f"{API}/timetable/{STATE['slot']}")


# ---------- exams ----------
class TestExams:
    def test_exam_flow(self, admin, teacher, student, ctx):
        g6 = ctx["g6"]["id"]; eng = ctx["ENG"]["id"]
        r = admin.post(f"{API}/exams", json={"name": f"{TAG} Exam", "type": "Unit Test", "academic_year": "2026-27", "term": "Term 1", "class_id": g6,
                                             "sections": ["A"], "subjects": [{"subject_id": eng, "date": TODAY, "max_marks": 50, "pass_marks": 20}]})
        assert r.status_code == 200, r.text
        eid = r.json()["id"]; STATE["exam"] = eid
        sid = student.me["profile_id"]
        # student should not see draft
        assert all(x["exam_id"] != eid for x in student.get(f"{API}/results/student/{sid}").json())
        assert student.get(f"{API}/report-card/{eid}/{sid}").status_code == 403
        mk = teacher.get(f"{API}/exams/{eid}/marks", params={"section": "A", "subject_id": eng})
        assert mk.status_code == 200, mk.text
        studs = mk.json()["students"]
        bad = teacher.post(f"{API}/exams/{eid}/marks", json={"section": "A", "subject_id": eng, "entries": [{"student_id": studs[0]["id"], "marks": 51}]})
        assert bad.status_code == 422
        ents = [{"student_id": s["id"], "marks": 40} for s in studs]
        assert teacher.post(f"{API}/exams/{eid}/marks", json={"section": "A", "subject_id": eng, "entries": ents}).json()["status"] == "draft"
        assert teacher.post(f"{API}/exams/{eid}/marks", json={"section": "A", "subject_id": eng, "entries": ents, "submit": True}).json()["status"] == "submitted"
        assert admin.post(f"{API}/exams/{eid}/publish").status_code == 200
        res = admin.get(f"{API}/exams/{eid}/results").json()
        assert res["results"][0]["percentage"] == 80.0 and res["results"][0]["result"] == "PASS"
        rc = student.get(f"{API}/report-card/{eid}/{sid}")
        assert rc.status_code == 200 and rc.json()["grade"] == "A"
        assert any(x["exam_id"] == eid for x in student.get(f"{API}/results/student/{sid}").json())

    def test_teacher_marks_unassigned_subject_403(self, teacher, admin, ctx):
        eid = STATE["exam"]
        r = teacher.get(f"{API}/exams/{eid}/marks", params={"section": "A", "subject_id": ctx["MATH"]["id"]})
        assert r.status_code in (403, 422)
        # teacher in published exam cannot change marks
        r = teacher.post(f"{API}/exams/{eid}/marks", json={"section": "A", "subject_id": ctx["ENG"]["id"], "entries": []})
        assert r.status_code == 403
        admin.post(f"{API}/exams/{eid}/publish", params={"publish": "false"})
        admin.delete(f"{API}/exams/{eid}")


# ---------- fees ----------
class TestFees:
    def test_fee_flow(self, admin):
        cls = STATE["cls"]
        st = admin.post(f"{API}/students", json={"name": f"{TAG} FeeStu", "dob": "2010-01-01", "gender": "Female", "class_id": cls["id"], "section": "A",
                                                 "academic_year": "2026-27", "admission_date": TODAY, "guardian_name": "G", "guardian_phone": "9999999999"}).json()
        STATE["fee_stu"] = st
        fs = admin.post(f"{API}/fee-structures", json={"name": f"{TAG} Tuition", "fee_type": "Tuition", "class_id": cls["id"], "academic_year": "2026-27", "amount": 1000, "due_date": "2026-11-30"})
        assert fs.status_code == 200, fs.text
        STATE["fs"] = fs.json()["id"]
        g = admin.post(f"{API}/invoices/generate", json={"structure_id": fs.json()["id"]}).json()
        assert g == {"created": 1, "skipped_existing": 0}
        assert admin.post(f"{API}/invoices/generate", json={"structure_id": fs.json()["id"]}).json() == {"created": 0, "skipped_existing": 1}
        inv = admin.get(f"{API}/invoices", params={"student_id": st["id"]}).json()["items"][0]
        STATE["inv"] = inv["id"]
        p = admin.post(f"{API}/payments", json={"invoice_id": inv["id"], "amount": 400, "method": "Cash", "date": TODAY})
        assert p.status_code == 200, p.text
        STATE["pay"] = p.json()["id"]
        i2 = admin.get(f"{API}/invoices/{inv['id']}").json()
        assert i2["status"] == "partial" and i2["balance"] == 600
        assert admin.post(f"{API}/payments", json={"invoice_id": inv["id"], "amount": 700, "method": "Cash", "date": TODAY}).status_code == 409
        rc = admin.get(f"{API}/payments/{p.json()['id']}/receipt")
        assert rc.status_code == 200 and rc.json()["payment"]["receipt_no"].startswith("RCPT2026-")

    def test_parent_own_invoices_and_online(self, parent):
        ids = parent.me["profile"]["student_ids"]
        d = parent.get(f"{API}/invoices", params={"page_size": 100}).json()
        assert all(x["student_id"] in ids for x in d["items"])
        unpaid = next((x for x in d["items"] if x["status"] in ("unpaid", "partial")), None)
        if unpaid:
            r = parent.post(f"{API}/payments/razorpay/order", json={"invoice_id": unpaid["id"], "origin_url": BASE_URL})
            assert r.status_code == 503 and "not configured" in r.text.lower()

    def test_refund_void_cleanup(self, admin):
        assert admin.post(f"{API}/payments/{STATE['pay']}/refund").status_code == 200
        assert admin.get(f"{API}/invoices/{STATE['inv']}").json()["status"] == "unpaid"
        assert admin.post(f"{API}/invoices/{STATE['inv']}/adjust", json={"void": True}).status_code == 200


# ---------- homework ----------
class TestHomework:
    def test_hw_flow(self, admin, teacher, student, ctx):
        r = teacher.post(f"{API}/homework-items", json={"title": f"{TAG} HW", "class_id": ctx["g6"]["id"], "section": "A", "subject_id": ctx["ENG"]["id"], "due_date": "2026-11-05", "max_score": 10})
        assert r.status_code == 200, r.text
        hid = r.json()["id"]; STATE["hw"] = hid
        s = student.post(f"{API}/homework/{hid}/submit", json={"text": "my answer"})
        assert s.status_code == 200, s.text
        subs = teacher.get(f"{API}/homework/{hid}/submissions").json()
        sub = next(x["submission"] for x in subs["students"] if x["id"] == student.me["profile_id"])
        assert teacher.put(f"{API}/submissions/{sub['id']}/grade", json={"grade": 11}).status_code == 422
        assert teacher.put(f"{API}/submissions/{sub['id']}/grade", json={"grade": 8, "feedback": "good"}).status_code == 200
        hw = next(h for h in student.get(f"{API}/homework").json()["items"] if h["id"] == hid)
        assert hw["my_submission"]["grade"] == 8
        admin.delete(f"{API}/homework-items/{hid}")

    def test_archived_homework_hidden(self, student, teacher):
        # regression: archived homework must not be listed
        hid = STATE["hw"]
        assert all(h["id"] != hid for h in student.get(f"{API}/homework").json()["items"]), "archived homework visible to student"
        assert all(h["id"] != hid for h in teacher.get(f"{API}/homework").json()["items"]), "archived homework visible to teacher"


class TestArchivedStudent:
    def test_archived_student_not_in_attendance_sheet(self, admin, ctx):
        # regression: archived students must not appear in attendance sheet
        body = {"name": f"{TAG} ArchStu", "dob": "2014-05-05", "gender": "Male", "class_id": ctx["g9"]["id"], "section": "B",
                "academic_year": "2026-27", "admission_date": TODAY, "guardian_name": "G", "guardian_phone": "9999999999"}
        st = admin.post(f"{API}/students", json=body).json()
        admin.delete(f"{API}/students/{st['id']}")
        sh = admin.get(f"{API}/attendance/sheet", params={"date": TODAY, "class_id": ctx["g9"]["id"], "section": "B"}).json()
        assert all(s["id"] != st["id"] for s in sh["students"]), "archived student listed in attendance sheet"


# ---------- library/transport/leave/announcements ----------
class TestMisc:
    def test_library(self, admin):
        b = admin.post(f"{API}/books", json={"title": f"{TAG} Book", "author": "A", "total_copies": 1})
        assert b.status_code == 200, b.text
        STATE["book"] = b.json()["id"]
        i = admin.post(f"{API}/library/issue", json={"book_id": b.json()["id"], "borrower_type": "student", "borrower_id": STATE["stu"]["id"]})
        assert i.status_code == 200, i.text
        assert admin.post(f"{API}/library/issue", json={"book_id": b.json()["id"], "borrower_type": "student", "borrower_id": STATE["fee_stu"]["id"]}).status_code == 409
        rt = admin.post(f"{API}/library/issues/{i.json()['id']}/return")
        assert rt.status_code == 200, rt.text
        assert admin.get(f"{API}/books/{b.json()['id']}").json()["available_copies"] == 1

    def test_transport_capacity(self, admin):
        v = admin.post(f"{API}/vehicles", json={"reg_no": f"{TAG[:12]}", "capacity": 1}).json()
        r = admin.post(f"{API}/routes", json={"name": f"{TAG} Route", "vehicle_id": v["id"], "stops": [{"name": "Stop1"}]}).json()
        STATE["veh"], STATE["route"] = v["id"], r["id"]
        assert admin.post(f"{API}/transport/assign", json={"student_id": STATE["stu"]["id"], "route_id": r["id"], "stop": "Stop1"}).status_code == 200
        x = admin.post(f"{API}/transport/assign", json={"student_id": STATE["fee_stu"]["id"], "route_id": r["id"], "stop": "Stop1"})
        assert x.status_code == 409
        admin.post(f"{API}/transport/assign", json={"student_id": STATE["stu"]["id"], "route_id": None})

    def test_leave_flow(self, admin, teacher):
        r = teacher.post(f"{API}/leaves", json={"leave_type": "Casual", "from_date": LD, "to_date": LD, "reason": f"{TAG} leave"})
        assert r.status_code == 200, r.text
        lid = r.json()["id"]
        assert admin.put(f"{API}/leaves/{lid}/review", json={"status": "approved"}).status_code == 200
        n = teacher.get(f"{API}/notifications").json()
        items = n if isinstance(n, list) else n.get("items", [])
        assert any("approved" in x["title"].lower() for x in items)

    def test_announcement_notifies(self, teacher):
        n = teacher.get(f"{API}/notifications").json()
        items = n if isinstance(n, list) else n.get("items", [])
        assert any(TAG in x["title"] for x in items)


# ---------- reports/audit/settings/dashboard ----------
class TestAdmin:
    def test_reports(self, admin):
        keys = [x["key"] for x in admin.get(f"{API}/reports").json()]
        fails = []
        ex = admin.get(f"{API}/exams").json()["items"]
        for k in keys:
            prm = {"exam_id": ex[0]["id"], "subject_id": ex[0]["subjects"][0]["subject_id"]} if k in ("exam_performance", "subject_marks") and ex else {}
            r = admin.get(f"{API}/reports/{k}", params=prm)
            c = admin.get(f"{API}/reports/{k}", params={**prm, "format": "csv"})
            if r.status_code != 200 or c.status_code != 200: fails.append((k, r.status_code, c.status_code))
        assert not fails, fails

    def test_audit_logs(self, admin):
        d = admin.get(f"{API}/audit-logs").json()
        assert d["total"] > 0 and "action" in d["items"][0]

    def test_settings_save(self, admin):
        old = admin.get(f"{API}/settings").json()["tagline"]
        r = admin.put(f"{API}/settings", json={"tagline": f"{TAG}"})
        assert r.status_code == 200 and r.json()["tagline"] == TAG
        admin.put(f"{API}/settings", json={"tagline": old})

    def test_dashboards(self, admin, teacher, student, parent):
        for s in (admin, teacher, student, parent):
            assert s.get(f"{API}/dashboard").status_code == 200

    def test_cleanup(self, admin):
        for path, key in (("students", "stu"), ("students", "fee_stu"), ("teachers", "tch"), ("parents", "par"), ("books", "book"), ("routes", "route"),
                          ("vehicles", "veh"), ("fee-structures", "fs"), ("announcements", "ann_id")):
            v = STATE.get(key)
            if v: admin.delete(f"{API}/{path}/{v['id'] if isinstance(v, dict) else v}")
        if STATE.get("cls"): admin.delete(f"{API}/classes/{STATE['cls']['id']}")
