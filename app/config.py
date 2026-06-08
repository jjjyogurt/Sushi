from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Influencer Video Intelligence"
    database_url: str = Field(default="sqlite:///./sushi.db", alias="DATABASE_URL")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    secure_cookies: bool = Field(default=False, alias="SECURE_COOKIES")
    auth_allow_user_enumeration: Optional[bool] = Field(default=None, alias="AUTH_ALLOW_USER_ENUMERATION")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model_analysis: str = Field(default="gemini-3-flash", alias="GEMINI_MODEL_ANALYSIS")
    gemini_model_chat: str = Field(default="gemini-3-flash", alias="GEMINI_MODEL_CHAT")
    analysis_version: str = Field(default="v1", alias="ANALYSIS_VERSION")
    default_language: str = "en"
    enable_mock_discovery: bool = Field(default=False, alias="ENABLE_MOCK_DISCOVERY")
    transcript_preferred_languages: str = Field(default="en,de,es,fr,it,ja,ko,zh-Hans", alias="TRANSCRIPT_LANGUAGES")
    youtube_transcript_api_key: str = Field(default="", alias="YOUTUBE_TRANSCRIPT_API_KEY")
    youtube_transcript_base_url: str = Field(
        default="https://www.youtubetranscript.dev/api/v2",
        alias="YOUTUBE_TRANSCRIPT_BASE_URL",
    )
    youtube_transcript_timeout_seconds: float = Field(default=30.0, alias="YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS")
    youtube_transcript_max_retries: int = Field(default=1, alias="YOUTUBE_TRANSCRIPT_MAX_RETRIES")
    youtube_data_api_key: str = Field(default="", alias="YOUTUBE_DATA_API_KEY")
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")
    serpapi_timeout_seconds: float = Field(default=20.0, alias="SERPAPI_TIMEOUT_SECONDS")
    youtube_comments_timeout_seconds: float = Field(default=30.0, alias="YOUTUBE_COMMENTS_TIMEOUT_SECONDS")
    youtube_comments_max_retries: int = Field(default=2, alias="YOUTUBE_COMMENTS_MAX_RETRIES")
    youtube_comments_page_size: int = Field(default=100, alias="YOUTUBE_COMMENTS_PAGE_SIZE")
    youtube_comments_max_pages: int = Field(default=200, alias="YOUTUBE_COMMENTS_MAX_PAGES")
    youtube_comments_max_reply_pages: int = Field(default=20, alias="YOUTUBE_COMMENTS_MAX_REPLY_PAGES")
    analysis_max_transcript_chars: int = Field(default=3000000, alias="ANALYSIS_MAX_TRANSCRIPT_CHARS")
    analysis_single_pass_max_estimated_tokens: int = Field(
        default=750000,
        alias="ANALYSIS_SINGLE_PASS_MAX_ESTIMATED_TOKENS",
    )
    analysis_estimated_chars_per_token: int = Field(default=4, alias="ANALYSIS_ESTIMATED_CHARS_PER_TOKEN")
    analysis_chunk_chars: int = Field(default=12000, alias="ANALYSIS_CHUNK_CHARS")
    analysis_chunk_overlap_chars: int = Field(default=1200, alias="ANALYSIS_CHUNK_OVERLAP_CHARS")
    analysis_max_chunks: int = Field(default=12, alias="ANALYSIS_MAX_CHUNKS")
    chat_max_context_chars: int = Field(default=24000, alias="CHAT_MAX_CONTEXT_CHARS")
    voc_failed_ratio_warn: float = Field(default=0.01, alias="VOC_FAILED_RATIO_WARN")
    voc_failed_ratio_ack: float = Field(default=0.05, alias="VOC_FAILED_RATIO_ACK")
    voc_confidence_high: float = Field(default=0.8, alias="VOC_CONFIDENCE_HIGH")
    voc_confidence_medium: float = Field(default=0.6, alias="VOC_CONFIDENCE_MEDIUM")
    gcp_project_id: str = Field(default="", alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="asia-southeast1", alias="GCP_REGION")
    analysis_worker_url: str = Field(default="", alias="ANALYSIS_WORKER_URL")
    analysis_worker_tasks_queue: str = Field(default="", alias="ANALYSIS_WORKER_TASKS_QUEUE")
    analysis_worker_task_service_account_email: str = Field(
        default="",
        alias="ANALYSIS_WORKER_TASK_SERVICE_ACCOUNT_EMAIL",
    )
    analysis_worker_internal_token: str = Field(default="", alias="ANALYSIS_WORKER_INTERNAL_TOKEN")
    analysis_worker_drain_path: str = Field(
        default="/internal/analysis-worker/drain",
        alias="ANALYSIS_WORKER_DRAIN_PATH",
    )
    analysis_worker_dispatch_deadline_seconds: int = Field(
        default=1800,
        alias="ANALYSIS_WORKER_DISPATCH_DEADLINE_SECONDS",
    )
    analysis_worker_drain_max_seconds: float = Field(
        default=1200.0,
        alias="ANALYSIS_WORKER_DRAIN_MAX_SECONDS",
    )
    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True, extra="ignore")

    def use_secure_cookies(self) -> bool:
        return self.secure_cookies or self.environment.lower() == "production"

    def public_user_list_allowed(self) -> bool:
        if self.auth_allow_user_enumeration is not None:
            return self.auth_allow_user_enumeration
        return self.environment.lower() != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
