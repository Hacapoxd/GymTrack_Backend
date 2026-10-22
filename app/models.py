"""Modelo de datos. Modulo 1 (Perfil) y Modulo 3 (Plantillas, Plan e IA asistida) + acceso."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import config
from .database import Base


def _id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """UTC ingenuo (lo que SQLite devuelve al leer)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ Acceso
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(10), default="USER")  # USER | ADMIN
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    profile: Mapped["AthleteProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # ADULT | TERMS_PRIVACY | DISCLAIMER (sin asesoria medica/nutricional)
    version: Mapped[str] = mapped_column(String(10), default=config.CONSENT_VERSION)
    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


# ------------------------------------------------------------------ Modulo 1
class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(6))             # MALE | FEMALE (sexo biologico)
    weight_kg: Mapped[float] = mapped_column(Float)
    height_cm: Mapped[float] = mapped_column(Float)
    days_per_week: Mapped[int] = mapped_column(Integer)
    goal: Mapped[str] = mapped_column(String(14))           # HYPERTROPHY | STRENGTH | CONDITIONING
    level: Mapped[str] = mapped_column(String(12))          # BEGINNER | INTERMEDIATE | ADVANCED (percibido)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    user: Mapped[User] = relationship(back_populates="profile")


class WeightEntry(Base):
    """Historial de peso corporal (el peso es actualizable; cada cambio deja registro)."""
    __tablename__ = "weight_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ Modulo 3: catalogo
class Exercise(Base):
    __tablename__ = "exercises"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    muscle_group: Mapped[str] = mapped_column(String(16), index=True)
    secondary_muscles: Mapped[list] = mapped_column(JSON, default=list)
    movement_pattern: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(10))        # COMPOUND | ISOLATION
    equipment: Mapped[str] = mapped_column(String(40), default="")
    technique: Mapped[list] = mapped_column(JSON, default=list)       # pasos de ejecucion
    common_errors: Mapped[list] = mapped_column(JSON, default=list)   # errores comunes
    media_url: Mapped[str | None] = mapped_column(String(300), nullable=True)   # GIF/video
    media_type: Mapped[str | None] = mapped_column(String(5), nullable=True)    # GIF | VIDEO
    load_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)      # fraccion del peso corporal (serie de trabajo, nivel intermedio, hombre)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000)


# ------------------------------------------------------------------ Modulo 3: plantillas maestras
class RoutineTemplate(Base):
    __tablename__ = "routine_templates"
    __table_args__ = (UniqueConstraint("days_per_week", "goal", "level"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    days_per_week: Mapped[int] = mapped_column(Integer, index=True)
    goal: Mapped[str] = mapped_column(String(14), index=True)
    level: Mapped[str] = mapped_column(String(12), index=True)
    days: Mapped[list["TemplateDay"]] = relationship(cascade="all, delete-orphan", order_by="TemplateDay.day_index")


class TemplateDay(Base):
    __tablename__ = "template_days"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    template_id: Mapped[str] = mapped_column(ForeignKey("routine_templates.id", ondelete="CASCADE"), index=True)
    day_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))      # "Día 1: Empuje"
    focus: Mapped[str] = mapped_column(String(80))     # "Pecho / Hombro / Tríceps"
    exercises: Mapped[list["TemplateExercise"]] = relationship(cascade="all, delete-orphan", order_by="TemplateExercise.position")


class TemplateExercise(Base):
    __tablename__ = "template_exercises"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    template_day_id: Mapped[str] = mapped_column(ForeignKey("template_days.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer)
    sets: Mapped[int] = mapped_column(Integer)
    rep_min: Mapped[int] = mapped_column(Integer)
    rep_max: Mapped[int] = mapped_column(Integer)
    rest_seconds: Mapped[int] = mapped_column(Integer)
    exercise: Mapped[Exercise] = relationship()


# ------------------------------------------------------------------ Modulo 3: plan del usuario (editable)
class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("routine_templates.id"))
    name: Mapped[str] = mapped_column(String(120))
    days_per_week: Mapped[int] = mapped_column(Integer)
    goal: Mapped[str] = mapped_column(String(14))
    level: Mapped[str] = mapped_column(String(12))
    body_weight_kg: Mapped[float] = mapped_column(Float)                        # base de la carga sugerida inicial
    sex: Mapped[str] = mapped_column(String(6))
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")           # ACTIVE | ARCHIVED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    template: Mapped[RoutineTemplate] = relationship()
    days: Mapped[list["PlanDay"]] = relationship(cascade="all, delete-orphan", order_by="PlanDay.day_index")


class PlanDay(Base):
    __tablename__ = "plan_days"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    template_day_id: Mapped[str | None] = mapped_column(ForeignKey("template_days.id"), nullable=True)
    day_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    focus: Mapped[str] = mapped_column(String(80))
    is_customized: Mapped[bool] = mapped_column(Boolean, default=False)
    exercises: Mapped[list["PlanExercise"]] = relationship(cascade="all, delete-orphan", order_by="PlanExercise.position")


class PlanExercise(Base):
    __tablename__ = "plan_exercises"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    plan_day_id: Mapped[str] = mapped_column(ForeignKey("plan_days.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer)
    sets: Mapped[int] = mapped_column(Integer)
    rep_min: Mapped[int] = mapped_column(Integer)
    rep_max: Mapped[int] = mapped_column(Integer)
    rest_seconds: Mapped[int] = mapped_column(Integer)
    suggested_load_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin: Mapped[str] = mapped_column(String(10), default="TEMPLATE")  # TEMPLATE | SWAPPED | CUSTOM | AI
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    exercise: Mapped[Exercise] = relationship()


class AiProposal(Base):
    """Propuesta de la IA sobre el plan. La IA solo PROPONE; nada cambia hasta que el usuario la aplica.
    Guardamos los tokens consumidos para controlar el costo (el proveedor cobra por token)."""
    __tablename__ = "ai_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))                # PERSONALIZE | ADJUST
    intent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    request_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summary: Mapped[str] = mapped_column(String(600), default="")
    operations: Mapped[list] = mapped_column(JSON, default=list)   # ya validadas por el backend
    discarded: Mapped[list] = mapped_column(JSON, default=list)    # propuestas del modelo que se descartaron y por que
    status: Mapped[str] = mapped_column(String(10), default="PENDING")  # PENDING | APPLIED | REJECTED
    model: Mapped[str] = mapped_column(String(80), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
