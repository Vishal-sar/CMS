# PRD — EduPrime School Management System

## Original problem statement
"Create a modern, professional, premium-looking School Management System (SMS)… Admin Dashboard and separate role-based dashboards for Teachers, Students, and Parents… real authentication, database persistence, working CRUD operations, role-based permissions…" The full 26-section brief covers auth, dashboard, students, staff, classes, attendance, timetable, exams, fees/payments, homework, library, transport, communication, portals, calendar, leave, reports, settings, security and deliverables.
Follow-up (2026-10-24): "Create account option add karo" · Turn on Razorpay/Cashfree payments · Fee reminder emails before the due date and when overdue.

User choices: Razorpay + Cashfree (Stripe isn't supported in India). Emergent managed email. Build everything at once. Currency INR.

## Architecture
FastAPI modules: core, routes_auth, routes_people, routes_academic, routes_exams, routes_fees, routes_misc, routes_dash, routes_reminders, seed, server.
Data is stored in MongoDB. The frontend is React with Tailwind and shadcn. A platform cron is defined in `.emergent/crons.yml`.

## Personas
Admin · Teacher · Student · Parent

## Implemented
- 2026-10-24: full MVP across all modules (see the README). Tested in iterations 1 and 2.
- 2026-10-24: self sign-up at /signup. New accounts stay pending until an admin approves them and links them to a profile; admins can also reject requests. Account requests notify admins, and approval emails the user.
- 2026-10-24: fee reminders. A cron runs daily at 09:00 IST (`/api/cron/fee-reminders`, Bearer WEBHOOK_CRON_SECRET), and admins can also run it with "Send now". It sends one "due soon" reminder (N days before, configurable) and one "overdue" reminder per invoice, by email and in-app. Failed emails are retried on the next run, and students who are not active are skipped. Tested in iteration 3.
- Razorpay/Cashfree code is ready. It is waiting for keys.

## Backlog
- P0: add Razorpay/Cashfree keys and register the webhooks
- P1: repeat reminders for overdue invoices (e.g. weekly), shadcn date pickers, SMS/WhatsApp
- P2: multi-school support, PDFs generated on the server
