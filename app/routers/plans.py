"""Modulo 3: asignacion del plan por filtros (dias + objetivo + nivel) y edicion libre."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..errors import ApiError
from ..models import AthleteProfile, Exercise, Plan, PlanDay, PlanExercise, User, utcnow
from ..schemas import (AddExerciseIn, CreatePlanIn, EditResult, IntensityIn, IntensityOut, PlanDayOut,
                       PlanExercisePatch, PlanOut, PlanSummary, ReorderIn, ReplaceIn, TemplatePreview)
from ..services import ai_assist, planner
from .athletes import get_profile

router = APIRouter(prefix="/plans", tags=["Plan"])


# ------------------------------------------------------------------ helpers
def _day_out(day: PlanDay) -> PlanDayOut:
    items = sorted(day.exercises, key=lambda e: e.position)
    return PlanDayOut.model_validate({
        "id": day.id, "day_index": day.day_index, "name": day.name, "focus": day.focus,
        "is_customized": day.is_customized, "estimated_minutes": planner.estimated_minutes(items),
        "total_sets": sum(i.sets for i in items), "exercises": items})


def _plan_out(db: Session, plan: Plan) -> PlanOut:
    reasons: list[str] = []
    if plan.status == "ACTIVE":
        prof = db.get(AthleteProfile, plan.user_id)
        if prof:
            if prof.days_per_week != plan.days_per_week:
                reasons.append(f"Ahora entrenas {prof.days_per_week} días por semana (el plan es de {plan.days_per_week}).")
            if prof.goal != plan.goal:
                reasons.append("Cambiaste tu objetivo principal.")
            if prof.level != plan.level:
                reasons.append("Cambiaste tu nivel.")
    return PlanOut.model_validate({
        "id": plan.id, "name": plan.name, "template_code": plan.template.code, "days_per_week": plan.days_per_week,
        "goal": plan.goal, "level": plan.level,
        "body_weight_kg": plan.body_weight_kg, "status": plan.status, "created_at": plan.created_at,
        "outdated": bool(reasons), "outdated_reasons": reasons, "warnings": planner.plan_warnings(plan),
        "days": [_day_out(d).model_dump() for d in plan.days]})


def _active(db: Session, user: User) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.user_id == user.id, Plan.status == "ACTIVE"))
    if plan is None:
        raise ApiError(404, "No tienes un plan activo.")
    return plan


def _day(plan: Plan, day_id: str) -> PlanDay:
    for d in plan.days:
        if d.id == day_id:
            return d
    raise ApiError(404, "Día del plan no encontrado.")


def _item(plan: Plan, item_id: str) -> tuple[PlanDay, PlanExercise]:
    for d in plan.days:
        for e in d.exercises:
            if e.id == item_id:
                return d, e
    raise ApiError(404, "Ejercicio del plan no encontrado.")


def _renumber(day: PlanDay) -> None:
    for i, e in enumerate(sorted(day.exercises, key=lambda x: x.position)):
        e.position = i


def _catalog_exercise(db: Session, exercise_id: str) -> Exercise:
    ex = db.get(Exercise, exercise_id)
    if ex is None or not ex.active:
        raise ApiError(404, "Ejercicio no encontrado o retirado del catálogo.")
    return ex


def _finish(db: Session, day: PlanDay, warnings: list[str] | None = None) -> EditResult:
    day.is_customized = True
    db.commit()
    db.refresh(day)
    return EditResult(day=_day_out(day), warnings=warnings or [])


# ------------------------------------------------------------------ asignacion y consulta
@router.get("/preview", response_model=TemplatePreview, summary="Plantilla que se asignaría con tu perfil actual")
def preview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    prof = get_profile(db, user)
    t = planner.match_template(db, prof.days_per_week, prof.goal, prof.level)
    if t is None:
        raise ApiError(404, "No hay una plantilla para esa combinación de días, objetivo y nivel.")
    return TemplatePreview(code=t.code, name=t.name, days_per_week=t.days_per_week, goal=t.goal, level=t.level,
                           days=[{"dayIndex": d.day_index, "name": d.name, "focus": d.focus,
                                  "exercises": [e.exercise.name for e in d.exercises]} for d in t.days])


@router.post("", response_model=PlanOut, status_code=201, summary="Generar y activar el plan según tu perfil")
def create_plan(body: CreatePlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    prof = get_profile(db, user)
    current = db.scalar(select(Plan).where(Plan.user_id == user.id, Plan.status == "ACTIVE"))
    if current and not body.replace_active:
        raise ApiError(409, "Ya tienes un plan activo. Envía replaceActive=true para reemplazarlo "
                            "(el actual se conserva en tu historial).")
    t = planner.match_template(db, prof.days_per_week, prof.goal, prof.level)
    if t is None:
        raise ApiError(404, "No hay una plantilla para esa combinación de días, objetivo y nivel.")
    if current:
        current.status, current.archived_at = "ARCHIVED", utcnow()
    plan = planner.instantiate_plan(db, user.id, prof, t)
    db.commit()
    return _plan_out(db, plan)


@router.get("/active", response_model=PlanOut, summary="Plan activo con sus días y ejercicios")
def get_active(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _plan_out(db, _active(db, user))


@router.get("", response_model=list[PlanSummary], summary="Historial de planes")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at.desc())).all()


@router.get("/{plan_id}", response_model=PlanOut, summary="Consultar un plan propio (activo o archivado)")
def get_plan(plan_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise ApiError(404, "Plan no encontrado.")
    return _plan_out(db, plan)


# ------------------------------------------------------------------ edicion libre (antes o durante la rutina)
@router.patch("/active/exercises/{item_id}", response_model=EditResult,
              summary="Editar series, repeticiones, descanso, carga o nota de un ejercicio")
def patch_item(item_id: str, body: PlanExercisePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _active(db, user)
    day, e = _item(plan, item_id)
    fields = body.model_fields_set
    rmin = body.rep_min if body.rep_min is not None else e.rep_min
    rmax = body.rep_max if body.rep_max is not None else e.rep_max
    if rmax < rmin:
        raise ApiError(422, "repMax no puede ser menor que repMin.")
    e.rep_min, e.rep_max = rmin, rmax
    if body.sets is not None:
        e.sets = body.sets
    if body.rest_seconds is not None:
        e.rest_seconds = body.rest_seconds
    if "suggested_load_kg" in fields:
        e.suggested_load_kg = body.suggested_load_kg
    if "note" in fields:
        e.note = body.note
    return _finish(db, day)


@router.delete("/active/exercises/{item_id}", response_model=EditResult, summary="Quitar un ejercicio del día")
def delete_item(item_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _active(db, user)
    day, e = _item(plan, item_id)
    day.exercises.remove(e)
    db.flush()
    _renumber(day)
    return _finish(db, day)


@router.post("/active/exercises/{item_id}/replace", response_model=EditResult,
             summary="Intercambiar un ejercicio por otro (p. ej. si el equipo está ocupado)")
def replace_item(item_id: str, body: ReplaceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _active(db, user)
    day, e = _item(plan, item_id)
    new = _catalog_exercise(db, body.exercise_id)
    if new.id == e.exercise_id:
        raise ApiError(409, "Ese ya es el ejercicio asignado.")
    if any(x.exercise_id == new.id for x in day.exercises):
        raise ApiError(409, "Ese ejercicio ya está en este día.")
    old = e.exercise
    fresh = planner.new_custom_exercise(plan, new, e.position, sets=e.sets)
    e.exercise_id, e.exercise = new.id, new
    e.rep_min, e.rep_max, e.rest_seconds = fresh.rep_min, fresh.rep_max, fresh.rest_seconds
    e.suggested_load_kg, e.origin, e.note = fresh.suggested_load_kg, "SWAPPED", None
    warnings = []
    if new.muscle_group != old.muscle_group:
        warnings.append(f"{new.name} trabaja {new.muscle_group} y reemplaza a {old.name} ({old.muscle_group}): "
                        "el enfoque del día cambia.")
    return _finish(db, day, warnings)


@router.post("/active/days/{day_id}/exercises", response_model=EditResult, status_code=201,
             summary="Agregar un ejercicio al día")
def add_item(day_id: str, body: AddExerciseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _active(db, user)
    day = _day(plan, day_id)
    ex = _catalog_exercise(db, body.exercise_id)
    if len(day.exercises) >= planner.MAX_EXERCISES_PER_DAY:
        raise ApiError(422, f"Máximo {planner.MAX_EXERCISES_PER_DAY} ejercicios por día.")
    if any(x.exercise_id == ex.id for x in day.exercises):
        raise ApiError(409, "Ese ejercicio ya está en este día.")
    pos = min(body.position, len(day.exercises)) if body.position is not None else len(day.exercises)
    for x in day.exercises:
        if x.position >= pos:
            x.position += 1
    day.exercises.append(planner.new_custom_exercise(plan, ex, pos, sets=body.sets))
    db.flush()
    _renumber(day)
    return _finish(db, day)


@router.put("/active/days/{day_id}/order", response_model=EditResult, summary="Reordenar los ejercicios del día")
def reorder(day_id: str, body: ReorderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _active(db, user)
    day = _day(plan, day_id)
    if sorted(body.exercise_ids) != sorted(e.id for e in day.exercises):
        raise ApiError(422, "exerciseIds debe contener exactamente los ejercicios actuales del día, sin repetir.")
    pos = {eid: i for i, eid in enumerate(body.exercise_ids)}
    for e in day.exercises:
        e.position = pos[e.id]
    return _finish(db, day)


@router.post("/active/days/{day_id}/reset", response_model=EditResult, summary="Volver al plan recomendado (plantilla)")
def reset(day_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _active(db, user)
    day = _day(plan, day_id)
    planner.reset_day(db, plan, day)
    db.commit()
    db.refresh(day)
    return EditResult(day=_day_out(day), warnings=[])


@router.post("/active/intensity", response_model=IntensityOut,
             summary="Bajar la intensidad sin IA: −1 serie (mín. 2) y −10 % de carga")
def lower_intensity(body: IntensityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _active(db, user)
    if body.day_id:
        _day(plan, body.day_id)
    days = ai_assist.lower_intensity(plan, body.day_id)
    db.commit()
    for d in days:
        db.refresh(d)
    return IntensityOut(days=[_day_out(d) for d in days])
