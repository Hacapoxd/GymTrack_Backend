"""Errores con el formato del SRS 2.3.2: {code, message, details}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CODES = {400: "GT-4000", 401: "GT-4010", 403: "GT-4030", 404: "GT-4040",
         409: "GT-4090", 415: "GT-4150", 422: "GT-4220", 429: "GT-4290", 503: "GT-5030"}


class ApiError(Exception):
    def __init__(self, status: int, message: str, details: list | None = None):
        self.status, self.message, self.details = status, message, details or []


def body(status: int, message: str, details: list | None = None) -> dict:
    return {"code": CODES.get(status, "GT-5000"), "message": message, "details": details or []}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return JSONResponse(body(e.status, e.message, e.details), status_code=e.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        return JSONResponse(body(e.status_code, str(e.detail)), status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, e: RequestValidationError):
        errs = e.errors()
        details = [{"field": ".".join(str(x) for x in err["loc"][1:]),   # vacío si el error es del objeto completo
                    "issue": err["msg"].removeprefix("Value error, ")} for err in errs]
        if any(err["type"] == "json_invalid" for err in errs):
            return JSONResponse(body(400, "Solicitud mal formada.", details), status_code=400)
        return JSONResponse(body(422, "Dato fuera de rango o incumple una regla de negocio.", details), status_code=422)
