from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Influencer Video Intelligence"
    database_url: str = Field(default="sqlite:///./sushi.db", alias="DATABASE_URL")
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
    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

