from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, User, AllocationHistory
from app.permissions import get_current_user
from app.routers.accounts import visible_accounts_query

router = APIRouter(prefix="/allocations", tags=["Account Allocations"])


class AllocationCreate(BaseModel):
    account_id: int = Field(gt=0)
    new_owner_id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=255)

class BulkAllocationCreate(BaseModel):
    account_ids: list[int] = Field(min_length=1, max_length=1000)
    new_owner_id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=255)


@router.post("")
def allocate_account(
    payload: AllocationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    # Only managers and the head can allocate accounts.
    if user.role not in {"manager", "head"}:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to allocate accounts.",
        )

    account = db.get(Account, payload.account_id)

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    if account.status in {"Closed", "Settled"}:
        raise HTTPException(
            status_code=400,
            detail="Closed or settled accounts cannot be reallocated."
        )

    new_owner = db.get(User, payload.new_owner_id)

    if new_owner is None or new_owner.role != "caller":
        raise HTTPException(
            status_code=400,
            detail="The new owner must be a valid caller.",
        )

    # An account must remain within its assigned office.
    if account.office_id != new_owner.office_id:
        raise HTTPException(
            status_code=400,
            detail="Account and caller must belong to the same office.",
        )

    if user.role == "manager":
        # Managers can allocate only within their own office
        # and only to their direct reports.
        if account.office_id != user.office_id:
            raise HTTPException(
                status_code=403,
                detail="You cannot allocate accounts outside your office.",
            )

        if new_owner.manager_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can allocate accounts only to your direct reports.",
            )

    if account.owner_id == new_owner.id:
        raise HTTPException(
            status_code=400,
            detail="This account is already assigned to that caller.",
        )

    previous_owner_id = account.owner_id

    history = AllocationHistory(
        account_id=account.id,
        previous_owner_id=previous_owner_id,
        new_owner_id=new_owner.id,
        allocated_by_id=user.id,
        reason=payload.reason,
    )

    account.owner_id = new_owner.id

    try:
        db.add(history)
        db.commit()
        db.refresh(history)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Account allocated successfully.",
        "allocation": {
            "account_id": account.id,
            "previous_owner_id": previous_owner_id,
            "new_owner_id": new_owner.id,
            "allocated_by_id": user.id,
            "reason": history.reason,
            "allocated_at": history.allocated_at,
        },
    }


@router.post("/bulk")
def bulk_allocate_accounts(payload: BulkAllocationCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user.role not in {"manager", "head"}:
        raise HTTPException(status_code=403, detail="Only managers and Head of Collections can allocate accounts.")
    if len(set(payload.account_ids)) != len(payload.account_ids):
        raise HTTPException(status_code=400, detail="Duplicate account IDs were selected.")
    caller = db.get(User, payload.new_owner_id)
    if caller is None or caller.role != "caller":
        raise HTTPException(status_code=400, detail="Select a valid caller.")
    if user.role == "manager" and (caller.office_id != user.office_id or caller.manager_id != user.id):
        raise HTTPException(status_code=403, detail="Managers may allocate only to their direct-report callers.")
    accounts = db.scalars(
        select(Account).where(Account.id.in_(payload.account_ids))
    ).all()

    if len(accounts) != len(payload.account_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more accounts were not found."
        )

    closed_accounts = [
        account.id
        for account in accounts
        if account.status in {"Closed", "Settled"}
    ]

    if closed_accounts:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Closed or settled accounts cannot be reallocated.",
                "account_ids": closed_accounts
            }
        )
    if any(a.office_id != caller.office_id for a in accounts):
        raise HTTPException(status_code=400, detail="All selected accounts must belong to the caller's office.")
    if user.role == "manager" and any(a.office_id != user.office_id for a in accounts):
        raise HTTPException(status_code=403, detail="Managers cannot allocate outside their office.")
    changed = 0
    try:
        for account in accounts:
            if account.owner_id == caller.id:
                continue
            db.add(AllocationHistory(account_id=account.id, previous_owner_id=account.owner_id,
                                     new_owner_id=caller.id, allocated_by_id=user.id, reason=payload.reason))
            account.owner_id = caller.id
            changed += 1
        db.commit()
        return {"message": "Bulk allocation completed.", "updated": changed,
                "unchanged": len(accounts)-changed, "caller_id": caller.id}
    except Exception:
        db.rollback()
        raise

@router.get("/callers")
def get_eligible_callers(
    request: Request,
    office_id: int,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if user.role not in {"manager", "head"}:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view eligible callers.",
        )

    query = select(User).where(
        User.role == "caller",
        User.office_id == office_id,
    )

    if user.role == "manager":
        if office_id != user.office_id:
            raise HTTPException(
                status_code=403,
                detail="You cannot view callers outside your office.",
            )

        query = query.where(User.manager_id == user.id)

    callers = db.scalars(query.order_by(User.name)).all()

    return {
        "items": [
            {
                "id": caller.id,
                "name": caller.name,
                "username": caller.username,
            }
            for caller in callers
        ]
    }

@router.get("/{account_id}")
def get_allocation_history(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    # Apply the same account visibility rules used elsewhere.
    account = db.scalar(
        visible_accounts_query(user).where(Account.id == account_id)
    )

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    records = db.scalars(
        select(AllocationHistory)
        .where(AllocationHistory.account_id == account_id)
        .order_by(AllocationHistory.allocated_at.desc())
    ).all()

    return {
        "account_id": account_id,
        "items": [
            {
                "id": record.id,
                "previous_owner_id": record.previous_owner_id,
                "new_owner_id": record.new_owner_id,
                "allocated_by_id": record.allocated_by_id,
                "allocated_at": record.allocated_at,
                "reason": record.reason,
            }
            for record in records
        ],
        "total": len(records),
    }