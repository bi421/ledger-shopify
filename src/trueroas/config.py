import yaml
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from zoneinfo import ZoneInfo

class Settings(BaseSettings):
    timezone: str = "Asia/Ulaanbaatar"
    currency_base: str = "USD"
    attribution_default: str = "7d_click_1d_view"
    meta_api_version: str = "v19.0"
    paths: dict[str, str] = Field(
        default_factory=lambda: {
            "raw": "data/raw",
            "clean": "data/clean",
            "warehouse": "data/warehouse.duckdb",
        }
    )
    
    FB_ACCESS_TOKEN: str = Field("local-dev-token", env="FB_ACCESS_TOKEN")
    FB_APP_ID: str = Field("local-dev-app", env="FB_APP_ID")
    FB_APP_SECRET: str = Field("local-dev-secret", env="FB_APP_SECRET")
    SLACK_WEBHOOK_URL: str | None = Field(None, env="SLACK_WEBHOOK_URL")
    SHOPIFY_ACCESS_TOKEN: str = Field("local-dev-token", env="SHOPIFY_ACCESS_TOKEN")
    SHOPIFY_STORE_URL: str = Field("localhost", env="SHOPIFY_STORE_URL")

    # Stitching Heuristics
    stitch_confidence_floor: float = 0.1
    stitch_confidence_ceiling: float = 0.9

    # Financial Reconciliation thresholds
    recon_variance_threshold: float = 0.10
    recon_critical_variance_threshold: float = 0.20
    recon_consecutive_weeks: int = 2
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, v: str) -> str:
        ZoneInfo(v)
        return v

@lru_cache()
def get_settings():
    config_path = Path("config/settings.yaml")
    with open(config_path, "r") as f:
        yaml_config = yaml.safe_load(f)
    
    # Merge YAML into environment settings
    return Settings(**yaml_config)
