from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import Exercise, User
from .security import hash_password
from .services.catalog_data import EXERCISES
from .services.planner import seed_templates


def seed_catalog(db: Session) -> int:
    if db.scalar(select(Exercise.id).limit(1)):
        return 0
    for i, (name, group, sec, pattern, cat, equip, ratio, tech, errs) in enumerate(EXERCISES):
        db.add(Exercise(name=name, muscle_group=group, secondary_muscles=sec, movement_pattern=pattern,
                        category=cat, equipment=equip, load_ratio=ratio, technique=tech, common_errors=errs,
                        sort_order=i))
    db.commit()
    return len(EXERCISES)


def ensure_admin(db: Session) -> None:
    if config.ADMIN_EMAIL and config.ADMIN_PASSWORD:
        email = config.ADMIN_EMAIL.strip().lower()
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, password_hash=hash_password(config.ADMIN_PASSWORD),
                        first_name="Admin", last_name="GymTrack", role="ADMIN"))
            db.commit()


def seed_all(db: Session) -> None:
    seed_catalog(db)
    seed_templates(db)
    ensure_admin(db)
