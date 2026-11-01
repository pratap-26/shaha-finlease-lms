# Shaha Finlease — Loan Management System

A demo-ready collections and recovery prototype built with FastAPI, SQLAlchemy, SQLite, server-rendered HTML, CSS and JavaScript.

## Scope and assumptions

This prototype starts with already-purchased written-off/NPA accounts. Loan origination, disbursement, portfolio purchase/costing and post-settlement workflows are outside the assessment scope. All supplied records are dummy data.

- Caller: can view and work only accounts allocated to them.
- Manager: can view their direct team's accounts and allocate within their office.
- Head of Collections: can view accounts across all offices and allocate within an office.
- Account `outstanding` is the loaded recovery target and is not reduced when a payment is recorded. The payment ledger stores receipts; status is derived as `Part-paid` or `Closed` against the loaded outstanding.
- CSV imports accept up to 100,000 data rows per upload. Duplicate loan numbers are skipped; invalid rows are reported.
- A pending PTP becomes `Broken` after its promised date if sufficient payment was not recorded by the promised date. If the promised amount was received by then, it becomes `Kept`.
- Bulk allocation is limited to 1,000 selected accounts per request. All selected accounts must belong to the target caller's office.

## Features

- Hashed-password login and signed session authentication
- Server-side role and office access controls
- CSV account import (up to 100,000 rows)
- Account search by customer, phone or loan number; status filtering and pagination
- Caller queue prioritisation for due/overdue follow-ups and promises
- Account workspace with call, PTP, payment and allocation history
- Call logging with disposition, remarks and next follow-up
- Promise-to-pay tracking and overdue status evaluation
- Payment ledger and recovery status calculation
- Single and bulk account allocation with reassignment history
- Role-scoped dashboard KPIs and portfolio distributions

## Technology

- Python 3.10+
- FastAPI and Uvicorn
- SQLAlchemy 2.x
- SQLite (local demo)
- Jinja2, HTML, CSS and vanilla JavaScript
- Argon2 password hashing and signed sessions

## Setup (Windows PowerShell)

Run these commands from the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` in the project root:

```text
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///./shaha_lms.db
```

Use a long random secret for any shared/demo deployment. Never commit `.env`.

Initialise and seed the local demo database:

```powershell
python init_db.py
python seed_data.py
python provision_demo_users.py
```

The seed script intentionally refuses to append duplicate users/accounts to an existing database. Do not run it against a database containing records you need to preserve.

Start the application:

```powershell
uvicorn app.main:app --reload
```

Open:
- Application: http://127.0.0.1:8000/login
- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

`provision_demo_users.py` prints one demo username/password for each supported role when the password is first created. Save those credentials securely; the script does not reset existing passwords.

## CSV upload format

Use a UTF-8 CSV with these required columns:

`loan_no, customer_name, mobile, office, product, original_amount, outstanding`

The full sample schema is in `data/accounts.csv`. Office values must match the seeded offices: `Jogeshwari`, `Dadar`, or `Bangalore`. Managers may upload only accounts for their own office; Head of Collections may upload for any seeded office.

## Suggested 10-minute demo

1. Log in as Head of Collections and show the cross-office dashboard.
2. Upload a CSV sample (or use the seeded 10,000-account portfolio).
3. Open Accounts, select multiple accounts from one office and bulk-allocate them to a caller.
4. Log in as that caller and show the caller-only portfolio/priority queue.
5. Open an account, save a call disposition and follow-up date.
6. Record a Promise to Pay and show its history.
7. Record a partial payment; show that loaded outstanding remains unchanged while total paid increases and status becomes `Part-paid`.
8. Record enough additional payment to meet the loaded outstanding; show status becomes `Closed`.
9. Log back in as Manager/Head and show role-scoped reporting and allocation history.

## Security and demo notes

- Passwords are stored as Argon2 hashes.
- API routes enforce session authentication and role/account visibility on the server.
- The local SQLite database, virtual environment and `.env` are excluded from Git.
- This is an assessment prototype, not a production collections platform. Production deployment would require HTTPS, managed secrets, database backups, audit/monitoring controls, stronger concurrent-payment protections and operational security review.
