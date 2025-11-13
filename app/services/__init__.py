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
from .monetisation_service import (
    attach_creator_privileges,
    calculate_revenue_split,
    calculate_subscription_totals,
    count_active_niches_for_user,
    ensure_subscription_metrics,
    get_active_creator_subscription,
    get_or_create_platform_settings,
    list_creator_plans,
    update_platform_settings,
    upsert_creator_plan,
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
    "attach_creator_privileges",
    "calculate_revenue_split",
    "calculate_subscription_totals",
    "count_active_niches_for_user",
    "ensure_subscription_metrics",
    "get_active_creator_subscription",
    "get_or_create_platform_settings",
    "list_creator_plans",
    "update_platform_settings",
    "upsert_creator_plan",
]
