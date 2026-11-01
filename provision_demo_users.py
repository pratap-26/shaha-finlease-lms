
import secrets

from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


DEMO_ROLES = ("caller", "manager", "head")


def provision_demo_users():
    with SessionLocal() as db:
        credentials = []

        for role in DEMO_ROLES:
            user = db.scalar(
                select(User)
                .where(User.role == role)
                .order_by(User.id)
                .limit(1)
            )

            if user is None:
                raise RuntimeError(
                    f"No employee found for role: {role}"
                )

            # Preserve an existing password if already provisioned.
            if user.password_hash is None:
                password = secrets.token_urlsafe(16)
                user.password_hash = hash_password(password)
            else:
                password = None

            credentials.append(
                (user.username, user.role, password)
            )

        db.commit()

        print("\nDemo login credentials")
        print("----------------------")

        for username, role, password in credentials:
            print(f"Role: {role}")
            print(f"Username: {username}")

            if password is None:
                print("Password already provisioned; unchanged.")
            else:
                print(f"Password: {password}")

            print()


if __name__ == "__main__":
    provision_demo_users()
