"""Motor determinista del Modulo 3: plantillas maestras, asignacion por filtros y parametrizacion.

Asignacion: query a routine_templates filtrando por (dias por semana + objetivo + nivel).
Parametrizacion por ejercicio: series, rango de reps, descanso (compuesto 90-120 s, aislamiento 60 s)
y carga sugerida inicial (ver suggest_load)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Exercise, Plan, PlanDay, PlanExercise, RoutineTemplate, TemplateDay,
                      TemplateExercise)

GOALS = ("HYPERTROPHY", "STRENGTH", "CONDITIONING")
LEVELS = ("BEGINNER", "INTERMEDIATE", "ADVANCED")
DAYS_RANGE = (2, 3, 4, 5, 6)
UPPER_BODY = {"CHEST", "BACK", "SHOULDERS", "BICEPS", "TRICEPS"}
WORK_SECONDS_PER_SET = 45          # para estimar duracion = sets * (45 s + descanso)

# ---------------------------------------------------------------- parametrizacion
LEVEL_FACTOR = {"BEGINNER": 0.6, "INTERMEDIATE": 1.0, "ADVANCED": 1.3}
GOAL_FACTOR = {"HYPERTROPHY": 1.0, "STRENGTH": 1.15, "CONDITIONING": 0.75}
FEMALE_FACTOR = {"upper": 0.65, "lower": 0.8}
EXERCISES_PER_DAY = {"BEGINNER": 4, "INTERMEDIATE": 5, "ADVANCED": 6}
MAX_EXERCISES_PER_DAY = 12


def default_params(goal: str, level: str, category: str, index: int = 2) -> tuple[int, int, int, int]:
    """(series, rep_min, rep_max, descanso_s) sin restricciones. index = posicion en el dia (0 = primero)."""
    comp = category == "COMPOUND"
    if level == "BEGINNER":
        sets = 3 if comp else 2
    elif level == "INTERMEDIATE":
        sets = (4 if index < 2 else 3) if comp else 3
    else:
        sets = (5 if (goal == "STRENGTH" and index == 0) else 4) if comp else 3
    if goal == "HYPERTROPHY":
        reps = (8, 12) if comp else (10, 15)
    elif goal == "STRENGTH":
        reps = ((6, 8) if level == "BEGINNER" else (4, 6)) if comp else (8, 10)
    else:  # CONDITIONING
        reps = (12, 15) if comp else (15, 20)
    rest = (120 if goal == "STRENGTH" else 90) if comp else 60
    return sets, reps[0], reps[1], rest


def _round_load(x: float) -> float:
    return max(2.5, round(x / 2.5) * 2.5)


def suggest_load(ex: Exercise, body_weight: float, sex: str, goal: str, level: str) -> float | None:
    """Carga inicial = peso corporal x ratio del ejercicio x nivel x objetivo x sexo, a pasos de 2.5 kg.
    Estimacion de partida (None para ejercicios de peso corporal); el usuario la ajusta."""
    if ex.load_ratio is None:
        return None
    f = LEVEL_FACTOR[level] * GOAL_FACTOR[goal]
    if sex == "FEMALE":
        f *= FEMALE_FACTOR["upper" if ex.muscle_group in UPPER_BODY else "lower"]
    return _round_load(body_weight * ex.load_ratio * f)


def estimated_minutes(items) -> int:
    secs = sum(i.sets * (WORK_SECONDS_PER_SET + i.rest_seconds) for i in items)
    return round(secs / 60)


# ---------------------------------------------------------------- plantillas maestras
# slot = (ejercicio, alternativa_para_principiante | None); orden = prioridad (compuestos primero)
SLOTS = {
    "PUSH": ("Empuje", "Pecho / Hombro / Tríceps", [
        ("Press de banca con barra", "Press de pecho en máquina"), ("Press militar con barra", "Press de hombros con mancuernas"),
        ("Press inclinado con mancuernas", None), ("Elevaciones laterales", None),
        ("Extensión de tríceps en polea", None), ("Aperturas en polea", None)]),
    "PULL": ("Tirón", "Espalda / Bíceps", [
        ("Jalón al pecho", None), ("Remo con barra", "Remo en polea baja"), ("Remo con mancuerna a una mano", None),
        ("Face pull", None), ("Curl de bíceps con barra", None), ("Curl martillo", None)]),
    "LEGS": ("Pierna", "Cuádriceps / Isquios / Gemelos", [
        ("Sentadilla con barra", "Sentadilla goblet"), ("Peso muerto rumano", None), ("Prensa de piernas", None),
        ("Curl femoral", None), ("Elevación de gemelos de pie", None), ("Extensión de cuádriceps", None)]),
    "UPPER": ("Torso", "Pecho / Espalda / Hombro / Brazos", [
        ("Press de banca con barra", "Press de pecho en máquina"), ("Remo con barra", "Remo en polea baja"),
        ("Press de hombros con mancuernas", None), ("Jalón al pecho", None),
        ("Curl de bíceps con barra", None), ("Extensión de tríceps en polea", None)]),
    "LOWER": ("Pierna", "Cuádriceps / Isquios / Glúteo / Gemelos", [
        ("Sentadilla con barra", "Sentadilla goblet"), ("Peso muerto rumano", None), ("Hip thrust con barra", None),
        ("Curl femoral", None), ("Elevación de gemelos de pie", None), ("Crunch abdominal", None)]),
    "FULL_A": ("Cuerpo completo A", "Pierna / Empuje / Tirón", [
        ("Sentadilla con barra", "Sentadilla goblet"), ("Press de banca con barra", "Press de pecho en máquina"),
        ("Jalón al pecho", None), ("Elevaciones laterales", None), ("Curl de bíceps con barra", None), ("Crunch abdominal", None)]),
    "FULL_B": ("Cuerpo completo B", "Bisagra / Empuje vertical / Tirón", [
        ("Peso muerto rumano", None), ("Press militar con barra", "Press de hombros con mancuernas"),
        ("Remo con barra", "Remo en polea baja"), ("Prensa de piernas", None),
        ("Extensión de tríceps en polea", None), ("Elevación de gemelos de pie", None)]),
}
SPLIT_BY_DAYS = {
    2: ["FULL_A", "FULL_B"],
    3: ["PUSH", "PULL", "LEGS"],
    4: ["UPPER", "LOWER", "UPPER", "LOWER"],
    5: ["PUSH", "PULL", "LEGS", "UPPER", "LOWER"],
    6: ["PUSH", "PULL", "LEGS", "PUSH", "PULL", "LEGS"],
}
LABEL_GOAL = {"HYPERTROPHY": "Hipertrofia", "STRENGTH": "Fuerza", "CONDITIONING": "Acondicionamiento"}
LABEL_LEVEL = {"BEGINNER": "Principiante", "INTERMEDIATE": "Intermedio", "ADVANCED": "Avanzado"}


def seed_templates(db: Session) -> int:
    """Genera las 45 plantillas maestras (5 frecuencias x 3 objetivos x 3 niveles). Idempotente."""
    if db.scalar(select(RoutineTemplate.id).limit(1)):
        return 0
    by_name = {e.name: e for e in db.scalars(select(Exercise))}
    n = 0
    for days in DAYS_RANGE:
        for goal in GOALS:
            for level in LEVELS:
                t = RoutineTemplate(code=f"D{days}-{goal}-{level}", days_per_week=days, goal=goal, level=level,
                                    name=f"{LABEL_GOAL[goal]} · {LABEL_LEVEL[level]} · {days} días")
                for i, split in enumerate(SPLIT_BY_DAYS[days], start=1):
                    title, focus, slots = SLOTS[split]
                    day = TemplateDay(day_index=i, name=f"Día {i}: {title}", focus=focus)
                    for pos, (main, beginner_alt) in enumerate(slots[:EXERCISES_PER_DAY[level]]):
                        ex = by_name[beginner_alt if (level == "BEGINNER" and beginner_alt) else main]
                        s, rmin, rmax, rest = default_params(goal, level, ex.category, pos)
                        day.exercises.append(TemplateExercise(exercise_id=ex.id, position=pos, sets=s,
                                                              rep_min=rmin, rep_max=rmax, rest_seconds=rest))
                    t.days.append(day)
                db.add(t)
                n += 1
    db.commit()
    return n


def match_template(db: Session, days: int, goal: str, level: str) -> RoutineTemplate | None:
    """Motor de asignacion: query filtrada por dias + objetivo + nivel."""
    return db.scalar(select(RoutineTemplate).where(
        RoutineTemplate.days_per_week == days, RoutineTemplate.goal == goal, RoutineTemplate.level == level))


# ---------------------------------------------------------------- instanciar el plan del usuario
def _plan_exercise_from_template(te: TemplateExercise, plan: Plan, position: int) -> PlanExercise:
    return PlanExercise(exercise_id=te.exercise_id, position=position, sets=te.sets, rep_min=te.rep_min,
                        rep_max=te.rep_max, rest_seconds=te.rest_seconds, origin="TEMPLATE",
                        suggested_load_kg=suggest_load(te.exercise, plan.body_weight_kg, plan.sex, plan.goal, plan.level))


def instantiate_plan(db: Session, user_id: str, profile, template: RoutineTemplate) -> Plan:
    plan = Plan(user_id=user_id, template_id=template.id, name=template.name, days_per_week=template.days_per_week,
                goal=template.goal, level=template.level, body_weight_kg=profile.weight_kg, sex=profile.sex)
    for td in template.days:
        day = PlanDay(template_day_id=td.id, day_index=td.day_index, name=td.name, focus=td.focus)
        for te in td.exercises:
            day.exercises.append(_plan_exercise_from_template(te, plan, te.position))
        plan.days.append(day)
    db.add(plan)
    return plan


def reset_day(db: Session, plan: Plan, day: PlanDay) -> None:
    """Vuelve el dia al plan recomendado (plantilla), conservando el contexto del plan (peso, restriccion)."""
    td = db.get(TemplateDay, day.template_day_id) if day.template_day_id else None
    if td is None:
        return
    day.exercises.clear()
    db.flush()
    for te in td.exercises:
        day.exercises.append(_plan_exercise_from_template(te, plan, te.position))
    day.is_customized = False


def new_custom_exercise(plan: Plan, ex: Exercise, position: int, sets: int | None = None) -> PlanExercise:
    s, rmin, rmax, rest = default_params(plan.goal, plan.level, ex.category)
    return PlanExercise(exercise_id=ex.id, position=position, sets=sets or s, rep_min=rmin, rep_max=rmax,
                        rest_seconds=rest, origin="CUSTOM",
                        suggested_load_kg=suggest_load(ex, plan.body_weight_kg, plan.sex, plan.goal, plan.level))


def plan_warnings(plan: Plan) -> list[str]:
    w = []
    if plan.level == "BEGINNER" and plan.days_per_week >= 5:
        w.append("Entrenar 5 o más días siendo principiante exige buena recuperación; considera empezar con 3 o 4 días.")
    return w
