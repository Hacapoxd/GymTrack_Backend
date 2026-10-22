import pytest

from .conftest import profile_body, register_and_login


def make_user(client, **over):
    email, h = register_and_login(client)
    assert client.post("/v1/athletes/me", json=profile_body(**over), headers=h).status_code == 201
    return h


def ex_id(client, h, name):
    return next(e["id"] for e in client.get("/v1/exercises", params={"q": name}, headers=h).json() if e["name"] == name)


def active(client, h):
    return client.get("/v1/plans/active", headers=h).json()


def test_no_plan_before_generation(client):
    h = make_user(client)
    assert client.get("/v1/plans/active", headers=h).status_code == 404


def test_templates_cover_every_filter_combination(client):
    for days in (2, 3, 4, 5, 6):
        for goal in ("HYPERTROPHY", "STRENGTH", "CONDITIONING"):
            for level in ("BEGINNER", "INTERMEDIATE", "ADVANCED"):
                h = make_user(client, daysPerWeek=days, goal=goal, level=level)
                p = client.get("/v1/plans/preview", headers=h)
                assert p.status_code == 200 and p.json()["code"] == f"D{days}-{goal}-{level}"
                assert len(p.json()["days"]) == days


def test_generate_plan_matches_filters_and_parameters(client):
    h = make_user(client, daysPerWeek=3, goal="HYPERTROPHY", level="INTERMEDIATE")
    r = client.post("/v1/plans", json={}, headers=h)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert [d["name"] for d in plan["days"]] == ["Día 1: Empuje", "Día 2: Tirón", "Día 3: Pierna"]
    assert plan["days"][0]["focus"] == "Pecho / Hombro / Tríceps"
    push = plan["days"][0]["exercises"]
    assert len(push) == 5 and push[0]["exercise"]["name"] == "Press de banca con barra"
    bench = push[0]
    assert (bench["sets"], bench["repMin"], bench["repMax"], bench["restSeconds"]) == (4, 8, 12, 90)
    assert bench["suggestedLoadKg"] == 52.5          # 70 kg x 0.75 x 1.0 x 1.0
    for d in plan["days"]:
        for e in d["exercises"]:
            if e["exercise"]["category"] == "COMPOUND":
                assert 90 <= e["restSeconds"] <= 120
            else:
                assert e["restSeconds"] == 60
    assert plan["outdated"] is False and "restrictedIntensity" not in plan and plan["warnings"] == []
    assert plan["days"][0]["estimatedMinutes"] > 0 and plan["days"][0]["totalSets"] == sum(e["sets"] for e in push)


def test_level_and_goal_change_the_assignment(client):
    h = make_user(client, goal="STRENGTH", level="BEGINNER")
    plan = client.post("/v1/plans", json={}, headers=h).json()
    first = plan["days"][0]["exercises"]
    assert len(first) == 4 and first[0]["exercise"]["name"] == "Press de pecho en máquina"   # principiante: máquina
    assert (first[0]["repMin"], first[0]["repMax"], first[0]["restSeconds"]) == (6, 8, 120)
    h2 = make_user(client, goal="STRENGTH", level="ADVANCED")
    p2 = client.post("/v1/plans", json={}, headers=h2).json()
    assert len(p2["days"][0]["exercises"]) == 6 and p2["days"][0]["exercises"][0]["sets"] == 5
    assert (p2["days"][0]["exercises"][0]["repMin"], p2["days"][0]["exercises"][0]["repMax"]) == (4, 6)


def test_sex_changes_suggested_load(client):
    hm = make_user(client, sex="MALE")
    hf = make_user(client, sex="FEMALE")
    m = client.post("/v1/plans", json={}, headers=hm).json()["days"][0]["exercises"][0]["suggestedLoadKg"]
    f = client.post("/v1/plans", json={}, headers=hf).json()["days"][0]["exercises"][0]["suggestedLoadKg"]
    assert f < m


def test_bodyweight_exercise_has_no_suggested_load(client):
    h = make_user(client)
    client.post("/v1/plans", json={}, headers=h)
    day = active(client, h)["days"][0]
    flex = ex_id(client, h, "Flexiones")
    r = client.post(f"/v1/plans/active/days/{day['id']}/exercises", json={"exerciseId": flex}, headers=h)
    assert r.status_code == 201 and r.json()["day"]["exercises"][-1]["suggestedLoadKg"] is None


def test_replace_requires_confirmation_and_keeps_history(client):
    h = make_user(client)
    first = client.post("/v1/plans", json={}, headers=h).json()
    r = client.post("/v1/plans", json={}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "GT-4090"
    second = client.post("/v1/plans", json={"replaceActive": True}, headers=h)
    assert second.status_code == 201 and second.json()["id"] != first["id"]
    hist = client.get("/v1/plans", headers=h).json()
    assert {p["status"] for p in hist} == {"ACTIVE", "ARCHIVED"} and len(hist) == 2
    assert client.get(f"/v1/plans/{first['id']}", headers=h).json()["status"] == "ARCHIVED"


def test_outdated_flag_after_profile_change(client):
    h = make_user(client)
    client.post("/v1/plans", json={}, headers=h)
    client.patch("/v1/athletes/me", json={"daysPerWeek": 4, "goal": "STRENGTH"}, headers=h)
    p = active(client, h)
    assert p["outdated"] and len(p["outdatedReasons"]) == 2
    client.post("/v1/plans", json={"replaceActive": True}, headers=h)
    assert active(client, h)["outdated"] is False


def test_edit_sets_reps_rest_load_note(client):
    h = make_user(client)
    client.post("/v1/plans", json={}, headers=h)
    item = active(client, h)["days"][0]["exercises"][0]
    r = client.patch(f"/v1/plans/active/exercises/{item['id']}",
                     json={"sets": 5, "repMin": 6, "repMax": 10, "restSeconds": 100, "suggestedLoadKg": 60, "note": "banco 3"}, headers=h)
    assert r.status_code == 200
    e = r.json()["day"]["exercises"][0]
    assert (e["sets"], e["repMin"], e["repMax"], e["restSeconds"], e["suggestedLoadKg"], e["note"]) == (5, 6, 10, 100, 60, "banco 3")
    assert r.json()["day"]["isCustomized"] is True
    # limpiar nota y carga con null explícito
    r = client.patch(f"/v1/plans/active/exercises/{item['id']}", json={"note": None, "suggestedLoadKg": None}, headers=h)
    assert r.json()["day"]["exercises"][0]["note"] is None and r.json()["day"]["exercises"][0]["suggestedLoadKg"] is None
    for bad in ({"sets": 0}, {"sets": 11}, {"repMin": 12, "repMax": 8}, {"restSeconds": -1}, {"suggestedLoadKg": -5}):
        assert client.patch(f"/v1/plans/active/exercises/{item['id']}", json=bad, headers=h).status_code == 422
    # repMax menor que el repMin guardado
    assert client.patch(f"/v1/plans/active/exercises/{item['id']}", json={"repMax": 3}, headers=h).status_code == 422
    r = client.patch(f"/v1/plans/active/exercises/{item['id']}", json={"repMin": 12, "repMax": 8}, headers=h)
    assert r.json()["details"][0] == {"field": "", "issue": "repMax no puede ser menor que repMin."}


def test_replace_exercise_free_with_warning_on_other_muscle(client):
    h = make_user(client)
    client.post("/v1/plans", json={}, headers=h)
    item = active(client, h)["days"][0]["exercises"][0]          # press de banca
    alts = client.get(f"/v1/exercises/{item['exercise']['id']}/alternatives", headers=h).json()
    assert alts and all(a["muscleGroup"] == "CHEST" for a in alts) and alts[0]["movementPattern"] == "HORIZONTAL_PUSH"
    mancuernas = ex_id(client, h, "Press de banca con mancuernas")
    r = client.post(f"/v1/plans/active/exercises/{item['id']}/replace", json={"exerciseId": mancuernas}, headers=h)
    assert r.status_code == 200 and r.json()["warnings"] == []
    e = r.json()["day"]["exercises"][0]
    assert e["exercise"]["name"] == "Press de banca con mancuernas" and e["origin"] == "SWAPPED" and e["sets"] == 4
    otro_grupo = ex_id(client, h, "Sentadilla con barra")
    r = client.post(f"/v1/plans/active/exercises/{item['id']}/replace", json={"exerciseId": otro_grupo}, headers=h)
    assert r.status_code == 200 and len(r.json()["warnings"]) == 1
    dup = ex_id(client, h, "Press militar con barra")                    # ya está en el día
    assert client.post(f"/v1/plans/active/exercises/{item['id']}/replace", json={"exerciseId": dup}, headers=h).status_code == 409
    assert client.post(f"/v1/plans/active/exercises/{item['id']}/replace", json={"exerciseId": "no-existe"}, headers=h).status_code == 404


def test_add_remove_reorder_and_reset(client):
    h = make_user(client)
    client.post("/v1/plans", json={}, headers=h)
    day = active(client, h)["days"][0]
    original = [e["id"] for e in day["exercises"]]
    # agregar en posición 1
    fly = ex_id(client, h, "Flexiones")
    r = client.post(f"/v1/plans/active/days/{day['id']}/exercises", json={"exerciseId": fly, "position": 1, "sets": 2}, headers=h)
    exs = r.json()["day"]["exercises"]
    assert len(exs) == 6 and exs[1]["exercise"]["name"] == "Flexiones" and exs[1]["sets"] == 2 and exs[1]["origin"] == "CUSTOM"
    assert [e["position"] for e in exs] == list(range(6))
    assert client.post(f"/v1/plans/active/days/{day['id']}/exercises", json={"exerciseId": fly}, headers=h).status_code == 409
    # reordenar (invertir)
    ids = [e["id"] for e in exs][::-1]
    r = client.put(f"/v1/plans/active/days/{day['id']}/order", json={"exerciseIds": ids}, headers=h)
    assert [e["id"] for e in r.json()["day"]["exercises"]] == ids
    assert client.put(f"/v1/plans/active/days/{day['id']}/order", json={"exerciseIds": ids[:-1]}, headers=h).status_code == 422
    # quitar uno y comprobar renumeración
    r = client.delete(f"/v1/plans/active/exercises/{ids[0]}", headers=h)
    assert len(r.json()["day"]["exercises"]) == 5 and [e["position"] for e in r.json()["day"]["exercises"]] == list(range(5))
    # volver al plan recomendado
    r = client.post(f"/v1/plans/active/days/{day['id']}/reset", headers=h)
    d = r.json()["day"]
    assert d["isCustomized"] is False and len(d["exercises"]) == 5
    assert [e["exercise"]["name"] for e in d["exercises"]] == [e["exercise"]["name"] for e in day["exercises"]]


def test_max_exercises_per_day(client):
    h = make_user(client, level="ADVANCED")
    client.post("/v1/plans", json={}, headers=h)
    day = active(client, h)["days"][0]
    names = [e["name"] for e in client.get("/v1/exercises", headers=h).json()]
    present = {e["exercise"]["name"] for e in day["exercises"]}
    codes = 0
    for e in client.get("/v1/exercises", headers=h).json():
        if e["name"] in present:
            continue
        r = client.post(f"/v1/plans/active/days/{day['id']}/exercises", json={"exerciseId": e["id"]}, headers=h)
        if r.status_code == 422:
            codes += 1
            break
    assert codes == 1


def test_cannot_touch_other_users_plan(client):
    h1, h2 = make_user(client), make_user(client)
    client.post("/v1/plans", json={}, headers=h1)
    client.post("/v1/plans", json={}, headers=h2)
    item = active(client, h1)["days"][0]["exercises"][0]["id"]
    day = active(client, h1)["days"][0]["id"]
    assert client.delete(f"/v1/plans/active/exercises/{item}", headers=h2).status_code == 404
    assert client.post(f"/v1/plans/active/days/{day}/reset", headers=h2).status_code == 404
    pid = active(client, h1)["id"]
    assert client.get(f"/v1/plans/{pid}", headers=h2).status_code == 404


def test_exercise_catalog_filters_and_ficha(client):
    h = make_user(client)
    legs = client.get("/v1/exercises", params={"muscleGroup": "quads"}, headers=h).json()
    assert legs and all(e["muscleGroup"] == "QUADS" for e in legs)
    ficha = client.get(f"/v1/exercises/{legs[0]['id']}", headers=h).json()
    assert ficha["technique"] and ficha["commonErrors"] and "mediaUrl" in ficha
    assert client.get("/v1/exercises/inexistente", headers=h).status_code == 404


def test_admin_manages_catalog_and_media(client):
    _, user_h = register_and_login(client)
    body = {"name": "Press Arnold", "muscleGroup": "SHOULDERS", "movementPattern": "VERTICAL_PUSH", "category": "COMPOUND",
            "equipment": "Mancuernas", "technique": ["Rota las palmas al subir."], "commonErrors": ["Arquear la espalda."]}
    assert client.post("/v1/admin/exercises", json=body, headers=user_h).status_code == 403
    t = client.post("/v1/auth/login", json={"email": "admin@gymtrack.test", "password": "Admin12345"}).json()
    ah = {"Authorization": f"Bearer {t['accessToken']}"}
    r = client.post("/v1/admin/exercises", json=body, headers=ah)
    assert r.status_code == 201 and client.post("/v1/admin/exercises", json=body, headers=ah).status_code == 409
    eid = r.json()["id"]
    r = client.patch(f"/v1/admin/exercises/{eid}", json={"mediaUrl": "https://cdn.example.com/arnold.gif", "mediaType": "GIF"}, headers=ah)
    assert r.status_code == 200 and r.json()["mediaType"] == "GIF"
    assert client.patch(f"/v1/admin/exercises/{eid}", json={"mediaUrl": "http://inseguro.com/a.gif"}, headers=ah).status_code == 422
    client.patch(f"/v1/admin/exercises/{eid}", json={"active": False}, headers=ah)
    assert eid not in [e["id"] for e in client.get("/v1/exercises", headers=user_h).json()]
    # el admin no tiene perfil de salud ni accede a los datos de otros
    assert client.get("/v1/athletes/me", headers=ah).status_code == 404


def test_plan_requires_profile(client):
    _, h = register_and_login(client)
    assert client.post("/v1/plans", json={}, headers=h).status_code == 404


def test_lower_intensity_without_ai(client):
    h = make_user(client)
    client.post("/v1/plans", json={}, headers=h)
    before = active(client, h)["days"][0]
    r = client.post("/v1/plans/active/intensity", json={"direction": "LOWER", "dayId": before["id"]}, headers=h)
    assert r.status_code == 200 and len(r.json()["days"]) == 1
    after = r.json()["days"][0]
    for b, a in zip(before["exercises"], after["exercises"]):
        assert a["sets"] == max(2, b["sets"] - 1)
        if b["suggestedLoadKg"] is not None:
            assert a["suggestedLoadKg"] <= b["suggestedLoadKg"]
    assert after["isCustomized"] is True
    # sin dayId baja todos los días; nunca baja de 2 series
    for _ in range(4):
        r = client.post("/v1/plans/active/intensity", json={}, headers=h)
    assert len(r.json()["days"]) == 3 and all(e["sets"] >= 2 for d in r.json()["days"] for e in d["exercises"])
    assert client.post("/v1/plans/active/intensity", json={"dayId": "no-existe"}, headers=h).status_code == 404
