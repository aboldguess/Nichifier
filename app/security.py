"""app.security
=================
Mini-README: Houses authentication utilities including password hashing, JWT token
creation/validation, and dependencies for retrieving the current user with role
checks. Relies on passlib and python-jose for cryptographic operations.
"""

from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .config import get_settings
from .database import get_db_session
from .logger import get_logger
from .models import User, UserRole

LOGGER = get_logger(__name__)

# NOTE: ``bcrypt`` truncates secrets longer than 72 bytes. ``bcrypt_sha256`` pre-hashes the
# password using SHA256 to safely accommodate longer passwords while keeping backwards
# compatibility with the verification step. This ensures our service remains resilient to
# long passphrases without raising runtime errors.
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

# Guardrails used when validating incoming passwords. Longer passphrases are still supported
# thanks to ``bcrypt_sha256`` but we establish a sane upper bound to limit resource usage.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Validate a plain password against a hashed value."""

    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""

    return pwd_context.hash(password)


def validate_password_requirements(password: str) -> tuple[bool, str | None]:
    """Validate password length requirements returning a tuple (is_valid, error_message)."""

    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    if len(password) > PASSWORD_MAX_LENGTH:
        return False, f"Password must be fewer than {PASSWORD_MAX_LENGTH} characters."
    return True, None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token."""

    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.token_expiry_minutes))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt


async def get_current_user(
    token: Annotated[str | None, Cookie(alias="nichifier_token")],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Retrieve the currently authenticated user from the JWT stored in cookies."""

    if token is None:
        LOGGER.warning("Attempted access without authentication cookie")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        LOGGER.error("JWT decode failure: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    stmt = select(User).where(User.id == int(user_id))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


def require_role(required_roles: list[UserRole]):
    """Dependency factory enforcing role membership for protected routes."""

    async def role_checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in required_roles:
            LOGGER.warning("User %s lacks required role %s", user.email, required_roles)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        return user

    return role_checker
