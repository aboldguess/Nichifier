"""app.routers.admin
=====================
Mini-README: Defines platform administrator routes including dashboards, theme
configuration placeholders, and user management listings. Access is restricted to
users with the global admin role.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db_session
from ..models import Niche, User, UserRole
from ..security import require_role

TEMPLATES = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_role([UserRole.ADMIN]))])


@router.get("/dashboard")
async def admin_dashboard(request: Request, session: AsyncSession = Depends(get_db_session)):
    """Render an overview dashboard for administrators."""

    users = (await session.execute(select(User))).scalars().all()
    niches = (
        await session.execute(select(Niche).options(selectinload(Niche.owner)))
    ).scalars().all()
    context = {
        "request": request,
        "users": users,
        "niches": niches,
        "config_help": "Admins can customise themes, cadence, and AI defaults here.",
        "title": "Admin Dashboard",
    }
    return TEMPLATES.TemplateResponse("admin_dashboard.html", context)
