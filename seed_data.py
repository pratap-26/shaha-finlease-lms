
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app.models import Account, Office, User


DATA_DIR = Path(__file__).resolve().parent / "data"

OFFICE_NAMES = ("Jogeshwari", "Dadar", "Bangalore")


def read_csv(filename):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def parse_date(value):
    if not value or not value.strip():
        return None
    return date.fromisoformat(value.strip())


def parse_money(value, field_name):
    try:
        amount = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid {field_name}: {value!r}")

    if not amount.is_finite():
        raise ValueError(f"Invalid {field_name}: {value!r}")

    if amount < 0:
        raise ValueError(f"Negative {field_name}: {value!r}")

    return amount.quantize(Decimal("0.01"))


def seed_database():
    users_data = read_csv("users.csv")
    accounts_data = read_csv("accounts.csv")

    if not users_data or not accounts_data:
        raise ValueError("Both CSV files must contain records.")

    # Validate that source identifiers and loan numbers are unique.
    user_codes = [row["user_id"].strip() for row in users_data]
    loan_numbers = [row["loan_no"].strip() for row in accounts_data]

    if len(user_codes) != len(set(user_codes)):
        raise ValueError("Duplicate user_id found in users.csv.")

    if len(loan_numbers) != len(set(loan_numbers)):
        raise ValueError("Duplicate loan_no found in accounts.csv.")

    with SessionLocal() as db:
        # Do not accidentally append duplicate seed data on reruns.
        existing_users = db.scalar(select(func.count()).select_from(User))
        existing_accounts = db.scalar(
            select(func.count()).select_from(Account)
        )

        if existing_users or existing_accounts:
            raise RuntimeError(
                "Seed cancelled: users or accounts already exist. "
                "Do not delete data manually; use the reset workflow "
                "we will implement separately."
            )

        # 1. Create the offices.
        offices = {
            name: Office(name=name)
            for name in OFFICE_NAMES
        }
        db.add_all(offices.values())
        db.flush()

        office_ids = {
            name: office.id
            for name, office in offices.items()
        }

        # 2. Create employees without manager links first.
        employee_by_code = {}

        for row in users_data:
            code = row["user_id"].strip()
            office_name = row["office"].strip()

            if office_name not in office_ids:
                raise ValueError(
                    f"Unknown office {office_name!r} for {code}"
                )

            username = (row.get("username") or "").strip()
            if not username:
                username = code.lower()

            user = User(
                employee_code=code,
                name=row["name"].strip(),
                role=row["role"].strip().lower(),
                username=username,
                password_hash=None,
                office_id=office_ids[office_name],
                manager_id=None,
            )

            db.add(user)
            employee_by_code[code] = user

        db.flush()

        # 3. Resolve manager codes to actual database IDs.
        for row in users_data:
            manager_code = (row.get("manager_id") or "").strip()

            if not manager_code:
                continue

            user = employee_by_code[row["user_id"].strip()]
            manager = employee_by_code.get(manager_code)

            if manager is None:
                raise ValueError(
                    f"Unknown manager {manager_code!r} "
                    f"for employee {user.employee_code}"
                )

            if manager.office_id != user.office_id:
                raise ValueError(
                    f"Cross-office reporting relationship: "
                    f"{user.employee_code} -> {manager_code}"
                )

            user.manager_id = manager.id

        # 4. Create the accounts and map their office names.
        for row in accounts_data:
            office_name = row["office"].strip()

            if office_name not in office_ids:
                raise ValueError(
                    f"Unknown office {office_name!r} "
                    f"for loan {row['loan_no']}"
                )

            original_amount = parse_money(
                row["original_amount"], "original_amount"
            )
            outstanding = parse_money(
                row["outstanding"], "outstanding"
            )

            account = Account(
                loan_no=row["loan_no"].strip(),
                portfolio=row["portfolio"].strip(),
                seller_bank=row["seller_bank"].strip(),
                customer_name=row["customer_name"].strip(),
                mobile=row["mobile"].strip(),
                email=row["email"].strip() or None,
                city=row["city"].strip() or None,
                state=row["state"].strip() or None,
                language=row["language"].strip() or None,
                product=row["product"].strip(),
                original_amount=original_amount,
                outstanding=outstanding,
                npa_date=parse_date(row["npa_date"]),
                last_payment_date=parse_date(
                    row["last_payment_date"]
                ),
                status=row["status"].strip(),
                office_id=office_ids[office_name],
                owner_id=None,
            )

            db.add(account)

        # All inserts succeed together, or the transaction rolls back.
        db.commit()

        print("Seed completed successfully.")
        print(f"Offices: {db.scalar(select(func.count()).select_from(Office))}")
        print(f"Users: {db.scalar(select(func.count()).select_from(User))}")
        print(f"Accounts: {db.scalar(select(func.count()).select_from(Account))}")


if __name__ == "__main__":
    try:
        Base.metadata.create_all(bind=engine)
        seed_database()
    except Exception as exc:
        print(f"Seed failed: {exc}")
        raise
