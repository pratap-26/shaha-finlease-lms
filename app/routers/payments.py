from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Payment, Account, AccountClosure, Settlement
from app.permissions import get_current_user
from app.routers.accounts import visible_accounts_query

router = APIRouter(prefix="/payments", tags=["Payments"])

class PaymentCreate(BaseModel):
    account_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)
    remarks: str | None = None

def check_account_access(account_id: int, user, db: Session):
    account = db.scalar(visible_accounts_query(user).where(Account.id == account_id))
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return account

def payment_totals(db: Session, account_id: int):
    return db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.account_id == account_id)) or Decimal("0.00")

def refresh_recovery_status(db: Session, account: Account):
    paid = Decimal(str(payment_totals(db, account.id)))
    loaded_outstanding = Decimal(str(account.outstanding))
    if paid <= 0:
        # No payment has been received; preserve the existing operational status.
        return paid
    elif paid < loaded_outstanding:
        account.status = "Part-paid"
    else:
        account.status = "Closed"
    return paid

@router.post("")
def record_payment(payload: PaymentCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    account = check_account_access(payload.account_id, user, db)
    if account.status in {"Closed", "Settled"}:
        raise HTTPException(
            status_code=400,
            detail="Payments cannot be recorded against a closed or settled account."
        )
    active_settlement = db.scalar(
        select(Settlement).where(
            Settlement.account_id == account.id,
            Settlement.status.in_(
                {"Pending", "Approved", "In Progress"}
            )
        )
    )

    if active_settlement:
        raise HTTPException(
            status_code=409,
            detail="A settlement is active for this account. Record payments through the settlement workflow."
        )
    reference = (payload.reference or "").strip() or None

    if reference:
        duplicate = db.scalar(
            select(Payment.id).where(
                Payment.account_id == account.id,
                func.lower(func.trim(Payment.reference)) == reference.lower()
            )
        )

        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail="This transaction reference has already been recorded for this account."
            )
    amount = Decimal(str(payload.amount)).quantize(Decimal("0.01"))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment must be greater than zero.")
    try:
        already_paid = Decimal(str(payment_totals(db, account.id)))
        remaining_recovery = Decimal(str(account.outstanding)) - already_paid
        if remaining_recovery <= 0:
            raise HTTPException(status_code=400, detail="This account has already reached its loaded recovery target.")
        if amount > remaining_recovery:
            raise HTTPException(status_code=400, detail=f"Payment exceeds remaining recovery target of {remaining_recovery}.")
        payment = Payment(
            account_id=account.id,
            recorded_by_id=user.id,
            amount=amount,
            paid_at=datetime.utcnow(),
            reference=reference,
            remarks=payload.remarks
        )
        db.add(payment)
        db.flush()
        paid_total = refresh_recovery_status(db, account)

        if account.status == "Closed":
            existing_closure = db.scalar(
                select(AccountClosure).where(
                    AccountClosure.account_id == account.id
                )
            )

            if existing_closure is None:
                db.add(
                    AccountClosure(
                        account_id=account.id,
                        closure_type="Full Recovery",
                        closure_reason="Full loaded recovery target received.",
                        total_recovered=paid_total,
                        closed_by_id=user.id,
                        closed_at=datetime.utcnow(),
                        remarks="Account automatically closed after full recovery."
                    )
                )

        db.commit()
        db.refresh(payment)
        return {"message": "Payment recorded successfully.",
                "payment": {"id": payment.id, "account_id": payment.account_id,
                            "recorded_by_id": payment.recorded_by_id, "amount": str(payment.amount),
                            "paid_at": payment.paid_at, "reference": payment.reference, "remarks": payment.remarks},
                "account": {"account_id": account.id,
                            "loaded_outstanding": str(account.outstanding),
                            "total_paid": str(paid_total), "status": account.status}}
    except Exception:
        db.rollback()
        raise

@router.get("")
def list_payments(request: Request, account_id: int | None = Query(default=None, gt=0),
                  page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
                  db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    visible_ids = visible_accounts_query(user).with_only_columns(Account.id)
    query = select(Payment).where(Payment.account_id.in_(visible_ids))
    if account_id is not None:
        check_account_access(account_id, user, db)
        query = query.where(Payment.account_id == account_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    records = db.scalars(query.order_by(Payment.paid_at.desc(), Payment.id.desc())
                         .offset((page-1)*page_size).limit(page_size)).all()
    return {"items": [{"id": x.id, "account_id": x.account_id, "recorded_by_id": x.recorded_by_id,
                       "amount": str(x.amount), "paid_at": x.paid_at, "reference": x.reference, "remarks": x.remarks}
                      for x in records],
            "pagination": {"page": page, "page_size": page_size, "total": total,
                           "pages": (total+page_size-1)//page_size}}

@router.get("/{account_id}")
def get_account_payments(account_id: int, request: Request, page: int = Query(default=1, ge=1),
                         page_size: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    check_account_access(account_id, user, db)
    query = select(Payment).where(Payment.account_id == account_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    records = db.scalars(query.order_by(Payment.paid_at.desc(), Payment.id.desc())
                         .offset((page-1)*page_size).limit(page_size)).all()
    paid_total = payment_totals(db, account_id)
    account = db.get(Account, account_id)
    return {"account_id": account_id, "loaded_outstanding": str(account.outstanding),
            "total_paid": str(paid_total), "items": [
                {"id": x.id, "recorded_by_id": x.recorded_by_id, "amount": str(x.amount),
                 "paid_at": x.paid_at, "reference": x.reference, "remarks": x.remarks} for x in records],
            "pagination": {"page": page, "page_size": page_size, "total": total,
                           "pages": (total+page_size-1)//page_size}}
