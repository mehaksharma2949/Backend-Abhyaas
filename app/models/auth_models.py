import uuid
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=True)
    phone = Column(String, unique=True, nullable=True)

    password_hash = Column(String, nullable=False)

    role = Column(String, nullable=False)

    is_email_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    channel = Column(String, nullable=False)  # email / phone
    otp_code = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token = Column(String, nullable=False)
    is_revoked = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
