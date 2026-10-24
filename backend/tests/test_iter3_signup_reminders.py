# Iteration 3: self sign-up (pending accounts, approval, reject), fee reminders (manual + cron), settings toggle
import os, uuid, random, time, pytest, requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
CREDS = {
    "admin": ("meetup2456bro@gmail.com", "Admin@12345"),
    "teacher": ("teacher@eduprime.demo", "Teacher@123"),
    "student": ("student@eduprime.demo", "Student@123"),
    "parent": ("parent@eduprime.demo", "Parent@123"),
}
TAG = "TEST_" + uuid.uuid4().hex[:6]
XFF = f"10.{random.randint(1,250)}.{random.randint(1,250)}.{random.randint(1,250)}"  # isolate rate-limit bucket
S = {}
CRON_SECRET = None
for line in open("/app/backend/.env"):
    if line.startswith("WEBHOOK_CRON_SECRET="):
        CRON_SECRET = line.split("=", 1)[1].strip().strip('"')


def _login(role):
    s = requests.Session()
    e, p = CREDS[role]
    r = s.post(f"{API}/auth/login", json={"email": e, "password": p})
    if r.status_code != 200:
        pytest.skip(f"login {role} failed {r.status_code}")
    s.me = r.json()
    return s


def _reg(email, pw="Passw0rd123", role="parent", xff=XFF):
    return requests.post(f"{API}/auth/register", headers={"X-Forwarded-For": xff},
                         json={"name": f"{TAG} Signup", "email": email, "password": pw, "role": role, "phone": "9876543210", "note": f"{TAG} note"})


@pytest.fixture(scope="module")
def admin(): return _login("admin")


def _find_user(admin, email):
    r = admin.get(f"{API}/users", params={"q": email, "pending": True})
    assert r.status_code == 200
    items = [u for u in r.json()["items"] if u["email"] == email]
    return items[0] if items else None


class TestSignup:
    def test_register_creates_pending(self, admin):
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        r = _reg(email)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        u = _find_user(admin, email)
        assert u and u["active"] is False and u["pending"] is True and u["role"] == "parent"
        assert "password_hash" not in u
        assert u["signup_note"].startswith(TAG)
        S["pending_email"] = email; S["pending_id"] = u["id"]

    def test_duplicate_409(self):
        r = _reg(S["pending_email"])
        assert r.status_code == 409

    def test_weak_password_422(self):
        r = _reg(f"test_{uuid.uuid4().hex[:8]}@example.com", pw="password")
        assert r.status_code == 422
        r2 = _reg(f"test_{uuid.uuid4().hex[:8]}@example.com", pw="short1")
        assert r2.status_code == 422

    def test_pending_login_403(self):
        r = requests.post(f"{API}/auth/login", json={"email": S["pending_email"], "password": "Passw0rd123"})
        assert r.status_code == 403 and "approval" in r.json()["detail"].lower()

    def test_pending_login_wrong_pw_401(self):
        r = requests.post(f"{API}/auth/login", json={"email": S["pending_email"], "password": "Wrong12345"})
        assert r.status_code == 401

    def test_rate_limit_429(self):
        # bucket already used by 4 calls above; 5th allowed, 6th blocked
        xff = f"10.200.{random.randint(1,250)}.{random.randint(1,250)}"
        codes = [_reg(f"test_rl{i}_{uuid.uuid4().hex[:6]}@example.com", pw="x", xff=xff).status_code for i in range(6)]
        assert codes[:5] == [422] * 5 and codes[5] == 429, codes

    def test_rate_limit_xff_spoof_bypass(self):
        # SECURITY: client-supplied X-Forwarded-For first hop is trusted -> rate limit bypassable
        xff = f"10.201.{random.randint(1,250)}.{random.randint(1,250)}"
        codes = [_reg(f"test_rl{i}_{uuid.uuid4().hex[:6]}@example.com", pw="x", xff=xff).status_code for i in range(6)]
        assert codes[5] == 429
        other = _reg(f"test_rlb_{uuid.uuid4().hex[:6]}@example.com", pw="x", xff=xff + "9").status_code
        S["xff_bypass"] = other != 429
        print("XFF spoof bypass possible:", S["xff_bypass"])

    def test_pending_filter_and_admin_notification(self, admin):
        r = admin.get(f"{API}/users", params={"pending": True, "page_size": 100})
        assert r.status_code == 200 and all(u.get("pending") for u in r.json()["items"])
        assert any(u["id"] == S["pending_id"] for u in r.json()["items"])
        n = admin.get(f"{API}/notifications").json()["items"]
        assert any("New account request" in x["title"] and TAG in x["title"] for x in n)

    def test_approve_requires_profile_422(self, admin):
        r = admin.put(f"{API}/users/{S['pending_id']}", json={"email": S["pending_email"], "name": f"{TAG} Signup", "role": "parent", "active": True, "profile_id": None})
        assert r.status_code == 422

    def test_non_admin_cannot_list_or_reject(self):
        p = _login("parent")
        assert p.get(f"{API}/users", params={"pending": True}).status_code == 403
        assert p.delete(f"{API}/users/{S['pending_id']}/request").status_code == 403

    def test_approve_with_profile_then_login(self, admin):
        pr = admin.post(f"{API}/parents", json={"name": f"{TAG} Parent", "email": S["pending_email"], "phone": "9876543210"})
        assert pr.status_code == 200, pr.text
        S["parent_id"] = pr.json()["id"]
        r = admin.put(f"{API}/users/{S['pending_id']}", json={"email": S["pending_email"], "name": f"{TAG} Signup", "role": "parent", "active": True, "profile_id": S["parent_id"]})
        assert r.status_code == 200, r.text
        d = r.json(); assert d["active"] is True and d["pending"] is False and d["profile_id"] == S["parent_id"]
        lg = requests.post(f"{API}/auth/login", json={"email": S["pending_email"], "password": "Passw0rd123"})
        assert lg.status_code == 200 and lg.json()["role"] == "parent"
        assert lg.json()["profile"]["id"] == S["parent_id"]

    def test_reject_deletes_request(self, admin):
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        xff = f"10.202.{random.randint(1,250)}.{random.randint(1,250)}"
        assert _reg(email, xff=xff).status_code == 200
        u = _find_user(admin, email)
        r = admin.delete(f"{API}/users/{u['id']}/request")
        assert r.status_code == 200
        assert _find_user(admin, email) is None
        assert admin.delete(f"{API}/users/{u['id']}/request").status_code == 404
        # cannot reject an approved (non-pending) user
        assert admin.delete(f"{API}/users/{S['pending_id']}/request").status_code == 404
        lg = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd123"})
        assert lg.status_code == 401


class TestReminders:
    def test_non_admin_403(self):
        for role in ("teacher", "parent"):
            s = _login(role)
            assert s.post(f"{API}/fees/send-reminders").status_code == 403
            assert s.get(f"{API}/fees/reminder-runs").status_code == 403

    def test_due_soon_flow(self, admin):
        assert S.get("parent_id"), "needs approved signup parent"
        classes = admin.get(f"{API}/classes", params={"page_size": 100}).json()["items"]
        g6 = [c for c in classes if c["name"] == "Grade 6"][0]
        today = admin.get(f"{API}/dashboard").json().get("today") or date.today().isoformat()
        st = admin.post(f"{API}/students", json={"name": f"{TAG} Stu", "dob": "2014-05-05", "gender": "Male", "class_id": g6["id"], "section": "A",
                                                 "academic_year": "2026-27", "admission_date": "2026-01-02", "guardian_name": "G", "guardian_phone": "9999999999",
                                                 "guardian_email": f"test_g_{uuid.uuid4().hex[:6]}@example.com", "parent_ids": [S["parent_id"]]})
        assert st.status_code == 200, st.text
        S["student_id"] = st.json()["id"]
        due = (date.fromisoformat(today) + timedelta(days=2)).isoformat()
        od = (date.fromisoformat(today) - timedelta(days=5)).isoformat()
        inv = admin.post(f"{API}/invoices", json={"student_id": S["student_id"], "items": [{"name": "TEST Tuition", "amount": 1000}], "due_date": due})
        inv2 = admin.post(f"{API}/invoices", json={"student_id": S["student_id"], "items": [{"name": "TEST Bus", "amount": 500}], "due_date": od})
        assert inv.status_code == 200 and inv2.status_code == 200, inv.text + inv2.text
        S["inv"] = inv.json()["id"]; S["inv2"] = inv2.json()["id"]
        r = admin.post(f"{API}/fees/send-reminders")
        assert r.status_code == 200, r.text
        d = r.json(); print("run1", d)
        for k in ("due_soon", "overdue", "emails_sent", "emails_failed"): assert isinstance(d[k], int)
        assert d["due_soon"] >= 1 and d["overdue"] >= 1
        assert d["emails_sent"] + d["emails_failed"] >= 2
        i1 = admin.get(f"{API}/invoices/{S['inv']}").json(); i2 = admin.get(f"{API}/invoices/{S['inv2']}").json()
        i1 = i1.get("invoice", i1); i2 = i2.get("invoice", i2)
        assert "due_soon" in i1.get("reminders", {}) and "overdue" in i2.get("reminders", {}), (i1.get("reminders"), i2.get("reminders"))
        # second run should not re-remind
        d2 = admin.post(f"{API}/fees/send-reminders").json(); print("run2", d2)
        assert d2["due_soon"] == 0 and d2["overdue"] == 0
        runs = admin.get(f"{API}/fees/reminder-runs")
        assert runs.status_code == 200 and len(runs.json()) >= 2 and "at" in runs.json()[0]

    def test_parent_in_app_notification(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": S["pending_email"], "password": "Passw0rd123"})
        assert r.status_code == 200
        n = s.get(f"{API}/notifications").json()["items"]
        titles = [x["title"] for x in n]
        assert any("Fee due on" in t for t in titles) and any("Fee overdue" in t for t in titles), titles

    def test_disabled_skipped_and_reenable(self, admin):
        try:
            r = admin.put(f"{API}/settings", json={"fee_reminders_enabled": False})
            assert r.status_code == 200, r.text
            d = admin.post(f"{API}/fees/send-reminders").json()
            assert d.get("skipped") == "disabled"
        finally:
            admin.put(f"{API}/settings", json={"fee_reminders_enabled": True})
        assert admin.get(f"{API}/settings").json()["fee_reminders_enabled"] is True

    def test_days_before_setting(self, admin):
        r = admin.put(f"{API}/settings", json={"fee_reminder_days_before": 5})
        assert r.status_code == 200
        assert admin.get(f"{API}/settings").json()["fee_reminder_days_before"] == 5
        neg = admin.put(f"{API}/settings", json={"fee_reminder_days_before": -3})
        S["neg_days_status"] = neg.status_code
        print("negative days_before status:", neg.status_code)
        admin.put(f"{API}/settings", json={"fee_reminder_days_before": 3})
        assert admin.get(f"{API}/settings").json()["fee_reminder_days_before"] == 3


class TestCron:
    URL = f"{API}/cron/fee-reminders"

    def test_no_auth_401(self):
        assert requests.post(self.URL, json={}).status_code == 401

    def test_wrong_bearer_401(self):
        assert requests.post(self.URL, json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401

    def test_correct_bearer_and_duplicate(self):
        rid = f"TEST_{uuid.uuid4().hex}"
        h = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": rid}
        t = time.time()
        r = requests.post(self.URL, json={"run_id": rid}, headers=h)
        assert r.status_code == 200 and r.json()["ok"] is True and not r.json().get("duplicate")
        assert time.time() - t < 10
        r2 = requests.post(self.URL, json={"run_id": rid}, headers=h)
        assert r2.status_code == 200 and r2.json().get("duplicate") is True

    def test_correct_bearer_no_body(self):
        r = requests.post(self.URL, headers={"Authorization": f"Bearer {CRON_SECRET}"})
        print("cron empty body status:", r.status_code)
        assert r.status_code in (200, 400)


class TestSmoke:
    def test_four_logins(self):
        for role in CREDS:
            s = _login(role)
            assert s.me["role"] == role

    def test_cleanup(self, admin):
        for k in ("inv", "inv2"):
            if S.get(k): admin.post(f"{API}/invoices/{S[k]}/adjust", json={"void": True, "reason": "TEST cleanup"})
        if S.get("student_id"): admin.delete(f"{API}/students/{S['student_id']}")
        # no DELETE /users/{id}; deactivate the approved TEST user
        if S.get("pending_id"): admin.post(f"{API}/users/{S['pending_id']}/toggle-active")
        if S.get("parent_id"): admin.delete(f"{API}/parents/{S['parent_id']}")
