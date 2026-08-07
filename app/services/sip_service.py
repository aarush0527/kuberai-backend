"""
SIP lifecycle. Two policy decisions:

1. Month-end clamping: a SIP anchored to the 31st runs on a short month's
   last day instead. anchor_day is stored SEPARATE from next_due_date
   specifically so this doesn't drift.

2. Past start dates clamp to today rather than being rejected outright;
   "starting yesterday" most naturally reads as "start me ASAP", not as
   an error. The caller is always told this happened.
"""

import calendar
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.events import log_event_now
from app.money import parse_rupee_amount, MoneyError
from app.price_provider import CachingPriceService
from app.services.common import get_or_create_user
from app.services.purchase_service import execute_purchase, REASON_MESSAGES


VALID_FREQUENCIES = {f.value for f in models.SIPFrequency}


@dataclass
class SIPOutcome:
    success: bool
    reason_code: str | None = None
    message: str | None = None
    sip: models.SIP | None = None
    already_existed: bool = False
    start_clamped: bool = False
    candidates: list[models.SIP] | None = None


def compute_next_due_date(current_due: date, frequency: str, anchor_day: int | None = None) -> date:

    if frequency == models.SIPFrequency.DAILY.value:
        return current_due.fromordinal(current_due.toordinal() + 1)
    if frequency == models.SIPFrequency.WEEKLY.value:
        return current_due.fromordinal(current_due.toordinal() + 7)
    if frequency == models.SIPFrequency.MONTHLY.value:
        if anchor_day is None:
            anchor_day = current_due.day
        year = current_due.year + (current_due.month // 12)
        month = current_due.month % 12 + 1
        last_day_of_month = calendar.monthrange(year, month)[1]
        clamped_day = min(anchor_day, last_day_of_month)
        return date(year, month, clamped_day)
    raise ValueError(f"unknown SIP frequency: {frequency}")


def resolve_monthly_start_date(today: date, anchor_day: int) -> date:

    this_month_last_day = calendar.monthrange(today.year, today.month)[1]
    this_month_target = date(today.year, today.month, min(anchor_day, this_month_last_day))
    if this_month_target >= today:
        return this_month_target

    year = today.year + (today.month // 12)
    month = today.month % 12 + 1
    next_month_last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, next_month_last_day))


def create_sip(
    db: Session,
    user_id: str,
    raw_amount: str,
    frequency: str,
    requested_start_date: date,
    correlation_id: str,
    requested_anchor_day: int | None = None,
) -> SIPOutcome:

    get_or_create_user(db, user_id)
    log_event_now(
        db, user_id, correlation_id, "sip_create_requested",
        {"amount": raw_amount, "frequency": frequency, "requested_start_date": requested_start_date.isoformat()},
    )

    if frequency not in VALID_FREQUENCIES:
        return _reject(db, user_id, correlation_id, "SIP_INVALID_FREQUENCY", f"Frequency must be one of {sorted(VALID_FREQUENCIES)}.")

    try:
        amount = parse_rupee_amount(raw_amount)
    except MoneyError as e:
        return _reject(db, user_id, correlation_id, e.reason_code, REASON_MESSAGES.get(e.reason_code, str(e)))

    if amount < settings.min_purchase_inr:
        return _reject(db, user_id, correlation_id, "AMOUNT_BELOW_MIN", REASON_MESSAGES["AMOUNT_BELOW_MIN"])
    if amount > settings.max_purchase_inr:
        return _reject(db, user_id, correlation_id, "AMOUNT_ABOVE_MAX", REASON_MESSAGES["AMOUNT_ABOVE_MAX"])

    today = date.today()
    start_clamped = requested_start_date < today
    start_date = today if start_clamped else requested_start_date
    if frequency == models.SIPFrequency.MONTHLY.value:
        anchor_day = requested_anchor_day if requested_anchor_day is not None else start_date.day
    else:
        anchor_day = None

    # Dedup: existence-based, no time window. An identical ACTIVE SIP
    # already existing is essentially never intentional (if you want more
    # gold, you increase an existing SIP, you don't create a duplicate).
    dup = (
        db.query(models.SIP)
        .filter_by(user_id=user_id, rupee_amount=amount, frequency=frequency, status=models.SIPStatus.ACTIVE.value)
        .first()
    )
    if dup is not None and (frequency != models.SIPFrequency.MONTHLY.value or dup.anchor_day == anchor_day):
        log_event_now(db, user_id, correlation_id, "sip_create_deduped", {"existing_sip_id": dup.id})
        return SIPOutcome(success=True, sip=dup, already_existed=True, message="You already have this SIP set up.")

    sip = models.SIP(
        user_id=user_id,
        rupee_amount=amount,
        frequency=frequency,
        anchor_day=anchor_day,
        next_due_date=start_date,
        status=models.SIPStatus.ACTIVE.value,
    )
    db.add(sip)
    db.flush()
    log_event_now(
        db, user_id, correlation_id, "sip_created",
        {"sip_id": sip.id, "amount": str(amount), "frequency": frequency, "next_due_date": start_date.isoformat(), "start_clamped": start_clamped},
    )
    db.commit()
    db.refresh(sip)
    return SIPOutcome(success=True, sip=sip, start_clamped=start_clamped)


def _find_user_active_sips(db: Session, user_id: str) -> list[models.SIP]:
    return db.query(models.SIP).filter_by(user_id=user_id, status=models.SIPStatus.ACTIVE.value).all()


def pause_sip(db: Session, user_id: str, sip_id: str | None, correlation_id: str) -> SIPOutcome:
    return _transition(db, user_id, sip_id, correlation_id, models.SIPStatus.PAUSED.value, "sip_paused")


def resume_sip(db: Session, user_id: str, sip_id: str | None, correlation_id: str) -> SIPOutcome:
    sip = _resolve_target_sip(db, user_id, sip_id, correlation_id, required_status=models.SIPStatus.PAUSED.value)
    if isinstance(sip, SIPOutcome):
        return sip
    sip.status = models.SIPStatus.ACTIVE.value
    log_event_now(db, user_id, correlation_id, "sip_resumed", {"sip_id": sip.id})
    db.commit()
    db.refresh(sip)
    return SIPOutcome(success=True, sip=sip)


def cancel_sip(db: Session, user_id: str, sip_id: str | None, correlation_id: str) -> SIPOutcome:
    sip = _resolve_target_sip(db, user_id, sip_id, correlation_id, required_status=None)
    if isinstance(sip, SIPOutcome):
        return sip
    sip.status = models.SIPStatus.CANCELLED.value
    log_event_now(db, user_id, correlation_id, "sip_cancelled", {"sip_id": sip.id})
    db.commit()
    db.refresh(sip)
    return SIPOutcome(success=True, sip=sip)


def _transition(db, user_id, sip_id, correlation_id, new_status, event_type):
    sip = _resolve_target_sip(db, user_id, sip_id, correlation_id, required_status=models.SIPStatus.ACTIVE.value)
    if isinstance(sip, SIPOutcome):
        return sip
    sip.status = new_status
    log_event_now(db, user_id, correlation_id, event_type, {"sip_id": sip.id})
    db.commit()
    db.refresh(sip)
    return SIPOutcome(success=True, sip=sip)


def _resolve_target_sip(db: Session, user_id: str, sip_id: str | None, correlation_id: str, required_status: str | None):

    if sip_id is not None:
        sip = db.get(models.SIP, sip_id)
        if sip is None or sip.user_id != user_id:
            return _reject(db, user_id, correlation_id, "SIP_NOT_FOUND", "I couldn't find that SIP.")
        if required_status is not None and sip.status != required_status:
            return _reject(db, user_id, correlation_id, "SIP_INVALID_STATE", f"That SIP isn't {required_status} right now.")
        return sip

    candidates = _find_user_active_sips(db, user_id) if required_status == models.SIPStatus.ACTIVE.value else (
        db.query(models.SIP).filter_by(user_id=user_id, status=required_status).all()
        if required_status is not None
        else db.query(models.SIP).filter(models.SIP.user_id == user_id, models.SIP.status != models.SIPStatus.CANCELLED.value).all()
    )

    if len(candidates) == 0:
        return _reject(db, user_id, correlation_id, "SIP_NOT_FOUND", "You don't have a SIP to act on.")
    if len(candidates) > 1:
        log_event_now(
            db, user_id, correlation_id, "sip_action_ambiguous",
            {"candidate_ids": [c.id for c in candidates]},
        )
        return SIPOutcome(
            success=False, reason_code="SIP_AMBIGUOUS",
            message="You have more than one SIP — which one did you mean?",
            candidates=candidates,
        )
    return candidates[0]


def _reject(db, user_id, correlation_id, reason_code, message) -> SIPOutcome:
    log_event_now(db, user_id, correlation_id, "sip_action_rejected", {"reason_code": reason_code})
    return SIPOutcome(success=False, reason_code=reason_code, message=message)


async def execute_due_installments(
    db: Session, price_service: CachingPriceService, correlation_id: str = "scheduler"
) -> list[dict]:

    today = date.today()
    due_sips = (
        db.query(models.SIP)
        .filter(models.SIP.status == models.SIPStatus.ACTIVE.value, models.SIP.next_due_date <= today)
        .all()
    )

    results = []
    for sip in due_sips:
        idempotency_key = f"sip:{sip.id}:{sip.next_due_date.isoformat()}"
        outcome = await execute_purchase(
            db, sip.user_id, str(sip.rupee_amount), correlation_id, price_service,
            idempotency_key=idempotency_key,
            txn_type=models.TransactionType.SIP_INSTALLMENT.value,
            sip_id=sip.id,
        )
        if outcome.success:
            sip.next_due_date = compute_next_due_date(sip.next_due_date, sip.frequency, sip.anchor_day)
            db.commit()
        results.append({"sip_id": sip.id, "success": outcome.success, "reason_code": outcome.reason_code})
    return results
