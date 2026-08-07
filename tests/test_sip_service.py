from datetime import date

from freezegun import freeze_time

from app import models
from app.services.sip_service import (
    compute_next_due_date,
    resolve_monthly_start_date,
    create_sip,
    pause_sip,
    resume_sip,
    cancel_sip,
    execute_due_installments,
)



# compute_next_due_date — pure function, direct tests


def test_daily_advances_one_day():
    assert compute_next_due_date(date(2026, 8, 5), "daily") == date(2026, 8, 6)


def test_weekly_advances_seven_days():
    assert compute_next_due_date(date(2026, 8, 5), "weekly") == date(2026, 8, 12)


def test_monthly_normal_case():
    assert compute_next_due_date(date(2026, 8, 15), "monthly", anchor_day=15) == date(2026, 9, 15)


def test_monthly_rolls_over_year_boundary():
    assert compute_next_due_date(date(2026, 12, 15), "monthly", anchor_day=15) == date(2027, 1, 15)


def test_monthly_clamps_31st_in_short_month():

    assert compute_next_due_date(date(2026, 1, 31), "monthly", anchor_day=31) == date(2026, 2, 28)


def test_monthly_bounces_back_after_short_month_because_anchor_persists():

    assert compute_next_due_date(date(2026, 2, 28), "monthly", anchor_day=31) == date(2026, 3, 31)


def test_resolve_monthly_start_date_uses_this_month_if_day_hasnt_passed():

    assert resolve_monthly_start_date(date(2026, 8, 5), 31) == date(2026, 8, 31)


def test_resolve_monthly_start_date_rolls_to_next_month_if_day_already_passed():

    assert resolve_monthly_start_date(date(2026, 8, 5), 1) == date(2026, 9, 1)


def test_resolve_monthly_start_date_clamps_within_a_short_month():

    assert resolve_monthly_start_date(date(2026, 9, 20), 31) == date(2026, 9, 30)


def test_anchor_day_override_survives_a_start_date_that_lands_in_a_short_month(db_session, make_user):

    make_user()
    with freeze_time("2026-09-20"):
        start = resolve_monthly_start_date(date(2026, 9, 20), 31)
        outcome = create_sip(
            db_session, "user_test1", "500.00", "monthly", start, "corr-1",
            requested_anchor_day=31,
        )
    assert outcome.success
    assert outcome.sip.anchor_day == 31          
    assert outcome.sip.next_due_date == date(2026, 9, 30)

    next_due = compute_next_due_date(outcome.sip.next_due_date, "monthly", outcome.sip.anchor_day)
    assert next_due == date(2026, 10, 31)


# create_sip — validation, past-date clamping, idempotency


def test_daily_sip_of_100_is_accepted(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        outcome = create_sip(db_session, "user_test1", "100.00", "daily", date(2026, 8, 5), "corr-1")
    assert outcome.success
    assert outcome.sip.frequency == "daily"


def test_invalid_frequency_is_rejected(db_session, make_user):
    make_user()
    outcome = create_sip(db_session, "user_test1", "500.00", "hourly", date(2026, 8, 5), "corr-1")
    assert outcome.success is False
    assert outcome.reason_code == "SIP_INVALID_FREQUENCY"


def test_past_start_date_clamps_to_today_and_says_so(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        outcome = create_sip(db_session, "user_test1", "1000.00", "weekly", date(2026, 8, 4), "corr-1")
    assert outcome.success
    assert outcome.start_clamped is True
    assert outcome.sip.next_due_date == date(2026, 8, 5)


def test_monthly_sip_from_the_31st_persists_anchor_day(db_session, make_user):
    make_user()
    with freeze_time("2026-01-15"):
        outcome = create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 1, 31), "corr-1")
    assert outcome.success
    assert outcome.sip.anchor_day == 31
    assert outcome.sip.next_due_date == date(2026, 1, 31)


def test_same_sip_creation_request_sent_twice_creates_only_one(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        first = create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 8, 31), "corr-1")
        second = create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 8, 31), "corr-2")

    assert first.success and second.success
    assert second.already_existed is True
    assert first.sip.id == second.sip.id
    assert db_session.query(models.SIP).filter_by(user_id="user_test1").count() == 1


def test_different_amount_is_not_treated_as_a_duplicate(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        first = create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 8, 31), "corr-1")
        second = create_sip(db_session, "user_test1", "700.00", "monthly", date(2026, 8, 31), "corr-2")

    assert first.sip.id != second.sip.id
    assert db_session.query(models.SIP).filter_by(user_id="user_test1").count() == 2


# pause / resume / cancel — the "which SIP did they mean" resolution

def test_pause_with_no_sips_reports_not_found(db_session, make_user):
    make_user()
    outcome = pause_sip(db_session, "user_test1", None, "corr-1")
    assert outcome.success is False
    assert outcome.reason_code == "SIP_NOT_FOUND"


def test_pause_with_exactly_one_sip_is_unambiguous(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 8, 5), "corr-1")

    outcome = pause_sip(db_session, "user_test1", None, "corr-2")
    assert outcome.success
    assert outcome.sip.status == models.SIPStatus.PAUSED.value


def test_pause_with_multiple_sips_asks_for_clarification(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 8, 5), "corr-1")
        create_sip(db_session, "user_test1", "1000.00", "weekly", date(2026, 8, 5), "corr-2")

    outcome = pause_sip(db_session, "user_test1", None, "corr-3")
    assert outcome.success is False
    assert outcome.reason_code == "SIP_AMBIGUOUS"


def test_resume_reactivates_a_paused_sip(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        created = create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 8, 5), "corr-1")
    pause_sip(db_session, "user_test1", created.sip.id, "corr-2")

    outcome = resume_sip(db_session, "user_test1", created.sip.id, "corr-3")
    assert outcome.success
    assert outcome.sip.status == models.SIPStatus.ACTIVE.value


def test_cancel_marks_sip_cancelled(db_session, make_user):
    make_user()
    with freeze_time("2026-08-05"):
        created = create_sip(db_session, "user_test1", "500.00", "monthly", date(2026, 8, 5), "corr-1")

    outcome = cancel_sip(db_session, "user_test1", created.sip.id, "corr-2")
    assert outcome.success
    assert outcome.sip.status == models.SIPStatus.CANCELLED.value


# execute_due_installments — the scheduler's core logic

async def test_due_installment_lands_in_ledger_and_advances_due_date(db_session, make_user, price_service):
    make_user()
    with freeze_time("2026-08-05"):
        created = create_sip(db_session, "user_test1", "500.00", "daily", date(2026, 8, 5), "corr-1")
        sip_id = created.sip.id
        results = await execute_due_installments(db_session, price_service)

    assert len(results) == 1
    assert results[0]["success"] is True

    txns = db_session.query(models.Transaction).filter_by(sip_id=sip_id).all()
    assert len(txns) == 1
    assert txns[0].type == models.TransactionType.SIP_INSTALLMENT.value

    sip = db_session.get(models.SIP, sip_id)
    assert sip.next_due_date == date(2026, 8, 6)


async def test_failed_installment_leaves_due_date_unchanged_for_retry(db_session, make_user, price_service):
    make_user()
    with freeze_time("2026-08-05"):
        created = create_sip(db_session, "user_test1", "500.00", "daily", date(2026, 8, 5), "corr-1")
        sip_id = created.sip.id
        price_service.provider.force_fail = True
        results = await execute_due_installments(db_session, price_service)

    assert results[0]["success"] is False
    sip = db_session.get(models.SIP, sip_id)
    assert sip.next_due_date == date(2026, 8, 5)  # unchanged — next tick will retry
    assert db_session.query(models.Transaction).filter_by(sip_id=sip_id).count() == 0


async def test_paused_sip_is_not_executed(db_session, make_user, price_service):
    make_user()
    with freeze_time("2026-08-05"):
        created = create_sip(db_session, "user_test1", "500.00", "daily", date(2026, 8, 5), "corr-1")
        pause_sip(db_session, "user_test1", created.sip.id, "corr-2")
        results = await execute_due_installments(db_session, price_service)

    assert results == []
    assert db_session.query(models.Transaction).filter_by(sip_id=created.sip.id).count() == 0


async def test_scheduler_tick_running_twice_does_not_double_charge(db_session, make_user, price_service):

    make_user()
    with freeze_time("2026-08-05"):
        created = create_sip(db_session, "user_test1", "500.00", "daily", date(2026, 8, 5), "corr-1")
        await execute_due_installments(db_session, price_service)
      
        sip = db_session.get(models.SIP, created.sip.id)
        sip.next_due_date = date(2026, 8, 5)
        db_session.commit()
        await execute_due_installments(db_session, price_service)

    txns = db_session.query(models.Transaction).filter_by(sip_id=created.sip.id).all()
    assert len(txns) == 1
