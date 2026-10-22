import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .errors import ApiError
from .models import User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise ApiError(401, "Token ausente, invalido o vencido.")
    try:
        data = decode_access_token(cred.credentials)
    except jwt.PyJWTError:
        raise ApiError(401, "Token ausente, invalido o vencido.")
    user = db.get(User, data["sub"])
    if user is None:
        raise ApiError(401, "Token ausente, invalido o vencido.")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        raise ApiError(403, "Se requiere rol de administrador.")
    return user


def get_llm():
    """Cliente de IA (o None si esta apagada). Las pruebas lo reemplazan con un falso."""
    from .services import llm
    return llm.get_client()
