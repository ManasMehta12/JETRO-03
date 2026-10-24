from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Takumi Knowledge Engine"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./data/takumi.db"
    demo_mode: bool = True
    enable_demo_auth: bool = True
    enable_demo_seed: bool = True
    enable_demo_reset: bool = True
    demo_seed_state: Literal["fresh", "approved_baseline"] = "fresh"
    enable_grounded_qa: bool = True
    enable_training_pack_export: bool = True
    demo_signing_secret: SecretStr | None = None
    demo_token_ttl_minutes: int = Field(480, ge=1, le=1440)
    ai_provider: Literal["fixture", "gemini"] = "fixture"
    enable_live_extraction: bool = False
    enable_live_gap_generation: bool = False
    enable_live_qa: bool = False
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    enable_media_upload: bool = False
    enable_media_processing: bool = False
    enable_media_streaming: bool = False
    max_upload_mb: int = 100
    max_video_duration_seconds: int = 240
    enable_processing_worker: bool = False
    processing_max_retries: int = 2
    enable_multilingual: bool = False
    enable_embeddings: bool = False
    enable_advanced_retrieval: bool = False
    log_level: str = "INFO"
    log_model_inputs: bool = False
    cors_origins: str = "http://localhost:3000"
    max_request_body_kb: int = 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_capabilities(self):
        reserved = {
            "ai_provider": 5,
            "enable_live_extraction": 5,
            "enable_media_processing": 5,
            "enable_processing_worker": 5,
            "log_model_inputs": 5,
            "enable_media_upload": 4,
            "enable_media_streaming": 4,
            "enable_live_gap_generation": 6,
            "enable_live_qa": 6,
            "enable_multilingual": 6,
            "enable_embeddings": 6,
            "enable_advanced_retrieval": 6,
        }
        for field, checkpoint in reserved.items():
            enabled = (
                self.ai_provider == "gemini" if field == "ai_provider" else getattr(self, field)
            )
            if enabled:
                name = "AI_PROVIDER=gemini" if field == "ai_provider" else field.upper()
                raise ValueError(
                    f"{name} is reserved for Checkpoint {checkpoint} and not implemented in V1"
                )
        for field in ("demo_mode", "enable_demo_auth", "enable_demo_reset", "enable_demo_seed"):
            if self.app_env == "production" and getattr(self, field):
                raise ValueError(f"{field.upper()} must be false when APP_ENV=production")
        for field in ("enable_demo_auth", "enable_demo_reset", "enable_demo_seed"):
            if not self.demo_mode and getattr(self, field):
                raise ValueError(f"{field.upper()} requires DEMO_MODE=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
