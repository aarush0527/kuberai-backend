from app import models
from app.services.purchase_service import Outcome
from app.services.sip_service import SIPOutcome


def transaction_to_dict(txn: models.Transaction) -> dict:
    return {
        "id": txn.id,
        "user_id": txn.user_id,
        "type": txn.type,
        "sip_id": txn.sip_id,
        "rupee_amount": str(txn.rupee_amount),
        "gold_price_used": str(txn.gold_price_used),
        "gold_quantity": str(txn.gold_quantity),
        "status": txn.status,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
    }


def sip_to_dict(sip: models.SIP) -> dict:
    return {
        "id": sip.id,
        "user_id": sip.user_id,
        "rupee_amount": str(sip.rupee_amount),
        "frequency": sip.frequency,
        "next_due_date": sip.next_due_date.isoformat(),
        "status": sip.status,
    }


def purchase_outcome_to_response(outcome: Outcome) -> dict:
    return {
        "success": outcome.success,
        "reason_code": outcome.reason_code,
        "message": outcome.message,
        "deduped": outcome.deduped,
        "transaction": transaction_to_dict(outcome.transaction) if outcome.transaction else None,
    }


def sip_outcome_to_response(outcome: SIPOutcome) -> dict:
    return {
        "success": outcome.success,
        "reason_code": outcome.reason_code,
        "message": outcome.message,
        "already_existed": outcome.already_existed,
        "start_clamped": outcome.start_clamped,
        "sip": sip_to_dict(outcome.sip) if outcome.sip else None,
    }
