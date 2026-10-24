import os, hmac, hashlib, base64, json, re, uuid
from typing import Optional, List
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from core import (db, now_iso, new_id, clean, require, audit, student_query, assert_student, get_settings, today, notify, next_seq,
                  get_current_user, paginate, crud, send_email, email_template, logger)

router = APIRouter(prefix="/api")
FEE_TYPES = ("Tuition", "Admission", "Examination", "Transport", "Activity", "Library", "Other")

class FeeStructureIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    fee_type: str
    class_id: str = "all"
    academic_year: str
    amount: float = Field(gt=0)
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    installment: str = "Full"

crud(router, "/fee-structures", "fee_structures", FeeStructureIn, search=("name", "fee_type"), filters=("class_id", "academic_year", "fee_type"))

def inv_view(inv, t):
    inv = clean(inv)
    if inv["status"] in ("unpaid", "partial") and inv["due_date"] < t: inv["display_status"] = "overdue"
    else: inv["display_status"] = inv["status"]
    return inv

def status_of(total, paid):
    return "paid" if paid >= total - 0.001 else ("partial" if paid > 0 else "unpaid")

async def inv_scope(user):
    if user["role"] == "admin": return {}
    if user["role"] == "teacher": raise HTTPException(403, "Teachers do not have access to financial records")
    return {"student_id": {"$in": [s["id"] for s in await db.students.find(await student_query(user), {"_id": 0, "id": 1}).to_list(50)]}}

@router.get("/invoices")
async def list_invoices(q: str = "", status: str = "", class_id: str = "", student_id: str = "", academic_year: str = "", page: int = 1, page_size: int = 20, user=Depends(get_current_user)):
    query = {"$and": [await inv_scope(user), {"status": {"$ne": "void"}} if status != "void" else {}]}
    t = await today()
    if status == "overdue": query["$and"].append({"status": {"$in": ["unpaid", "partial"]}, "due_date": {"$lt": t}})
    elif status: query["$and"].append({"status": status})
    if class_id: query["$and"].append({"class_id": class_id})
    if student_id: query["$and"].append({"student_id": student_id})
    if academic_year: query["$and"].append({"academic_year": academic_year})
    if q: query["$and"].append({"$or": [{f: {"$regex": re.escape(q), "$options": "i"}} for f in ("invoice_no", "student_name", "admission_no")]})
    res = await paginate(db.invoices, query, page, page_size, "-created_at")
    res["items"] = [inv_view(i, t) for i in res["items"]]
    return res

@router.get("/invoices/{iid}")
async def get_invoice(iid: str, user=Depends(get_current_user)):
    inv = await db.invoices.find_one({"$and": [{"id": iid}, await inv_scope(user)]}, {"_id": 0})
    if not inv: raise HTTPException(404, "Invoice not found")
    pays = await db.payments.find({"invoice_id": iid}, {"_id": 0}).sort("date", -1).to_list(100)
    return {**inv_view(inv, await today()), "payments": pays}

class InvItem(BaseModel):
    name: str
    amount: float = Field(gt=0)

class InvoiceIn(BaseModel):
    student_id: str
    items: List[InvItem]
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    discount: float = Field(0, ge=0)
    discount_reason: str = ""
    academic_year: Optional[str] = None

async def make_invoice(st, items, due, discount, reason, year, user, structure_id=None):
    sub = round(sum(i["amount"] for i in items), 2)
    if discount > sub: raise HTTPException(422, "Discount cannot exceed invoice amount")
    total = round(sub - discount, 2)
    doc = {"id": new_id(), "invoice_no": await next_seq("inv", f"INV{(year or '')[:4]}-", 5), "student_id": st["id"], "student_name": st["name"], "admission_no": st["admission_no"],
           "class_id": st["class_id"], "class_name": st.get("class_name"), "section": st["section"], "items": items, "subtotal": sub, "discount": discount,
           "discount_reason": reason, "late_fee": 0, "total": total, "paid": 0, "balance": total, "due_date": due, "status": status_of(total, 0),
           "academic_year": year, "structure_id": structure_id, "created_by": user["id"], "created_at": now_iso()}
    await db.invoices.insert_one(dict(doc))
    return doc

@router.post("/invoices")
async def create_invoice(body: InvoiceIn, user=Depends(require("admin"))):
    st = await db.students.find_one({"id": body.student_id}, {"_id": 0})
    if not st: raise HTTPException(404, "Student not found")
    s = await get_settings()
    doc = await make_invoice(st, [i.model_dump() for i in body.items], body.due_date, body.discount, body.discount_reason, body.academic_year or s["academic_year"], user)
    await audit(user, "create", "invoices", doc["id"], {"total": doc["total"], "discount": body.discount})
    return clean(doc)

class GenerateIn(BaseModel):
    structure_id: str
    section: str = ""

@router.post("/invoices/generate")
async def generate(body: GenerateIn, user=Depends(require("admin"))):
    fs = await db.fee_structures.find_one({"id": body.structure_id, "archived": {"$ne": True}}, {"_id": 0})
    if not fs: raise HTTPException(404, "Fee structure not found")
    q = {"status": "active", "archived": {"$ne": True}}
    if fs["class_id"] != "all": q["class_id"] = fs["class_id"]
    if body.section: q["section"] = body.section
    if fs["fee_type"] == "Transport": q["transport.route_id"] = {"$exists": True, "$ne": None}
    created = skipped = 0
    for st in await db.students.find(q, {"_id": 0}).to_list(5000):
        if await db.invoices.find_one({"student_id": st["id"], "structure_id": fs["id"], "status": {"$ne": "void"}}): skipped += 1; continue
        await make_invoice(st, [{"name": fs["name"], "amount": fs["amount"]}], fs["due_date"], 0, "", fs["academic_year"], user, fs["id"]); created += 1
    await audit(user, "generate_invoices", "invoices", None, {"structure": fs["name"], "created": created, "skipped": skipped})
    return {"created": created, "skipped_existing": skipped}

class AdjustIn(BaseModel):
    discount: Optional[float] = Field(None, ge=0)
    discount_reason: str = ""
    apply_late_fee: bool = False
    void: bool = False

@router.post("/invoices/{iid}/adjust")
async def adjust(iid: str, body: AdjustIn, user=Depends(require("admin"))):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv: raise HTTPException(404, "Invoice not found")
    if body.void:
        if inv["paid"] > 0: raise HTTPException(409, "Cannot void an invoice with payments; refund payments first")
        await db.invoices.update_one({"id": iid}, {"$set": {"status": "void"}}); await audit(user, "void", "invoices", iid)
        return {"ok": True}
    disc = inv["discount"] if body.discount is None else body.discount
    late = inv["late_fee"]
    if body.apply_late_fee:
        if inv["late_fee"] > 0: raise HTTPException(409, "Late fee already applied")
        if inv["due_date"] >= await today() or inv["status"] == "paid": raise HTTPException(409, "Late fee applies only to overdue invoices")
        late = (await get_settings())["late_fee_amount"]
    total = round(inv["subtotal"] - disc + late, 2)
    if total < inv["paid"]: raise HTTPException(422, "New total would be less than the amount already paid")
    await db.invoices.update_one({"id": iid}, {"$set": {"discount": disc, "discount_reason": body.discount_reason or inv.get("discount_reason", ""), "late_fee": late, "total": total,
                                                         "balance": round(total - inv["paid"], 2), "status": status_of(total, inv["paid"])}})
    await audit(user, "adjust", "invoices", iid, {"discount": [inv["discount"], disc], "late_fee": [inv["late_fee"], late]})
    return {"ok": True}

# ---- payments ----
class PaymentIn(BaseModel):
    invoice_id: str
    amount: float = Field(gt=0)
    method: str
    reference: str = ""
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: str = ""

async def record_payment(inv_id, amount, method, reference, date, user_id, gateway=None, gateway_ref=None):
    amount = round(amount, 2)
    inv = await db.invoices.find_one_and_update({"id": inv_id, "balance": {"$gte": amount - 0.001}, "status": {"$ne": "void"}},
                                                 {"$inc": {"paid": amount, "balance": -amount}}, return_document=True)
    if not inv: raise HTTPException(409, "Amount exceeds the outstanding balance")
    await db.invoices.update_one({"id": inv_id}, {"$set": {"status": status_of(inv["total"], inv["paid"])}})
    yr = date[:4]
    pay = {"id": new_id(), "receipt_no": await next_seq(f"rcpt{yr}", f"RCPT{yr}-", 6), "invoice_id": inv_id, "invoice_no": inv["invoice_no"], "student_id": inv["student_id"],
           "student_name": inv["student_name"], "admission_no": inv["admission_no"], "class_id": inv["class_id"], "class_name": inv.get("class_name"), "amount": amount,
           "method": method, "reference": reference, "date": date, "status": "success", "gateway": gateway, "gateway_ref": gateway_ref, "recorded_by": user_id, "created_at": now_iso()}
    await db.payments.insert_one(dict(pay))
    st = await db.students.find_one({"id": inv["student_id"]}, {"_id": 0, "parent_ids": 1, "id": 1})
    uids = [u["id"] for u in await db.users.find({"$or": [{"profile_id": st["id"], "role": "student"}, {"profile_id": {"$in": st.get("parent_ids", [])}, "role": "parent"}]}, {"_id": 0, "id": 1}).to_list(10)]
    await notify(uids, f"Payment received: ₹{amount:,.2f}", f"Receipt {pay['receipt_no']} for invoice {inv['invoice_no']}", "/fees")
    return clean(pay)

@router.post("/payments")
async def add_payment(body: PaymentIn, user=Depends(require("admin"))):
    s = await get_settings()
    if body.method not in s["payment_methods"]: raise HTTPException(422, "Payment method is not enabled")
    if body.date > await today(): raise HTTPException(422, "Payment date cannot be in the future")
    pay = await record_payment(body.invoice_id, body.amount, body.method, body.reference, body.date, user["id"])
    await audit(user, "record_payment", "payments", pay["id"], {"amount": body.amount, "invoice": pay["invoice_no"]})
    return pay

@router.get("/payments")
async def list_payments(q: str = "", method: str = "", status: str = "", class_id: str = "", date_from: str = "", date_to: str = "", page: int = 1, page_size: int = 20, user=Depends(get_current_user)):
    query = {"$and": [await inv_scope(user)]}
    for k, v in (("method", method), ("status", status), ("class_id", class_id)):
        if v: query["$and"].append({k: v})
    if date_from or date_to: query["$and"].append({"date": {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}})
    if q: query["$and"].append({"$or": [{f: {"$regex": re.escape(q), "$options": "i"}} for f in ("receipt_no", "student_name", "invoice_no")]})
    res = await paginate(db.payments, query, page, page_size, "-created_at")
    agg = [x async for x in db.payments.aggregate([{"$match": {**query, "$and": query["$and"] + [{"status": "success"}]}}, {"$group": {"_id": None, "sum": {"$sum": "$amount"}}}])]
    res["sum"] = agg[0]["sum"] if agg else 0
    return res

@router.get("/payments/{pid}/receipt")
async def receipt(pid: str, user=Depends(get_current_user)):
    p = await db.payments.find_one({"$and": [{"id": pid}, await inv_scope(user)]}, {"_id": 0})
    if not p: raise HTTPException(404, "Receipt not found")
    inv = await db.invoices.find_one({"id": p["invoice_id"]}, {"_id": 0})
    s = await get_settings()
    return {"payment": p, "invoice": inv_view(inv, await today()), "school": {k: s[k] for k in ("school_name", "address", "phone", "email", "logo_file_id", "receipt_footer", "currency_symbol")}}

@router.post("/payments/{pid}/refund")
async def refund(pid: str, user=Depends(require("admin"))):
    p = await db.payments.find_one_and_update({"id": pid, "status": "success"}, {"$set": {"status": "refunded", "refunded_at": now_iso()}})
    if not p: raise HTTPException(409, "Payment not found or already refunded")
    inv = await db.invoices.find_one_and_update({"id": p["invoice_id"]}, {"$inc": {"paid": -p["amount"], "balance": p["amount"]}}, return_document=True)
    await db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": status_of(inv["total"], inv["paid"])}})
    await audit(user, "refund", "payments", pid, {"amount": p["amount"], "gateway": p.get("gateway")})
    return {"ok": True, "note": "Recorded as refunded. Gateway refunds must also be issued in the provider dashboard." if p.get("gateway") else "Recorded as refunded."}

# ---- online payment gateways ----
def rzp_ok(): return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))
def cf_ok(): return bool(os.environ.get("CASHFREE_CLIENT_ID") and os.environ.get("CASHFREE_CLIENT_SECRET"))
CF_BASE = lambda: "https://api.cashfree.com/pg" if os.environ.get("CASHFREE_ENV") == "production" else "https://sandbox.cashfree.com/pg"

@router.get("/payments-config")
async def providers(user=Depends(get_current_user)):
    return {"razorpay": rzp_ok(), "cashfree": cf_ok(), "razorpay_key_id": os.environ.get("RAZORPAY_KEY_ID") if rzp_ok() else None,
            "cashfree_mode": "production" if os.environ.get("CASHFREE_ENV") == "production" else "sandbox"}

class OnlineIn(BaseModel):
    invoice_id: str
    amount: Optional[float] = Field(None, gt=0)
    origin_url: str = ""

async def payable(user, body):
    if user["role"] not in ("parent", "student", "admin"): raise HTTPException(403, "Not permitted")
    inv = await db.invoices.find_one({"$and": [{"id": body.invoice_id}, await inv_scope(user)]}, {"_id": 0})
    if not inv or inv["status"] in ("paid", "void"): raise HTTPException(404, "Invoice is not payable")
    amt = round(body.amount or inv["balance"], 2)
    if amt > inv["balance"] + 0.001: raise HTTPException(422, "Amount exceeds the outstanding balance")
    return inv, amt

async def settle_order(order_id, gateway_ref):
    o = await db.payment_orders.find_one_and_update({"order_id": order_id, "status": {"$nin": ["paid"]}}, {"$set": {"status": "paid", "gateway_ref": gateway_ref, "paid_at": now_iso()}})
    if not o: return None
    pay = await record_payment(o["invoice_id"], o["amount"], f"Online ({o['gateway'].title()})", gateway_ref, (await today()), o["user_id"], o["gateway"], gateway_ref)
    await db.payment_orders.update_one({"order_id": order_id}, {"$set": {"payment_id": pay["id"]}})
    return pay

@router.post("/payments/razorpay/order")
async def rzp_order(body: OnlineIn, user=Depends(get_current_user)):
    if not rzp_ok(): raise HTTPException(503, "Razorpay is not configured yet")
    inv, amt = await payable(user, body)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post("https://api.razorpay.com/v1/orders", auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]),
                         json={"amount": int(round(amt * 100)), "currency": "INR", "receipt": inv["invoice_no"][:40], "notes": {"invoice_id": inv["id"]}})
    if r.status_code >= 400: logger.error(f"razorpay order failed {r.status_code}"); raise HTTPException(502, "Could not start Razorpay payment")
    o = r.json()
    await db.payment_orders.insert_one({"order_id": o["id"], "gateway": "razorpay", "invoice_id": inv["id"], "amount": amt, "user_id": user["id"], "status": "created", "created_at": now_iso()})
    return {"order_id": o["id"], "amount": o["amount"], "currency": "INR", "key_id": os.environ["RAZORPAY_KEY_ID"], "invoice_no": inv["invoice_no"], "name": inv["student_name"]}

class RzpVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

@router.post("/payments/razorpay/verify")
async def rzp_verify(body: RzpVerifyIn, user=Depends(get_current_user)):
    if not rzp_ok(): raise HTTPException(503, "Razorpay is not configured")
    exp = hmac.new(os.environ["RAZORPAY_KEY_SECRET"].encode(), f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(exp, body.razorpay_signature): raise HTTPException(400, "Payment signature verification failed")
    o = await db.payment_orders.find_one({"order_id": body.razorpay_order_id, "user_id": user["id"]})
    if not o: raise HTTPException(404, "Order not found")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"https://api.razorpay.com/v1/payments/{body.razorpay_payment_id}", auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))
    p = r.json() if r.status_code < 400 else {}
    if p.get("order_id") != body.razorpay_order_id or p.get("status") not in ("captured", "authorized") or p.get("amount") != int(round(o["amount"] * 100)):
        await db.payment_orders.update_one({"order_id": o["order_id"], "status": {"$ne": "paid"}}, {"$set": {"status": "pending_verification"}})
        return {"status": "pending", "message": "Payment not yet confirmed by Razorpay. It will update automatically once confirmed."}
    pay = await settle_order(body.razorpay_order_id, body.razorpay_payment_id)
    return {"status": "paid", "receipt_no": pay["receipt_no"] if pay else None}

@router.post("/webhooks/razorpay")
async def rzp_webhook(request: Request):
    raw = await request.body(); sec = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not sec or not hmac.compare_digest(hmac.new(sec.encode(), raw, hashlib.sha256).hexdigest(), sig): raise HTTPException(400, "Invalid signature")
    ev = json.loads(raw); et = ev.get("event", "")
    ent = ev.get("payload", {}).get("payment", {}).get("entity", {})
    if et in ("payment.captured", "order.paid") and ent.get("order_id"): await settle_order(ent["order_id"], ent.get("id"))
    elif et == "payment.failed" and ent.get("order_id"): await db.payment_orders.update_one({"order_id": ent["order_id"], "status": {"$ne": "paid"}}, {"$set": {"status": "failed"}})
    elif et.startswith("refund."):
        pid = ev.get("payload", {}).get("refund", {}).get("entity", {}).get("payment_id")
        if pid: await db.payments.update_one({"gateway_ref": pid}, {"$set": {"gateway_refund_status": et}})
    return {"ok": True}

def cf_headers(idem=None):
    h = {"Content-Type": "application/json", "x-client-id": os.environ["CASHFREE_CLIENT_ID"], "x-client-secret": os.environ["CASHFREE_CLIENT_SECRET"],
         "x-api-version": "2025-01-01", "x-request-id": str(uuid.uuid4())}
    if idem: h["x-idempotency-key"] = idem
    return h

@router.post("/payments/cashfree/order")
async def cf_order(body: OnlineIn, user=Depends(get_current_user)):
    if not cf_ok(): raise HTTPException(503, "Cashfree is not configured yet")
    inv, amt = await payable(user, body)
    if not body.origin_url.startswith("https://"): raise HTTPException(422, "Invalid origin")
    oid = f"fee_{inv['id'][:12]}_{uuid.uuid4().hex[:10]}"
    st = await db.students.find_one({"id": inv["student_id"]}, {"_id": 0})
    phone = re.sub(r"\D", "", st.get("guardian_phone") or "")[-10:] or "9999999999"
    payload = {"order_id": oid, "order_amount": amt, "order_currency": "INR",
               "customer_details": {"customer_id": inv["student_id"][:40], "customer_name": st.get("guardian_name") or st["name"], "customer_email": user["email"], "customer_phone": phone},
               "order_meta": {"return_url": f"{body.origin_url.rstrip('/')}/payment-result?gateway=cashfree&order_id={oid}"}, "order_note": f"Invoice {inv['invoice_no']}"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{CF_BASE()}/orders", headers=cf_headers(oid), json=payload)
    if r.status_code >= 400: logger.error(f"cashfree order failed {r.status_code} {r.text[:200]}"); raise HTTPException(502, "Could not start Cashfree payment")
    await db.payment_orders.insert_one({"order_id": oid, "gateway": "cashfree", "invoice_id": inv["id"], "amount": amt, "user_id": user["id"], "status": "created", "created_at": now_iso()})
    return {"order_id": oid, "payment_session_id": r.json()["payment_session_id"]}

@router.get("/payments/order-status/{order_id}")
async def order_status(order_id: str, user=Depends(get_current_user)):
    o = await db.payment_orders.find_one({"order_id": order_id, "user_id": user["id"]}, {"_id": 0})
    if not o: raise HTTPException(404, "Order not found")
    if o["status"] != "paid" and o["gateway"] == "cashfree" and cf_ok():
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{CF_BASE()}/orders/{order_id}", headers=cf_headers())
        cs = r.json().get("order_status") if r.status_code < 400 else None
        if cs == "PAID":
            async with httpx.AsyncClient(timeout=20) as c:
                pr = await c.get(f"{CF_BASE()}/orders/{order_id}/payments", headers=cf_headers())
            ok = [p for p in (pr.json() if pr.status_code < 400 else []) if p.get("payment_status") == "SUCCESS"]
            await settle_order(order_id, str(ok[0]["cf_payment_id"]) if ok else order_id)
        elif cs in ("EXPIRED", "TERMINATED"): await db.payment_orders.update_one({"order_id": order_id}, {"$set": {"status": "failed"}})
        o = await db.payment_orders.find_one({"order_id": order_id}, {"_id": 0})
    pay = await db.payments.find_one({"id": o.get("payment_id")}, {"_id": 0}) if o.get("payment_id") else None
    return {"order_id": order_id, "status": o["status"], "amount": o["amount"], "receipt_no": pay["receipt_no"] if pay else None, "payment_id": pay["id"] if pay else None}

@router.post("/webhooks/cashfree")
async def cf_webhook(request: Request):
    if not cf_ok(): raise HTTPException(503, "Not configured")
    raw = await request.body(); ts = request.headers.get("x-webhook-timestamp", ""); sig = request.headers.get("x-webhook-signature", "")
    exp = base64.b64encode(hmac.new(os.environ["CASHFREE_CLIENT_SECRET"].encode(), ts.encode() + raw, hashlib.sha256).digest()).decode()
    if not ts or not hmac.compare_digest(exp, sig): raise HTTPException(400, "Invalid signature")
    data = json.loads(raw).get("data", {}); oid = data.get("order", {}).get("order_id"); p = data.get("payment", {})
    if oid and p.get("payment_status") == "SUCCESS": await settle_order(oid, str(p.get("cf_payment_id")))
    elif oid and p.get("payment_status") in ("FAILED", "USER_DROPPED"): await db.payment_orders.update_one({"order_id": oid, "status": {"$ne": "paid"}}, {"$set": {"status": "failed"}})
    return {"ok": True}
