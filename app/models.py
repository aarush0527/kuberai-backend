import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Numeric,
    Date,
    Integer,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class TransactionType(str, enum.Enum):
    PURCHASE = "purchase"
    SIP_INSTALLMENT = "sip_installment"


class TransactionStatus(str, enum.Enum):
    COMPLETED = "completed"
    REJECTED = "rejected"


class SIPStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class SIPFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: gen_id("user"),
    )

    display_name: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: gen_id("txn"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(String, nullable=False)

    sip_id: Mapped[str | None] = mapped_column(
        ForeignKey("sips.id"),
        nullable=True,
        index=True,
    )

    rupee_amount: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=True),
        nullable=False,
    )

    gold_price_used: Mapped[float] = mapped_column(
        Numeric(14, 4, asdecimal=True),
        nullable=False,
    )

    gold_quantity: Mapped[float] = mapped_column(
        Numeric(14, 4, asdecimal=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String, nullable=False)

    idempotency_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class SIP(Base):
    __tablename__ = "sips"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: gen_id("sip"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    rupee_amount: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=True),
        nullable=False,
    )

    frequency: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    next_due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=SIPStatus.ACTIVE.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )