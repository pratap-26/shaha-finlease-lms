from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Payment, CallLog, PTP, Office
from app.permissions import get_current_user
from app.routers.accounts import visible_accounts_query

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    # Restrict every metric to accounts this user is allowed to view.
    visible_ids = (
        visible_accounts_query(user)
        .with_only_columns(Account.id)
        .subquery()
    )

    account_filter = Account.id.in_(select(visible_ids.c.id))

    total_accounts = db.scalar(
        select(func.count(Account.id)).where(account_filter)
    ) or 0

    total_outstanding = db.scalar(
        select(func.coalesce(func.sum(Account.outstanding), 0))
        .where(account_filter)
    ) or 0

    total_original = db.scalar(
        select(func.coalesce(func.sum(Account.original_amount), 0))
        .where(account_filter)
    ) or 0

    total_recovered = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.account_id.in_(select(visible_ids.c.id)))
    ) or 0

    total_calls = db.scalar(
        select(func.count(CallLog.id))
        .where(CallLog.account_id.in_(select(visible_ids.c.id)))
    ) or 0

    total_ptps = db.scalar(
        select(func.count(PTP.id))
        .where(PTP.account_id.in_(select(visible_ids.c.id)))
    ) or 0

    pending_ptps = db.scalar(
        select(func.count(PTP.id)).where(
            PTP.account_id.in_(select(visible_ids.c.id)),
            PTP.status == "Pending",
        )
    ) or 0

    pending_ptp_amount = db.scalar(
        select(func.coalesce(func.sum(PTP.promised_amount), 0))
        .where(
            PTP.account_id.in_(select(visible_ids.c.id)),
            PTP.status == "Pending",
        )
    ) or 0

    status_rows = db.execute(
        select(Account.status, func.count(Account.id))
        .where(account_filter)
        .group_by(Account.status)
        .order_by(Account.status)
    ).all()

    office_rows = db.execute(
        select(Office.name, func.count(Account.id))
        .join(Account, Account.office_id == Office.id)
        .where(account_filter)
        .group_by(Office.name)
        .order_by(Office.name)
    ).all()

    return {
        "user": {
            "name": user.name,
            "role": user.role,
        },
        "kpis": {
            "total_accounts": total_accounts,
            "total_original_amount": str(total_original),
            "total_outstanding": str(total_outstanding),
            "total_recovered": str(total_recovered),
            "total_calls": total_calls,
            "total_ptps": total_ptps,
            "pending_ptps": pending_ptps,
            "pending_ptp_amount": str(pending_ptp_amount),
        },
        "account_status": [
            {"status": status, "count": count}
            for status, count in status_rows
        ],
        "office_distribution": [
            {"office": office, "count": count}
            for office, count in office_rows
        ],
    }