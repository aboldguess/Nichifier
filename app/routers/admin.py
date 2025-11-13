"""app.routers.admin
=====================
Mini-README: Defines platform administrator routes including dashboards, theme
configuration placeholders, and user management listings. Access is restricted to
users with the global admin role.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db_session
from ..models import Niche, User, UserRole
from ..security import require_role
from ..services import (
    get_or_create_platform_settings,
    list_creator_plans,
    update_platform_settings,
    upsert_creator_plan,
)

TEMPLATES = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_role([UserRole.ADMIN]))])


@router.get("/dashboard")
async def admin_dashboard(request: Request, session: AsyncSession = Depends(get_db_session)):
    """Render an overview dashboard for administrators."""

    users = (await session.execute(select(User))).scalars().all()
    niches = (
        await session.execute(select(Niche).options(selectinload(Niche.owner)))
    ).scalars().all()
    context = {
        "request": request,
        "users": users,
        "niches": niches,
        "config_help": "Admins can customise themes, cadence, and AI defaults here.",
        "title": "Admin Dashboard",
    }
    return TEMPLATES.TemplateResponse("admin_dashboard.html", context)


@router.get("/monetisation")
async def monetisation_overview(request: Request, session: AsyncSession = Depends(get_db_session)):
    """Render the hidden monetisation control centre for administrators."""

    settings = await get_or_create_platform_settings(session)
    plans = await list_creator_plans(session)
    context = {
        "request": request,
        "settings": settings,
        "plans": plans,
        "title": "Monetisation Controls",
    }
    return TEMPLATES.TemplateResponse("admin_monetisation.html", context)


@router.post("/monetisation/settings")
async def monetisation_update_settings(
    platform_fee_percent: str = Form(...),
    minimum_platform_fee: str = Form(...),
    currency_code: str = Form(...),
    stripe_publishable_key: str = Form(""),
    stripe_secret_key: str = Form(""),
    session: AsyncSession = Depends(get_db_session),
):
    """Persist updates to platform fee configuration then redirect back."""

    try:
        fee_percent = Decimal(platform_fee_percent)
        minimum_fee = Decimal(minimum_platform_fee)
    except Exception as exc:  # noqa: BLE001 - Input validation path
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid monetary value supplied") from exc

    await update_platform_settings(
        session,
        platform_fee_percent=fee_percent,
        minimum_platform_fee=minimum_fee,
        currency_code=currency_code,
        stripe_publishable_key=stripe_publishable_key or None,
        stripe_secret_key=stripe_secret_key or None,
    )

    return RedirectResponse(url="/admin/monetisation", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/monetisation/plan")
async def monetisation_upsert_plan(
    plan_id: int | None = Form(None),
    slug: str = Form(...),
    display_name: str = Form(...),
    description: str = Form(""),
    monthly_fee: str = Form("0"),
    currency_code: str = Form("GBP"),
    stripe_price_id: str = Form(""),
    max_niches: int = Form(1),
    feature_summary: str = Form(""),
    platform_fee_discount_percent: str = Form("0"),
    session: AsyncSession = Depends(get_db_session),
):
    """Create or update a curator plan definition from the admin panel."""

    try:
        monthly_fee_decimal = Decimal(monthly_fee)
        discount_decimal = Decimal(platform_fee_discount_percent)
    except Exception as exc:  # noqa: BLE001 - Input validation path
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid monetary value supplied") from exc

    try:
        await upsert_creator_plan(
            session,
            plan_id=plan_id,
            slug=slug,
            display_name=display_name,
            description=description,
            monthly_fee=monthly_fee_decimal,
            currency_code=currency_code,
            stripe_price_id=stripe_price_id,
            max_niches=max_niches,
            feature_summary=feature_summary,
            platform_fee_discount_percent=discount_decimal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return RedirectResponse(url="/admin/monetisation", status_code=status.HTTP_303_SEE_OTHER)
