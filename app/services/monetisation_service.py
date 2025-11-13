"""app.services.monetisation_service
====================================
Mini-README: Helper routines that encapsulate the business logic for the platform's
subscription monetisation model. Functions cover platform fee calculations, ensuring
settings rows exist, and CRUD helpers for curator plans so routers remain tidy.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..logger import get_logger
from ..models import (
    CreatorPlan,
    CreatorSubscription,
    CreatorSubscriptionStatus,
    Niche,
    PlatformMonetisationSettings,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
)

LOGGER = get_logger(__name__)
DEFAULT_PLATFORM_FEE_PERCENT = Decimal("15.00")
DEFAULT_PLATFORM_MIN_FEE = Decimal("1.00")
DEFAULT_CURRENCY = "GBP"


def _quantize_amount(value: Decimal) -> Decimal:
    """Round monetary values to two decimal places using bankers' rounding."""

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def get_or_create_platform_settings(session: AsyncSession) -> PlatformMonetisationSettings:
    """Retrieve the singleton monetisation settings row, creating sensible defaults."""

    result = await session.execute(select(PlatformMonetisationSettings).limit(1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = PlatformMonetisationSettings(
            platform_fee_percent=DEFAULT_PLATFORM_FEE_PERCENT,
            minimum_platform_fee=DEFAULT_PLATFORM_MIN_FEE,
            currency_code=DEFAULT_CURRENCY,
        )
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
        LOGGER.info(
            "Created default monetisation settings (fee=%s%%, minimum=%s %s)",
            settings.platform_fee_percent,
            settings.minimum_platform_fee,
            settings.currency_code,
        )
    return settings


async def update_platform_settings(
    session: AsyncSession,
    *,
    platform_fee_percent: Decimal,
    minimum_platform_fee: Decimal,
    currency_code: str,
    stripe_publishable_key: str | None,
    stripe_secret_key: str | None,
) -> PlatformMonetisationSettings:
    """Persist updates to the singleton monetisation configuration."""

    settings = await get_or_create_platform_settings(session)
    settings.platform_fee_percent = _quantize_amount(platform_fee_percent)
    settings.minimum_platform_fee = _quantize_amount(minimum_platform_fee)
    settings.currency_code = currency_code.upper()
    settings.stripe_publishable_key = stripe_publishable_key or None
    settings.stripe_secret_key = stripe_secret_key or None

    await session.commit()
    await session.refresh(settings)

    LOGGER.info(
        "Updated monetisation settings fee=%s%% minimum=%s %s",
        settings.platform_fee_percent,
        settings.minimum_platform_fee,
        settings.currency_code,
    )
    return settings


async def list_creator_plans(session: AsyncSession) -> list[CreatorPlan]:
    """Return curator plans ordered by monthly fee ascending for deterministic UX."""

    result = await session.execute(select(CreatorPlan).order_by(CreatorPlan.monthly_fee))
    plans = result.scalars().all()
    LOGGER.debug("Fetched %d creator plans", len(plans))
    return plans


async def upsert_creator_plan(
    session: AsyncSession,
    *,
    plan_id: int | None,
    slug: str,
    display_name: str,
    description: str | None,
    monthly_fee: Decimal,
    currency_code: str,
    stripe_price_id: str | None,
    max_niches: int,
    feature_summary: str,
    platform_fee_discount_percent: Decimal,
) -> CreatorPlan:
    """Create a new or update an existing curator plan definition."""

    normalized_slug = slug.strip().lower().replace(" ", "-")

    if plan_id is None:
        plan = CreatorPlan(slug=normalized_slug)
        session.add(plan)
    else:
        result = await session.execute(select(CreatorPlan).where(CreatorPlan.id == plan_id))
        plan = result.scalar_one_or_none()
        if plan is None:
            raise ValueError("Creator plan not found")

    plan.display_name = display_name.strip()
    plan.description = (description or "").strip() or None
    plan.monthly_fee = _quantize_amount(monthly_fee)
    plan.currency_code = currency_code.upper()
    plan.stripe_price_id = (stripe_price_id or "").strip() or None
    plan.max_niches = max(1, max_niches)
    plan.feature_summary = feature_summary.strip()
    plan.platform_fee_discount_percent = _quantize_amount(platform_fee_discount_percent)

    await session.commit()
    await session.refresh(plan)

    LOGGER.info("Upserted creator plan slug=%s id=%s", plan.slug, plan.id)
    return plan


def calculate_subscription_totals(
    *,
    newsletter_price: Decimal,
    report_price: Decimal,
    wants_newsletter: bool,
    wants_report: bool,
) -> Decimal:
    """Compute the gross recurring amount for a subscriber based on chosen products."""

    gross = Decimal("0.00")
    if wants_newsletter:
        gross += newsletter_price
    if wants_report:
        gross += report_price
    return _quantize_amount(gross)


def calculate_revenue_split(
    gross_amount: Decimal,
    *,
    settings: PlatformMonetisationSettings,
    creator_plan: CreatorPlan | None = None,
) -> tuple[Decimal, Decimal]:
    """Return a tuple of ``(platform_fee, creator_payout)`` respecting minimums."""

    if gross_amount <= 0:
        return (Decimal("0.00"), Decimal("0.00"))

    effective_fee_percent = settings.platform_fee_percent
    if creator_plan and creator_plan.platform_fee_discount_percent:
        effective_fee_percent = max(
            Decimal("0.00"),
            settings.platform_fee_percent - creator_plan.platform_fee_discount_percent,
        )

    platform_fee = gross_amount * (effective_fee_percent / Decimal("100"))
    platform_fee = max(platform_fee, settings.minimum_platform_fee)
    platform_fee = _quantize_amount(platform_fee)
    creator_amount = _quantize_amount(gross_amount - platform_fee)

    LOGGER.debug(
        "Calculated revenue split gross=%s platform=%s creator=%s", gross_amount, platform_fee, creator_amount
    )
    return platform_fee, creator_amount


async def attach_creator_privileges(user: User, active_plan: CreatorPlan | None, session: AsyncSession) -> None:
    """Ensure the user's role and premium flag mirror the state of their creator plan."""

    desired_role = UserRole.NICHE_ADMIN if active_plan else UserRole.SUBSCRIBER
    user.role = desired_role if user.role != UserRole.ADMIN else user.role
    user.is_premium = active_plan is not None or user.role == UserRole.ADMIN
    await session.commit()
    await session.refresh(user)

    LOGGER.info(
        "Updated user %s role=%s premium=%s based on creator plan",
        user.email,
        user.role,
        user.is_premium,
    )


async def get_active_creator_subscription(session: AsyncSession, user_id: int) -> CreatorSubscription | None:
    """Return the user's active creator subscription if one exists."""

    result = await session.execute(
        select(CreatorSubscription)
        .where(
            CreatorSubscription.user_id == user_id,
            CreatorSubscription.status.in_(
                [CreatorSubscriptionStatus.ACTIVE, CreatorSubscriptionStatus.TRIALING]
            ),
        )
        .order_by(CreatorSubscription.started_at.desc())
    )
    subscription = result.scalar_one_or_none()
    return subscription


async def ensure_subscription_metrics(
    session: AsyncSession,
    subscription: Subscription,
    *,
    gross_amount: Decimal,
    settings: PlatformMonetisationSettings,
    creator_plan: CreatorPlan | None,
    currency_code: str,
    billing_cadence: str,
) -> Subscription:
    """Update revenue split fields on a subscription row in-place."""

    platform_fee, creator_payout = calculate_revenue_split(
        gross_amount,
        settings=settings,
        creator_plan=creator_plan,
    )

    subscription.currency_code = currency_code
    subscription.billing_cadence = billing_cadence
    subscription.gross_amount = _quantize_amount(gross_amount)
    subscription.platform_fee_amount = platform_fee
    subscription.creator_payout_amount = creator_payout
    subscription.status = SubscriptionStatus.ACTIVE if gross_amount > 0 else SubscriptionStatus.TRIALING

    await session.commit()
    await session.refresh(subscription)
    LOGGER.info(
        "Updated subscription id=%s metrics gross=%s platform=%s creator=%s",
        subscription.id,
        subscription.gross_amount,
        subscription.platform_fee_amount,
        subscription.creator_payout_amount,
    )
    return subscription


async def count_active_niches_for_user(session: AsyncSession, user_id: int) -> int:
    """Return the number of niches a user currently owns for plan enforcement."""

    result = await session.execute(select(func.count(Niche.id)).where(Niche.owner_id == user_id))
    count = result.scalar_one()
    return count


