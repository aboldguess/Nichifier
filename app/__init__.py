"""app.__init__
=================
Mini-README: This package initialises the Nichifier application namespace. It exposes
utility functions for creating the FastAPI application and ensures modules are
available for import across the project structure.
"""

from .config import get_settings
from .logger import get_logger

__all__ = ["get_settings", "get_logger"]
