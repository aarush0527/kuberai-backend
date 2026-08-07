import uuid
from datetime import datetime, date

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Numeric,
    Date,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: gen_id("user"),
    )

    display_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

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

    amount: Mapped[float] = mapped_column(
        Numeric(12, 2, asdecimal=True),
        nullable=False,
    )

    gold_quantity: Mapped[float] = mapped_column(
        Numeric(12, 4, asdecimal=True),
        nullable=False,
    )

    gold_price: Mapped[float] = mapped_column(
        Numeric(12, 4, asdecimal=True),
        nullable=False,
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

    amount: Mapped[float] = mapped_column(
        Numeric(12, 2, asdecimal=True),
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )