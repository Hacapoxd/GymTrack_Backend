"""Gestion del catalogo (solo rol ADMIN). No accede a datos personales de salud."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import admin_user
from ..errors import ApiError
from ..models import Exercise, User
from ..schemas import ExerciseCreate, ExerciseOut, ExerciseUpdate

router = APIRouter(prefix="/admin/exercises", tags=["Administración"])


@router.post("", response_model=ExerciseOut, status_code=201, summary="Crear ejercicio del catálogo")
def create(body: ExerciseCreate, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    if db.scalar(select(Exercise.id).where(Exercise.name == body.name)):
        raise ApiError(409, "Ya existe un ejercicio con ese nombre.")
    if bool(body.media_url) != bool(body.media_type):
        raise ApiError(422, "mediaUrl y mediaType deben enviarse juntos.")
    ex = Exercise(**body.model_dump(), sort_order=10_000)
    db.add(ex)
    db.commit()
    return ex


@router.patch("/{exercise_id}", response_model=ExerciseOut,
              summary="Editar ficha, cargar GIF/video o retirar un ejercicio (active=false)")
def update(exercise_id: str, body: ExerciseUpdate, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    ex = db.get(Exercise, exercise_id)
    if ex is None:
        raise ApiError(404, "Ejercicio no encontrado.")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != ex.name and db.scalar(select(Exercise.id).where(Exercise.name == data["name"])):
        raise ApiError(409, "Ya existe un ejercicio con ese nombre.")
    for k, v in data.items():
        setattr(ex, k, v)
    if bool(ex.media_url) != bool(ex.media_type):
        raise ApiError(422, "mediaUrl y mediaType deben enviarse juntos.")
    db.commit()
    return ex
