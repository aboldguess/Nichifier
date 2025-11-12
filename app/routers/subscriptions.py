"""app.routers.subscriptions
=============================
Mini-README: Provides endpoints and pages for subscribers to manage newsletter and
report subscriptions. Supports CRUD operations for authenticated users with
subscriber or higher privileges.
"""

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

    if subscription is None:
        subscription = Subscription(
            user_id=user.id,
            niche_id=niche_id,
            wants_newsletter=wants_newsletter,
            wants_report=wants_report,
        )
        session.add(subscription)
    else:
        subscription.wants_newsletter = wants_newsletter
        subscription.wants_report = wants_report

    await session.commit()
    LOGGER.info("User %s updated subscription for niche %s", user.email, niche_id)

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

    await session.delete(subscription)
    await session.commit()
    LOGGER.info("User %s deleted subscription %s", user.email, subscription_id)
    return RedirectResponse(url="/subscriptions/manage", status_code=status.HTTP_303_SEE_OTHER)
