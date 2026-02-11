import os
from twilio.rest import Client
from app.core.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

def get_twilio_client():
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        raise RuntimeError("Twilio credentials missing")
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_otp_call(phone: str, otp: str):
    if not PUBLIC_BASE_URL:
        raise RuntimeError("PUBLIC_BASE_URL missing in .env")

    client = get_twilio_client()

    twiml_url = f"{PUBLIC_BASE_URL}/otp/twilio-voice?otp={otp}"

    call = client.calls.create(
        to=phone,
        from_=TWILIO_PHONE_NUMBER,
        url=twiml_url
    )

    return call.sid
