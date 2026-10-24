import os, re, io, csv, uuid, logging, asyncio, ipaddress
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import bcrypt, jwt, httpx, requests
from fastapi import Request, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
logger = logging.getLogger("sms")
ROLES = ("admin", "teacher", "student", "parent")

DEFAULT_SETTINGS = {
    "id": "school", "school_name": "EduPrime International School", "tagline": "Excellence in Education",
    "logo_file_id": None, "address": "12 Knowledge Park, Bengaluru, Karnataka 560001", "email": "office@eduprime.demo",
    "phone": "+91 80 4000 1234", "website": "https://eduprime.demo", "academic_year": "2026-27",
    "terms": ["Term 1", "Term 2"], "currency": "INR", "currency_symbol": "₹", "date_format": "DD MMM YYYY",
    "timezone": "Asia/Kolkata", "genders": ["Male", "Female", "Other"],
    "grading": [{"min": 90, "grade": "A+"}, {"min": 80, "grade": "A"}, {"min": 70, "grade": "B+"}, {"min": 60, "grade": "B"},
                {"min": 50, "grade": "C"}, {"min": 40, "grade": "D"}, {"min": 0, "grade": "F"}],
    "pass_percent": 40, "low_attendance_threshold": 75, "teacher_edit_past_attendance": False,
    "late_fee_amount": 200, "library_fine_per_day": 5, "library_loan_days": 14, "session_minutes": 30,
    "working_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    "periods": [
        {"no": 1, "start": "08:30", "end": "09:15", "type": "class"}, {"no": 2, "start": "09:15", "end": "10:00", "type": "class"},
        {"no": 3, "start": "10:00", "end": "10:20", "type": "break"}, {"no": 4, "start": "10:20", "end": "11:05", "type": "class"},
        {"no": 5, "start": "11:05", "end": "11:50", "type": "class"}, {"no": 6, "start": "11:50", "end": "12:30", "type": "lunch"},
        {"no": 7, "start": "12:30", "end": "13:15", "type": "class"}, {"no": 8, "start": "13:15", "end": "14:00", "type": "class"}],
    "receipt_footer": "This is a computer generated receipt.", "student_leave_approver": "admin",
    "auto_excuse_on_leave": True, "allow_student_profile_edit": True, "email_notifications": True,
    "retention_years": 7, "fee_reminders_enabled": True, "fee_reminder_days_before": 3, "payment_methods": ["Cash", "Bank Transfer", "Card", "UPI", "Cheque"],
}

def now(): return datetime.now(timezone.utc)
def now_iso(): return now().isoformat()
def new_id(): return uuid.uuid4().hex

def clean(d):
    if d:
        d.pop("_id", None); d.pop("password_hash", None)
    return d

async def get_settings():
    s = await db.settings.find_one({"id": "school"}, {"_id": 0})
    return {**DEFAULT_SETTINGS, **(s or {})}

async def today():
    s = await get_settings()
    return datetime.now(ZoneInfo(s.get("timezone") or "UTC")).date().isoformat()

def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h):
    try: return bcrypt.checkpw(p.encode(), h.encode())
    except Exception: return False

def make_token(uid, typ, minutes, pv=0):
    return jwt.encode({"sub": uid, "type": typ, "pv": pv, "exp": now() + timedelta(minutes=minutes)}, os.environ["JWT_SECRET"], algorithm="HS256")

async def set_auth_cookies(resp, user, remember=True):
    s = await get_settings()
    mins = int(s.get("session_minutes") or 30)
    pv = user.get("pv", 0)
    resp.set_cookie("access_token", make_token(user["id"], "access", mins, pv), httponly=True, secure=True, samesite="lax", max_age=mins * 60, path="/")
    days = 7 if remember else 1
    resp.set_cookie("refresh_token", make_token(user["id"], "refresh", days * 1440, pv), httponly=True, secure=True, samesite="lax",
                    max_age=days * 86400 if remember else None, path="/")

def clear_auth_cookies(resp):
    resp.delete_cookie("access_token", path="/"); resp.delete_cookie("refresh_token", path="/")

async def user_from_token(token, typ):
    try:
        p = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session")
    if p.get("type") != typ: raise HTTPException(401, "Invalid session")
    u = await db.users.find_one({"id": p["sub"]}, {"_id": 0})
    if not u or not u.get("active", True) or u.get("pv", 0) != p.get("pv", 0):
        raise HTTPException(401, "Session no longer valid")
    return clean(u)

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    h = request.headers.get("Authorization", "")
    if not token and h.startswith("Bearer "): token = h[7:]
    if not token: raise HTTPException(401, "Not authenticated")
    return await user_from_token(token, "access")

def require(*roles):
    async def dep(user=Depends(get_current_user)):
        if roles and user["role"] not in roles: raise HTTPException(403, "You do not have permission for this action")
        return user
    return dep

async def audit(user, action, entity, entity_id=None, details=None):
    await db.audit_logs.insert_one({"id": new_id(), "user_id": user.get("id") if user else None, "user_name": user.get("name") if user else "system",
                                    "role": user.get("role") if user else None, "action": action, "entity": entity, "entity_id": entity_id,
                                    "details": details, "created_at": now_iso()})

async def notify(user_ids, title, body="", link=None):
    docs = [{"id": new_id(), "user_id": u, "title": title, "body": body, "link": link, "read": False, "created_at": now_iso()} for u in set(user_ids) if u]
    if docs: await db.notifications.insert_many(docs)

async def audience_user_ids(roles=None, class_ids=None, sections=None):
    roles = roles or []
    ids = []
    if class_ids:
        sq = {"class_id": {"$in": class_ids}, "status": "active"}
        if sections: sq["section"] = {"$in": sections}
        studs = await db.students.find(sq, {"_id": 0, "id": 1, "parent_ids": 1}).to_list(5000)
        sids = [s["id"] for s in studs]; pids = [p for s in studs for p in s.get("parent_ids", [])]
        q = []
        if not roles or "student" in roles: q.append({"role": "student", "profile_id": {"$in": sids}})
        if not roles or "parent" in roles: q.append({"role": "parent", "profile_id": {"$in": pids}})
        if "teacher" in roles or not roles:
            tids = [a["teacher_id"] for a in await db.assignments.find({"class_id": {"$in": class_ids}}, {"_id": 0}).to_list(1000)]
            q.append({"role": "teacher", "profile_id": {"$in": tids}})
        if "admin" in roles: q.append({"role": "admin"})
        if q: ids = [u["id"] for u in await db.users.find({"$or": q, "active": True}, {"_id": 0, "id": 1}).to_list(10000)]
    else:
        q = {"active": True} if not roles else {"role": {"$in": roles}, "active": True}
        ids = [u["id"] for u in await db.users.find(q, {"_id": 0, "id": 1}).to_list(10000)]
    return ids

async def next_seq(name, prefix, width=4):
    r = await db.counters.find_one_and_update({"id": name}, {"$inc": {"v": 1}}, upsert=True, return_document=True)
    return f"{prefix}{str(r['v']).zfill(width)}"

async def paginate(col, query, page=1, page_size=20, sort="-created_at", proj=None):
    page = max(1, page); page_size = min(max(1, page_size), 500)
    field = sort.lstrip("-"); direction = -1 if sort.startswith("-") else 1
    total = await col.count_documents(query)
    items = await col.find(query, proj or {"_id": 0, "password_hash": 0}).sort(field, direction).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}

async def teacher_ctx(user):
    tid = user.get("profile_id")
    asg = await db.assignments.find({"teacher_id": tid}, {"_id": 0}).to_list(500)
    pairs = {(a["class_id"], a["section"]) for a in asg}
    subj = {(a["class_id"], a["section"], a["subject_id"]) for a in asg}
    async for c in db.classes.find({"sections.class_teacher_id": tid}, {"_id": 0}):
        for s in c.get("sections", []):
            if s.get("class_teacher_id") == tid: pairs.add((c["id"], s["name"]))
    return tid, pairs, subj

async def class_teacher_pairs(tid):
    out = set()
    async for c in db.classes.find({"sections.class_teacher_id": tid}, {"_id": 0}):
        for s in c.get("sections", []):
            if s.get("class_teacher_id") == tid: out.add((c["id"], s["name"]))
    return out

async def student_query(user):
    r = user["role"]
    if r == "admin": return {}
    if r == "student": return {"id": user.get("profile_id") or "__none__"}
    if r == "parent":
        p = await db.parents.find_one({"id": user.get("profile_id")}, {"_id": 0}) or {}
        return {"id": {"$in": p.get("student_ids", [])}}
    _, pairs, _ = await teacher_ctx(user)
    return {"$or": [{"class_id": c, "section": s} for c, s in pairs]} if pairs else {"id": "__none__"}

async def assert_student(user, sid):
    q = await student_query(user)
    st = await db.students.find_one({"$and": [q, {"id": sid}]}, {"_id": 0})
    if not st: raise HTTPException(404, "Student not found or not accessible")
    return st

async def assert_section_access(user, class_id, section, subject_id=None):
    if user["role"] == "admin": return
    if user["role"] != "teacher": raise HTTPException(403, "Not permitted")
    _, pairs, subj = await teacher_ctx(user)
    ok = (class_id, section, subject_id) in subj if subject_id else (class_id, section) in pairs
    if not ok: raise HTTPException(403, "You are not assigned to this class/section" + (" and subject" if subject_id else ""))

def to_csv(rows, cols, filename):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow([c[1] for c in cols])
    for r in rows:
        w.writerow([("" if r.get(c[0]) is None else (", ".join(map(str, r.get(c[0]))) if isinstance(r.get(c[0]), list) else r.get(c[0]))) for c in cols])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})

# ---------- generic CRUD ----------
def crud(router, path, coll, Model, read_roles=ROLES, write_roles=("admin",), search=(), filters=(), hooks=None, csv_cols=None):
    hooks = hooks or {}
    col = db[coll]
    tag = coll

    async def build_query(request, user, q, include_archived):
        query = {} if include_archived else {"archived": {"$ne": True}}
        for f in filters:
            v = request.query_params.get(f)
            if v not in (None, ""): query[f] = v
        if q and search: query["$or"] = [{s: {"$regex": re.escape(q), "$options": "i"}} for s in search]
        if "scope" in hooks: query = {"$and": [query, await hooks["scope"](user)]}
        return query

    def proj(user):
        hide = hooks["hide"](user) if "hide" in hooks else []
        return {"_id": 0, **{k: 0 for k in hide}}

    async def list_items(request: Request, q: str = "", page: int = 1, page_size: int = Query(20, le=500), sort: str = "-created_at",
                         include_archived: bool = False, format: str = "", user=Depends(require(*read_roles))):
        query = await build_query(request, user, q, include_archived)
        if format == "csv":
            rows = await col.find(query, proj(user)).to_list(20000)
            await audit(user, "export", coll, None, {"count": len(rows)})
            return to_csv(rows, csv_cols or [(k, k) for k in (rows[0].keys() if rows else [])], coll)
        return await paginate(col, query, page, page_size, sort, proj(user))

    async def get_item(item_id: str, user=Depends(require(*read_roles))):
        query = {"id": item_id}
        if "scope" in hooks: query = {"$and": [query, await hooks["scope"](user)]}
        d = await col.find_one(query, proj(user))
        if not d: raise HTTPException(404, "Not found")
        return d

    async def create_item(body: Model, user=Depends(require(*write_roles))):
        data = body.model_dump()
        extra = {k: data.pop(k) for k in list(data) if k.startswith("_")}
        if "before_save" in hooks: data = await hooks["before_save"](data, user, None)
        data.update({"id": new_id(), "created_at": now_iso(), "updated_at": now_iso(), "archived": False})
        await col.insert_one(dict(data))
        if "after_create" in hooks: await hooks["after_create"](data, user, extra)
        await audit(user, "create", coll, data["id"])
        return clean(data)

    async def update_item(item_id: str, body: Model, user=Depends(require(*write_roles))):
        old = await owned(item_id, user)
        data = body.model_dump()
        for k in [k for k in data if k.startswith("_")]: data.pop(k)
        if "before_save" in hooks: data = await hooks["before_save"](data, user, old)
        data["updated_at"] = now_iso()
        await col.update_one({"id": item_id}, {"$set": data})
        changed = {k: [old.get(k), v] for k, v in data.items() if old.get(k) != v and k != "updated_at"}
        await audit(user, "update", coll, item_id, changed)
        return clean(await col.find_one({"id": item_id}, {"_id": 0}))

    async def owned(item_id, user):
        query = {"id": item_id}
        if "scope" in hooks: query = {"$and": [query, await hooks["scope"](user)]}
        old = await col.find_one(query, {"_id": 0})
        if not old: raise HTTPException(404, "Not found")
        if "owner_check" in hooks: await hooks["owner_check"](old, user)
        return old

    async def archive_item(item_id: str, user=Depends(require(*write_roles))):
        old = await owned(item_id, user)
        extra = {"status": "archived", "status_before_archive": old.get("status")} if coll == "students" else {}
        await col.update_one({"id": item_id}, {"$set": {"archived": True, "updated_at": now_iso(), **extra}})
        await audit(user, "archive", coll, item_id)
        return {"ok": True}

    async def restore_item(item_id: str, user=Depends(require(*write_roles))):
        old = await owned(item_id, user)
        extra = {}
        if coll == "students":
            prev = old.get("status_before_archive") or "active"
            if prev == "active":
                c = await db.classes.find_one({"id": old["class_id"]}, {"_id": 0}) or {}
                sec = next((s for s in c.get("sections", []) if s["name"] == old["section"]), {})
                cnt = await db.students.count_documents({"class_id": old["class_id"], "section": old["section"], "status": "active"})
                if sec.get("capacity") and cnt >= int(sec["capacity"]): raise HTTPException(409, "Section is at full capacity; transfer first")
            extra = {"status": prev}
        await col.update_one({"id": item_id}, {"$set": {"archived": False, **extra}})
        await audit(user, "restore", coll, item_id)
        return {"ok": True}

    router.add_api_route(path, list_items, methods=["GET"], name=f"{tag}_list")
    router.add_api_route(path + "/{item_id}", get_item, methods=["GET"], name=f"{tag}_get")
    router.add_api_route(path, create_item, methods=["POST"], name=f"{tag}_create")
    router.add_api_route(path + "/{item_id}", update_item, methods=["PUT"], name=f"{tag}_update")
    router.add_api_route(path + "/{item_id}", archive_item, methods=["DELETE"], name=f"{tag}_archive")
    router.add_api_route(path + "/{item_id}/restore", restore_item, methods=["POST"], name=f"{tag}_restore")

# ---------- email (Emergent managed Resend) ----------
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv", "send us your password",
             "enter your password below", "confirm your card number", "your full card number", "seed phrase", "recovery phrase",
             "verify your card", "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)

def _host_ok(host):
    if not host or "xn--" in host: return False
    try:
        ipaddress.ip_address(host); return False
    except ValueError: pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)

def _same_site(shown, real): return shown == real or real.endswith("." + shown) or shown.endswith("." + real)

class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags, self.urls, self.anchors = set(), [], []; self._href, self._text = None, []
    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower()); self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a": self._href = dict((k.lower(), v) for k, v in attrs).get("href"); self._text = []
    def handle_data(self, data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None: self.anchors.append((self._href, "".join(self._text))); self._href, self._text = None, []

def _assert_safe_email(subject, html):
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}: raise ValueError("No forms in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body: raise ValueError(f"credential ask {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")): continue
        if not low.startswith("https://"): raise ValueError(f"non-https url {url!r} (G3)")
        if not _host_ok(urlparse(low).hostname or "") or urlparse(low).username is not None: raise ValueError(f"bad url {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real: continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real): raise ValueError("anchor mismatch (G3)")

async def send_email(to, subject, html):
    """Returns True if accepted by the provider; never raises."""
    try:
        _assert_safe_email(subject, html)
        payload = {"to": [to], "subject": subject, "html": html, "from_name": os.environ["EMAIL_FROM_NAME"]}
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": os.environ["EMERGENT_EMAIL_KEY"]}, json=payload)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.warning(f"Email not sent: {e} {getattr(getattr(e, 'response', None), 'text', '')[:200]}")
        return False

def email_template(title, lines, cta=None):
    s = os.environ["EMAIL_FROM_NAME"]
    body = "".join(f"<p style='margin:0 0 12px'>{escape(l)}</p>" for l in lines)
    btn = f"<p><a href='{escape(cta[1])}' style='background:#0A192F;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none'>{escape(cta[0])}</a></p>" if cta else ""
    return (f"<table role='presentation' width='100%'><tr><td style='padding:24px;font-family:Arial,sans-serif;color:#0A192F'>"
            f"<h2 style='margin:0 0 16px'>{escape(title)}</h2>{body}{btn}"
            f"<p style='font-size:12px;color:#888'>Sent by {escape(s)}. We never ask for your password or card details by email.</p></td></tr></table>")

# ---------- object storage ----------
STORAGE_URL = ((os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com").rstrip("/") + "/objstore/api/v1/storage"
_storage_key = None

def init_storage(force=False):
    global _storage_key
    if _storage_key and not force: return _storage_key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    r.raise_for_status(); _storage_key = r.json()["storage_key"]
    return _storage_key

def _put(path, data, ct):
    r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(), "Content-Type": ct}, data=data, timeout=120)
    if r.status_code == 404:
        r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(True), "Content-Type": ct}, data=data, timeout=120)
    r.raise_for_status(); return r.json()

def _get(path):
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage()}, timeout=60)
    r.raise_for_status(); return r.content, r.headers.get("Content-Type", "application/octet-stream")

async def put_object(path, data, ct): return await asyncio.to_thread(_put, path, data, ct)
async def get_object(path): return await asyncio.to_thread(_get, path)
