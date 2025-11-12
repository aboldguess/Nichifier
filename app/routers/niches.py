"""app.routers.niches
======================
Mini-README: Exposes routes for listing niches, viewing detailed pages, and allowing
niche administrators to create or update niche configuration. Includes template-powered
pages alongside JSON APIs for programmatic access.
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..logger import get_logger
from ..models import Niche, User, UserRole
from ..schemas import NicheCreate
from ..security import require_role

TEMPLATES = Jinja2Templates(directory="app/templates")
LOGGER = get_logger(__name__)

router = APIRouter(prefix="/niches", tags=["Niches"])


@router.get("/")
async def list_niches(request: Request, session: AsyncSession = Depends(get_db_session)):
    """Render the splash page with all niches."""

    niches = (await session.execute(select(Niche))).scalars().all()
    return TEMPLATES.TemplateResponse("home.html", {"request": request, "niches": niches, "title": "Business Niche News"})


@router.get("/{niche_id}")
async def niche_detail(niche_id: int, request: Request, session: AsyncSession = Depends(get_db_session)):
    """Render a detailed niche marketing page."""

    stmt = select(Niche).where(Niche.id == niche_id)
    result = await session.execute(stmt)
    niche = result.scalar_one_or_none()
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")

    return TEMPLATES.TemplateResponse("niche_detail.html", {"request": request, "niche": niche, "title": niche.name})


@router.get("/manage/create")
async def create_niche_form(
    request: Request,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
):
    """Render the form for creating a niche."""

    return TEMPLATES.TemplateResponse("niche_editor.html", {"request": request, "user": user, "title": "Create Niche"})


@router.post("/manage/create")
async def create_niche(
    request: Request,
    name: str = Form(...),
    short_description: str = Form(...),
    detailed_description: str = Form(""),
    splash_image_url: str = Form(""),
    newsletter_price: float = Form(0),
    report_price: float = Form(0),
    voice_instructions: str = Form(""),
    style_guide: str = Form(""),
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
    session: AsyncSession = Depends(get_db_session),
):
    """Persist a new niche in the database."""

    stmt = select(Niche).where(Niche.name == name)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Niche already exists")

    niche = Niche(
        name=name,
        short_description=short_description,
        detailed_description=detailed_description,
        splash_image_url=splash_image_url or None,
        newsletter_price=newsletter_price,
        report_price=report_price,
        voice_instructions=voice_instructions,
        style_guide=style_guide,
        owner_id=user.id,
    )
    session.add(niche)
    await session.commit()

    LOGGER.info("User %s created niche %s", user.email, name)
    return RedirectResponse(url=f"/niches/{niche.id}", status_code=status.HTTP_303_SEE_OTHER)
