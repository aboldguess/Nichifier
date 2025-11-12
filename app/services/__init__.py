"""app.services
=================
Mini-README: Declares the service layer package responsible for background tasks and
AI prompt orchestration within Nichifier.
"""

from .newsletter_service import AggregatedArticle, build_newsletter_prompt, build_report_prompt, fetch_news_feed

__all__ = [
    "AggregatedArticle",
    "build_newsletter_prompt",
    "build_report_prompt",
    "fetch_news_feed",
]
