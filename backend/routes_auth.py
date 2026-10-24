import os, secrets
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from core import (db, now, now_iso, new_id, clean, hash_password, verify_password, set_auth_cookies, clear_auth_cookies,
                  user_from_token, get_current_user, require, audit, paginate, send_email, email_template, get_settings, notify)

router = APIRouter(prefix="/api")

class LoginIn(BaseModel):
    email: str
    password: str
    remember: bool = True

class ForgotIn(BaseModel):
    email: str
    origin_url: str = ""

class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)

class ChangePwIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

class ProfileIn(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=300)

class UserIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(pattern="^(admin|teacher|student|parent)$")
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    profile_id: Optional[str] = None
    active: bool = True

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(parent|teacher|student)$")
    phone: str = Field(min_length=6, max_length=20)
    note: str = Field("", max_length=300)

class AdminResetIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)

def strong(p):
    if len(p) < 8 or not any(c.isdigit() for c in p) or not any(c.isalpha() for c in p):
        raise HTTPException(422, "Password must be at least 8 characters and include letters and numbers")

async def user_out(u):
    u = clean(dict(u))
    prof = None
    coll = {"teacher": "teachers", "student": "students", "parent": "parents"}.get(u["role"])
    if coll and u.get("profile_id"):
        prof = await db[coll].find_one({"id": u["profile_id"]}, {"_id": 0, "salary": 0})
    u["profile"] = prof
    return u

@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.strip().lower()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    ident = f"{ip}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and att.get("locked_until") and att["locked_until"] > now_iso():
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    u = await db.users.find_one({"email": email}, {"_id": 0})
    if not u or not verify_password(body.password, u.get("password_hash", "")):
        cnt = (att or {}).get("count", 0) + 1
        await db.login_attempts.update_one({"identifier": ident}, {"$set": {"count": cnt, "locked_until": (now() + timedelta(minutes=15)).isoformat() if cnt >= 5 else None}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    if u.get("pending"):
        raise HTTPException(403, "Your account is awaiting approval by the school. You'll get an email once it's approved.")
    if not u.get("active", True):
        raise HTTPException(403, "Your account is deactivated. Contact the school administrator.")
    await db.login_attempts.delete_one({"identifier": ident})
    await db.users.update_one({"id": u["id"]}, {"$set": {"last_login": now_iso()}})
    await set_auth_cookies(response, u, body.remember)
    await audit(u, "login", "auth", u["id"])
    return await user_out(u)

@router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}

@router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return await user_out(user)

@router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    t = request.cookies.get("refresh_token")
    if not t: raise HTTPException(401, "Session expired")
    u = await user_from_token(t, "refresh")
    await set_auth_cookies(response, u, True)
    return {"ok": True}

@router.post("/auth/forgot-password")
async def forgot(body: ForgotIn):
    email = body.email.strip().lower()
    u = await db.users.find_one({"email": email, "active": True}, {"_id": 0})
    if u:
        recent = await db.password_reset_tokens.count_documents({"user_id": u["id"], "created_at": {"$gt": (now() - timedelta(minutes=15)).isoformat()}})
        if recent < 3:
            token = secrets.token_urlsafe(32)
            await db.password_reset_tokens.insert_one({"token": token, "user_id": u["id"], "used": False, "created_at": now_iso(), "expires_at": now() + timedelta(hours=1)})
            origin = body.origin_url.rstrip("/") if body.origin_url.startswith("https://") else ""
            if origin:
                s = await get_settings()
                await send_email(u["email"], f"Reset your {s['school_name']} password", email_template(
                    "Password reset request", [f"Hi {u['name']},", "We received a request to reset your password. This link expires in 1 hour.",
                                               "If you did not request this, you can ignore this email."], ("Reset password", f"{origin}/reset-password?token={token}")))
    return {"ok": True, "message": "If an account exists for that email, a reset link has been sent."}

@router.post("/auth/reset-password")
async def reset(body: ResetIn):
    strong(body.password)
    t = await db.password_reset_tokens.find_one({"token": body.token, "used": False})
    if not t or t["expires_at"].replace(tzinfo=now().tzinfo) < now():
        raise HTTPException(400, "This reset link is invalid or has expired")
    await db.users.update_one({"id": t["user_id"]}, {"$set": {"password_hash": hash_password(body.password)}, "$inc": {"pv": 1}})
    await db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    u = await db.users.find_one({"id": t["user_id"]}, {"_id": 0})
    await audit(u, "password_reset", "users", u["id"])
    return {"ok": True}

@router.post("/auth/change-password")
async def change_pw(body: ChangePwIn, response: Response, user=Depends(get_current_user)):
    strong(body.new_password)
    u = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.current_password, u["password_hash"]): raise HTTPException(400, "Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}, "$inc": {"pv": 1}})
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    await set_auth_cookies(response, u, True)
    await audit(user, "change_password", "users", user["id"])
    return {"ok": True}

@router.put("/auth/profile")
async def update_profile(body: ProfileIn, user=Depends(get_current_user)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "name" in data and user["role"] in ("admin",):
        await db.users.update_one({"id": user["id"]}, {"$set": {"name": data["name"]}})
    contact = {k: data[k] for k in ("phone", "address") if k in data}
    coll = {"teacher": "teachers", "parent": "parents", "student": "students"}.get(user["role"])
    if coll and contact and user.get("profile_id"):
        if user["role"] == "student" and not (await get_settings()).get("allow_student_profile_edit"):
            raise HTTPException(403, "Profile editing is disabled by the school")
        await db[coll].update_one({"id": user["profile_id"]}, {"$set": contact})
    await audit(user, "update_profile", "users", user["id"], contact)
    return await user_out(await db.users.find_one({"id": user["id"]}, {"_id": 0}))

@router.post("/auth/register")
async def register(body: RegisterIn):
    strong(body.password)
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists. Try signing in or resetting your password.")
    doc = {"id": new_id(), "email": email, "name": body.name.strip(), "role": body.role, "password_hash": hash_password(body.password), "profile_id": None,
           "active": False, "pending": True, "pv": 0, "phone": body.phone, "signup_note": body.note, "created_at": now_iso()}
    await db.users.insert_one(dict(doc))
    admins = [a["id"] for a in await db.users.find({"role": "admin", "active": True}, {"_id": 0, "id": 1}).to_list(50)]
    await notify(admins, f"New account request: {doc['name']} ({body.role})", body.note[:100] or email, "/users")
    await audit(None, "signup_request", "users", doc["id"], {"role": body.role})
    return {"ok": True, "message": "Account request received. The school will review and approve it."}

# ---- user management (admin) ----
@router.get("/users")
async def list_users(q: str = "", role: str = "", pending: bool = False, page: int = 1, page_size: int = 20, user=Depends(require("admin"))):
    query = {"pending": True} if pending else {}
    if role: query["role"] = role
    if q:
        import re
        query["$or"] = [{"name": {"$regex": re.escape(q), "$options": "i"}}, {"email": {"$regex": re.escape(q), "$options": "i"}}]
    return await paginate(db.users, query, page, page_size, "-created_at")

async def create_user_record(email, name, role, password, profile_id=None, active=True, demo=False):
    email = email.strip().lower()
    if await db.users.find_one({"email": email}): raise HTTPException(409, "A user with this email already exists")
    if profile_id and await db.users.find_one({"profile_id": profile_id, "role": role}):
        raise HTTPException(409, "This profile already has a login account")
    doc = {"id": new_id(), "email": email, "name": name, "role": role, "password_hash": hash_password(password), "profile_id": profile_id,
           "active": active, "pv": 0, "created_at": now_iso(), "demo": demo}
    await db.users.insert_one(dict(doc))
    return clean(doc)

@router.post("/users")
async def create_user(body: UserIn, user=Depends(require("admin"))):
    if not body.password: raise HTTPException(422, "Password is required")
    strong(body.password)
    if body.role != "admin" and not body.profile_id: raise HTTPException(422, "Link this account to a teacher, student or parent profile")
    u = await create_user_record(body.email, body.name, body.role, body.password, body.profile_id, body.active)
    await audit(user, "create", "users", u["id"], {"role": body.role})
    return u

@router.put("/users/{uid}")
async def update_user(uid: str, body: UserIn, user=Depends(require("admin"))):
    if uid == user["id"] and (body.role != "admin" or not body.active): raise HTTPException(400, "You cannot demote or deactivate yourself")
    if await db.users.find_one({"email": body.email.lower(), "id": {"$ne": uid}}): raise HTTPException(409, "Email already in use")
    old = await db.users.find_one({"id": uid}, {"_id": 0})
    if not old: raise HTTPException(404, "User not found")
    if body.active and body.role != "admin" and not body.profile_id: raise HTTPException(422, "Link this account to a teacher, student or parent profile before activating")
    if body.profile_id and await db.users.find_one({"profile_id": body.profile_id, "role": body.role, "id": {"$ne": uid}}): raise HTTPException(409, "That profile already has a login account")
    approving = old.get("pending") and body.active
    await db.users.update_one({"id": uid}, {"$set": {"email": body.email.lower(), "name": body.name, "role": body.role, "profile_id": body.profile_id, "active": body.active,
                                                   **({"pending": False, "approved_by": user["name"], "approved_at": now_iso()} if approving else {})}})
    await audit(user, "approve_signup" if approving else "update", "users", uid, {"role": body.role, "active": body.active})
    if approving:
        s = await get_settings()
        await send_email(body.email.lower(), f"Your {s['school_name']} account is approved", email_template("Account approved", [f"Hi {body.name},", "Your portal account has been approved. You can now sign in with the email and password you registered with."]))
    return clean(await db.users.find_one({"id": uid}, {"_id": 0}))

@router.delete("/users/{uid}/request")
async def reject_signup(uid: str, user=Depends(require("admin"))):
    r = await db.users.delete_one({"id": uid, "pending": True})
    if not r.deleted_count: raise HTTPException(404, "Pending request not found")
    await audit(user, "reject_signup", "users", uid)
    return {"ok": True}

@router.post("/users/{uid}/toggle-active")
async def toggle_user(uid: str, user=Depends(require("admin"))):
    if uid == user["id"]: raise HTTPException(400, "You cannot deactivate yourself")
    u = await db.users.find_one({"id": uid})
    if not u: raise HTTPException(404, "User not found")
    await db.users.update_one({"id": uid}, {"$set": {"active": not u.get("active", True)}, "$inc": {"pv": 1}})
    await audit(user, "deactivate" if u.get("active", True) else "activate", "users", uid)
    return {"active": not u.get("active", True)}

@router.post("/users/{uid}/reset-password")
async def admin_reset(uid: str, body: AdminResetIn, user=Depends(require("admin"))):
    strong(body.password)
    r = await db.users.update_one({"id": uid}, {"$set": {"password_hash": hash_password(body.password)}, "$inc": {"pv": 1}})
    if not r.matched_count: raise HTTPException(404, "User not found")
    await audit(user, "admin_password_reset", "users", uid)
    await notify([uid], "Your password was reset by an administrator")
    return {"ok": True}
