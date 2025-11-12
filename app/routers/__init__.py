"""app.routers
================
Mini-README: Router package initialiser exposing the different FastAPI routers used by
the Nichifier platform for authentication, niche management, admin tasks, and
subscriptions.
"""

from . import admin, auth, niches, subscriptions

__all__ = ["admin", "auth", "niches", "subscriptions"]
