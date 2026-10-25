from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Apify
    apify_token: str = ""
    apify_actor_id: str = "trudax~reddit-scraper-lite"

    # Anthropic
    anthropic_api_key: str = ""
    scoring_model: str = "claude-haiku-5-5"
    drafting_model: str = "claude-sonnet-5-5"

    # App
    database_url: str = "sqlite+aiosqlite:///./leadroom.db"
    scan_interval_minutes: int = 60
    max_post_age_hours: int = 24
    min_intent_score: int = 50
    product_description: str = (
        "A SaaS tool that helps founders find customers on Reddit."
    )
    posting_handle: str = "your_reddit_handle"


settings = Settings()
