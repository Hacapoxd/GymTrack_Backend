"""Modulo 3: catalogo de ejercicios y fichas tecnicas (tecnica, errores comunes, GIF/video)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..errors import ApiError
from ..models import Exercise, User
from ..schemas import ExerciseOut

router = APIRouter(prefix="/exercises", tags=["Ejercicios"])


@router.get("", response_model=list[ExerciseOut], summary="Listar ejercicios activos (con filtros)")
def list_exercises(muscle_group: str | None = Query(None, alias="muscleGroup"), q: str | None = None,
                   category: str | None = None, equipment: str | None = None,
                   _: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Exercise).where(Exercise.active.is_(True))
    if muscle_group:
        stmt = stmt.where(Exercise.muscle_group == muscle_group.upper())
    if category:
        stmt = stmt.where(Exercise.category == category.upper())
    if equipment:
        stmt = stmt.where(Exercise.equipment.ilike(equipment))
    if q:
        stmt = stmt.where(Exercise.name.ilike(f"%{q.strip()}%"))
    return db.scalars(stmt.order_by(Exercise.sort_order, Exercise.name).limit(200)).all()


@router.get("/{exercise_id}", response_model=ExerciseOut, summary="Ficha técnica de un ejercicio")
def get_exercise(exercise_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    ex = db.get(Exercise, exercise_id)
    if ex is None:
        raise ApiError(404, "Ejercicio no encontrado.")
    return ex


@router.get("/{exercise_id}/alternatives", response_model=list[ExerciseOut],
            summary="Alternativas del mismo grupo muscular (primero el mismo patrón de movimiento)")
def alternatives(exercise_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    ex = db.get(Exercise, exercise_id)
    if ex is None:
        raise ApiError(404, "Ejercicio no encontrado.")
    rows = db.scalars(select(Exercise).where(Exercise.active.is_(True), Exercise.muscle_group == ex.muscle_group,
                                             Exercise.id != ex.id).order_by(Exercise.sort_order)).all()
    return sorted(rows, key=lambda e: (e.movement_pattern != ex.movement_pattern, e.sort_order))
