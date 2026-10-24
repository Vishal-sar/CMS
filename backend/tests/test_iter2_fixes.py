# Iteration 2 regression: ownership/scope on archive/restore/update, archived students exclusion, homework archive,
# timetable validation, report card section check, mark clearing, settings type validation, smoke
import os, uuid, pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
CREDS = {
    "admin": ("meetup2456bro@gmail.com", "Admin@12345"),
    "teacher": ("teacher@eduprime.demo", "Teacher@123"),
    "student": ("student@eduprime.demo", "Student@123"),
    "parent": ("parent@eduprime.demo", "Parent@123"),
}
TAG = "TEST_" + uuid.uuid4().hex[:6]
S = {}


def _login(role):
    s = requests.Session()
    e, p = CREDS[role]
    r = s.post(f"{API}/auth/login", json={"email": e, "password": p, "remember": True})
    if r.status_code != 200:
        pytest.skip(f"login {role} failed {r.status_code} {r.text}")
    s.me = r.json()
    return s


@pytest.fixture(scope="module")
def admin(): return _login("admin")
@pytest.fixture(scope="module")
def teacher(): return _login("teacher")
@pytest.fixture(scope="module")
def student(): return _login("student")
@pytest.fixture(scope="module")
def parent(): return _login("parent")


@pytest.fixture(scope="module")
def ctx(admin):
    classes = admin.get(f"{API}/classes", params={"page_size": 100}).json()["items"]
    subs = admin.get(f"{API}/subjects", params={"page_size": 100}).json()["items"]
    c = {x["name"]: x for x in classes}; s = {x["code"]: x for x in subs}
    asg = admin.get(f"{API}/assignments", params={"page_size": 500})
    return {"g6": c["Grade 6"], "g9": c["Grade 9"], "ENG": s["ENG"], "MATH": s["MATH"], "SCI": s["SCI"],
            "today": admin.get(f"{API}/dashboard").json().get("today") or None, "asg": asg.json() if asg.status_code == 200 else None}


def _stu(admin, ctx, name, cls="g6", sec="A"):
    body = {"name": f"{TAG} {name}", "dob": "2014-05-05", "gender": "Male", "class_id": ctx[cls]["id"], "section": sec,
            "academic_year": "2026-27", "admission_date": "2026-01-02", "guardian_name": "G", "guardian_phone": "9999999999"}
    r = admin.post(f"{API}/students", json=body)
    assert r.status_code == 200, r.text
    S.setdefault("students", []).append(r.json()["id"])
    return r.json(), body


# (1) ownership / scope
class TestOwnership:
    def test_teacher_cannot_archive_admin_announcement(self, admin, teacher):
        a = admin.post(f"{API}/announcements", json={"title": f"{TAG} adm ann", "body": "x", "roles": ["teacher"]}).json()
        S["ann"] = a["id"]
        r = teacher.delete(f"{API}/announcements/{a['id']}")
        assert r.status_code == 403, r.text
        r = teacher.post(f"{API}/announcements/{a['id']}/restore")
        assert r.status_code == 403, r.text
        assert admin.get(f"{API}/announcements/{a['id']}").json()["archived"] is False

    def test_teacher_cannot_put_admin_announcement(self, admin, teacher, ctx):
        r = teacher.put(f"{API}/announcements/{S['ann']}", json={"title": "hacked", "body": "x", "roles": ["teacher"], "class_ids": [ctx["g6"]["id"]]})
        assert r.status_code == 403, r.text
        assert admin.get(f"{API}/announcements/{S['ann']}").json()["title"] == f"{TAG} adm ann"

    def test_teacher_cannot_touch_other_teachers_homework(self, admin, teacher, ctx):
        # admin creates hw in a section/subject not taught by demo teacher -> teacher_id is other teacher (or None)
        r = admin.post(f"{API}/homework-items", json={"title": f"{TAG} otherHW", "class_id": ctx["g9"]["id"], "section": "A", "subject_id": ctx["MATH"]["id"], "due_date": "2027-11-05", "max_score": 10})
        assert r.status_code == 200, r.text
        hid = r.json()["id"]; S["hw_other"] = hid
        assert r.json()["teacher_id"] != teacher.me["profile_id"]
        d = teacher.delete(f"{API}/homework-items/{hid}")
        assert d.status_code in (403, 404), d.text
        u = teacher.put(f"{API}/homework-items/{hid}", json={"title": "x", "class_id": ctx["g9"]["id"], "section": "A", "subject_id": ctx["MATH"]["id"], "due_date": "2027-11-05", "max_score": 10})
        assert u.status_code in (403, 404), u.text
        assert admin.get(f"{API}/homework-items/{hid}").json()["archived"] is False

    def test_restore_nonexistent_404(self, admin):
        for p in ("students", "announcements", "homework-items", "books"):
            r = admin.post(f"{API}/{p}/doesnotexist{uuid.uuid4().hex}/restore")
            assert r.status_code == 404, (p, r.status_code)
        assert admin.delete(f"{API}/students/nope{uuid.uuid4().hex}").status_code == 404


# (2) archived students excluded
class TestArchivedStudents:
    def test_archive_sets_status_and_excluded(self, admin, ctx):
        st, _ = _stu(admin, ctx, "Arch")
        sid = st["id"]
        assert admin.delete(f"{API}/students/{sid}").status_code == 200
        g = admin.get(f"{API}/students/{sid}").json()
        assert g["status"] == "archived" and g["archived"] is True
        sh = admin.get(f"{API}/attendance/sheet", params={"date": "2026-01-05", "class_id": ctx["g6"]["id"], "section": "A"}).json()
        assert all(x["id"] != sid for x in sh["students"])
        sm = admin.get(f"{API}/attendance/summary", params={"class_id": ctx["g6"]["id"], "section": "A"})
        assert sid not in sm.text
        # save attendance with archived student -> should be rejected / not saved
        r = admin.post(f"{API}/attendance/sheet", json={"date": "2026-01-05", "class_id": ctx["g6"]["id"], "section": "A", "entries": [{"student_id": sid, "status": "present"}]})
        S["att_archived_status"] = r.status_code
        assert r.status_code in (200, 422)
        S["arch_sid"] = sid

    def test_archived_excluded_marks_results(self, admin, ctx):
        sid = S["arch_sid"]
        e = admin.post(f"{API}/exams", json={"name": f"{TAG} ExamA", "type": "Unit Test", "academic_year": "2026-27", "term": "Term 1", "class_id": ctx["g6"]["id"],
                                             "sections": ["A"], "subjects": [{"subject_id": ctx["ENG"]["id"], "date": "2026-01-05", "max_marks": 50, "pass_marks": 20}]})
        assert e.status_code == 200, e.text
        eid = e.json()["id"]; S["exam"] = eid
        mk = admin.get(f"{API}/exams/{eid}/marks", params={"section": "A", "subject_id": ctx["ENG"]["id"]}).json()
        assert all(x["id"] != sid for x in mk["students"]), "archived in marks entry"
        res = admin.get(f"{API}/exams/{eid}/results").json()
        assert all(x["id"] != sid for x in res["results"]), "archived student listed in exam results"

    def test_archived_excluded_hw_submissions(self, admin, teacher, ctx):
        sid = S["arch_sid"]
        r = teacher.post(f"{API}/homework-items", json={"title": f"{TAG} HW", "class_id": ctx["g6"]["id"], "section": "A", "subject_id": ctx["ENG"]["id"], "due_date": "2027-11-05", "max_score": 10})
        assert r.status_code == 200, r.text
        S["hw"] = r.json()["id"]
        subs = teacher.get(f"{API}/homework/{S['hw']}/submissions").json()
        assert all(x["id"] != sid for x in subs["students"])

    def test_capacity_ignores_archived(self, admin):
        body = {"name": f"{TAG} CapCls", "grade_level": 11, "sections": [{"name": "A", "capacity": 1}]}
        c = admin.post(f"{API}/classes", json=body)
        assert c.status_code == 200, c.text
        S["cls"] = c.json()["id"]
        sb = {"name": f"{TAG} Cap1", "dob": "2010-01-01", "gender": "Male", "class_id": S["cls"], "section": "A", "academic_year": "2026-27",
              "admission_date": "2026-01-02", "guardian_name": "G", "guardian_phone": "9999999999"}
        a = admin.post(f"{API}/students", json=sb).json(); S["students"].append(a["id"])
        assert admin.post(f"{API}/students", json={**sb, "name": f"{TAG} Cap2"}).status_code == 409
        admin.delete(f"{API}/students/{a['id']}")
        b = admin.post(f"{API}/students", json={**sb, "name": f"{TAG} Cap3"})
        assert b.status_code == 200, b.text
        S["students"].append(b.json()["id"])
        S["cap_a"] = a["id"]

    def test_restore_sets_active(self, admin, ctx):
        sid = S["arch_sid"]
        assert admin.post(f"{API}/students/{sid}/restore").status_code == 200
        g = admin.get(f"{API}/students/{sid}").json()
        assert g["status"] == "active" and g["archived"] is False
        sh = admin.get(f"{API}/attendance/sheet", params={"date": "2026-01-05", "class_id": ctx["g6"]["id"], "section": "A"}).json()
        assert any(x["id"] == sid for x in sh["students"])

    def test_restore_over_capacity(self, admin):
        # section capacity 1 is filled by Cap3; restoring Cap1 would exceed capacity
        r = admin.post(f"{API}/students/{S['cap_a']}/restore")
        S["restore_over_cap"] = r.status_code
        assert r.status_code == 409, f"restore exceeded capacity: {r.status_code}"

    def test_update_archived_student_does_not_reactivate(self, admin, ctx):
        st, body = _stu(admin, ctx, "ArchUpd")
        admin.delete(f"{API}/students/{st['id']}")
        r = admin.put(f"{API}/students/{st['id']}", json={**body, "name": f"{TAG} ArchUpd2"})
        g = admin.get(f"{API}/students/{st['id']}").json()
        sh = admin.get(f"{API}/attendance/sheet", params={"date": "2026-01-05", "class_id": ctx["g6"]["id"], "section": "A"}).json()
        assert not any(x["id"] == st["id"] for x in sh["students"]), f"PUT on archived student reset status to {g.get('status')} archived={g.get('archived')} (put {r.status_code})"


# (3) homework archive
class TestHomeworkArchive:
    def test_archive_hides(self, teacher, student):
        hid = S["hw"]
        assert any(h["id"] == hid for h in teacher.get(f"{API}/homework").json()["items"])
        assert teacher.delete(f"{API}/homework-items/{hid}").status_code == 200
        assert all(h["id"] != hid for h in teacher.get(f"{API}/homework").json()["items"])
        assert all(h["id"] != hid for h in student.get(f"{API}/homework").json()["items"])
        assert student.post(f"{API}/homework/{hid}/submit", json={"text": "x"}).status_code in (403, 404, 409, 422), "can submit to archived hw"


# (4) timetable validation
class TestTimetable:
    def test_unassigned_teacher_422(self, admin, teacher, ctx):
        tid = teacher.me["profile_id"]
        r = admin.post(f"{API}/timetable", json={"class_id": ctx["g9"]["id"], "section": "A", "day": "Mon", "period_no": 1, "subject_id": ctx["MATH"]["id"], "teacher_id": tid})
        # demo teacher may not teach MATH in 9-A
        assert r.status_code in (422, 409), r.text

    def test_invalid_class_section_422(self, admin, teacher, ctx):
        tid = teacher.me["profile_id"]
        r = admin.post(f"{API}/timetable", json={"class_id": "nope", "section": "A", "day": "Mon", "period_no": 1, "subject_id": ctx["ENG"]["id"], "teacher_id": tid})
        assert r.status_code == 422
        r = admin.post(f"{API}/timetable", json={"class_id": ctx["g6"]["id"], "section": "Z", "day": "Mon", "period_no": 1, "subject_id": ctx["ENG"]["id"], "teacher_id": tid})
        assert r.status_code == 422 and "section" in r.text.lower()


# (5) report card section, (6) mark clearing
class TestExams:
    def test_mark_clear(self, admin, ctx):
        eid = S["exam"]; eng = ctx["ENG"]["id"]
        studs = admin.get(f"{API}/exams/{eid}/marks", params={"section": "A", "subject_id": eng}).json()["students"]
        sid = studs[0]["id"]
        assert admin.post(f"{API}/exams/{eid}/marks", json={"section": "A", "subject_id": eng, "entries": [{"student_id": sid, "marks": 33}]}).status_code == 200
        m = admin.get(f"{API}/exams/{eid}/marks", params={"section": "A", "subject_id": eng}).json()
        row = next(x for x in m["students"] if x["id"] == sid)
        assert "33" in str(row)
        assert admin.post(f"{API}/exams/{eid}/marks", json={"section": "A", "subject_id": eng, "entries": [{"student_id": sid, "marks": None, "absent": False}]}).status_code == 200
        m = admin.get(f"{API}/exams/{eid}/marks", params={"section": "A", "subject_id": eng}).json()
        row = next(x for x in m["students"] if x["id"] == sid)
        assert "33" not in str(row), row

    def test_report_card_other_section_404(self, admin, ctx):
        e = admin.post(f"{API}/exams", json={"name": f"{TAG} ExamB", "type": "Unit Test", "academic_year": "2026-27", "term": "Term 1", "class_id": ctx["g6"]["id"],
                                             "sections": ["B"], "subjects": [{"subject_id": ctx["ENG"]["id"], "date": "2026-01-05", "max_marks": 50, "pass_marks": 20}]})
        if e.status_code != 200: pytest.skip(f"Grade 6-B may not exist: {e.text}")
        S["examB"] = e.json()["id"]
        r = admin.get(f"{API}/report-card/{S['examB']}/{S['arch_sid']}")
        assert r.status_code == 404
        assert admin.get(f"{API}/report-card/{S['exam']}/{S['arch_sid']}").status_code == 200


# (7) settings validation
class TestSettings:
    def test_type_validation(self, admin):
        before = admin.get(f"{API}/settings").json()
        assert admin.put(f"{API}/settings", json={"pass_percent": "abc"}).status_code == 422
        assert admin.put(f"{API}/settings", json={"email_notifications": "yes"}).status_code == 422
        assert admin.put(f"{API}/settings", json={"terms": "Term 1"}).status_code == 422
        assert admin.put(f"{API}/settings", json={"school_name": 123}).status_code == 422
        r = admin.put(f"{API}/settings", json={"pass_percent": "45"})
        assert r.status_code == 200 and r.json()["pass_percent"] == 45
        admin.put(f"{API}/settings", json={"pass_percent": before["pass_percent"]})
        assert admin.get(f"{API}/settings").json()["pass_percent"] == before["pass_percent"]

    def test_negative_number(self, admin):
        before = admin.get(f"{API}/settings").json()
        r = admin.put(f"{API}/settings", json={"pass_percent": -10})
        S["neg_pass"] = r.status_code
        if r.status_code == 200: admin.put(f"{API}/settings", json={"pass_percent": before["pass_percent"]})
        assert r.status_code == 422, "pass_percent=-10 accepted"


# smoke + cleanup
class TestSmoke:
    def test_dashboards(self, admin, teacher, student, parent):
        for s in (admin, teacher, student, parent):
            assert s.get(f"{API}/dashboard").status_code == 200

    def test_cleanup(self, admin):
        for sid in S.get("students", []): admin.delete(f"{API}/students/{sid}")
        for k, p in (("ann", "announcements"), ("hw_other", "homework-items"), ("exam", "exams"), ("examB", "exams")):
            if S.get(k): admin.delete(f"{API}/{p}/{S[k]}")
        if S.get("cls"): admin.delete(f"{API}/classes/{S['cls']}")
