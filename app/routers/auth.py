from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..deps import current_user
from ..errors import ApiError
from ..models import Consent, RefreshToken, User, utcnow
from ..schemas import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from ..security import (create_access_token, hash_password, hash_refresh, new_refresh_token,
                        verify_password)

router = APIRouter(prefix="/auth", tags=["Acceso"])
_DUMMY_HASH = hash_password("dummy-password-1")  # iguala tiempos cuando el correo no existe


def _issue(db: Session, user: User) -> TokenOut:
    raw, h = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=h, expires_at=utcnow() + timedelta(days=config.REFRESH_TOKEN_DAYS)))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role), refresh_token=raw,
                    expires_in=config.ACCESS_TOKEN_MINUTES * 60)


@router.post("/register", response_model=UserOut, status_code=201, summary="Crear cuenta (CU: registro)")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise ApiError(409, "Ese correo ya está registrado. Inicia sesión o recupera tu contraseña.")
    user = User(email=body.email, password_hash=hash_password(body.password),
                first_name=body.first_name.strip(), last_name=body.last_name.strip())
    db.add(user)
    db.flush()
    for kind in ("ADULT", "TERMS_PRIVACY", "DISCLAIMER"):
        db.add(Consent(user_id=user.id, kind=kind))
    db.commit()
    return user


@router.post("/login", response_model=TokenOut, summary="Iniciar sesión")
def login(body: LoginIn, db: Session = Depends(get_db)):
    generic = "Credenciales incorrectas o cuenta bloqueada temporalmente."
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        raise ApiError(401, generic)
    if user.locked_until and user.locked_until > utcnow():
        raise ApiError(401, generic)
    if not verify_password(body.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= config.MAX_FAILED_LOGINS:
            user.locked_until = utcnow() + timedelta(minutes=config.LOCKOUT_MINUTES)
            user.failed_attempts = 0
        db.commit()
        raise ApiError(401, generic)
    user.failed_attempts, user.locked_until = 0, None
    return _issue(db, user)


@router.post("/refresh", response_model=TokenOut, summary="Renovar tokens (rotación del refresh token)")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    tok = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh(body.refresh_token)))
    if tok is None or tok.revoked or tok.expires_at < utcnow():
        raise ApiError(401, "Token ausente, inválido o vencido.")
    tok.revoked = True
    user = db.get(User, tok.user_id)
    return _issue(db, user)


@router.get("/me", response_model=UserOut, summary="Usuario autenticado")
def me(user: User = Depends(current_user)):
    return user
