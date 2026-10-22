"""GymTrack API: Modulo 1 (Perfil) + Modulo 3 (Plan, plantillas e IA asistida)."""
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, database, errors, models  # noqa: F401  (models registra las tablas)
from .routers import admin, ai, athletes, auth, exercises, plans
from .security import decode_access_token
from .seed import seed_all


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.Base.metadata.create_all(database.engine)
    with database.SessionLocal() as db:
        seed_all(db)
    yield


app = FastAPI(title="GymTrack API", version="0.1.0", lifespan=lifespan,
              description="Módulo 1 (Perfil) y Módulo 3 (Plan, plantillas e IA asistida por token). "
                          "GymTrack no cubre salud, nutrición ni seguimiento médico.")
errors.install(app)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"],
                   allow_headers=["Authorization", "Content-Type"], max_age=600)

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Ventana deslizante en memoria (1 proceso). Para varios procesos usar Redis."""
    if request.method == "OPTIONS" or not request.url.path.startswith("/v1"):
        return await call_next(request)
    key = request.client.host if request.client else "anon"
    auth_h = request.headers.get("authorization", "")
    if auth_h.lower().startswith("bearer "):
        try:
            key = decode_access_token(auth_h[7:])["sub"]
        except jwt.PyJWTError:
            pass
    now, q = time.monotonic(), _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MINUTE:
        return JSONResponse(errors.body(429, "Límite de solicitudes excedido."), status_code=429,
                            headers={"Retry-After": "60"})
    q.append(now)
    return await call_next(request)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


for r in (auth.router, athletes.router, exercises.router, plans.router, ai.router, admin.router):
    app.include_router(r, prefix="/v1")
