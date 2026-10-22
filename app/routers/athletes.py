"""Modulo 1: Perfil del usuario (datos antropometricos y parametros de entrenamiento)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..errors import ApiError
from ..models import AthleteProfile, User, WeightEntry
from ..schemas import ProfileCreate, ProfileOut, ProfilePatch, WeightEntryOut
from ..services.profile import age_of, bmi_of

router = APIRouter(tags=["Perfil"])


def _profile_out(p: AthleteProfile) -> ProfileOut:
    return ProfileOut(birth_date=p.birth_date, age=age_of(p.birth_date), sex=p.sex, weight_kg=p.weight_kg,
                      height_cm=p.height_cm, bmi=bmi_of(p.weight_kg, p.height_cm), days_per_week=p.days_per_week,
                      goal=p.goal, level=p.level, updated_at=p.updated_at)


def get_profile(db: Session, user: User) -> AthleteProfile:
    p = db.get(AthleteProfile, user.id)
    if p is None:
        raise ApiError(404, "Aún no completaste tu perfil.")
    return p


@router.post("/athletes/me", response_model=ProfileOut, status_code=201, summary="Crear el perfil")
def create_profile(body: ProfileCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(AthleteProfile, user.id):
        raise ApiError(409, "Ya tienes un perfil. Usa PATCH /athletes/me para actualizarlo.")
    p = AthleteProfile(user_id=user.id, birth_date=body.birth_date, sex=body.sex, weight_kg=body.weight_kg,
                       height_cm=body.height_cm, days_per_week=body.days_per_week, goal=body.goal, level=body.level)
    db.add(p)
    db.add(WeightEntry(user_id=user.id, weight_kg=body.weight_kg))
    db.commit()
    return _profile_out(p)


@router.get("/athletes/me", response_model=ProfileOut, summary="Consultar el perfil (incluye IMC calculado)")
def read_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _profile_out(get_profile(db, user))


@router.patch("/athletes/me", response_model=ProfileOut, summary="Actualizar peso, días, objetivo o nivel")
def patch_profile(body: ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_profile(db, user)
    if body.weight_kg is not None and body.weight_kg != p.weight_kg:
        p.weight_kg = body.weight_kg
        db.add(WeightEntry(user_id=user.id, weight_kg=body.weight_kg))
    for f in ("days_per_week", "goal", "level"):
        v = getattr(body, f)
        if v is not None:
            setattr(p, f, v)
    db.commit()
    return _profile_out(p)


@router.get("/athletes/me/weights", response_model=list[WeightEntryOut], summary="Historial de peso corporal")
def weight_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(WeightEntry).where(WeightEntry.user_id == user.id)
                      .order_by(WeightEntry.recorded_at.desc(), WeightEntry.id.desc())).all()
