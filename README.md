# EduPrime School Management System

Full-stack SMS: React (CRA + Tailwind + shadcn/ui) frontend, FastAPI backend, MongoDB.

## Portals
Admin, Teacher, Student, Parent — role-based routes in the UI and server-side authorization on every API endpoint.

## Setup
- Backend env (`backend/.env`): `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `EMERGENT_EMAIL_KEY`, `EMAIL_FROM_NAME`, `EMERGENT_LLM_KEY` (object storage), `APP_NAME`,
  optional `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `CASHFREE_CLIENT_ID`, `CASHFREE_CLIENT_SECRET`, `CASHFREE_ENV` (sandbox|production).
- Frontend env: `REACT_APP_BACKEND_URL`.
- Start: `uvicorn server:app --port 8001` and `yarn start`.

## Database
Unique indexes are created on startup (`server.py`). Demo seed data (`seed.py`) is inserted once, flagged `demo: true`, removable from Settings → Data.

## Payments
Razorpay / Cashfree once keys are set. Invoices update only after server-side verification (signature + gateway lookup, or signed webhook).
Webhooks: `POST /api/webhooks/razorpay`, `POST /api/webhooks/cashfree`.

## Notes
- MongoDB standalone has no multi-document transactions; multi-record operations use atomic conditional updates.
- SMS / WhatsApp / GPS are not configured and are shown as such.
