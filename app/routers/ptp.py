
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PTP, Account, Payment
from app.permissions import get_current_user
from app.routers.accounts import visible_accounts_query


router = APIRouter(prefix="/ptp", tags=["Promise to Pay"])

def refresh_overdue_ptps(db: Session, account_id: int | None = None):
    query = select(PTP).where(PTP.status == "Pending", PTP.promised_date < date.today())
    if account_id is not None:
        query = query.where(PTP.account_id == account_id)
    records = db.scalars(query).all()
    for ptp in records:
        paid = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.account_id == ptp.account_id,
                Payment.paid_at >= ptp.created_at
            )
        ) or Decimal("0")
        ptp.status = "Kept" if Decimal(str(paid)) >= Decimal(str(ptp.promised_amount)) else "Broken"
    if records:
        db.commit()


PTPStatus = Literal["Pending", "Kept", "Broken", "Cancelled"]


class PTPCreate(BaseModel):
    account_id: int = Field(gt=0)
    promised_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    promised_date: date
    remarks: str | None = None


class PTPStatusUpdate(BaseModel):
    status: PTPStatus


def check_account_access(account_id: int, user, db: Session):
    account = db.scalar(
        visible_accounts_query(user).where(Account.id == account_id)
    )

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    return account


def check_ptp_access(ptp_id: int, user, db: Session):
    query = (
        select(PTP)
        .join(Account, PTP.account_id == Account.id)
        .where(PTP.id == ptp_id)
    )

    ptp = db.scalar(
        query.join(
            visible_accounts_query(user).subquery(),
            Account.id == visible_accounts_query(user).subquery().c.id
        )
    )

    if ptp is None:
        raise HTTPException(status_code=404, detail="PTP record not found.")

    return ptp


@router.post("")
def create_ptp(
    payload: PTPCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    check_account_access(payload.account_id, user, db)

    if payload.promised_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Promised date cannot be in the past.",
        )

    ptp = PTP(
        account_id=payload.account_id,
        created_by_id=user.id,
        promised_amount=payload.promised_amount,
        promised_date=payload.promised_date,
        status="Pending",
        remarks=payload.remarks,
        created_at=datetime.utcnow(),
    )

    db.add(ptp)
    db.commit()
    db.refresh(ptp)

    return {
        "message": "Payment promise recorded successfully.",
        "ptp": {
            "id": ptp.id,
            "account_id": ptp.account_id,
            "created_by_id": ptp.created_by_id,
            "promised_amount": str(ptp.promised_amount),
            "promised_date": ptp.promised_date,
            "status": ptp.status,
            "remarks": ptp.remarks,
            "created_at": ptp.created_at,
        },
    }


@router.get("/{account_id}")
def get_account_ptps(
    account_id: int,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    check_account_access(account_id, user, db)
    refresh_overdue_ptps(db, account_id)

    query = select(PTP).where(PTP.account_id == account_id)

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    records = db.scalars(
        query.order_by(PTP.created_at.desc(), PTP.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "account_id": account_id,
        "items": [
            {
                "id": p.id,
                "created_by_id": p.created_by_id,
                "promised_amount": str(p.promised_amount),
                "promised_date": p.promised_date,
                "status": p.status,
                "remarks": p.remarks,
                "created_at": p.created_at,
            }
            for p in records
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("")
def list_ptps(
    request: Request,
    status_filter: PTPStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    refresh_overdue_ptps(db)

    visible_ids = visible_accounts_query(user).with_only_columns(
        Account.id
    )

    query = select(PTP).where(PTP.account_id.in_(visible_ids))

    if status_filter:
        query = query.where(PTP.status == status_filter)

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    records = db.scalars(
        query.order_by(PTP.promised_date.asc(), PTP.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": [
            {
                "id": p.id,
                "account_id": p.account_id,
                "created_by_id": p.created_by_id,
                "promised_amount": str(p.promised_amount),
                "promised_date": p.promised_date,
                "status": p.status,
                "remarks": p.remarks,
                "created_at": p.created_at,
            }
            for p in records
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.patch("/{ptp_id}")
def update_ptp_status(
    ptp_id: int,
    payload: PTPStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    ptp = db.get(PTP, ptp_id)

    if ptp is None:
        raise HTTPException(status_code=404, detail="PTP record not found.")

    check_account_access(ptp.account_id, user, db)

    ptp.status = payload.status

    db.commit()
    db.refresh(ptp)

    return {
        "message": "PTP status updated successfully.",
        "id": ptp.id,
        "status": ptp.status,
    }
