"""app.services
=================
Mini-README: Declares the service layer package responsible for background tasks and
AI prompt orchestration within Nichifier.
"""

from .newsletter_service import (
    AggregatedArticle,
    build_newsletter_prompt,
    build_report_prompt,
    fetch_news_feed,
)
from .niche_service import (
    NicheNameConflictError,
    create_niche,
    delete_niche,
    fetch_all_niches,
    fetch_niche_by_id,
    update_niche,
)

__all__ = [
    "AggregatedArticle",
    "build_newsletter_prompt",
    "build_report_prompt",
    "fetch_news_feed",
    "NicheNameConflictError",
    "create_niche",
    "delete_niche",
    "fetch_all_niches",
    "fetch_niche_by_id",
    "update_niche",
]
