from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.deps import get_db
from app.models.auth_schemas import SignupEmail, SignupPhone, LoginBody, RefreshBody, ResetPasswordBody
from app.models.auth_models import User, RefreshToken, OTPCode

from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token
)

from app.core.config import ADMIN_TEACHER_CODE
from app.core.utils_phone import normalize_phone, is_valid_phone


router = APIRouter(tags=["Auth"])


# ----------------- SIGNUP EMAIL -----------------
@router.post("/signup/email")
def signup_email(body: SignupEmail, db: Session = Depends(get_db)):

    role = body.role.lower().strip()
    if role not in ["student", "teacher"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    # ✅ bcrypt safety
    if len(body.password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")

    if role == "teacher":
        if body.admin_code != ADMIN_TEACHER_CODE:
            raise HTTPException(status_code=403, detail="Invalid admin code")

    email = body.email.lower()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=body.name,
        email=email,
        phone=None,
        password_hash=hash_password(body.password),
        role=role
    )
    db.add(user)
    db.commit()

    return {"message": "User created. Now verify email OTP using /otp/email/send"}


# ----------------- SIGNUP PHONE -----------------
@router.post("/signup/phone")
def signup_phone(body: SignupPhone, db: Session = Depends(get_db)):

    role = body.role.lower().strip()
    if role not in ["student", "teacher"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    # ✅ bcrypt safety
    if len(body.password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")

    if role == "teacher":
        if body.admin_code != ADMIN_TEACHER_CODE:
            raise HTTPException(status_code=403, detail="Invalid admin code")

    phone = normalize_phone(body.phone)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=400, detail="Invalid phone number")

    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = User(
        name=body.name,
        email=None,
        phone=phone,
        password_hash=hash_password(body.password),
        role=role
    )
    db.add(user)
    db.commit()

    return {"message": "User created. Now verify phone OTP using /otp/phone/send"}


# ----------------- LOGIN -----------------
@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):

    identifier = body.identifier.strip()

    if "@" in identifier:
        user = db.query(User).filter(User.email == identifier.lower()).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_email_verified:
            raise HTTPException(status_code=403, detail="Email not verified")
    else:
        phone = normalize_phone(identifier)
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_phone_verified:
            raise HTTPException(status_code=403, detail="Phone not verified")

    # ✅ bcrypt safety
    if len(body.password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(str(user.id), user.role)

    refresh_token = create_refresh_token()
    db.add(RefreshToken(user_id=user.id, token=refresh_token))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role
    }


# ----------------- REFRESH -----------------
@router.post("/refresh")
def refresh(body: RefreshBody, db: Session = Depends(get_db)):

    row = db.query(RefreshToken).filter(
        RefreshToken.token == body.refresh_token,
        RefreshToken.is_revoked == False
    ).first()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access = create_access_token(str(user.id), user.role)

    return {"access_token": new_access, "token_type": "bearer"}


# ----------------- LOGOUT -----------------
@router.post("/logout")
def logout(body: RefreshBody, db: Session = Depends(get_db)):

    row = db.query(RefreshToken).filter(RefreshToken.token == body.refresh_token).first()
    if not row:
        return {"message": "Logged out"}  # safe response

    row.is_revoked = True
    db.commit()

    return {"message": "Logged out successfully"}


# ----------------- RESET PASSWORD -----------------
@router.post("/reset-password")
def reset_password(body: ResetPasswordBody, db: Session = Depends(get_db)):

    identifier = body.identifier.strip()

    # ✅ bcrypt safety
    if len(body.new_password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")

    # find user
    if "@" in identifier:
        user = db.query(User).filter(User.email == identifier.lower()).first()
        channel = "email"
    else:
        phone = normalize_phone(identifier)
        user = db.query(User).filter(User.phone == phone).first()
        channel = "phone"

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # get latest otp
    otp_row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.channel == channel)
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

    # update password
    user.password_hash = hash_password(body.new_password)
    db.commit()

    return {"message": "Password reset successful"}
