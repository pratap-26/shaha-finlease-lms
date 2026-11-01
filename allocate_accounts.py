
from app.database import SessionLocal
from app.models import User, Account


def allocate_accounts():
    db = SessionLocal()

    try:
        offices = db.query(User.office_id).filter(
            User.role == "caller"
        ).distinct().all()

        total_assigned = 0

        print("\nACCOUNT ALLOCATION STARTED")
        print("=" * 55)

        for (office_id,) in offices:
            callers = (
                db.query(User)
                .filter(
                    User.role == "caller",
                    User.office_id == office_id
                )
                .order_by(User.id)
                .all()
            )

            if not callers:
                raise ValueError(
                    f"No callers found for office {office_id}"
                )

            # Fetch only unassigned accounts in this office.
            accounts = (
                db.query(Account)
                .filter(
                    Account.office_id == office_id,
                    Account.owner_id.is_(None)
                )
                .order_by(Account.id)
                .all()
            )

            # Distribute accounts evenly using round-robin allocation.
            for index, account in enumerate(accounts):
                caller = callers[index % len(callers)]
                account.owner_id = caller.id

            total_assigned += len(accounts)

            print(f"\nOffice ID: {office_id}")
            print(f"Callers: {len(callers)}")
            print(f"Newly allocated accounts: {len(accounts)}")

            # Show resulting ownership counts.
            for caller in callers:
                count = (
                    db.query(Account)
                    .filter(Account.owner_id == caller.id)
                    .count()
                )
                print(f"  {caller.username}: {count} accounts")

        db.commit()

        print("\n" + "=" * 55)
        print("ALLOCATION COMPLETED SUCCESSFULLY")
        print(f"New accounts allocated: {total_assigned}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    allocate_accounts()
