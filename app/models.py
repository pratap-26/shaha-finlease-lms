
from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Boolean,
    DateTime,
    Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Office(Base):
    __tablename__ = "offices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"Office(id={self.id}, name={self.name!r})"



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)

    role = Column(String(30), nullable=False)

    office_id = Column(
        Integer,
        ForeignKey("offices.id"),
        nullable=False,
    )

    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    office = relationship("Office")
    manager = relationship(
        "User",
        remote_side="User.id",
        foreign_keys=[manager_id],
    )

    def __repr__(self):
        return f"User(id={self.id}, name={self.name!r}, role={self.role!r})"



class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    loan_no = Column(String(30), unique=True, nullable=False, index=True)

    portfolio = Column(String(50), nullable=True)
    seller_bank = Column(String(100), nullable=True)

    customer_name = Column(String(150), nullable=False)
    mobile = Column(String(20), nullable=False, index=True)
    email = Column(String(150), nullable=True)

    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    language = Column(String(50), nullable=True)

    product = Column(String(30), nullable=False)

    original_amount = Column(Numeric(12, 2), nullable=False)
    outstanding = Column(Numeric(12, 2), nullable=False)

    npa_date = Column(Date, nullable=True)
    last_payment_date = Column(Date, nullable=True)

    status = Column(String(30), nullable=False, default="New")

    office_id = Column(
        Integer,
        ForeignKey("offices.id"),
        nullable=False,
    )

    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    office = relationship("Office")
    owner = relationship("User")

    def __repr__(self):
        return f"Account(loan_no={self.loan_no!r}, status={self.status!r})"



class AllocationHistory(Base):
    __tablename__ = "allocation_history"

    id = Column(Integer, primary_key=True, index=True)

    account_id = Column(
        Integer,
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    previous_owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    new_owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    allocated_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    allocated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    reason = Column(String(255), nullable=True)



class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)

    account_id = Column(
        Integer,
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    caller_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    disposition = Column(String(50), nullable=False)
    remarks = Column(Text, nullable=True)
    next_follow_up = Column(Date, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )



class PTP(Base):
    __tablename__ = "ptps"

    id = Column(Integer, primary_key=True, index=True)

    account_id = Column(
        Integer,
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    created_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    promised_amount = Column(Numeric(12, 2), nullable=False)
    promised_date = Column(Date, nullable=False)

    status = Column(
        String(20),
        nullable=False,
        default="Pending",
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    remarks = Column(Text, nullable=True)



class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    account_id = Column(
        Integer,
        ForeignKey("accounts.id"),
        nullable=False,
        index=True,
    )

    recorded_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    amount = Column(Numeric(12, 2), nullable=False)

    paid_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    reference = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)


