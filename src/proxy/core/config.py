from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "moonshot-proxy"
    version: str = "0.1.0"

    # Provider selection (swap the adapter without touching proxy/mapper code).
    provider_name: str = "openligadb"
    provider_base_url: str = "https://www.openligadb.de"

    # HTTP client
    upstream_timeout_s: float = 10.0

    # Rate limiting: max upstream requests per second (per process). 0 disables.
    upstream_rate_per_sec: float = 5.0

    # Exponential backoff with jitter on transient upstream errors.
    upstream_max_retries: int = 3
    upstream_backoff_base_s: float = 0.2

    # Logging
    log_body_max_chars: int = 512


settings = Settings()
