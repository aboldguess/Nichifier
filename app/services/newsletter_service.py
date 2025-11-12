"""app.services.newsletter_service
==================================
Mini-README: Implements helper routines for aggregating news articles and preparing
prompts for AI-generated newsletters and reports. Uses HTTPX for fetching example
feeds and structures prompts for OpenAI-compatible chat completion APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

import httpx

from ..config import get_settings
from ..logger import get_logger

LOGGER = get_logger(__name__)


@dataclass
class AggregatedArticle:
    """Lightweight container for aggregated news content."""

    source: str
    title: str
    url: str
    summary: str
    published_at: datetime


async def fetch_news_feed(feed_url: str, limit: int = 5) -> List[AggregatedArticle]:
    """Fetch news data from a JSON API endpoint.

    The implementation assumes the endpoint returns a JSON array with `title`, `url`,
    and optional `summary` fields. Errors are logged and result in an empty list.
    """

    settings = get_settings()
    timeout = httpx.Timeout(5.0, read=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(feed_url, headers={"User-Agent": settings.app_name})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            LOGGER.error("Failed to fetch feed %s: %s", feed_url, exc)
            return []

    articles: List[AggregatedArticle] = []
    for item in response.json()[:limit]:
        articles.append(
            AggregatedArticle(
                source=item.get("source", "Unknown"),
                title=item.get("title", "Untitled"),
                url=item.get("url", ""),
                summary=item.get("summary", ""),
                published_at=datetime.utcnow(),
            )
        )
    return articles


def build_newsletter_prompt(niche_name: str, voice: str, style: str, articles: Iterable[AggregatedArticle]) -> str:
    """Construct a prompt guiding ChatGPT to create a newsletter."""

    article_lines = "\n".join(f"- {article.title} ({article.url})" for article in articles)
    prompt = (
        f"You are writing a daily briefing for the '{niche_name}' industry.\n"
        f"Voice guidance: {voice or 'Use an energetic, professional tone.'}\n"
        f"Style guidance: {style or 'Write in short paragraphs with bullet highlights.'}\n"
        "Summarise the following articles with crisp insights and action items:\n"
        f"{article_lines}"
    )
    return prompt


def build_report_prompt(niche_name: str, cadence: str, voice: str, style: str, insights: Iterable[str]) -> str:
    """Construct a prompt for longform reports."""

    insights_block = "\n".join(f"* {point}" for point in insights)
    prompt = (
        f"Draft a {cadence} deep-dive report for the '{niche_name}' niche.\n"
        f"Voice guidance: {voice or 'Adopt an authoritative yet friendly tone.'}\n"
        f"Style guidance: {style or 'Include executive summary, key metrics, and outlook.'}\n"
        "Incorporate the following curated insights:\n"
        f"{insights_block}"
    )
    return prompt
