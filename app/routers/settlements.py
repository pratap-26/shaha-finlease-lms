from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Account,
    Payment,
    Settlement,
    SettlementPayment,
    AccountClosure,
)
from app.permissions import get_current_user
from app.routers.accounts import visible_accounts_query


router = APIRouter(prefix="/settlements", tags=["Settlements"])


# -------------------- REQUEST SCHEMAS --------------------

class SettlementCreate(BaseModel):
    account_id: int = Field(gt=0)
    proposed_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=5, max_length=2000)
    remarks: str | None = Field(default=None, max_length=2000)
    payment_due_date: date | None = None


class SettlementDecision(BaseModel):
    remarks: str | None = Field(default=None, max_length=2000)


class SettlementPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)
    remarks: str | None = Field(default=None, max_length=2000)


# -------------------- HELPERS --------------------

ACTIVE_SETTLEMENT_STATUSES = {"Pending", "Approved", "In Progress"}


def get_visible_account(account_id: int, user, db: Session):
    account = db.scalar(
        visible_accounts_query(user).where(Account.id == account_id)
    )

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    return account


def get_settlement(settlement_id: int, user, db: Session):
    settlement = db.get(Settlement, settlement_id)

    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found.")

    get_visible_account(settlement.account_id, user, db)

    return settlement


def require_approver(user, account):
    if user.role not in {"manager", "head"}:
        raise HTTPException(
            status_code=403,
            detail="Only Managers and Head of Collections can review settlements.",
        )

    if user.role == "manager" and user.office_id != account.office_id:
        raise HTTPException(
            status_code=403,
            detail="You can approve settlements only within your office.",
        )

def regular_payment_total(db: Session, account_id: int) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.account_id == account_id)
    )
    return Decimal(str(total or 0))
def settlement_paid_total(db: Session, settlement_id: int) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(SettlementPayment.amount), 0))
        .where(SettlementPayment.settlement_id == settlement_id)
    )

    return Decimal(str(total or 0))


def settlement_response(db: Session, settlement: Settlement):
    paid = settlement_paid_total(db, settlement.id)

    target = (
        Decimal(str(settlement.approved_amount))
        if settlement.approved_amount is not None
        else Decimal("0.00")
    )

    return {
        "id": settlement.id,
        "account_id": settlement.account_id,
        "original_outstanding": str(settlement.original_outstanding),
        "proposed_amount": str(settlement.proposed_amount),
        "approved_amount": (
            str(settlement.approved_amount)
            if settlement.approved_amount is not None
            else None
        ),
        "waiver_amount": (
            str(settlement.waiver_amount)
            if settlement.waiver_amount is not None
            else None
        ),
        "amount_paid": str(paid),
        "amount_remaining": str(max(target - paid, Decimal("0.00"))),
        "reason": settlement.reason,
        "remarks": settlement.remarks,
        "status": settlement.status,
        "proposed_by_id": settlement.proposed_by_id,
        "reviewed_by_id": settlement.reviewed_by_id,
        "proposed_at": settlement.proposed_at,
        "reviewed_at": settlement.reviewed_at,
        "payment_due_date": settlement.payment_due_date,
    }


# -------------------- PROPOSE SETTLEMENT --------------------

@router.post("")
def propose_settlement(
    payload: SettlementCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    account = get_visible_account(payload.account_id, user, db)

    if account.status in {"Closed", "Settled"}:
        raise HTTPException(
            status_code=400,
            detail="A closed or settled account cannot receive a new settlement proposal.",
        )

    loaded_outstanding = Decimal(str(account.outstanding))
    previously_recovered = regular_payment_total(db, account.id)
    outstanding = loaded_outstanding - previously_recovered

    if outstanding <= 0:
        raise HTTPException(
            status_code=400,
            detail="No outstanding recovery balance remains for settlement."
        )

    amount = Decimal(str(payload.proposed_amount)).quantize(
        Decimal("0.01")
    )

    if amount >= outstanding:
        raise HTTPException(
            status_code=400,
            detail="Settlement amount must be lower than the loaded outstanding.",
        )

    if payload.payment_due_date and payload.payment_due_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Settlement payment due date cannot be in the past.",
        )

    existing = db.scalar(
        select(Settlement).where(
            Settlement.account_id == account.id,
            Settlement.status.in_(ACTIVE_SETTLEMENT_STATUSES),
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="An active settlement already exists for this account.",
        )

    settlement = Settlement(
        account_id=account.id,
        original_outstanding=outstanding,
        proposed_amount=amount,
        reason=payload.reason.strip(),
        remarks=payload.remarks,
        proposed_by_id=user.id,
        status="Pending",
        payment_due_date=payload.payment_due_date,
    )

    db.add(settlement)

    try:
        db.commit()
        db.refresh(settlement)
        return {
            "message": "Settlement proposal submitted for approval.",
            "settlement": settlement_response(db, settlement),
        }
    except Exception:
        db.rollback()
        raise


# -------------------- LIST SETTLEMENTS --------------------

@router.get("")
def list_settlements(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    account_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    visible_ids = visible_accounts_query(user).with_only_columns(Account.id)

    query = select(Settlement).where(
        Settlement.account_id.in_(visible_ids)
    )

    if status_filter:
        query = query.where(Settlement.status == status_filter)

    if account_id is not None:
        get_visible_account(account_id, user, db)
        query = query.where(Settlement.account_id == account_id)

    records = db.scalars(
        query.order_by(Settlement.proposed_at.desc())
    ).all()

    return {
        "items": [
            settlement_response(db, item)
            for item in records
        ],
        "total": len(records),
    }


# -------------------- APPROVE SETTLEMENT --------------------

@router.post("/{settlement_id}/approve")
def approve_settlement(
    settlement_id: int,
    payload: SettlementDecision,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    settlement = get_settlement(settlement_id, user, db)
    account = db.get(Account, settlement.account_id)

    require_approver(user, account)

    if settlement.proposed_by_id == user.id:
        raise HTTPException(
            status_code=403,
            detail="A user cannot approve their own settlement proposal.",
        )

    if settlement.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending settlement proposals can be approved.",
        )

    if account.status in {"Closed", "Settled"}:
        raise HTTPException(
            status_code=400,
            detail="This account has already been closed or settled.",
        )

    amount = Decimal(str(settlement.proposed_amount))
    loaded_outstanding = Decimal(str(account.outstanding))
    previously_recovered = regular_payment_total(db, account.id)
    outstanding = loaded_outstanding - previously_recovered

    if outstanding <= 0:
        raise HTTPException(
            status_code=400,
            detail="No outstanding recovery balance remains for settlement."
        )

    if amount >= outstanding:
        raise HTTPException(
            status_code=400,
            detail="The proposed settlement is no longer valid against the current outstanding.",
        )

    settlement.approved_amount = amount
    settlement.waiver_amount = outstanding - amount
    settlement.status = "Approved"
    settlement.reviewed_by_id = user.id
    settlement.reviewed_at = datetime.utcnow()

    if payload.remarks:
        settlement.remarks = (
            (settlement.remarks or "")
            + "\nApproval: "
            + payload.remarks
        )

    try:
        db.commit()
        db.refresh(settlement)

        return {
            "message": "Settlement approved successfully.",
            "settlement": settlement_response(db, settlement),
        }
    except Exception:
        db.rollback()
        raise


# -------------------- REJECT SETTLEMENT --------------------

@router.post("/{settlement_id}/reject")
def reject_settlement(
    settlement_id: int,
    payload: SettlementDecision,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    settlement = get_settlement(settlement_id, user, db)
    account = db.get(Account, settlement.account_id)

    require_approver(user, account)

    if settlement.proposed_by_id == user.id:
        raise HTTPException(
            status_code=403,
            detail="A user cannot reject their own settlement proposal.",
        )

    if settlement.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending settlement proposals can be rejected.",
        )

    if not payload.remarks or not payload.remarks.strip():
        raise HTTPException(
            status_code=400,
            detail="A rejection reason is required.",
        )

    settlement.status = "Rejected"
    settlement.reviewed_by_id = user.id
    settlement.reviewed_at = datetime.utcnow()
    settlement.remarks = (
        (settlement.remarks or "")
        + "\nRejection: "
        + payload.remarks.strip()
    )

    try:
        db.commit()
        db.refresh(settlement)

        return {
            "message": "Settlement proposal rejected.",
            "settlement": settlement_response(db, settlement),
        }
    except Exception:
        db.rollback()
        raise


# -------------------- RECORD SETTLEMENT PAYMENT --------------------

@router.post("/{settlement_id}/payments")
def record_settlement_payment(
    settlement_id: int,
    payload: SettlementPaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    settlement = get_settlement(settlement_id, user, db)
    account = db.get(Account, settlement.account_id)

    if settlement.status not in {"Approved", "In Progress"}:
        raise HTTPException(
            status_code=400,
            detail="Payments can be recorded only against approved settlements.",
        )

    if account.status in {"Closed", "Settled"}:
        raise HTTPException(
            status_code=400,
            detail="This account is already closed or settled.",
        )

    amount = Decimal(str(payload.amount)).quantize(
        Decimal("0.01")
    )

    approved = Decimal(str(settlement.approved_amount))
    already_paid = settlement_paid_total(db, settlement.id)
    remaining = approved - already_paid

    if amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Payment exceeds the remaining settlement amount of {remaining}.",
        )

    payment = SettlementPayment(
        settlement_id=settlement.id,
        recorded_by_id=user.id,
        amount=amount,
        paid_at=datetime.utcnow(),
        reference=payload.reference,
        remarks=payload.remarks,
    )

    db.add(payment)
    db.flush()

    new_total = already_paid + amount

    if new_total >= approved:
        settlement.status = "Completed"
        account.status = "Settled"

        closure = db.scalar(
            select(AccountClosure).where(
                AccountClosure.account_id == account.id
            )
        )

        if closure is None:
            previous_recovery = regular_payment_total(db, account.id)
            total_recovery = previous_recovery + new_total

            db.add(
                AccountClosure(
                    account_id=account.id,
                    closure_type="Settlement",
                    closure_reason=settlement.reason,
                    total_recovered=total_recovery,
                    closed_by_id=user.id,
                    closed_at=datetime.utcnow(),
                    remarks=(
                        f"Settlement completed. "
                        f"Previous regular recovery: ₹{previous_recovery}. "
                        f"Settlement recovery: ₹{new_total}."
                    ),
                )
            )

    else:
        settlement.status = "In Progress"

    try:
        db.commit()
        db.refresh(payment)
        db.refresh(settlement)

        return {
            "message": (
                "Settlement completed and account marked Settled."
                if settlement.status == "Completed"
                else "Settlement payment recorded successfully."
            ),
            "payment": {
                "id": payment.id,
                "settlement_id": payment.settlement_id,
                "amount": str(payment.amount),
                "paid_at": payment.paid_at,
                "reference": payment.reference,
            },
            "settlement": settlement_response(db, settlement),
            "account_status": account.status,
        }

    except Exception:
        db.rollback()
        raise