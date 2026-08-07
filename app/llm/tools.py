TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_purchase",
            "description": "Execute a one-time gold purchase for the amount the user specified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "string",
                        "description": (
                            "The rupee amount exactly as the user stated it, as a decimal "
                            "string (e.g. '333.33'). Do not round, reinterpret, or convert it."
                        ),
                    }
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_sip_create",
            "description": (
                "Create a recurring gold purchase (SIP). Describe what the user said — "
                "never compute an actual calendar date yourself; the system resolves the "
                "real schedule from these fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "string", "description": "Rupee amount per installment, as a decimal string."},
                    "frequency": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "day_of_month": {
                        "type": "integer",
                        "description": (
                            "1-31, ONLY if the user named a specific day of the month for a "
                            "monthly SIP (e.g. 'from the 31st'). Omit otherwise."
                        ),
                    },
                    "relative_start": {
                        "type": "string",
                        "enum": ["today", "yesterday", "tomorrow"],
                        "description": "Only if the user described the start using exactly one of these words.",
                    },
                    "explicit_date": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD, only if the user gave an explicit calendar date.",
                    },
                },
                "required": ["amount", "frequency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_sip_pause",
            "description": "Pause an existing SIP.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_sip_resume",
            "description": "Resume a paused SIP.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_sip_cancel",
            "description": "Cancel a SIP.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_clarification",
            "description": (
                "The request is genuinely ambiguous about what action to take. "
                "Ask exactly one clear question before doing anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["question"],
            },
        },
    },
]
