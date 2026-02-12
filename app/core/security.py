import secrets
import hashlib
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.core.config import JWT_SECRET, JWT_ALGO, ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password using SHA256 pre-hashing to avoid bcrypt's 72-byte limit."""
    # Pre-hash with SHA256 to ensure we stay within bcrypt's limits
    # This allows unlimited password lengths while maintaining security
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return pwd_context.hash(password_hash)

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return pwd_context.verify(password_hash, hashed)

def create_access_token(user_id: str, role: str):
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)
