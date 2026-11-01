# Shaha Finlease — Loan Management System

A role-based Loan Management System (LMS) prototype designed to streamline loan recovery operations, portfolio management and collection workflows at Shaha Finlease.

Built using **FastAPI, SQLAlchemy, SQLite, HTML, CSS and JavaScript**, the application provides a centralised workspace for managing acquired stressed-loan portfolios across multiple offices.

---

## 1. Project Overview

Unlike conventional banking LMS platforms focused on loan origination and disbursement, this system addresses the post-acquisition recovery lifecycle.

The application supports the management of written-off and Non-Performing Asset (NPA) portfolios, enabling collection teams to track customer accounts, allocate recovery responsibilities, record interactions, manage payment commitments and monitor collections.

The prototype supports three operational roles across three offices:

- **Head of Collections:** Organisation-wide portfolio visibility and oversight.
- **Manager:** Office-scoped portfolio management and caller allocation.
- **Caller:** Access to assigned accounts, customer interactions and recovery activities.

**Project scope:** The system starts with already-acquired loan portfolios. Portfolio acquisition, purchase-cost calculations, loan origination, disbursement and post-settlement workflows are outside the current scope.

## 2. Key Features

### Authentication and Access Control
- Secure login with Argon2 password hashing.
- Signed session-based authentication.
- Server-side role-based and office-level access restrictions.
- Callers can access only their assigned accounts.
- Managers can access accounts within their office and manage their teams.
- Head of Collections has cross-office visibility.

### Portfolio Management
- CSV-based account ingestion supporting up to 100,000 data rows per upload.
- Account search by customer name, mobile number or loan number.
- Status filtering and paginated account listings.
- Duplicate loan-number detection and invalid-row reporting.
- Account records containing customer, loan, office and outstanding-balance information.

### Account Allocation
- Individual and bulk account allocation to callers.
- Office-level allocation validation.
- Allocation and reassignment history.
- Recording of allocation reasons and ownership changes.

### Collections Workspace
- Caller-specific account queue.
- Prioritisation of due and overdue follow-ups and payment promises.
- Customer account overview.
- Consolidated call, PTP, payment and allocation histories.

### Call Management
- Record call dispositions and remarks.
- Schedule the next follow-up date.
- Maintain a chronological interaction history.

### Promise to Pay (PTP)
- Record promised payment amounts and dates.
- Track pending, kept and broken promises.
- Evaluate overdue promises against recorded payments when relevant PTP or portfolio data is accessed.

### Payment Management
- Record payments with transaction references and remarks.
- Maintain a separate payment ledger.
- Preserve the originally loaded outstanding amount.
- Calculate total payments received.
- Update account recovery status based on payment progress.

### Dashboard and Reporting
- Role-scoped dashboard.
- Total account and outstanding-balance summaries.
- Payment recovery and call activity metrics.
- Account-status distribution.
- Office-wise portfolio distribution.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| ORM / Database Layer | SQLAlchemy 2.x |
| Database | SQLite |
| Frontend | HTML5, CSS3, JavaScript |
| Templating | Jinja2 |
| Authentication | Argon2, signed sessions |
| Application Server | Uvicorn |

The application uses server-rendered pages and vanilla JavaScript to keep the frontend lightweight and straightforward to maintain.

## 4. Architecture and Project Structure

```text
shaha-finlease-lms/
│
├── app/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── config.py
│   ├── auth.py
│   ├── permissions.py
│   │
│   ├── routers/
│   │   ├── auth.py
│   │   ├── accounts.py
│   │   ├── allocations.py
│   │   ├── call_logs.py
│   │   ├── dashboard.py
│   │   ├── imports.py
│   │   ├── payments.py
│   │   └── ptp.py
│   │
│   ├── templates/
│   └── static/
│       ├── css/
│       └── js/
│
├── data/
├── requirements.txt
├── init_db.py
├── seed_data.py
├── provision_demo_users.py
├── allocate_accounts.py
├── inspect_data.py
├── README.md
└── .gitignore
```

**Core database entities:**

- Office
- User
- Account
- AllocationHistory
- CallLog
- PTP
- Payment

The backend is organised into modular API routers, while SQLAlchemy models manage the underlying relational data.

## 5. Local Installation and Setup

### Prerequisites

- Python 3.10 or later
- pip
- Git

### Step 1 — Clone the repository

```powershell
git clone https://github.com/pratap-26/shaha-finlease-lms.git
cd shaha-finlease-lms
```

### Step 2 — Create and activate a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3 — Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4 — Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-long-random-secret-key
DATABASE_URL=sqlite:///./shaha_lms.db
```

Generate a secure secret key using:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Replace the placeholder with the generated value.

**Important:** Keep `.env` private. Never commit credentials, secret keys or local database files to version control.

### Step 5 — Initialise the database

```powershell
python init_db.py
```

### Step 6 — Populate demo data and provision users

```powershell
python seed_data.py
python provision_demo_users.py
```

The seed process creates the initial demo portfolio and organisational structure. The provisioning script generates demo login credentials when passwords are first created.

Save the generated credentials securely.

**Note:** The seed script is intended for initial database setup. Do not run it against an existing database containing records you need to preserve; it is not an in-place reset operation.

### Step 7 — Start the application

```powershell
uvicorn app.main:app --reload
```

The application will be available locally.

## 6. Application Endpoints

| Resource | URL |
|---|---|
| Login | http://127.0.0.1:8000/login |
| Dashboard | http://127.0.0.1:8000/dashboard |
| Account Portfolio | http://127.0.0.1:8000/portfolio |
| API Documentation | http://127.0.0.1:8000/docs |
| Health Check | http://127.0.0.1:8000/health |

FastAPI's interactive Swagger interface is available at `/docs`.

## 7. CSV Import Specification

The portfolio import endpoint accepts UTF-8 CSV files.

Required columns:

```text
loan_no
customer_name
mobile
office
product
original_amount
outstanding
```

Supported office values:

- Jogeshwari
- Dadar
- Bangalore

**Import constraints:**
- Maximum 100,000 data rows per upload.
- Maximum upload size: 50 MB.
- Duplicate loan numbers are skipped.
- Invalid records are reported.
- Managers can import accounts only for their own office.
- Head of Collections can import accounts across offices.

Additional CSV columns may be included where supported by the importer.

## 8. Business Rules and Assumptions

The following rules govern the prototype:

1. Accounts represent already-acquired recovery portfolios.
2. Each account has an assigned owner, subject to role-based visibility.
3. Account ownership changes are recorded in allocation history.
4. The loaded outstanding balance represents the recovery target and is not reduced when payments are recorded.
5. Payments are maintained separately in the payment ledger.
6. Account recovery status reflects payment progress against the loaded outstanding amount.
7. A PTP is evaluated as Kept or Broken based on its promised date and recorded payments when relevant data is accessed. The prototype does not run a separate scheduled background job.
8. Bulk allocation supports up to 1,000 accounts per request.
9. Manager-level access is restricted to the manager's office.
10. The application uses SQLite for local demonstration and can be adapted to a production database.

## 9. Suggested Demonstration Workflow

The following sequence demonstrates the end-to-end recovery lifecycle:

| Stage | Demonstration |
|---|---|
| 1. Authentication | Log in as Head of Collections and show cross-office visibility. |
| 2. Portfolio ingestion | Import a CSV portfolio and demonstrate the upload result. |
| 3. Allocation | Log in as Manager and bulk-allocate accounts to a caller. |
| 4. Caller workflow | Log in as Caller and view the assigned account queue. |
| 5. Customer interaction | Open an account and record a call disposition, remarks and follow-up date. |
| 6. Payment commitment | Create a Promise to Pay with an amount and due date. |
| 7. Payment collection | Record a partial payment and demonstrate the updated recovery status. |
| 8. Verification | Show payment history, allocation history and role-specific visibility. |

## 10. Future Enhancements

Potential improvements beyond the current prototype include:

- PostgreSQL deployment for production-scale concurrent operations.
- Automated background jobs for PTP expiry and scheduled follow-ups.
- Advanced collection analytics and recovery-performance reporting.
- Audit trails and enhanced operational monitoring.
- Role-specific performance dashboards.
- Payment gateway and external agency integrations.
- Deployment with HTTPS, managed secrets and automated backups.

## 11. Limitations and Security Considerations

This project is an assessment prototype and is not intended for direct production deployment.

Although it implements password hashing, signed sessions and server-side access controls, a production deployment would require additional security and operational safeguards, including:

- HTTPS and secure cookie configuration.
- Managed secret storage and credential rotation.
- Database backup and recovery procedures.
- Comprehensive audit logging.
- Stronger transaction and concurrent-payment controls.
- Automated background processing.
- Security testing and deployment hardening.

---

**Shaha Finlease LMS**  
*Loan Recovery | Portfolio Management | Collections Operations*

Developed as a functional prototype demonstrating a centralised, role-based loan recovery management workflow.