"""app.routers.auth
====================
Mini-README: Defines authentication-related routes including registration, login,
logout, and dashboard access. Integrates with FastAPI's template rendering system to
provide user-friendly screens while enforcing secure password and JWT handling.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..logger import get_logger
from ..models import BillingProfile, User, UserRole
from ..security import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    create_access_token,
    get_current_user,
    get_password_hash,
    validate_password_requirements,
    verify_password,
)

TEMPLATES = Jinja2Templates(directory="app/templates")
LOGGER = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/register")
async def register_form(request: Request):
    """Render the registration form."""

    return TEMPLATES.TemplateResponse("register.html", {"request": request, "title": "Register"})


@router.post("/register")
async def register_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new user record and redirect to login."""

    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        LOGGER.warning("Registration attempt with existing email: %s", email)
        return TEMPLATES.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered. Please sign in instead.", "title": "Register"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    is_valid_password, password_error = validate_password_requirements(password)
    if not is_valid_password:
        LOGGER.warning(
            "Registration attempt with invalid password length for email %s (min=%s, max=%s)",
            email,
            PASSWORD_MIN_LENGTH,
            PASSWORD_MAX_LENGTH,
        )
        return TEMPLATES.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": password_error,
                "title": "Register",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    hashed_password = get_password_hash(password)
    user = User(email=email, hashed_password=hashed_password, full_name=full_name)
    session.add(user)
    await session.flush()

    billing_profile = BillingProfile(user_id=user.id)
    session.add(billing_profile)
    await session.commit()

    LOGGER.info("Registered user %s with billing profile %s", email, billing_profile.id)

    return TEMPLATES.TemplateResponse(
        "login.html",
        {"request": request, "message": "Registration successful. Please sign in.", "title": "Sign In"},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/login")
async def login_form(request: Request):
    """Render the login page."""

    return TEMPLATES.TemplateResponse("login.html", {"request": request, "title": "Sign In"})


@router.post("/login")
async def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Authenticate a user and set a JWT cookie."""

    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        return TEMPLATES.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials. Please try again.", "title": "Sign In"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if len(password) > PASSWORD_MAX_LENGTH:
        LOGGER.warning(
            "Login attempt with password exceeding max length for email %s", email
        )
        return TEMPLATES.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid credentials. Please try again.",
                "title": "Sign In",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not await verify_password(password, user.hashed_password):
        return TEMPLATES.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials. Please try again.", "title": "Sign In"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    access_token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=1))
    redirect = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key="nichifier_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600,
    )
    return redirect


@router.get("/logout")
async def logout_user():
    """Clear the authentication cookie and redirect to home."""

    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("nichifier_token")
    return response


@router.get("/profile")
async def profile_page(request: Request, user: User = Depends(get_current_user)):
    """Display a basic profile page for the authenticated user."""

    return TEMPLATES.TemplateResponse("dashboard.html", {"request": request, "user": user, "role": user.role.value, "is_admin": user.role == UserRole.ADMIN, "is_niche_admin": user.role == UserRole.NICHE_ADMIN, "title": "My Dashboard"})
