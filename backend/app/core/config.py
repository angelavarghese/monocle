from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./monocle.db"
    jwt_secret_key: str = "development-only-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    market_data_provider: str = "finnhub"
    finnhub_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    chat_max_tokens: int = 200
    chat_rate_limit_per_minute: int = 10
    cors_origins: list[str] = ["http://localhost:3000"]
    poll_interval_seconds: int = 60
    stale_threshold_minutes: int = 5
    price_move_threshold_pct: float = 2.0
    volume_spike_multiplier: float = 2.0
    sector_deviation_threshold_pct: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
