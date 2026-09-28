from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from .config import settings

password_hash = PasswordHash.recommended()


def hash_password(value: str) -> str:
    return password_hash.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    return password_hash.verify(value, hashed)


def create_token(user_id: str) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": user_id, "exp": expiry}, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> str:
    return str(jwt.decode(token, settings.secret_key, algorithms=["HS256"])["sub"])
