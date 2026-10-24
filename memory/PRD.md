# PRD — EduPrime School Management System

## Original problem statement
"Create a modern, professional, premium-looking School Management System (SMS)… Admin Dashboard and separate role-based dashboards for Teachers, Students, and Parents… real authentication, database persistence, working CRUD operations, role-based permissions…" The full brief covers 26 sections: auth, admin dashboard, students, staff, classes/subjects, attendance, timetable, exams/results/report cards, fees/payments (Razorpay), homework, library, transport, notifications/announcements, parent/student/teacher portals, calendar, leave, reports, settings, sidebar, DB design, security, testing and deliverables.

User choices: payment providers Razorpay + Cashfree + Stripe (Stripe sandbox isn't available in India, so it was not built). Emergent managed email (Resend). Build everything in one go. Currency INR.

## Architecture
- FastAPI (`/app/backend`): core.py (db, auth/JWT cookies, RBAC, scoping, generic CRUD, audit, notify, email, object storage), routes_auth, routes_people, routes_academic, routes_exams, routes_fees, routes_misc, routes_dash, seed.py, server.py (middleware for rate limits and CSRF origin checks, indexes, seeding)
- MongoDB with unique indexes. Demo data is flagged `demo: true` and can be removed in Settings.
- React (CRA, Tailwind, shadcn): config-driven CrudPage/FormDialog/DataTable, role-based nav and routes, light/dark mode

## Personas
School admin · Teacher · Student · Parent

## Implemented (2026-10-24)
- Auth: login, remember me, show/hide password, forgot/reset by email, change password, refresh tokens, lockout, rate limit, session expiry, admin user management (activate/deactivate, reset)
- Admin dashboard with live stats and charts, quick actions and activity feed
- Students: auto admission numbers, CRUD/archive/restore, filters, CSV import/export, promote, section transfer, profile, ID card, history
- Teachers/staff with employee IDs (salary visible to admins only); parents linked to children; portal login creation
- Classes and sections (capacity, class teacher), subjects, teacher assignments, academic years
- Attendance: bulk marking, corrections history, summaries and low-attendance flags, staff attendance, printing
- Timetable grid with teacher, room and assignment conflict checks; class and teacher views
- Exams: setup, marks entry (draft/submit, validation, correction log), publishing, results and ranks, printable report cards with attendance and remarks
- Fees: structures, bulk invoice generation, ad-hoc invoices, partial payments, receipts, discounts, late fee, void, refund. Razorpay and Cashfree with server-side verification and webhooks (inactive until keys are added)
- Homework with attachments, submissions and grading; library with issue/return and fines; transport (vehicles, routes, stops, capacity, history)
- Calendar (events, exams, deadlines), leave workflow that auto-excuses attendance, announcements plus in-app notifications, reports (15 types, CSV and print), audit logs, settings, JSON backup

## Backlog
- P0: Add Razorpay/Cashfree keys and register the webhooks
- P1: shadcn date pickers, SMS/WhatsApp provider, weighted multi-exam final results, attendance by term
- P2: multi-school tenancy, PDF generation on the server, parent self-service fee reminders
