"""app.routers.subscriptions
=============================
Mini-README: Provides endpoints and pages for subscribers to manage newsletter and
report subscriptions. Supports CRUD operations for authenticated users with
subscriber or higher privileges. Monetisation calculations ensure platform fees and
creator payouts are maintained accurately.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db_session
from ..logger import get_logger
from ..models import Niche, Subscription, User
from ..security import get_current_user
from ..services import (
    calculate_subscription_totals,
    ensure_subscription_metrics,
    get_active_creator_subscription,
    get_or_create_platform_settings,
)

TEMPLATES = Jinja2Templates(directory="app/templates")
LOGGER = get_logger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/manage")
async def manage_subscriptions(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Display the subscription management dashboard."""

    subscriptions = (
        await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .options(selectinload(Subscription.niche))
        )
    ).scalars().all()
    niches = (await session.execute(select(Niche))).scalars().all()
    context = {"request": request, "user": user, "subscriptions": subscriptions, "niches": niches, "title": "Subscription Manager"}
    return TEMPLATES.TemplateResponse("subscription_management.html", context)


@router.post("/manage")
async def upsert_subscription(
    request: Request,
    niche_id: int = Form(...),
    wants_newsletter: bool = Form(False),
    wants_report: bool = Form(False),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Create or update a subscription for the authenticated user."""

    stmt = select(Subscription).where(Subscription.user_id == user.id, Subscription.niche_id == niche_id)
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    niche = await session.get(Niche, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")

    if subscription is None:
        subscription = Subscription(
            user_id=user.id,
            niche_id=niche_id,
            wants_newsletter=wants_newsletter,
            wants_report=wants_report,
            currency_code=niche.currency_code,
        )
        session.add(subscription)
    else:
        subscription.wants_newsletter = wants_newsletter
        subscription.wants_report = wants_report
        subscription.currency_code = niche.currency_code

    await session.flush()

    gross_amount = calculate_subscription_totals(
        newsletter_price=Decimal(str(niche.newsletter_price or 0)),
        report_price=Decimal(str(niche.report_price or 0)),
        wants_newsletter=wants_newsletter,
        wants_report=wants_report,
    )

    settings = await get_or_create_platform_settings(session)
    creator_plan = None
    if niche.owner_id:
        owner_subscription = await get_active_creator_subscription(session, niche.owner_id)
        if owner_subscription:
            creator_plan = owner_subscription.plan

    if wants_newsletter and wants_report:
        billing_cadence = "bundle"
    elif wants_report:
        billing_cadence = niche.report_cadence
    else:
        billing_cadence = niche.newsletter_cadence

    await ensure_subscription_metrics(
        session,
        subscription,
        gross_amount=gross_amount,
        settings=settings,
        creator_plan=creator_plan,
        currency_code=niche.currency_code,
        billing_cadence=billing_cadence,
    )

    LOGGER.info(
        "User %s updated subscription for niche %s (gross=%s %s)",
        user.email,
        niche_id,
        subscription.currency_code,
        subscription.gross_amount,
    )

    return RedirectResponse(url="/subscriptions/manage", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Remove a subscription owned by the authenticated user."""

    stmt = select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == user.id)
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    # AsyncSession.delete is intentionally called without awaiting because it is
    # a synchronous method that schedules the deletion for the next commit.
    session.delete(subscription)
    await session.commit()
    LOGGER.info("User %s deleted subscription %s", user.email, subscription_id)
    return RedirectResponse(url="/subscriptions/manage", status_code=status.HTTP_303_SEE_OTHER)
