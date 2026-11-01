
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, CallLog
from app.permissions import get_current_user
from app.routers.accounts import visible_accounts_query


router = APIRouter(prefix="/call-logs", tags=["Call Logs"])


# Request body for creating a call log.
class CallLogCreate(BaseModel):
    account_id: int = Field(gt=0)
    disposition: str = Field(min_length=1, max_length=50)
    remarks: str | None = None
    next_follow_up: date | None = None


def get_accessible_account(account_id: int, user, db: Session):
    """Return an account only if the user is allowed to access it."""

    account = db.scalar(
        visible_accounts_query(user).where(Account.id == account_id)
    )

    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Account not found.",
        )

    return account


@router.post("")
def create_call_log(
    payload: CallLogCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    # Verify account access before recording the interaction.
    get_accessible_account(payload.account_id, user, db)

    log = CallLog(
        account_id=payload.account_id,
        caller_id=user.id,
        disposition=payload.disposition.strip(),
        remarks=payload.remarks,
        next_follow_up=payload.next_follow_up,
        created_at=datetime.utcnow(),
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return {
        "message": "Call log created successfully.",
        "call_log": {
            "id": log.id,
            "account_id": log.account_id,
            "caller_id": log.caller_id,
            "disposition": log.disposition,
            "remarks": log.remarks,
            "next_follow_up": log.next_follow_up,
            "created_at": log.created_at,
        },
    }


@router.get("/{account_id}")
def get_account_call_logs(
    account_id: int,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    # Do not reveal call history for inaccessible accounts.
    get_accessible_account(account_id, user, db)

    query = select(CallLog).where(
        CallLog.account_id == account_id
    )

    total = len(
        db.scalars(query).all()
    )

    logs = db.scalars(
        query.order_by(CallLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "account_id": account_id,
        "items": [
            {
                "id": log.id,
                "caller_id": log.caller_id,
                "disposition": log.disposition,
                "remarks": log.remarks,
                "next_follow_up": log.next_follow_up,
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
    }
