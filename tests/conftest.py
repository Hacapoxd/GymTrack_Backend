import os

# Por defecto BD SQLite en memoria. Para probar contra PostgreSQL: TEST_DATABASE_URL=postgresql://...
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["ADMIN_EMAIL"] = "admin@gymtrack.test"
os.environ["ADMIN_PASSWORD"] = "Admin12345"
os.environ["AI_API_KEY"] = ""                       # vacío y definido: ni un .env puede activar la IA real en las pruebas

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


_n = {"i": 0}


def register_and_login(client, password="Secreta123"):
    _n["i"] += 1
    email = f"user{_n['i']}@test.com"
    r = client.post("/v1/auth/register", json={"firstName": "Alex", "lastName": "Morgan", "email": email,
                    "password": password, "isAdult": True, "acceptTerms": True, "acceptDisclaimer": True})
    assert r.status_code == 201, r.text
    t = client.post("/v1/auth/login", json={"email": email, "password": password}).json()
    return email, {"Authorization": f"Bearer {t['accessToken']}"}


@pytest.fixture()
def user(client):
    return register_and_login(client)


def profile_body(**over):
    b = {"birthDate": "1998-03-14", "sex": "MALE", "weightKg": 70, "heightCm": 172, "daysPerWeek": 3,
         "goal": "HYPERTROPHY", "level": "INTERMEDIATE"}
    b.update(over)
    return b
