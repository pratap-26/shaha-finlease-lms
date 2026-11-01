@'
# Shaha Finlease - Loan Management System

A role-based Loan Management System built using FastAPI, SQLAlchemy, SQLite, HTML, CSS and JavaScript.

## Features

- Role-based authentication: Caller, Manager and Head
- Secure password hashing and session-based authentication
- Dashboard with portfolio KPIs and distributions
- Account portfolio with search, filtering and pagination
- Account-level customer workspace
- Call logging and follow-up tracking
- Promise to Pay (PTP) recording and status management
- Payment recording and payment history
- Account allocation and allocation history
- Role-based account visibility

## Technology Stack

- Backend: Python, FastAPI
- Database: SQLite, SQLAlchemy
- Frontend: HTML, CSS, JavaScript
- Authentication: Argon2 password hashing, signed sessions
- API documentation: Swagger UI

## Project Structure

```text
shaha_lms/
├── app/
│   ├── routers/
│   ├── static/
│   ├── templates/
│   ├── models.py
│   ├── database.py
│   ├── auth.py
│   └── main.py
├── data/
├── tests/
├── init_db.py
├── seed_data.py
├── allocate_accounts.py
├── provision_demo_users.py
├── requirements.txt
└── README.md