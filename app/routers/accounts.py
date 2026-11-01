
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, User
from app.permissions import get_current_user, require_roles

router = APIRouter(prefix="/accounts", tags=["Accounts"])

def visible_accounts_query(user: User):
    """Build a query restricted to the user's permitted accounts."""
    query = select(Account)

    if user.role == "head":
        # Head of Collections can view accounts across all offices.
        return query

    if user.role == "manager":
        # Include the manager and their direct reports.
        team_ids = select(User.id).where(User.manager_id == user.id)

        return query.where(
            or_(
                Account.owner_id == user.id,
                Account.owner_id.in_(team_ids),
            )
        )

    # Callers can view only accounts allocated to themselves.
    return query.where(Account.owner_id == user.id)


@router.get("")
def list_accounts(
    request: Request,
    search: str | None = Query(default=None, max_length=100),
    status_filter: str | None = Query(default=None, alias="status"),
    office_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    query = visible_accounts_query(user)

    # Apply optional filters after enforcing the access boundary.
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Account.loan_no.ilike(term),
                Account.customer_name.ilike(term),
                Account.mobile.ilike(term),
            )
        )

    if status_filter and status_filter.strip():
        query = query.where(Account.status == status_filter.strip())

    if office_id is not None:
        query = query.where(Account.office_id == office_id)

    # Count the filtered results before pagination.
    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    offset = (page - 1) * page_size

    accounts = db.scalars(
        query.order_by(Account.id)
        .offset(offset)
        .limit(page_size)
    ).all()

    return {
        "items": [
            {
                "id": account.id,
                "loan_no": account.loan_no,
                "customer_name": account.customer_name,
                "mobile": account.mobile,
                "product": account.product,
                "outstanding": str(account.outstanding),
                "status": account.status,
                "office_id": account.office_id,
                "owner_id": account.owner_id,
            }
            for account in accounts
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total or 0,
            "pages": ((total or 0) + page_size - 1) // page_size,
        },
    }


@router.get("/{account_id}")
def get_account(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    account = db.scalar(
        visible_accounts_query(user).where(Account.id == account_id)
    )

    if account is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Account not found.",
        )

    return {
        "id": account.id,
        "loan_no": account.loan_no,
        "customer_name": account.customer_name,
        "mobile": account.mobile,
        "email": account.email,
        "city": account.city,
        "state": account.state,
        "language": account.language,
        "product": account.product,
        "original_amount": str(account.original_amount),
        "outstanding": str(account.outstanding),
        "status": account.status,
        "office_id": account.office_id,
        "owner_id": account.owner_id,
    }
