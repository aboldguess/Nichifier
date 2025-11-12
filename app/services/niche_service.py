"""app.services.niche_service
=============================
Mini-README: Provides reusable database operations for managing niches. Encapsulates
CRUD helpers, validation, and logging so routes remain focused on HTTP concerns.
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..logger import get_logger
from ..models import Niche, NewsletterIssue, NewsArticle, ReportIssue, Subscription

LOGGER = get_logger(__name__)


class NicheNameConflictError(ValueError):
    """Raised when a requested niche name would violate uniqueness."""


async def fetch_all_niches(session: AsyncSession) -> list[Niche]:
    """Return all niches ordered alphabetically for deterministic presentation."""

    stmt = select(Niche).order_by(func.lower(Niche.name))
    result = await session.execute(stmt)
    niches = result.scalars().all()
    LOGGER.debug("Fetched %d niches for listing", len(niches))
    return niches


async def fetch_niche_by_id(session: AsyncSession, niche_id: int) -> Niche | None:
    """Retrieve a single niche by its identifier."""

    stmt = select(Niche).where(Niche.id == niche_id)
    result = await session.execute(stmt)
    niche = result.scalar_one_or_none()
    LOGGER.debug("Lookup niche_id=%s found=%s", niche_id, bool(niche))
    return niche


def _sanitise_payload(niche_data: dict[str, Any]) -> dict[str, Any]:
    """Trim whitespace and normalise optional fields to ``None``."""

    cleaned = dict(niche_data)
    for key in ("name", "short_description"):
        value = cleaned.get(key)
        if isinstance(value, str):
            cleaned[key] = value.strip()
    for optional_key in ("detailed_description", "splash_image_url", "voice_instructions", "style_guide"):
        if optional_key in cleaned:
            value = cleaned[optional_key]
            if isinstance(value, str):
                cleaned[optional_key] = value.strip() or None
    return cleaned


async def _ensure_unique_name(
    session: AsyncSession,
    *,
    name: str,
    exclude_ids: Iterable[int] | None = None,
) -> None:
    """Ensure the provided name is unique, optionally excluding some IDs."""

    normalized_name = name.strip()
    stmt = select(Niche).where(func.lower(Niche.name) == func.lower(normalized_name))
    if exclude_ids:
        stmt = stmt.where(Niche.id.notin_(list(exclude_ids)))
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        LOGGER.warning("Niche name conflict detected for '%s'", normalized_name)
        raise NicheNameConflictError("A niche with that name already exists.")


async def create_niche(
    session: AsyncSession,
    niche_data: dict[str, Any],
    *,
    owner_id: int | None,
) -> Niche:
    """Persist a new niche after validating uniqueness."""

    cleaned_payload = _sanitise_payload(niche_data)
    await _ensure_unique_name(session, name=cleaned_payload["name"])

    niche = Niche(owner_id=owner_id, **cleaned_payload)
    session.add(niche)
    await session.commit()
    await session.refresh(niche)

    LOGGER.info("Created niche %s (id=%s) by owner_id=%s", niche.name, niche.id, owner_id)
    return niche


async def update_niche(
    session: AsyncSession,
    niche: Niche,
    updates: dict[str, Any],
) -> Niche:
    """Apply partial updates to an existing niche, validating name uniqueness."""

    cleaned_updates = _sanitise_payload(updates)

    name_update = cleaned_updates.get("name")
    if name_update and name_update != niche.name:
        await _ensure_unique_name(session, name=name_update, exclude_ids=[niche.id])

    for field, value in cleaned_updates.items():
        setattr(niche, field, value)

    await session.commit()
    await session.refresh(niche)

    LOGGER.info("Updated niche id=%s with fields=%s", niche.id, sorted(cleaned_updates.keys()))
    return niche


async def delete_niche(session: AsyncSession, niche: Niche) -> None:
    """Remove a niche and clean up dependent rows for referential integrity."""

    niche_id = niche.id

    # Capture counts for observability so we know what was removed alongside the niche.
    subscription_count = (
        await session.execute(
            select(func.count(Subscription.id)).where(Subscription.niche_id == niche_id)
        )
    ).scalar_one()
    newsletter_issue_ids = (
        await session.execute(
            select(NewsletterIssue.id).where(NewsletterIssue.niche_id == niche_id)
        )
    ).scalars().all()
    newsletter_issue_count = len(newsletter_issue_ids)
    newsletter_article_count = 0
    if newsletter_issue_ids:
        newsletter_article_count = (
            await session.execute(
                select(func.count(NewsArticle.id)).where(
                    NewsArticle.newsletter_issue_id.in_(newsletter_issue_ids)
                )
            )
        ).scalar_one()
    report_issue_count = (
        await session.execute(
            select(func.count(ReportIssue.id)).where(ReportIssue.niche_id == niche_id)
        )
    ).scalar_one()

    LOGGER.info(
        "Deleting niche id=%s name=%s (subscriptions=%s newsletters=%s reports=%s articles=%s)",
        niche_id,
        niche.name,
        subscription_count,
        newsletter_issue_count,
        report_issue_count,
        newsletter_article_count,
    )

    # Remove dependent records explicitly because the schema does not use cascades.
    if newsletter_issue_ids:
        await session.execute(
            delete(NewsArticle).where(NewsArticle.newsletter_issue_id.in_(newsletter_issue_ids))
        )
    await session.execute(delete(NewsletterIssue).where(NewsletterIssue.niche_id == niche_id))
    await session.execute(delete(ReportIssue).where(ReportIssue.niche_id == niche_id))
    await session.execute(delete(Subscription).where(Subscription.niche_id == niche_id))

    await session.delete(niche)
    await session.commit()
    LOGGER.info("Deleted niche id=%s name=%s", niche_id, niche.name)
