from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class SignupEmail(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)
    role: str
    admin_code: Optional[str] = None


class SignupPhone(BaseModel):
    name: str
    phone: str
    password: str = Field(..., min_length=6, max_length=72)
    role: str
    admin_code: Optional[str] = None


class SendEmailOTP(BaseModel):
    email: EmailStr


class VerifyEmailOTP(BaseModel):
    email: EmailStr
    otp: str


class SendPhoneOTP(BaseModel):
    phone: str


class VerifyPhoneOTP(BaseModel):
    phone: str
    otp: str


class LoginBody(BaseModel):
    identifier: str
    password: str = Field(..., min_length=1, max_length=72)


class RefreshBody(BaseModel):
    refresh_token: str


class ResetPasswordBody(BaseModel):
    identifier: str
    otp: str
    new_password: str = Field(..., min_length=6, max_length=72)
