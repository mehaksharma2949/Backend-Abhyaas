from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse
from datetime import datetime, timedelta

from app.core.deps import get_db
from app.core.config import PUBLIC_BASE_URL, TWILIO_PHONE_NUMBER
from app.core.utils_phone import normalize_phone, is_valid_phone

from app.models.auth_models import User, OTPCode
from app.models.auth_schemas import (
    SendEmailOTP, VerifyEmailOTP,
    SendPhoneOTP, VerifyPhoneOTP
)

from app.services.otp_service import generate_otp
from app.services.email_service import send_email_otp
from app.services.twilio_service import get_twilio_client


router = APIRouter(tags=["OTP"])


# ---------------- EMAIL OTP ----------------
@router.post("/email/send")
def send_email(body: SendEmailOTP, db: Session = Depends(get_db)):

    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = generate_otp()

    db.add(OTPCode(user_id=user.id, channel="email", otp_code=otp))
    db.commit()

    send_email_otp(email, otp)

    return {"message": "Email OTP sent"}


@router.post("/email/verify")
def verify_email(body: VerifyEmailOTP, db: Session = Depends(get_db)):

    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp_row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.channel == "email")
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not otp_row:
        raise HTTPException(status_code=400, detail="OTP not found")

    now = datetime.now(otp_row.created_at.tzinfo)
    if now - otp_row.created_at > timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="OTP expired")

    if otp_row.otp_code != body.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user.is_email_verified = True
    db.commit()

    return {"message": "Email verified successfully"}


# ---------------- PHONE OTP (TWILIO VOICE CALL) ----------------
@router.post("/phone/send")
def send_phone(body: SendPhoneOTP, db: Session = Depends(get_db)):

    phone = normalize_phone(body.phone)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=400, detail="Invalid phone")

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = generate_otp()

    db.add(OTPCode(user_id=user.id, channel="phone", otp_code=otp))
    db.commit()

    if not PUBLIC_BASE_URL:
        raise HTTPException(
            status_code=500,
            detail="PUBLIC_BASE_URL missing (required for Twilio webhook)"
        )

    try:
        client = get_twilio_client()

        twiml_url = f"{PUBLIC_BASE_URL}/otp/twilio-voice?otp={otp}"

        client.calls.create(
            to=phone,
            from_=TWILIO_PHONE_NUMBER,
            url=twiml_url
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio call failed: {str(e)}")

    return {"message": "OTP call initiated"}


@router.post("/phone/verify")
def verify_phone(body: VerifyPhoneOTP, db: Session = Depends(get_db)):

    phone = normalize_phone(body.phone)
    user = db.query(User).filter(User.phone == phone).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp_row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.channel == "phone")
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not otp_row:
        raise HTTPException(status_code=400, detail="OTP not found")

    now = datetime.now(otp_row.created_at.tzinfo)
    if now - otp_row.created_at > timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="OTP expired")

    if otp_row.otp_code != body.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user.is_phone_verified = True
    db.commit()

    return {"message": "Phone verified successfully"}


# ---------------- TWILIO WEBHOOK ----------------
@router.api_route("/twilio-voice", methods=["GET", "POST"])
async def twilio_voice(request: Request):

    otp = request.query_params.get("otp", "000000")
    spaced_otp = " ".join(list(otp))

    response = VoiceResponse()
    response.say(f"Your Abhyaas verification code is {spaced_otp}.", language="en-IN")
    response.pause(length=1)
    response.say(f"I repeat. Your code is {spaced_otp}.", language="en-IN")

    return Response(content=str(response), media_type="application/xml")
