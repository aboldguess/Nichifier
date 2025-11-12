"""app.routers.niches
======================
Mini-README: Exposes routes for listing niches, viewing detailed pages, and allowing
niche administrators to create, update, or delete niche configuration. Provides both
template-powered management pages and JSON APIs for programmatic use.
"""

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..logger import get_logger
from ..models import Niche, User, UserRole
from ..schemas import NicheCreate, NicheRead, NicheUpdate
from ..security import require_role
from ..services import (
    NicheNameConflictError,
    create_niche as service_create_niche,
    delete_niche as service_delete_niche,
    fetch_all_niches,
    fetch_niche_by_id,
    update_niche as service_update_niche,
)

TEMPLATES = Jinja2Templates(directory="app/templates")
LOGGER = get_logger(__name__)

router = APIRouter(prefix="/niches", tags=["Niches"])


def _normalize_optional_text(value: str | None) -> str | None:
    """Convert blank strings to ``None`` to keep database records tidy."""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _build_editor_context(
    request: Request,
    *,
    title: str,
    form_action: str,
    submit_label: str,
    user: User,
    niche: Niche | None = None,
    is_update: bool = False,
    form_values: dict[str, Any] | None = None,
    error_message: str | None = None,
    delete_action: str | None = None,
) -> dict[str, Any]:
    """Construct the template context shared by create and edit pages."""

    return {
        "request": request,
        "title": title,
        "user": user,
        "niche": niche,
        "is_update": is_update,
        "form_action": form_action,
        "submit_label": submit_label,
        "form_values": form_values or {},
        "error_message": error_message,
        "delete_action": delete_action,
    }


def _prepare_form_payload(
    *,
    name: str,
    short_description: str,
    detailed_description: str,
    splash_image_url: str,
    newsletter_price: float,
    report_price: float,
    voice_instructions: str,
    style_guide: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalise incoming form strings and return both DB payload and form echoes."""

    payload = {
        "name": name.strip(),
        "short_description": short_description.strip(),
        "detailed_description": _normalize_optional_text(detailed_description),
        "splash_image_url": _normalize_optional_text(splash_image_url),
        "newsletter_price": newsletter_price,
        "report_price": report_price,
        "voice_instructions": _normalize_optional_text(voice_instructions),
        "style_guide": _normalize_optional_text(style_guide),
    }

    form_values = {
        "name": payload["name"],
        "short_description": payload["short_description"],
        "detailed_description": detailed_description.strip(),
        "splash_image_url": splash_image_url.strip(),
        "newsletter_price": newsletter_price,
        "report_price": report_price,
        "voice_instructions": voice_instructions.strip(),
        "style_guide": style_guide.strip(),
    }

    return payload, form_values


def _ensure_management_access(niche: Niche, user: User) -> None:
    """Validate the user has permission to manage a niche."""

    if user.role == UserRole.ADMIN:
        return
    if niche.owner_id == user.id:
        return
    LOGGER.warning("User %s attempted to manage niche %s without permission", user.email, niche.id)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not manage this niche.")


@router.get("/")
async def list_niches(request: Request, session: AsyncSession = Depends(get_db_session)):
    """Render the splash page with all niches."""

    niches = await fetch_all_niches(session)
    return TEMPLATES.TemplateResponse("home.html", {"request": request, "niches": niches, "title": "Business Niche News"})


@router.get("/{niche_id}")
async def niche_detail(niche_id: int, request: Request, session: AsyncSession = Depends(get_db_session)):
    """Render a detailed niche marketing page."""

    niche = await fetch_niche_by_id(session, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")

    return TEMPLATES.TemplateResponse("niche_detail.html", {"request": request, "niche": niche, "title": niche.name})


@router.get("/manage/create")
async def create_niche_form(
    request: Request,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
):
    """Render the form for creating a niche."""

    context = _build_editor_context(
        request,
        title="Create Niche",
        form_action="/niches/manage/create",
        submit_label="Create niche",
        user=user,
    )
    return TEMPLATES.TemplateResponse("niche_editor.html", context)


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

    payload, form_values = _prepare_form_payload(
        name=name,
        short_description=short_description,
        detailed_description=detailed_description,
        splash_image_url=splash_image_url,
        newsletter_price=newsletter_price,
        report_price=report_price,
        voice_instructions=voice_instructions,
        style_guide=style_guide,
    )

    try:
        niche = await service_create_niche(session, payload, owner_id=user.id)
    except NicheNameConflictError as exc:
        context = _build_editor_context(
            request,
            title="Create Niche",
            form_action="/niches/manage/create",
            submit_label="Create niche",
            user=user,
            form_values=form_values,
            error_message=str(exc),
        )
        return TEMPLATES.TemplateResponse(
            "niche_editor.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    LOGGER.info("User %s created niche %s", user.email, payload["name"])
    return RedirectResponse(url=f"/niches/{niche.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/manage/{niche_id}/edit")
async def edit_niche_form(
    niche_id: int,
    request: Request,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
    session: AsyncSession = Depends(get_db_session),
):
    """Render the edit form with existing niche data."""

    niche = await fetch_niche_by_id(session, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    _ensure_management_access(niche, user)

    context = _build_editor_context(
        request,
        title=f"Edit {niche.name}",
        form_action=f"/niches/manage/{niche.id}/edit",
        submit_label="Save changes",
        user=user,
        niche=niche,
        is_update=True,
        delete_action=f"/niches/manage/{niche.id}/delete",
    )
    return TEMPLATES.TemplateResponse("niche_editor.html", context)


@router.post("/manage/{niche_id}/edit")
async def update_niche(
    niche_id: int,
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
    """Apply updates to an existing niche and redirect to its detail page."""

    niche = await fetch_niche_by_id(session, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    _ensure_management_access(niche, user)

    payload, form_values = _prepare_form_payload(
        name=name,
        short_description=short_description,
        detailed_description=detailed_description,
        splash_image_url=splash_image_url,
        newsletter_price=newsletter_price,
        report_price=report_price,
        voice_instructions=voice_instructions,
        style_guide=style_guide,
    )

    try:
        updated_niche = await service_update_niche(session, niche, payload)
    except NicheNameConflictError as exc:
        context = _build_editor_context(
            request,
            title=f"Edit {niche.name}",
            form_action=f"/niches/manage/{niche.id}/edit",
            submit_label="Save changes",
            user=user,
            niche=niche,
            is_update=True,
            form_values=form_values,
            error_message=str(exc),
            delete_action=f"/niches/manage/{niche.id}/delete",
        )
        return TEMPLATES.TemplateResponse(
            "niche_editor.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    LOGGER.info("User %s updated niche %s", user.email, updated_niche.name)
    return RedirectResponse(url=f"/niches/{updated_niche.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/manage/{niche_id}/delete")
async def delete_niche(
    niche_id: int,
    request: Request,
    confirmation_text: str = Form(...),
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a niche after explicit confirmation."""

    niche = await fetch_niche_by_id(session, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    _ensure_management_access(niche, user)

    if confirmation_text.strip().upper() != "DELETE":
        context = _build_editor_context(
            request,
            title=f"Edit {niche.name}",
            form_action=f"/niches/manage/{niche.id}/edit",
            submit_label="Save changes",
            user=user,
            niche=niche,
            is_update=True,
            error_message="Type DELETE in capitals to confirm removal.",
            delete_action=f"/niches/manage/{niche.id}/delete",
        )
        return TEMPLATES.TemplateResponse(
            "niche_editor.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    await service_delete_niche(session, niche)
    LOGGER.info("User %s deleted niche %s", user.email, niche.name)
    return RedirectResponse(url="/niches", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/api", response_model=list[NicheRead])
async def api_list_niches(session: AsyncSession = Depends(get_db_session)) -> list[Niche]:
    """Return all niches as JSON."""

    return await fetch_all_niches(session)


@router.get("/api/{niche_id}", response_model=NicheRead)
async def api_get_niche(niche_id: int, session: AsyncSession = Depends(get_db_session)) -> Niche:
    """Return a single niche by identifier."""

    niche = await fetch_niche_by_id(session, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    return niche


@router.post("/api", response_model=NicheRead, status_code=status.HTTP_201_CREATED)
async def api_create_niche(
    payload: NicheCreate,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
    session: AsyncSession = Depends(get_db_session),
) -> Niche:
    """API endpoint for creating niches."""

    try:
        niche = await service_create_niche(session, payload.model_dump(exclude_none=True), owner_id=user.id)
    except NicheNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return niche


@router.put("/api/{niche_id}", response_model=NicheRead)
async def api_update_niche(
    niche_id: int,
    payload: NicheUpdate,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
    session: AsyncSession = Depends(get_db_session),
) -> Niche:
    """API endpoint for updating niche metadata."""

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    niche = await fetch_niche_by_id(session, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    _ensure_management_access(niche, user)

    try:
        return await service_update_niche(session, niche, updates)
    except NicheNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/api/{niche_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_niche(
    niche_id: int,
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """API endpoint for deleting a niche."""

    niche = await fetch_niche_by_id(session, niche_id)
    if niche is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
    _ensure_management_access(niche, user)

    await service_delete_niche(session, niche)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
