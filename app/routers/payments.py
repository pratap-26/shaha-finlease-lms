
from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Payment, Account
from app.permissions import get_current_user
from app.routers.accounts import visible_accounts_query


router = APIRouter(prefix="/payments", tags=["Payments"])


class PaymentCreate(BaseModel):
    account_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


def check_account_access(account_id: int, user, db: Session):
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
def record_payment(
    payload: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    account = check_account_access(payload.account_id, user, db)

    try:
        outstanding = Decimal(str(account.outstanding))
        payment_amount = Decimal(str(payload.amount))

        if payment_amount > outstanding:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Payment exceeds outstanding balance. "
                    f"Current outstanding: {outstanding}"
                ),
            )

        if outstanding <= Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail="This account has no outstanding balance.",
            )

        new_outstanding = outstanding - payment_amount

        payment = Payment(
            account_id=account.id,
            recorded_by_id=user.id,
            amount=payment_amount,
            paid_at=datetime.utcnow(),
            reference=payload.reference,
            remarks=payload.remarks,
        )

        account.outstanding = new_outstanding
        account.last_payment_date = date.today()

        if new_outstanding == Decimal("0"):
            account.status = "Paid"

        db.add(payment)
        db.commit()
        db.refresh(payment)
        db.refresh(account)

        return {
            "message": "Payment recorded and account balance updated successfully.",
            "payment": {
                "id": payment.id,
                "account_id": payment.account_id,
                "recorded_by_id": payment.recorded_by_id,
                "amount": str(payment.amount),
                "paid_at": payment.paid_at,
                "reference": payment.reference,
                "remarks": payment.remarks,
            },
            "account": {
                "account_id": account.id,
                "previous_outstanding": str(outstanding),
                "payment_amount": str(payment_amount),
                "new_outstanding": str(account.outstanding),
                "status": account.status,
            },
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get("")
def list_payments(
    request: Request,
    account_id: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    visible_ids = visible_accounts_query(user).with_only_columns(
        Account.id
    )

    query = select(Payment).where(
        Payment.account_id.in_(visible_ids)
    )

    if account_id is not None:
        query = query.where(Payment.account_id == account_id)

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    records = db.scalars(
        query.order_by(Payment.paid_at.desc(), Payment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": [
            {
                "id": p.id,
                "account_id": p.account_id,
                "recorded_by_id": p.recorded_by_id,
                "amount": str(p.amount),
                "paid_at": p.paid_at,
                "reference": p.reference,
                "remarks": p.remarks,
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


@router.get("/{account_id}")
def get_account_payments(
    account_id: int,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    check_account_access(account_id, user, db)

    query = select(Payment).where(
        Payment.account_id == account_id
    )

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    records = db.scalars(
        query.order_by(Payment.paid_at.desc(), Payment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "account_id": account_id,
        "items": [
            {
                "id": p.id,
                "recorded_by_id": p.recorded_by_id,
                "amount": str(p.amount),
                "paid_at": p.paid_at,
                "reference": p.reference,
                "remarks": p.remarks,
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
