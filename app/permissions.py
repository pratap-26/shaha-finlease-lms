
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import User


ALLOWED_ROLES = {"caller", "manager", "head"}


def get_current_user(request: Request, db: Session) -> User:
    """Return the authenticated user from the signed session."""
    user_id = request.session.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in first.",
        )

    user = db.get(User, user_id)

    if user is None:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session is no longer valid.",
        )

    if user.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role is not authorized to use this application.",
        )

    return user


def require_roles(user: User, *roles: str) -> User:
    """Reject users whose roles are not permitted for an operation."""
    if user.role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )

    return user
