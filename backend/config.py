from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    GOOGLE_CLOUD_PROJECT: str = "keraltysandbox"
    GOOGLE_CLOUD_REGION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    USE_VERTEX_AI: bool = False
    GOOGLE_API_KEY: Optional[str] = None
    # Rolling AI Studio aliases (July 2026: resolve to gemini-3.5-flash /
    # gemini-3.1-pro-preview). gemini-2.5-flash/pro were HARD-DEPRECATED on the
    # AI Studio key path ("no longer available", 404) — pinned versions die;
    # the -latest aliases survive deprecations. NOTE: these aliases do NOT
    # exist on Vertex AI — a rollback to GOOGLE_GENAI_USE_VERTEXAI=1 must also
    # override both env vars with explicit Vertex model IDs.
    GEMINI_FLASH_MODEL: str = "gemini-flash-latest"
    GEMINI_PRO_MODEL: str = "gemini-pro-latest"
    GEMINI_LIVE_MODEL: str = "gemini-live-2.5-flash-native-audio"
    # Probed July 2026: only imagen-3.0-generate-001 is served on keraltysandbox
    # (imagen-4.0-* and 3.0-002 return 404). image_tools has a fallback chain, so
    # bumping this when newer models land is just a setting change.
    IMAGEN_MODEL: str = "imagen-3.0-generate-001"
    IMAGEN_ASPECT_RATIO: str = "16:9"
    # Google Slides IDs of the corporate template decks (converted from the
    # re-themed branding/generated/*.pptx by scripts/upload_slides_template.py).
    # Empty = decks start from a blank default-themed presentation.
    SLIDES_TEMPLATE_ID: str = ""                      # Template_Keralty (default)
    SLIDES_TEMPLATE_ID_PRESIDENCIA_CORP: str = ""     # Template_Presidencia__Corporativo
    SLIDES_TEMPLATE_ID_PRESIDENCIA_STD: str = ""      # Template_Presidencia__Estandar
    # Brand engine font: the Google-catalog stand-in for Clan Pro (which the
    # Slides/Docs APIs cannot render). Confirmed empirically via thumbnail probe.
    BRAND_ENGINE_FONT: str = "Archivo"
    BRAND_LOGOS_ENABLED: bool = True
    GEMINI_TTS_MODEL: str = "gemini-2.5-flash-preview-tts"
    GEMINI_TTS_VOICE: str = "Kore"

    # Multi-LLM chat (model picker). Keys must be ambient in os.environ on
    # Cloud Run — LiteLLM/openai read them directly. A missing key hides that
    # provider's models from the picker (GET /api/models).
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MODEL_ID_CLAUDE_FABLE: str = "claude-fable-5"
    MODEL_ID_CLAUDE_OPUS: str = "claude-opus-4-8"
    MODEL_ID_CLAUDE_SONNET: str = "claude-sonnet-5"
    MODEL_ID_CLAUDE_HAIKU: str = "claude-haiku-4-5-20251001"
    # OpenAI ids probed live against the account's /v1/models (July 2026) —
    # env-overridable if OpenAI renames them.
    MODEL_ID_OPENAI_SOL: str = "gpt-5.6-sol"
    MODEL_ID_OPENAI_TERRA: str = "gpt-5.6-terra"
    MODEL_ID_OPENAI_LUNA: str = "gpt-5.6-luna"
    MODEL_ID_OPENAI_GPT55: str = "gpt-5.5"
    OPENAI_IMAGE_MODEL: str = "gpt-image-2"  # probed available July 2026

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/callback"

    USE_IAP: bool = False
    USE_AGENT_ENGINE: bool = False
    USE_RAG_ENGINE: bool = False
    USE_LIVEKIT: bool = False
    SEARCH_GROUNDING_ENABLED: bool = False
    VOICE_ENABLED: bool = True
    SLIDES_ENABLED: bool = True
    IMAGE_GEN_ENABLED: bool = True
    ADMIN_PANEL_ENABLED: bool = False

    FIRESTORE_DATABASE: str = "(default)"
    GCS_BUCKET: str = "keralty-agent-dev-artifacts"
    
    SECRET_KEY: str = "super-secret-key-replace-in-prod"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"

    LOG_LEVEL: str = "INFO"
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "keralty-agent-backend"
    ERROR_REPORTING_ENABLED: bool = False

    EMAIL_GMAIL_ENABLED: bool = True
    EMAIL_GMAIL_SCOPES: str = "https://www.googleapis.com/auth/gmail.modify"
    EMAIL_OUTLOOK_ENABLED: bool = False
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_REDIRECT_URI: str = "http://localhost:8000/auth/outlook/callback"
    EMAIL_SEND_ENABLED: bool = True
    EMAIL_TRACKING_ENABLED: bool = True
    EMAIL_TRACKING_FOLLOWUP_DAYS: int = 3
    EMAIL_MAX_THREADS: int = 50
    EMAIL_DIGEST_ENABLED: bool = True

    # Correo Ejecutivo v2 — incremental scan over a rolling window.
    EMAIL_SCAN_WINDOW_DAYS: int = 7        # default; per-user override on users doc (clamped 3-14)
    EMAIL_SCAN_MAX_THREADS: int = 150      # hard cap per scan (inbox + sent combined)
    EMAIL_ANALYSIS_BATCH_SIZE: int = 15    # threads per Gemini analysis call
    EMAIL_SCAN_COOLDOWN_SECONDS: int = 60  # double-open guard: serve stored state within this window

    # Phase 3 — machine-invoked endpoints (/hooks/*). Empty SA email disables them (404).
    GMAIL_PUSH_TOPIC: str = "projects/keraltysandbox/topics/gmail-notifications"
    HOOKS_OIDC_SERVICE_ACCOUNT: str = ""
    HOOKS_OIDC_AUDIENCE: str = ""

    NEWS_CACHE_TTL_HOURS: int = 4
    NEWS_MAX_ITEMS_PER_SOURCE: int = 10
    NEWS_MAX_AGE_HOURS: int = 24

    KB_AGENT_ENABLED: bool = True
    KB_RAG_CORPUS_ID: str = "keralty-kb-corpus-prod"
    KB_INDEX_ENDPOINT: Optional[str] = None
    KB_MAX_RESULTS: int = 10

    # RAG pipeline knobs (E1-E10 guardrails)
    RAG_CHUNK_TARGET_TOKENS: int = 800
    RAG_CHUNK_MAX_TOKENS: int = 1000
    RAG_CHUNK_OVERLAP_PCT: float = 0.15
    RAG_CHUNK_MIN_TOKENS: int = 120
    RAG_K_DENSE: int = 30
    RAG_K_SPARSE: int = 30
    RAG_K_FUSED: int = 20
    RAG_RERANK_TOP_K: int = 8
    RAG_REWRITE_COUNT: int = 3
    RAG_NEIGHBOR_WINDOW: int = 1
    RAG_ABSTAIN_THRESHOLD: float = 0.5
    RAG_EMBED_MODEL: str = "text-embedding-005"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
