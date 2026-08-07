"""
Fast-path pattern matching for unambiguous messages. Returns a
ProposedAction when confident, None when not — never a guess. Anything
this doesn't confidently match falls through to the LLM tier (see
chat_service.py). Both tiers emit the exact same ProposedAction schema.
"""

import re

from app.llm.schemas import ProposedAction

AMOUNT_RE = r"[-+]?\d+(?:\.\d+)?"

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+|your\s+)?(?:previous\s+|prior\s+)?instructions", re.I),
    re.compile(r"disregard\s+(?:all\s+|your\s+)?(?:previous\s+|prior\s+)?instructions", re.I),
    re.compile(r"developer\s+mode", re.I),
    re.compile(r"print\s+your\s+(?:system\s+)?(?:prompt|instructions)", re.I),
    re.compile(r"reveal\s+your\s+(?:system\s+)?(?:prompt|instructions)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:in|a)\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
]

INJECTION_REPLY = (
    "I can't share internal instructions or skip how purchases actually work — "
    "but I'm glad to help you buy some gold for real, or answer questions about it."
)

PURCHASE_PATTERNS = [
    re.compile(rf"buy\s+gold\s+worth\s+({AMOUNT_RE})\s*rupees?", re.I),
    re.compile(rf"buy\s+gold\s+worth\s+({AMOUNT_RE})", re.I),
    re.compile(rf"buy\s+({AMOUNT_RE})\s*rupees?\s+(?:worth\s+)?of\s+gold", re.I),
    re.compile(rf"purchase\s+gold\s+worth\s+({AMOUNT_RE})", re.I),
    re.compile(rf"({AMOUNT_RE})\s*(?:rs\.?|rupye|rupee)?\s*ka\s+(?:gold|sona)\s+le\s+lo", re.I),  # Hinglish
]

PRICE_QUERY_RE = re.compile(rf"how\s+much\s+gold.*?({AMOUNT_RE})\s*rupees?", re.I)

SIP_KEYWORD_RE = re.compile(r"\bsip\b", re.I)
SIP_PAUSE_RE = re.compile(r"\bpause\b.*\bsip\b|\bsip\b.*\bpause\b", re.I)
SIP_RESUME_RE = re.compile(r"\bresume\b.*\bsip\b|\bunpause\b.*\bsip\b|\bsip\b.*\bresume\b", re.I)
SIP_CANCEL_RE = re.compile(r"\bcancel\b.*\bsip\b|\bstop\b.*\bsip\b|\bsip\b.*\bcancel\b", re.I)

SIP_AMOUNT_PATTERNS = [
    re.compile(rf"(?:rs\.?|₹)\s*({AMOUNT_RE})", re.I),
    re.compile(rf"({AMOUNT_RE})\s*(?:rs\.?|rupees?)", re.I),
    re.compile(rf"sip\s+of\s+({AMOUNT_RE})", re.I),
]

FREQUENCY_PATTERNS = {
    "daily": re.compile(r"\bdaily\b|\bevery\s+day\b", re.I),
    "weekly": re.compile(r"\bweekly\b|\bevery\s+week\b", re.I),
    "monthly": re.compile(r"\bmonthly\b|\bevery\s+month\b", re.I),
}

DAY_OF_MONTH_RE = re.compile(r"(?:from\s+the\s+|on\s+the\s+)?\b(\d{1,2})(?:st|nd|rd|th)\b", re.I)

RELATIVE_START_PATTERNS = {
    "yesterday": re.compile(r"\byesterday\b", re.I),
    "tomorrow": re.compile(r"\btomorrow\b", re.I),
    "today": re.compile(r"\btoday\b", re.I),
}


def _extract_sip_amount(text: str) -> str | None:
    for pat in SIP_AMOUNT_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


def _extract_frequency(lowered: str) -> str | None:
    for freq, pat in FREQUENCY_PATTERNS.items():
        if pat.search(lowered):
            return freq
    return None


def try_match(message: str) -> ProposedAction | None:
    text = message.strip()
    lowered = text.lower()

    for pat in INJECTION_PATTERNS:
        if pat.search(lowered):
            return ProposedAction(kind="info", reply_text=INJECTION_REPLY, resolved_by="pattern")

  
    if SIP_KEYWORD_RE.search(lowered):
        if SIP_PAUSE_RE.search(lowered):
            return ProposedAction(kind="sip_pause", resolved_by="pattern")
        if SIP_RESUME_RE.search(lowered):
            return ProposedAction(kind="sip_resume", resolved_by="pattern")
        if SIP_CANCEL_RE.search(lowered):
            return ProposedAction(kind="sip_cancel", resolved_by="pattern")

        amount = _extract_sip_amount(text)
        frequency = _extract_frequency(lowered)
        if amount is not None and frequency is not None:
            day_match = DAY_OF_MONTH_RE.search(lowered)
            day_of_month = int(day_match.group(1)) if (day_match and frequency == "monthly") else None

            relative_start = None
            for label, pat in RELATIVE_START_PATTERNS.items():
                if pat.search(lowered):
                    relative_start = label
                    break

            return ProposedAction(
                kind="sip_create",
                amount=amount,
                frequency=frequency,
                day_of_month=day_of_month,
                relative_start=relative_start,
                resolved_by="pattern",
            )

        return None

    price_query = PRICE_QUERY_RE.search(lowered)
    if price_query:
        return ProposedAction(kind="price_query", amount=price_query.group(1), resolved_by="pattern")

    for pat in PURCHASE_PATTERNS:
        m = pat.search(text)
        if m:
            return ProposedAction(kind="purchase", amount=m.group(1), resolved_by="pattern")

    return None
