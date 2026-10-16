"""Settings. Values come from environment variables or a .env file (see .env.example)."""
import os

from dotenv import load_dotenv

load_dotenv()

_db = os.getenv("DATABASE_URL", "sqlite:///sewa.db").strip()
# Some hosts give "postgres://", SQLAlchemy needs "postgresql://".
DATABASE_URL = "postgresql://" + _db[len("postgres://"):] if _db.startswith("postgres://") else _db

# DEV_MODE=1: the login code is also returned to the browser and sample departments are loaded.
# Use it ONLY on your own computer. On the internet always use DEV_MODE=0.
DEV_MODE = os.getenv("DEV_MODE", "1") == "1"

# This email becomes the top admin when it logs in.
SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "").strip().lower()

COUNTRY_CODE = os.getenv("COUNTRY_CODE", "91")

# How login codes are sent: "console" (printed in the server log), "brevo" (email API), or "smtp".
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "console").strip().lower()
EMAIL_FROM = os.getenv("EMAIL_FROM", "").strip()
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Sewa").strip()
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Leave empty to only save alerts inside the app and print WhatsApp messages in the server log.
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
