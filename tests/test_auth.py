from .conftest import register_and_login


def test_register_requires_consents(client):
    r = client.post("/v1/auth/register", json={"firstName": "A", "lastName": "B", "email": "c@d.com",
                    "password": "Secreta123", "isAdult": True, "acceptTerms": True, "acceptDisclaimer": False})
    assert r.status_code == 422 and r.json()["code"] == "GT-4220"


def test_weak_password_and_duplicate_email(client):
    base = {"firstName": "A", "lastName": "B", "email": "dup@d.com", "isAdult": True, "acceptTerms": True, "acceptDisclaimer": True}
    assert client.post("/v1/auth/register", json={**base, "password": "corta1"}).status_code == 422
    assert client.post("/v1/auth/register", json={**base, "password": "soloLetrasaa"}).status_code == 422
    assert client.post("/v1/auth/register", json={**base, "password": "Secreta123"}).status_code == 201
    assert client.post("/v1/auth/register", json={**base, "password": "Secreta123"}).status_code == 409


def test_login_lockout_after_5_failures(client):
    email, _ = register_and_login(client)
    for _ in range(5):
        r = client.post("/v1/auth/login", json={"email": email, "password": "mala"})
        assert r.status_code == 401
    # incluso con la clave correcta queda bloqueado temporalmente (mensaje genérico)
    r = client.post("/v1/auth/login", json={"email": email, "password": "Secreta123"})
    assert r.status_code == 401


def test_refresh_rotation(client):
    email, _ = register_and_login(client)
    t = client.post("/v1/auth/login", json={"email": email, "password": "Secreta123"}).json()
    r1 = client.post("/v1/auth/refresh", json={"refreshToken": t["refreshToken"]})
    assert r1.status_code == 200
    assert client.post("/v1/auth/refresh", json={"refreshToken": t["refreshToken"]}).status_code == 401  # ya usado


def test_protected_routes_need_token(client):
    r = client.get("/v1/athletes/me")
    assert r.status_code == 401 and r.json()["code"] == "GT-4010"
    assert client.get("/v1/athletes/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_malformed_json_is_400(client):
    r = client.post("/v1/auth/login", content="{no es json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["code"] == "GT-4000"
