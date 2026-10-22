from datetime import date


def age_of(birth: date, today: date | None = None) -> int:
    t = today or date.today()
    return t.year - birth.year - ((t.month, t.day) < (birth.month, birth.day))


def bmi_of(weight_kg: float, height_cm: float) -> float:
    """IMC = peso / estatura^2. Es solo un dato de referencia; GymTrack no lo interpreta ni emite diagnosticos."""
    return round(weight_kg / ((height_cm / 100) ** 2), 1)
