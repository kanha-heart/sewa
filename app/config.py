"""Settings. Values come from environment variables or a .env file (see .env.example)."""
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sewa.db")

# DEV_MODE=1: the login code is also returned to the browser and sample departments are loaded.
# Set DEV_MODE=0 when you deploy for real users.
DEV_MODE = os.getenv("DEV_MODE", "1") == "1"

# This phone number becomes the top admin when it logs in (10 digits, no country code).
SUPERADMIN_PHONE = "".join(ch for ch in os.getenv("SUPERADMIN_PHONE", "9000000000") if ch.isdigit())[-10:]

COUNTRY_CODE = os.getenv("COUNTRY_CODE", "91")

# Leave empty to only print WhatsApp messages in the server console.
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
