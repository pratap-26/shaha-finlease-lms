import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Account, Office
from app.permissions import get_current_user

router = APIRouter(prefix="/imports", tags=["CSV Import"])
REQUIRED = {"loan_no","customer_name","mobile","office","product","original_amount","outstanding"}

def money(value, field):
    try:
        amount = Decimal(str(value).strip()).quantize(Decimal("0.01"))
        if not amount.is_finite() or amount < 0:
            raise ValueError()
        return amount
    except Exception:
        raise ValueError(f"Invalid {field}: {value!r}")

def parse_date(value):
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None

@router.post("/accounts")
async def upload_accounts_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user.role not in {"manager", "head"}:
        raise HTTPException(status_code=403, detail="Only managers and Head of Collections can upload accounts.")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV exceeds the 50 MB limit.")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        headers = {h.strip() for h in (reader.fieldnames or [])}
        missing = REQUIRED - headers
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(sorted(missing))}")
        offices = {o.name.lower(): o.id for o in db.scalars(select(Office)).all()}
        existing = set(db.scalars(select(Account.loan_no)).all())
        batch, errors, imported, skipped = [], [], 0, 0
        for line_no, row in enumerate(reader, start=2):
            if line_no > 100001:
                raise HTTPException(status_code=400, detail="Maximum 100,000 data rows per upload.")
            try:
                loan_no = (row.get("loan_no") or "").strip()
                if not loan_no:
                    raise ValueError("loan_no is required")
                if loan_no in existing:
                    skipped += 1
                    continue
                office_name = (row.get("office") or "").strip().lower()
                office_id = offices.get(office_name)
                if not office_id:
                    raise ValueError(f"Unknown office: {row.get('office')}")
                if user.role == "manager" and office_id != user.office_id:
                    raise ValueError("Managers may upload only for their own office.")
                original = money(row.get("original_amount"), "original_amount")
                outstanding = money(row.get("outstanding"), "outstanding")
                if not all([(row.get("customer_name") or "").strip(), (row.get("mobile") or "").strip(),
                            (row.get("product") or "").strip()]):
                    raise ValueError("customer_name, mobile and product are required")
                batch.append(Account(
                    loan_no=loan_no, portfolio=(row.get("portfolio") or "").strip() or None,
                    seller_bank=(row.get("seller_bank") or "").strip() or None,
                    customer_name=row["customer_name"].strip(), mobile=row["mobile"].strip(),
                    email=(row.get("email") or "").strip() or None, city=(row.get("city") or "").strip() or None,
                    state=(row.get("state") or "").strip() or None, language=(row.get("language") or "").strip() or None,
                    product=row["product"].strip(), original_amount=original, outstanding=outstanding,
                    npa_date=parse_date(row.get("npa_date")), last_payment_date=parse_date(row.get("last_payment_date")),
                    status=(row.get("status") or "New").strip() or "New", office_id=office_id, owner_id=user.id if user.role == 'manager' else None
                ))
                existing.add(loan_no)
                if len(batch) >= 2000:
                    db.add_all(batch); db.flush(); imported += len(batch); batch.clear()
            except Exception as exc:
                errors.append({"row": line_no, "error": str(exc)})
                if len(errors) >= 100:
                    break
        if batch:
            db.add_all(batch); imported += len(batch)
        db.commit()
        return {"message": "CSV import completed.", "imported": imported, "skipped_duplicates": skipped,
                "error_count": len(errors), "errors": errors, "max_rows": 100000}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"CSV import failed: {exc}")
