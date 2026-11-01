
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import verify_password
from app.database import get_db
from app.models import User
from app.permissions import ALLOWED_ROLES, get_current_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.username == username.strip())
    )

    # Use the same response for an unknown user and a wrong password.
    if (
        user is None
        or user.password_hash is None
        or not verify_password(password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    if user.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Your role is not authorized to use this application.",
        )

    # Start a fresh session after successful authentication.
    request.session.clear()
    request.session["user_id"] = user.id

    return {
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "role": user.role,
            "office_id": user.office_id,
        },
    }


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully."}


@router.get("/me")
def who_am_i(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "role": user.role,
        "office_id": user.office_id,
    }
