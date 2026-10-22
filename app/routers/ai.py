"""IA asistida por token (Módulo 3): personalizar el plan o ajustarlo (bajar/subir intensidad, acortar sesión).
La IA propone; el backend valida; el usuario confirma. Los tokens consumidos quedan registrados."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..deps import current_user, get_llm
from ..errors import ApiError
from ..models import AiProposal, Exercise, Plan, User, utcnow
from ..schemas import AiApplyOut, AiProposalCreate, AiProposalOut, AiStatusOut
from ..services import ai_assist as ai
from ..services.llm import LLMClient, LLMError
from ..services.profile import age_of
from .athletes import get_profile
from .plans import _active, _day_out

log = logging.getLogger("gymtrack.ai")
router = APIRouter(prefix="/ai", tags=["IA asistida"])

_CAMEL = {"sets": "sets", "rep_min": "repMin", "rep_max": "repMax", "rest_seconds": "restSeconds", "load_kg": "loadKg"}


def _catalog(db: Session) -> dict[str, Exercise]:
    return {e.id: e for e in db.scalars(select(Exercise).where(Exercise.active.is_(True)).order_by(Exercise.sort_order))}


def _today_start():
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _usage(db: Session, user_id: str) -> tuple[int, int]:
    n, tok = db.execute(select(func.count(AiProposal.id), func.coalesce(func.sum(AiProposal.input_tokens + AiProposal.output_tokens), 0))
                        .where(AiProposal.user_id == user_id, AiProposal.created_at >= _today_start())).one()
    return int(n), int(tok)


def _own(db: Session, user: User, pid: str) -> AiProposal:
    pr = db.get(AiProposal, pid)
    if pr is None or pr.user_id != user.id:
        raise ApiError(404, "Propuesta no encontrada.")
    return pr


@router.get("/status", response_model=AiStatusOut, summary="¿Está activa la IA? Uso de hoy")
def status(user: User = Depends(current_user), db: Session = Depends(get_db), client: LLMClient | None = Depends(get_llm)):
    n, tok = _usage(db, user.id)
    return AiStatusOut(enabled=client is not None, provider=client.provider if client else None,
                       model=client.model if client else None, daily_limit=config.AI_DAILY_LIMIT, used_today=n, tokens_today=tok)


@router.post("/proposals", response_model=AiProposalOut, status_code=201, summary="Pedir una propuesta a la IA (no cambia nada todavía)")
def create(body: AiProposalCreate, user: User = Depends(current_user), db: Session = Depends(get_db),
           client: LLMClient | None = Depends(get_llm)):
    if client is None:
        raise ApiError(503, "La IA no está activada en este servidor. Puedes usar “Bajar intensidad” sin IA.")
    profile = get_profile(db, user)
    plan = _active(db, user)
    if body.day_id and not any(d.id == body.day_id for d in plan.days):
        raise ApiError(404, "Día del plan no encontrado.")
    if body.message and ai.OUT_OF_SCOPE.search(body.message):
        raise ApiError(422, ai.OUT_OF_SCOPE_MSG)
    used, _ = _usage(db, user.id)
    if used >= config.AI_DAILY_LIMIT:
        raise ApiError(429, f"Llegaste al límite de {config.AI_DAILY_LIMIT} propuestas con IA por hoy. "
                            "Puedes seguir usando “Bajar intensidad” sin IA.")
    catalog = _catalog(db)
    prompt = ai.build_user_prompt(profile, plan, list(catalog.values()), body.kind, body.intent, body.message,
                                  body.max_minutes, body.day_id, age_of(profile.birth_date))
    try:
        res = client.complete(ai.SYSTEM_PROMPT, prompt, config.AI_MAX_OUTPUT_TOKENS)
    except LLMError as e:
        log.warning("Fallo del proveedor de IA: %s", e)   # sin datos personales
        raise ApiError(503, "El asistente de IA no está disponible ahora. Intenta más tarde o usa “Bajar intensidad” sin IA.")

    data = ai.parse_model_json(res.text)
    if data is None:
        summary, ops, bad = "No pude generar una propuesta válida. Intenta de nuevo.", [], ["La respuesta del modelo no tenía el formato esperado."]
    else:
        summary = str(data.get("summary") or "")[:600]
        ops, bad = ai.validate_operations(data.get("operations", []), plan, catalog, body.intent, body.day_id)
        if body.intent == "SHORTEN_SESSION" and ops and body.max_minutes:
            mins = ai.minutes_after(plan, ops, catalog)
            over = [f"{d.name} (~{mins[d.id]} min)" for d in plan.days if (not body.day_id or d.id == body.day_id) and mins[d.id] > body.max_minutes]
            if over:
                summary = (summary + f" Aviso: aun así {', '.join(over)} supera tus {body.max_minutes} min.").strip()[:600]
    if not ops and not summary:
        summary = "No hay cambios que proponer para esta petición."
    pr = AiProposal(user_id=user.id, plan_id=plan.id, kind=body.kind, intent=body.intent, request_text=body.message,
                    summary=summary, operations=ops, discarded=bad, status="PENDING" if ops else "REJECTED",
                    model=res.model, input_tokens=res.input_tokens, output_tokens=res.output_tokens)
    db.add(pr)
    db.commit()
    return pr


@router.get("/proposals", response_model=list[AiProposalOut], summary="Mis últimas propuestas")
def list_proposals(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(AiProposal).where(AiProposal.user_id == user.id).order_by(AiProposal.created_at.desc()).limit(20)).all()


@router.get("/proposals/{proposal_id}", response_model=AiProposalOut, summary="Ver una propuesta")
def get_proposal(proposal_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _own(db, user, proposal_id)


@router.post("/proposals/{proposal_id}/reject", response_model=AiProposalOut, summary="Descartar una propuesta")
def reject(proposal_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pr = _own(db, user, proposal_id)
    if pr.status != "PENDING":
        raise ApiError(409, "Esa propuesta ya fue resuelta.")
    pr.status, pr.decided_at = "REJECTED", utcnow()
    db.commit()
    return pr


@router.post("/proposals/{proposal_id}/apply", response_model=AiApplyOut, summary="Aplicar la propuesta al plan (la confirma el usuario)")
def apply(proposal_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pr = _own(db, user, proposal_id)
    if pr.status != "PENDING":
        raise ApiError(409, "Esa propuesta ya fue resuelta.")
    plan = db.get(Plan, pr.plan_id)
    if plan is None or plan.status != "ACTIVE":
        raise ApiError(409, "La propuesta era para un plan que ya no está activo.")
    catalog = _catalog(db)
    raw = [{"op": o["op"], "itemId": o["item_id"], "dayId": o["day_id"], "exerciseId": o["exercise_id"], "reason": o["reason"],
            **{_CAMEL[k]: v for k, v in o["changes"].items()}} for o in pr.operations]
    # Se vuelve a validar contra el plan de AHORA: el usuario pudo editarlo desde que se generó la propuesta.
    ops, bad = ai.validate_operations(raw, plan, catalog, pr.intent)
    if not ops:
        raise ApiError(409, "Tu plan cambió y la propuesta ya no es aplicable. Pide una nueva.")
    days = ai.apply_operations(plan, ops, catalog)
    pr.status, pr.decided_at = "APPLIED", utcnow()
    pr.discarded = [*pr.discarded, *[f"Al aplicar: {b}" for b in bad]]
    db.commit()
    for d in days:
        db.refresh(d)
    return AiApplyOut(proposal=pr, days=[_day_out(d) for d in days])
