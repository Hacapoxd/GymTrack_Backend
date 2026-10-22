import pytest

from .conftest import profile_body


def test_profile_not_found_before_creation(client, user):
    assert client.get("/v1/athletes/me", headers=user[1]).status_code == 404


def test_create_profile_computes_age_and_bmi(client, user):
    r = client.post("/v1/athletes/me", json=profile_body(), headers=user[1])
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["bmi"] == 23.7 and d["age"] >= 27
    assert "bmiCategory" not in d and "parq" not in d          # sin clasificación de salud
    assert client.post("/v1/athletes/me", json=profile_body(), headers=user[1]).status_code == 409


@pytest.mark.parametrize("over", [{"weightKg": 20}, {"heightCm": 300}, {"daysPerWeek": 1}, {"daysPerWeek": 7},
                                  {"birthDate": "2015-01-01"}, {"goal": "OTRO"}, {"sex": "X"}, {"level": "PRO"}])
def test_profile_validation(client, user, over):
    r = client.post("/v1/athletes/me", json=profile_body(**over), headers=user[1])
    assert r.status_code == 422 and r.json()["code"] == "GT-4220"


def test_no_health_endpoints_exist(client, user):
    assert client.get("/v1/parq/questions").status_code == 404
    assert client.post("/v1/athletes/me/parq", json={}, headers=user[1]).status_code in (404, 405)


def test_patch_updates_weight_days_and_logs_weight(client, user):
    client.post("/v1/athletes/me", json=profile_body(), headers=user[1])
    r = client.patch("/v1/athletes/me", json={"weightKg": 72.5, "daysPerWeek": 4}, headers=user[1])
    assert r.status_code == 200 and r.json()["weightKg"] == 72.5 and r.json()["daysPerWeek"] == 4
    w = client.get("/v1/athletes/me/weights", headers=user[1]).json()
    assert [x["weightKg"] for x in w] == [72.5, 70]
    assert client.patch("/v1/athletes/me", json={}, headers=user[1]).status_code == 422
    r = client.patch("/v1/athletes/me", json={"weightKg": 72.5, "sex": "FEMALE"}, headers=user[1])
    assert r.json()["sex"] == "MALE"          # los datos base no se editan por PATCH
