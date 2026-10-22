import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

Sex = Literal["MALE", "FEMALE"]
Goal = Literal["HYPERTROPHY", "STRENGTH", "CONDITIONING"]
Level = Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"]
MuscleGroup = Literal["CHEST", "BACK", "SHOULDERS", "BICEPS", "TRICEPS", "QUADS", "HAMSTRINGS", "GLUTES", "CALVES", "CORE"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# ------------------------------------------------------------ acceso
class RegisterIn(CamelModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    is_adult: bool
    accept_terms: bool
    accept_disclaimer: bool

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Correo electrónico inválido.")
        return v

    @field_validator("password")
    @classmethod
    def _pwd(cls, v):
        if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("La contraseña debe tener 8 caracteres o más, con letras y números.")
        return v

    @model_validator(mode="after")
    def _consents(self):
        if not (self.is_adult and self.accept_terms and self.accept_disclaimer):
            raise ValueError("Debes confirmar que eres mayor de 18 años, aceptar los términos y entender que GymTrack no ofrece asesoría médica ni nutricional.")
        return self


class LoginIn(CamelModel):
    email: str
    password: str


class RefreshIn(CamelModel):
    refresh_token: str


class TokenOut(CamelModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class UserOut(CamelModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str


# ------------------------------------------------------------ modulo 1
def _birth(v: date) -> date:
    today = date.today()
    age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
    if age < 18:
        raise ValueError("Debes ser mayor de 18 años.")
    if age > 100:
        raise ValueError("Fecha de nacimiento fuera de rango.")
    return v


class ProfileCreate(CamelModel):
    birth_date: date
    sex: Sex
    weight_kg: float = Field(ge=30, le=300)
    height_cm: float = Field(ge=120, le=230)
    days_per_week: int = Field(ge=2, le=6)
    goal: Goal
    level: Level

    @field_validator("birth_date")
    @classmethod
    def _check_birth(cls, v):
        return _birth(v)


class ProfilePatch(CamelModel):
    """Solo se actualizan peso y parametros de entrenamiento. Fecha de nacimiento, sexo y estatura no se editan aqui."""
    weight_kg: float | None = Field(default=None, ge=30, le=300)
    days_per_week: int | None = Field(default=None, ge=2, le=6)
    goal: Goal | None = None
    level: Level | None = None

    @model_validator(mode="after")
    def _any(self):
        if all(getattr(self, f) is None for f in ("weight_kg", "days_per_week", "goal", "level")):
            raise ValueError("Envía al menos un campo a actualizar.")
        return self


class ProfileOut(CamelModel):
    birth_date: date
    age: int
    sex: Sex
    weight_kg: float
    height_cm: float
    bmi: float
    days_per_week: int
    goal: Goal
    level: Level
    updated_at: datetime


class WeightEntryOut(CamelModel):
    weight_kg: float
    recorded_at: datetime


# ------------------------------------------------------------ modulo 3: catalogo
class ExerciseOut(CamelModel):
    id: str
    name: str
    muscle_group: str
    secondary_muscles: list[str]
    movement_pattern: str
    category: str
    equipment: str
    technique: list[str]
    common_errors: list[str]
    media_url: str | None
    media_type: str | None
    active: bool


class ExerciseCreate(CamelModel):
    name: str = Field(min_length=2, max_length=120)
    muscle_group: MuscleGroup
    secondary_muscles: list[MuscleGroup] = []
    movement_pattern: str = Field(min_length=2, max_length=32)
    category: Literal["COMPOUND", "ISOLATION"]
    equipment: str = Field(default="", max_length=40)
    technique: list[str] = []
    common_errors: list[str] = []
    media_url: str | None = Field(default=None, max_length=300, pattern=r"^https://")
    media_type: Literal["GIF", "VIDEO"] | None = None
    load_ratio: float | None = Field(default=None, ge=0, le=3)


class ExerciseUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    equipment: str | None = Field(default=None, max_length=40)
    technique: list[str] | None = None
    common_errors: list[str] | None = None
    media_url: str | None = Field(default=None, max_length=300, pattern=r"^https://")
    media_type: Literal["GIF", "VIDEO"] | None = None
    load_ratio: float | None = Field(default=None, ge=0, le=3)
    active: bool | None = None


# ------------------------------------------------------------ modulo 3: plan
class PlanExerciseOut(CamelModel):
    id: str
    position: int
    exercise: ExerciseOut
    sets: int
    rep_min: int
    rep_max: int
    rest_seconds: int
    suggested_load_kg: float | None
    origin: str
    note: str | None


class PlanDayOut(CamelModel):
    id: str
    day_index: int
    name: str
    focus: str
    is_customized: bool
    estimated_minutes: int
    total_sets: int
    exercises: list[PlanExerciseOut]


class PlanOut(CamelModel):
    id: str
    name: str
    template_code: str
    days_per_week: int
    goal: Goal
    level: Level
    body_weight_kg: float
    status: str
    created_at: datetime
    outdated: bool
    outdated_reasons: list[str]
    warnings: list[str]
    days: list[PlanDayOut]


class PlanSummary(CamelModel):
    id: str
    name: str
    status: str
    goal: Goal
    level: Level
    days_per_week: int
    created_at: datetime
    archived_at: datetime | None


class TemplatePreview(CamelModel):
    code: str
    name: str
    days_per_week: int
    goal: Goal
    level: Level
    days: list[dict]


class CreatePlanIn(CamelModel):
    replace_active: bool = False


class PlanExercisePatch(CamelModel):
    sets: int | None = Field(default=None, ge=1, le=10)
    rep_min: int | None = Field(default=None, ge=1, le=50)
    rep_max: int | None = Field(default=None, ge=1, le=50)
    rest_seconds: int | None = Field(default=None, ge=0, le=600)
    suggested_load_kg: float | None = Field(default=None, ge=0, le=500)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _ranges(self):
        if self.rep_min is not None and self.rep_max is not None and self.rep_max < self.rep_min:
            raise ValueError("repMax no puede ser menor que repMin.")
        return self


class AddExerciseIn(CamelModel):
    exercise_id: str
    position: int | None = Field(default=None, ge=0)
    sets: int | None = Field(default=None, ge=1, le=10)


class ReplaceIn(CamelModel):
    exercise_id: str


class ReorderIn(CamelModel):
    exercise_ids: list[str]


class EditResult(CamelModel):
    day: PlanDayOut
    warnings: list[str] = []


# ------------------------------------------------------------ IA asistida (por token)
class AiStatusOut(CamelModel):
    enabled: bool
    provider: str | None
    model: str | None
    daily_limit: int
    used_today: int
    tokens_today: int


class AiProposalCreate(CamelModel):
    kind: Literal["PERSONALIZE", "ADJUST"]
    intent: Literal["LOWER_INTENSITY", "RAISE_INTENSITY", "SHORTEN_SESSION", "FREE"] | None = None
    message: str | None = Field(default=None, max_length=300)
    day_id: str | None = None
    max_minutes: int | None = Field(default=None, ge=20, le=120)

    @model_validator(mode="after")
    def _coherent(self):
        if self.message is not None:
            self.message = self.message.strip() or None
        if self.kind == "ADJUST":
            if self.intent is None:
                raise ValueError("Para kind=ADJUST indica la intención (intent).")
            if self.intent == "SHORTEN_SESSION" and self.max_minutes is None:
                raise ValueError("Para acortar la sesión indica maxMinutes (20 a 120).")
            if self.intent == "FREE" and not self.message:
                raise ValueError("Para intent=FREE escribe un mensaje (message).")
        return self


class AiOperationOut(CamelModel):
    op: Literal["UPDATE", "REPLACE", "ADD", "REMOVE"]
    item_id: str | None = None
    day_id: str | None = None
    exercise_id: str | None = None
    changes: dict = {}
    description: str
    reason: str = ""


class AiProposalOut(CamelModel):
    id: str
    kind: str
    intent: str | None
    request_text: str | None
    summary: str
    operations: list[AiOperationOut]
    discarded: list[str]
    status: str
    model: str
    input_tokens: int
    output_tokens: int
    created_at: datetime


class AiApplyOut(CamelModel):
    proposal: AiProposalOut
    days: list[PlanDayOut]


class IntensityIn(CamelModel):
    direction: Literal["LOWER"] = "LOWER"
    day_id: str | None = None


class IntensityOut(CamelModel):
    days: list[PlanDayOut]
