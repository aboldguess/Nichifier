"""nichifier_platform_server
============================
Mini-README: Entry point for running the Nichifier platform. Creates the FastAPI
application, mounts routers, exposes CLI utilities for database initialisation, and
starts an ASGI server with configurable host/port/log level settings.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import get_logger, get_settings
from app.database import AsyncSessionMaker, apply_schema_upgrades, get_db_session, init_db
from app.models import Niche, User, UserRole
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import niches as niches_router
from app.routers import subscriptions as subscriptions_router
from app.services import (
    count_active_niches_for_user,
    get_active_creator_subscription,
    get_or_create_platform_settings,
)
from app.security import get_current_user

LOGGER = get_logger(__name__)
TEMPLATES = Jinja2Templates(directory="app/templates")
TEMPLATES.env.globals['current_year'] = __import__('datetime').datetime.utcnow().year
TEMPLATES.env.globals['brand_name'] = 'Nichifier BI'


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""

    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    static_dir = Path("app/static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(auth_router.router)
    app.include_router(niches_router.router)
    app.include_router(subscriptions_router.router)
    app.include_router(admin_router.router)

    @app.on_event("startup")
    async def ensure_database_schema() -> None:
        """Create tables and patch any lightweight schema changes on boot."""

        await init_db()
        await apply_schema_upgrades()

    @app.get("/", response_class=HTMLResponse)
    async def splash_page(request: Request, session: AsyncSession = Depends(get_db_session)):
        niches = (await session.execute(select(Niche))).scalars().all()
        return TEMPLATES.TemplateResponse(
            "home.html",
            {
                "request": request,
                "niches": niches,
                "headline": "Business Niche News",
                "cta_message": "Choose a niche to subscribe or learn more",
            },
        )


    @app.get("/premium", response_class=HTMLResponse)
    async def premium_upgrade(request: Request):
        return TEMPLATES.TemplateResponse(
            "premium_upgrade.html",
            {"request": request, "title": "Upgrade to Premium"},
        )

    @app.get("/how-it-works", response_class=HTMLResponse)
    async def how_it_works(request: Request):
        """Guide prospective users through the end-to-end Nichifier workflow."""

        onboarding_steps = [
            {
                "title": "1. Create your free Nichifier account",
                "description": (
                    "Sign up with your email address and confirm your details. "
                    "The platform immediately provisions secure defaults and "
                    "enables newsletter subscriptions."
                ),
                "action": "Use the Create account button in the navigation bar.",
            },
            {
                "title": "2. Subscribe to niche intelligence",
                "description": (
                    "Browse the public niche catalogue and subscribe to free daily "
                    "briefings. This keeps you informed while you prepare your own "
                    "niche launch."
                ),
                "action": "Click 'Subscribe to a free daily briefing' on the home page.",
            },
            {
                "title": "3. Upgrade when you're ready to curate",
                "description": (
                    "Upgrade to a creator plan to unlock the niche editor, AI tone "
                    "configuration, and monetisation controls."
                ),
                "action": "Visit the Premium Upgrade screen from the navigation menu.",
            },
            {
                "title": "4. Configure your first niche",
                "description": (
                    "Use the guided niche editor to define your audience, pricing, "
                    "and branding. The platform validates each step and tracks "
                    "completion so nothing gets missed."
                ),
                "action": "Select Add Niche → Configure niche to launch your workspace.",
            },
            {
                "title": "5. Publish and iterate",
                "description": (
                    "Once approved, Nichifier publishes your niche storefront, sends "
                    "the inaugural briefing, and surfaces analytics on the dashboard. "
                    "Iterate using feedback and our learning resources."
                ),
                "action": "Monitor the Dashboard for engagement metrics and optimisation tips.",
            },
        ]

        operational_checks = [
            {
                "name": "Team roles",
                "detail": "Assign collaborator roles via Manage Users before launch to avoid access gaps.",
            },
            {
                "name": "Compliance",
                "detail": "Upload required policies and ensure newsletter compliance from the Dashboard checklist.",
            },
            {
                "name": "Monetisation",
                "detail": "Connect your payment processor under Subscription Details to enable paid reports.",
            },
        ]

        return TEMPLATES.TemplateResponse(
            "how_it_works.html",
            {
                "request": request,
                "title": "How Nichifier Works",
                "onboarding_steps": onboarding_steps,
                "operational_checks": operational_checks,
            },
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(
        request: Request,
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ):
        niches = (await session.execute(select(Niche))).scalars().all()
        creator_subscription = await get_active_creator_subscription(session, user.id)
        monetisation_settings = await get_or_create_platform_settings(session)
        plan_usage = None
        if creator_subscription and creator_subscription.plan:
            owned = await count_active_niches_for_user(session, user.id)
            plan_usage = {
                "used": owned,
                "limit": creator_subscription.plan.max_niches,
            }
        return TEMPLATES.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "niches": niches,
                "role": user.role.value,
                "is_admin": user.role == UserRole.ADMIN,
                "is_niche_admin": user.role == UserRole.NICHE_ADMIN,
                "creator_subscription": creator_subscription,
                "creator_plan": creator_subscription.plan if creator_subscription else None,
                "monetisation_settings": monetisation_settings,
                "plan_usage": plan_usage,
            },
        )

    @app.get("/healthz")
    async def healthcheck() -> dict[str, Any]:
        return {"status": "ok"}

    return app


app = create_app()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for running the server."""

    parser = argparse.ArgumentParser(description="Nichifier Platform Server")
    parser.add_argument("--host", default=get_settings().default_host, help="Host to bind the server")
    parser.add_argument("--port", type=int, default=get_settings().default_port, help="Port to bind the server")
    parser.add_argument("--reload", action="store_true", help="Enable autoreload for development")
    parser.add_argument("--log-level", default="info", help="Logging level for Uvicorn")
    parser.add_argument("--init-db", action="store_true", help="Initialise the database and exit")
    parser.add_argument(
        "--promote-user",
        metavar="EMAIL",
        help="Promote the specified user (by email) to an elevated role and exit",
    )
    parser.add_argument(
        "--role",
        choices=[role.value for role in UserRole],
        help="Role to assign when using --promote-user",
    )

    args = parser.parse_args()
    if args.promote_user and not args.role:
        parser.error("--promote-user requires --role to be supplied")

    return args


async def promote_user(email: str, role: UserRole) -> None:
    """Elevate a user's privileges using an operational AsyncSession workflow."""

    LOGGER.info("Promoting user %s to role %s", email, role.value)

    async with AsyncSessionMaker() as session:
        # Look up the user securely by unique email address.
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            LOGGER.error("No user found with email %s", email)
            raise SystemExit(1)

        user.role = role
        user.is_premium = role in (UserRole.ADMIN, UserRole.NICHE_ADMIN)

        await session.commit()
        LOGGER.info(
            "Successfully promoted %s to %s (premium=%s)",
            email,
            role.value,
            user.is_premium,
        )


async def initialise_database() -> None:
    """Initialise database tables if they do not exist."""

    LOGGER.info("Initialising database...")
    await init_db()
    await apply_schema_upgrades()
    LOGGER.info("Database initialisation complete")


def main() -> None:
    """CLI entrypoint for running the ASGI server."""

    args = parse_args()
    performed_cli_action = False

    if args.init_db:
        asyncio.run(initialise_database())
        performed_cli_action = True

    if args.promote_user:
        asyncio.run(promote_user(args.promote_user, UserRole(args.role)))
        performed_cli_action = True

    if performed_cli_action:
        return

    uvicorn.run(
        "nichifier_platform_server:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
