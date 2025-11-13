"""app.routers.niches
======================
Mini-README: Exposes routes for listing niches, viewing detailed pages, and allowing
niche administrators to create, update, or delete niche configuration. Provides both
template-powered management pages and JSON APIs for programmatic use.
"""

from decimal import Decimal, InvalidOperation
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
    count_active_niches_for_user,
    get_active_creator_subscription,
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
    creator_plan: Any | None = None,
    plan_limit_message: str | None = None,
    plan_locked: bool = False,
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
        "creator_plan": creator_plan,
        "plan_limit_message": plan_limit_message,
        "plan_locked": plan_locked,
    }


def _parse_decimal(value: str) -> Decimal:
    """Convert a string to a two-decimal-place ``Decimal`` or raise ``ValueError``."""

    try:
        decimal_value = Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:  # noqa: BLE001 - value originates from form input
        raise ValueError("Invalid price provided. Please use numbers only.") from exc
    return decimal_value


def _prepare_form_payload(
    *,
    name: str,
    short_description: str,
    detailed_description: str,
    splash_image_url: str,
    newsletter_price: Decimal,
    report_price: Decimal,
    currency_code: str,
    newsletter_cadence: str,
    report_cadence: str,
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
        "currency_code": currency_code,
        "newsletter_cadence": newsletter_cadence,
        "report_cadence": report_cadence,
        "voice_instructions": _normalize_optional_text(voice_instructions),
        "style_guide": _normalize_optional_text(style_guide),
    }

    form_values = {
        "name": payload["name"],
        "short_description": payload["short_description"],
        "detailed_description": detailed_description.strip(),
        "splash_image_url": splash_image_url.strip(),
        "newsletter_price": f"{newsletter_price:.2f}",
        "report_price": f"{report_price:.2f}",
        "currency_code": currency_code,
        "newsletter_cadence": newsletter_cadence,
        "report_cadence": report_cadence,
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


async def _creator_plan_context(
    session: AsyncSession,
    user: User,
) -> tuple[Any | None, str | None, bool]:
    """Return contextual information about a user's curator plan and quota."""

    if user.role == UserRole.ADMIN:
        return None, "Admins can create unlimited niches.", False

    creator_subscription = await get_active_creator_subscription(session, user.id)
    if creator_subscription is None or creator_subscription.plan is None:
        return None, "Upgrade to a curator plan from your dashboard to unlock niche creation.", True

    plan = creator_subscription.plan
    owned_niches = await count_active_niches_for_user(session, user.id)
    remaining = max(plan.max_niches - owned_niches, 0)
    message = (
        f"{plan.display_name} allows {plan.max_niches} niches. You have {remaining} slot(s) remaining this cycle."
    )
    return plan, message, remaining <= 0


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
    session: AsyncSession = Depends(get_db_session),
):
    """Render the form for creating a niche."""

    creator_plan, plan_message, plan_locked = await _creator_plan_context(session, user)
    context = _build_editor_context(
        request,
        title="Create Niche",
        form_action="/niches/manage/create",
        submit_label="Create niche",
        user=user,
        creator_plan=creator_plan,
        plan_limit_message=plan_message,
        plan_locked=plan_locked,
    )
    return TEMPLATES.TemplateResponse("niche_editor.html", context)


@router.post("/manage/create")
async def create_niche(
    request: Request,
    name: str = Form(...),
    short_description: str = Form(...),
    detailed_description: str = Form(""),
    splash_image_url: str = Form(""),
    newsletter_price: str = Form("0"),
    report_price: str = Form("0"),
    currency_code: str = Form("GBP"),
    newsletter_cadence: str = Form("monthly"),
    report_cadence: str = Form("monthly"),
    voice_instructions: str = Form(""),
    style_guide: str = Form(""),
    user: User = Depends(require_role([UserRole.ADMIN, UserRole.NICHE_ADMIN])),
    session: AsyncSession = Depends(get_db_session),
):
    """Persist a new niche in the database."""

    creator_plan, plan_message, plan_locked = await _creator_plan_context(session, user)
    raw_form_values = {
        "name": name,
        "short_description": short_description,
        "detailed_description": detailed_description,
        "splash_image_url": splash_image_url,
        "newsletter_price": newsletter_price,
        "report_price": report_price,
        "currency_code": currency_code,
        "newsletter_cadence": newsletter_cadence,
        "report_cadence": report_cadence,
        "voice_instructions": voice_instructions,
        "style_guide": style_guide,
    }

    if plan_locked:
        context = _build_editor_context(
            request,
            title="Create Niche",
            form_action="/niches/manage/create",
            submit_label="Create niche",
            user=user,
            form_values=raw_form_values,
            error_message=plan_message,
            creator_plan=creator_plan,
            plan_limit_message=plan_message,
            plan_locked=plan_locked,
        )
        return TEMPLATES.TemplateResponse(
            "niche_editor.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    try:
        newsletter_price_decimal = _parse_decimal(newsletter_price)
        report_price_decimal = _parse_decimal(report_price)
    except ValueError as exc:
        context = _build_editor_context(
            request,
            title="Create Niche",
            form_action="/niches/manage/create",
            submit_label="Create niche",
            user=user,
            form_values=raw_form_values,
            error_message=str(exc),
            creator_plan=creator_plan,
            plan_limit_message=plan_message,
            plan_locked=plan_locked,
        )
        return TEMPLATES.TemplateResponse(
            "niche_editor.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    payload, form_values = _prepare_form_payload(
        name=name,
        short_description=short_description,
        detailed_description=detailed_description,
        splash_image_url=splash_image_url,
        newsletter_price=newsletter_price_decimal,
        report_price=report_price_decimal,
        currency_code=currency_code,
        newsletter_cadence=newsletter_cadence,
        report_cadence=report_cadence,
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
            creator_plan=creator_plan,
            plan_limit_message=plan_message,
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

    creator_plan, plan_message, _ = await _creator_plan_context(session, user)
    context = _build_editor_context(
        request,
        title=f"Edit {niche.name}",
        form_action=f"/niches/manage/{niche.id}/edit",
        submit_label="Save changes",
        user=user,
        niche=niche,
        is_update=True,
        delete_action=f"/niches/manage/{niche.id}/delete",
        creator_plan=creator_plan,
        plan_limit_message=plan_message,
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
    newsletter_price: str = Form("0"),
    report_price: str = Form("0"),
    currency_code: str = Form("GBP"),
    newsletter_cadence: str = Form("monthly"),
    report_cadence: str = Form("monthly"),
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

    creator_plan, plan_message, _ = await _creator_plan_context(session, user)
    raw_form_values = {
        "name": name,
        "short_description": short_description,
        "detailed_description": detailed_description,
        "splash_image_url": splash_image_url,
        "newsletter_price": newsletter_price,
        "report_price": report_price,
        "currency_code": currency_code,
        "newsletter_cadence": newsletter_cadence,
        "report_cadence": report_cadence,
        "voice_instructions": voice_instructions,
        "style_guide": style_guide,
    }

    try:
        newsletter_price_decimal = _parse_decimal(newsletter_price)
        report_price_decimal = _parse_decimal(report_price)
    except ValueError as exc:
        context = _build_editor_context(
            request,
            title=f"Edit {niche.name}",
            form_action=f"/niches/manage/{niche.id}/edit",
            submit_label="Save changes",
            user=user,
            niche=niche,
            is_update=True,
            form_values=raw_form_values,
            error_message=str(exc),
            delete_action=f"/niches/manage/{niche.id}/delete",
            creator_plan=creator_plan,
            plan_limit_message=plan_message,
        )
        return TEMPLATES.TemplateResponse(
            "niche_editor.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    payload, form_values = _prepare_form_payload(
        name=name,
        short_description=short_description,
        detailed_description=detailed_description,
        splash_image_url=splash_image_url,
        newsletter_price=newsletter_price_decimal,
        report_price=report_price_decimal,
        currency_code=currency_code,
        newsletter_cadence=newsletter_cadence,
        report_cadence=report_cadence,
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
            creator_plan=creator_plan,
            plan_limit_message=plan_message,
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

    _, plan_message, plan_locked = await _creator_plan_context(session, user)
    if plan_locked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=plan_message)

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
