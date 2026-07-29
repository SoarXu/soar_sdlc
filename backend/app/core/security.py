from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str) -> str:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def encrypt_secret(value: str) -> str:
    return _secret_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return _secret_fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def _secret_fernet() -> Fernet:
    key = settings.git_platform_encryption_key.strip()
    if not key:
        raise SecretConfigurationError("GIT_PLATFORM_ENCRYPTION_KEY must be configured before storing Git tokens")
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as error:
        raise SecretConfigurationError("GIT_PLATFORM_ENCRYPTION_KEY is not a valid Fernet key") from error


class SecretConfigurationError(ValueError):
    pass
