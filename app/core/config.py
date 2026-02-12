import os
from dotenv import load_dotenv

load_dotenv()

# -------- JWT --------
JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret")
JWT_ALGO = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

# -------- Admin Teacher Code --------
ADMIN_TEACHER_CODE = os.getenv("ADMIN_TEACHER_CODE", "ABHYAAS-TEACHER-2026")

# -------- Database --------
DATABASE_URL = os.getenv("DATABASE_URL")

# -------- Base URL (optional) --------
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# -------- Twilio --------
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")  # Required only for Twilio call webhook
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# -------- SendGrid --------
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")  # verified sender in sendgrid
