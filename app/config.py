from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):


    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "kuberai-clone"
    environment: str = "development"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "sqlite:///./data/app.db"

    # --- Money / purchase limits ---
    # ₹1 minimum: low barrier to entry, cleanly rejects dust amounts like ₹0.5.
    # ₹5,00,000 maximum: well above realistic retail digital-gold ticket size,
    min_purchase_inr: Decimal = Decimal("1.00")
    max_purchase_inr: Decimal = Decimal("500000.00")

    # --- Idempotency ---
    purchase_dedup_window_seconds: int = 60

    # --- Price provider ---
    price_cache_ttl_seconds: int = 60
    # Hard ceiling on how stale a cached price may be used during an
    # outage before the system fails safe instead of executing against
    # a possibly-wrong price.
    price_staleness_ceiling_seconds: int = 600  # 10 minutes
    # Illustrative starting point for the simulated feed — real 24K INR/gram
    # rate as of Aug 2026 is roughly this; the simulated provider then does
    # a small bounded random walk from here on each call.
    price_base_inr_per_gram: Decimal = Decimal("14500.0000")

    # --- SIP scheduler ---
    scheduler_poll_interval_seconds: int = 60

    # --- LLM (Groq) ---
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

settings = Settings()
