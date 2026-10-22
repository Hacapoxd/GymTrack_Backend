"""Configuracion central (variables de entorno con valores por defecto de desarrollo)."""
import os

from dotenv import load_dotenv

load_dotenv()   # lee el archivo .env si existe (nunca pisa variables ya definidas, p. ej. las de Railway)

def _db_url() -> str:
    """Railway entrega postgres:// o postgresql://; SQLAlchemy necesita el driver explicito (psycopg v3)."""
    url = os.getenv("DATABASE_URL", "sqlite:///./gymtrack.db")
    for old in ("postgres://", "postgresql://"):
        if url.startswith(old):
            return "postgresql+psycopg://" + url[len(old):]
    return url


DATABASE_URL = _db_url()
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 30
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
CONSENT_VERSION = "1.0"
# Origenes permitidos para el frontend (separados por coma). "*" solo para desarrollo.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# ---- IA asistida por token (opcional). Sin AI_API_KEY las funciones de IA quedan apagadas y el resto funciona igual.
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic").lower()   # anthropic | openai (API compatible con OpenAI, p. ej. Gemini o Groq)
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")                          # anthropic: por defecto un modelo pequeno y barato
AI_BASE_URL = os.getenv("AI_BASE_URL", "")
AI_MAX_OUTPUT_TOKENS = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "1500"))
AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "10"))       # propuestas por usuario y por dia (control de costo)
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
