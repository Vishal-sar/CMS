import os, hmac, asyncio
from datetime import date as Date, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from core import db, now_iso, require, audit, get_settings, today, notify, send_email, email_template, logger

router = APIRouter(prefix="/api")

async def recipients(student_id):
    st = await db.students.find_one({"id": student_id}, {"_id": 0}) or {}
    pids = st.get("parent_ids", [])
    users = await db.users.find({"role": "parent", "profile_id": {"$in": pids}, "active": True}, {"_id": 0, "id": 1, "email": 1}).to_list(10)
    emails = {u["email"] for u in users}
    for p in await db.parents.find({"id": {"$in": pids}}, {"_id": 0, "email": 1}).to_list(10):
        if p.get("email"): emails.add(p["email"].lower())
    if st.get("guardian_email"): emails.add(st["guardian_email"].lower())
    # demo addresses are not real mailboxes
    return [u["id"] for u in users], sorted(e for e in emails if not e.endswith(".demo"))

async def run_fee_reminders():
    s = await get_settings()
    if not s.get("fee_reminders_enabled", True): return {"skipped": "disabled"}
    t = await today(); days = int(s.get("fee_reminder_days_before", 3))
    soon = (Date.fromisoformat(t) + timedelta(days=days)).isoformat()
    sym = s.get("currency_symbol", "₹")
    out = {"due_soon": 0, "overdue": 0, "emails_sent": 0, "emails_failed": 0}
    jobs = [("due_soon", {"due_date": {"$gte": t, "$lte": soon}, "reminders.due_soon": {"$exists": False}}),
            ("overdue", {"due_date": {"$lt": t}, "reminders.overdue": {"$exists": False}})]
    for kind, q in jobs:
        for inv in await db.invoices.find({"status": {"$in": ["unpaid", "partial"]}, **q}, {"_id": 0}).to_list(5000):
            st = await db.students.find_one({"id": inv["student_id"]}, {"_id": 0, "status": 1, "archived": 1})
            if not st or st.get("status") != "active" or st.get("archived"): continue
            claim = await db.invoices.update_one({"id": inv["id"], f"reminders.{kind}": {"$exists": False}}, {"$set": {f"reminders.{kind}": {"at": now_iso(), "status": "sending"}}})
            if not claim.modified_count: continue
            uids, emails = await recipients(inv["student_id"])
            items = ", ".join(i["name"] for i in inv["items"])
            title = f"Fee {'due on ' + inv['due_date'] if kind == 'due_soon' else 'overdue'}: {inv['student_name']}"
            lines = [f"Dear Parent/Guardian of {inv['student_name']} ({inv['class_name']}-{inv['section']}),",
                     f"Invoice {inv['invoice_no']} ({items}) has an outstanding balance of {sym}{inv['balance']:,.2f}.",
                     f"Due date: {inv['due_date']}." + (" This invoice is now overdue; late fees may apply as per school policy." if kind == "overdue" else ""),
                     "You can view and pay it from the Fees section of the parent portal, or at the school office.", "Please ignore this message if you have already paid."]
            await notify(uids, title, f"Balance {sym}{inv['balance']:,.2f} on {inv['invoice_no']}", "/fees")
            sent = []
            for e in emails:
                ok = await send_email(e, f"{s['school_name']}: {title}", email_template(title, lines))
                out["emails_sent" if ok else "emails_failed"] += 1
                if ok: sent.append(e)
            if emails and not sent:
                await db.invoices.update_one({"id": inv["id"]}, {"$unset": {f"reminders.{kind}": ""}})
            else:
                await db.invoices.update_one({"id": inv["id"]}, {"$set": {f"reminders.{kind}": {"at": now_iso(), "emails": sent}}})
            out[kind] += 1
    await db.reminder_runs.insert_one({"at": now_iso(), **out})
    return out

@router.post("/fees/send-reminders")
async def send_now(user=Depends(require("admin"))):
    r = await run_fee_reminders()
    await audit(user, "fee_reminders_manual", "invoices", None, r)
    return r

@router.get("/fees/reminder-runs")
async def runs(user=Depends(require("admin"))):
    return await db.reminder_runs.find({}, {"_id": 0}).sort("at", -1).to_list(10)

async def _bg():
    try: await run_fee_reminders()
    except Exception as e: logger.error(f"fee reminders failed: {e}")

@router.post("/cron/fee-reminders")
async def cron_fee_reminders(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], os.environ["WEBHOOK_CRON_SECRET"]): raise HTTPException(401, "Unauthorized")
    raw = await request.body()
    try: env = await request.json() if raw.strip() else {}
    except Exception: raise HTTPException(400, "Invalid body")
    run_id = request.headers.get("X-Webhook-Id") or (env or {}).get("run_id")
    if run_id:
        if await db.cron_runs.find_one({"run_id": run_id}): return {"ok": True, "duplicate": True}
        await db.cron_runs.insert_one({"run_id": run_id, "at": now_iso()})
    asyncio.create_task(_bg())
    return {"ok": True}
