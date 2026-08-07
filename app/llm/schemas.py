

from dataclasses import dataclass, field

ACTION_KINDS = {
    "purchase",
    "sip_create",
    "sip_pause",
    "sip_resume",
    "sip_cancel",
    "price_query",
    "info",       
                  
    "clarify",    
}


@dataclass
class ProposedAction:
    kind: str

    # purchase / sip_create / price_query
    amount: str | None = None

    # sip_create
    frequency: str | None = None
    day_of_month: int | None = None          # explicit "from the Nth"
    relative_start: str | None = None        # "today" | "yesterday" | "tomorrow"
    explicit_date: str | None = None         # ISO date, if the user gave one directly

    # sip_pause / sip_resume / sip_cancel
    sip_ref: str | None = None               # rarely resolvable from text alone

    # info / clarify
    reply_text: str | None = None
    clarify_options: list[str] = field(default_factory=list)

    # provenance — which tier produced this, for the audit trail
    resolved_by: str = "pattern"             # "pattern" | "llm"

    def __post_init__(self):
        if self.kind not in ACTION_KINDS:
            raise ValueError(f"unknown ProposedAction kind: {self.kind}")
