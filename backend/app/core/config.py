from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Deploy lock — one vertical per database (see docs/VERTICAL_BOUNDARIES.md).
    DEPLOY_VERTICAL: str = "LIVEWELL360"
    # Empty uses the default sqlite file for DEPLOY_VERTICAL (safehomeops.db, etc.).
    DATABASE_URL: str = ""

    # Public-facing product name (marketing, family portal copy, AI prompts, customer docs).
    # Keep DEPLOY_VERTICAL=LIVEWELL360 as the stable internal id when renaming the brand.
    BRAND_NAME: str = "KushAlaya"

    SECRET_KEY: str = "changedsecretkey"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    CORS_ORIGINS: str = "*"

    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 10

    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER: str = "documents"

    # S3-compatible object storage (Cloudflare R2, Backblaze B2, AWS S3).
    # Enable with STORAGE_BACKEND=s3 (or r2). Keep local default until you switch.
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "auto"
    S3_PUBLIC_BASE_URL: str = ""  # optional CDN/custom domain; otherwise key-only URLs

    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""
    ENABLE_TELEMETRY: bool = True

    # Outbound alerts: log (default) | ses | msg91 | meta (WhatsApp stub) — see docs/NOTIFICATIONS.md
    NOTIFICATION_EMAIL_PROVIDER: str = "log"
    NOTIFICATION_SMS_PROVIDER: str = "log"
    NOTIFICATION_WHATSAPP_PROVIDER: str = "log"

    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_FROM_EMAIL: str = ""

    # Gmail / generic SMTP (NOTIFICATION_EMAIL_PROVIDER=smtp)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "KushAlaya"
    # Extra SOS/alert recipients (comma-separated). Defaults to SMTP_FROM_EMAIL when empty.
    SMTP_ALERT_TO: str = ""
    # Android app SOS alarm (FCM HTTP v1). Service-account JSON path, or the JSON inline.
    # Empty: no pushes; the web siren works as before. See mobile/README.md.
    FCM_SERVICE_ACCOUNT_FILE: str = ""
    FCM_SERVICE_ACCOUNT_JSON: str = ""
    FCM_PROJECT_ID: str = ""
    # Android app self-update files (app/api/v1/app_release.py). Empty: backend/releases.
    APP_RELEASES_DIR: str = ""
    # Public family self-sign-up (phone match). Off: anyone knowing a client's phone could
    # claim their family login. Families get logins from staff (Clients → Add family member).
    ALLOW_FAMILY_SELF_REGISTER: bool = False

    MSG91_AUTH_KEY: str = ""
    MSG91_SENDER_ID: str = ""
    MSG91_ROUTE: str = "4"
    MSG91_TEMPLATE_ID: str = ""
    # WhatsApp via MSG91 (NOTIFICATION_WHATSAPP_PROVIDER=msg91). Number as 91XXXXXXXXXX.
    MSG91_WHATSAPP_NUMBER: str = ""
    # Approved utility template with one {{1}} variable; carries every free-text alert.
    MSG91_WHATSAPP_TEXT_TEMPLATE: str = "kushalaya_update"

    # Twilio SMS + WhatsApp (lab: trial account + verified personal number)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_SMS_FROM: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"
    TWILIO_ALERT_TO: str = ""

    # Telegram (free lab SOS alerts)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # WhatsApp Business Platform (Meta Cloud API) — stub until BSP onboarding
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_API_VERSION: str = "v21.0"

    DOCUMENT_INTELLIGENCE_ENDPOINT: str = ""
    DOCUMENT_INTELLIGENCE_KEY: str = ""
    DOCUMENT_INTELLIGENCE_API_VERSION: str = "2024-11-30"
    DOCUMENT_INTELLIGENCE_MODEL: str = "prebuilt-idDocument"

    # Azure OpenAI — Workforce Copilot (optional)
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2025-01-01-preview"
    AZURE_OPENAI_TEMPERATURE: float = 0.2
    AZURE_OPENAI_MAX_TOKENS: int = 1200

    # Session activity timeline (Session activity UI).
    # standard (default): meaningful user actions + AI/system events; API calls only for
    #   mutations and errors — not list/hydration GETs.
    # verbose: also log successful GETs (rubric, catalog, auth/me, list sync, …).
    ACTIVITY_LOG_MODE: str = "standard"

    # LiveWell AI — Contract C (room analysis) + Contract E (image edit)
    GEMINI_API_KEY: str = ""
    AI_VISION_PROVIDER: str = "gemini"  # gemini | none
    AI_VISION_MODEL: str = "gemini-3.5-flash"
    # Tried in order when AI_VISION_MODEL returns 404 (model retired / not enabled).
    AI_VISION_MODEL_FALLBACKS: str = "gemini-2.5-flash,gemini-2.0-flash"
    FAL_KEY: str = ""
    AI_RENDER_PROVIDER: str = ""  # optional override: gemini_image | gpt_image | fal_kontext | local_stub | none
    # Gemini room previews (provider gemini_image): fast model first, stronger model for the QA retry.
    AI_IMAGE_GEMINI_MODEL: str = "gemini-3.1-flash-image"
    AI_IMAGE_GEMINI_RETRY_MODEL: str = "gemini-3-pro-image"
    # GPT Image room previews (provider gpt_image). Azure endpoint/key default to the chat ones above.
    AZURE_OPENAI_IMAGE_DEPLOYMENT: str = ""  # e.g. gpt-image-1-mini
    AI_IMAGE_QUALITY: str = "medium"  # low | medium | high (cost grows with quality)
    AZURE_OPENAI_IMAGE_ENDPOINT: str = ""
    AZURE_OPENAI_IMAGE_API_KEY: str = ""
    AZURE_OPENAI_IMAGE_API_VERSION: str = "2025-04-01-preview"
    OPENAI_API_KEY: str = ""
    OPENAI_IMAGE_MODEL: str = "gpt-image-1-mini"

    DEFAULT_CAREGIVER_HOURLY_RATE: float = 250.0
    DEFAULT_ELDER_HOURLY_RATE: float = 450.0
    DEFAULT_GST_RATE: float = 18.0
    DEFAULT_INVOICE_PAYMENT_DAYS: int = 30

    STRIPE_SECRET_KEY: str = ""
    RAZORPAY_KEY_ID: str = ""

    # Reject location events when reported GPS accuracy is worse than this (meters).
    # Mobile browsers often report 50–100m indoors; use 100 for pilots, 30 for strict prod.
    MAX_GPS_ACCURACY_METERS: float = 100.0

    CHECKR_WEBHOOK_SECRET: str = ""

    # LiveWell IoT (MG7 → Mosquitto → iot_ingestor → POST /api/v1/iot/events)
    IOT_INGEST_API_KEY: str = ""
    IOT_MQTT_RUNTIME: str = "/var/lib/safehomeops/mqtt"
    IOT_MQTT_PUBLIC_HOST: str = "ops.kushalaya.com"
    # Privileged helper for Wearables "Apply to Mosquitto" (sudo -n via install-safehome-sudoers.sh)
    IOT_MQTT_APPLY_SCRIPT: str = "/opt/safehomeops/app/scripts/deploy/apply-mqtt-hub-user.sh"
    IOT_MQTT_INGESTOR_APPLY_SCRIPT: str = "/opt/safehomeops/app/scripts/deploy/apply-mqtt-ingestor.sh"

    # Family prepaid wallet — Razorpay. Leave keys blank to run the stub
    # provider (no network calls, recharges settle locally for dev/demo).
    PAYMENTS_PROVIDER: str = "stub"  # stub | razorpay
    PAYMENTS_CURRENCY: str = "INR"
    WALLET_MIN_RECHARGE_MINOR: int = 10_000  # ₹100
    WALLET_MAX_RECHARGE_MINOR: int = 5_000_000  # ₹50,000
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.CORS_ORIGINS or "*").strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
