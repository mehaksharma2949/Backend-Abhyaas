from pydantic import BaseModel, EmailStr
from typing import Optional

# -------- Signup --------
class SignupEmail(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str  # student/teacher
    admin_code: Optional[str] = None

class SignupPhone(BaseModel):
    name: str
    phone: str
    password: str
    role: str
    admin_code: Optional[str] = None

# -------- OTP --------
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

# -------- Login --------
class LoginBody(BaseModel):
    identifier: str  # email or phone
    password: str

class RefreshBody(BaseModel):
    refresh_token: str
class ResetPasswordBody(BaseModel):
    identifier: str   # email or phone
    otp: str
    new_password: str
