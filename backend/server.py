from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os, time, logging
from collections import defaultdict
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from pymongo.errors import DuplicateKeyError, PyMongoError
from core import db, client, new_id, now_iso, hash_password, verify_password, init_storage, logger
import routes_auth, routes_people, routes_academic, routes_exams, routes_fees, routes_misc, routes_dash, routes_reminders
from seed import seed_demo, seed_demo_logins

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
app = FastAPI(title="EduPrime School Management System")

_hits = defaultdict(list)
RATE = {"/api/auth/login": (60, 60), "/api/auth/register": (5, 600), "/api/auth/forgot-password": (5, 300), "/api/auth/reset-password": (10, 300)}

@app.middleware("http")
async def security(request: Request, call_next):
    path = request.url.path
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[-1].strip()
    if path in RATE:
        lim, win = RATE[path]; key = f"{ip}:{path}"; t = time.time()
        _hits[key] = [x for x in _hits[key] if x > t - win]
        if len(_hits[key]) >= lim: return JSONResponse({"detail": "Too many requests. Please wait and try again."}, status_code=429)
        _hits[key].append(t)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.cookies.get("access_token") and not path.startswith(("/api/webhooks", "/api/cron")):
        origin = request.headers.get("origin")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if origin and urlparse(origin).netloc != host: return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"; resp.headers["X-Frame-Options"] = "DENY"; resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp

@app.exception_handler(DuplicateKeyError)
async def dup_handler(request, exc): return JSONResponse({"detail": "A record with these details already exists"}, status_code=409)

@app.exception_handler(PyMongoError)
async def db_handler(request, exc):
    logger.error(f"DB error: {exc}"); return JSONResponse({"detail": "Database error. Please try again."}, status_code=503)

for r in (routes_auth, routes_people, routes_academic, routes_exams, routes_fees, routes_misc, routes_dash, routes_reminders): app.include_router(r.router)

@app.get("/api/health")
async def health(): return {"ok": True}

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origin_regex=".*" if os.environ.get("CORS_ORIGINS", "*") == "*" else None,
                   allow_origins=[] if os.environ.get("CORS_ORIGINS", "*") == "*" else os.environ["CORS_ORIGINS"].split(","), allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    idx = [("users", [("email", 1)], True), ("users", [("id", 1)], True), ("students", [("admission_no", 1)], True), ("students", [("id", 1)], True), ("teachers", [("employee_id", 1)], True),
           ("attendance", [("date", 1), ("student_id", 1)], True), ("attendance", [("class_id", 1), ("section", 1), ("date", 1)], False),
           ("marks", [("exam_id", 1), ("student_id", 1), ("subject_id", 1)], True), ("timetable", [("class_id", 1), ("section", 1), ("day", 1), ("period_no", 1)], True),
           ("assignments", [("class_id", 1), ("section", 1), ("subject_id", 1)], True), ("invoices", [("invoice_no", 1)], True), ("invoices", [("student_id", 1)], False),
           ("payments", [("receipt_no", 1)], True), ("payment_orders", [("order_id", 1)], True), ("books", [("accession_no", 1)], True),
           ("submissions", [("homework_id", 1), ("student_id", 1)], True), ("staff_attendance", [("date", 1), ("teacher_id", 1)], True),
           ("notifications", [("user_id", 1), ("created_at", -1)], False), ("audit_logs", [("created_at", -1)], False), ("login_attempts", [("identifier", 1)], False)]
    for coll, keys, uniq in idx:
        try: await db[coll].create_index(keys, unique=uniq)
        except Exception as e: logger.warning(f"index {coll}: {e}")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    email, pw = os.environ["ADMIN_EMAIL"].lower(), os.environ["ADMIN_PASSWORD"]
    ex = await db.users.find_one({"email": email})
    if not ex:
        await db.users.insert_one({"id": new_id(), "email": email, "name": "School Administrator", "role": "admin", "password_hash": hash_password(pw), "profile_id": None, "active": True, "pv": 0, "created_at": now_iso()})
    elif not verify_password(pw, ex["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(pw)}})
    data = await seed_demo()
    await seed_demo_logins(data)
    try: init_storage()
    except Exception as e: logger.error(f"Storage init failed: {e}")

@app.on_event("shutdown")
async def shutdown(): client.close()
