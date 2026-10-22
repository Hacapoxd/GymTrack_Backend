"""Pruebas de la IA asistida con un modelo FALSO: no se llama a ningún proveedor ni se gastan tokens."""
import json

import pytest

from app import config
from app.deps import get_llm
from app.main import app
from app.services.llm import LLMError, LLMResult
from .conftest import profile_body, register_and_login


class FakeLLM:
    provider, model = "fake", "fake-model"

    def __init__(self):
        self.calls, self.next = [], None

    def complete(self, system, user, max_tokens):
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        if isinstance(self.next, Exception):
            raise self.next
        text = self.next if isinstance(self.next, str) else json.dumps(self.next)
        return LLMResult(text, 1200, 300, "fake-model")


@pytest.fixture()
def fake():
    f = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: f
    yield f
    app.dependency_overrides.pop(get_llm, None)


def setup_plan(client, **over):
    email, h = register_and_login(client)
    client.post("/v1/athletes/me", json=profile_body(**over), headers=h)
    client.post("/v1/plans", json={}, headers=h)
    return email, h, client.get("/v1/plans/active", headers=h).json()


def propose(client, h, **body):
    return client.post("/v1/ai/proposals", json={"kind": "ADJUST", "intent": "LOWER_INTENSITY", **body}, headers=h)


def ex_id(client, h, name):
    return next(e["id"] for e in client.get("/v1/exercises", params={"q": name}, headers=h).json() if e["name"] == name)


def test_ai_is_off_without_token(client):
    _, h, _ = setup_plan(client)
    assert client.get("/v1/ai/status", headers=h).json()["enabled"] is False
    assert propose(client, h).status_code == 503
    # lo determinista sigue funcionando sin IA
    assert client.post("/v1/plans/active/intensity", json={}, headers=h).status_code == 200


def test_propose_does_not_change_plan_until_applied(client, fake):
    _, h, plan = setup_plan(client)
    bench = plan["days"][0]["exercises"][0]
    fake.next = {"summary": "Bajé una serie y un poco de carga.", "operations": [
        {"op": "UPDATE", "itemId": bench["id"], "sets": bench["sets"] - 1, "loadKg": bench["suggestedLoadKg"] - 5, "reason": "Descanso extra."}]}
    r = propose(client, h, message="esta semana tengo poco tiempo")
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["status"] == "PENDING" and p["inputTokens"] == 1200 and p["outputTokens"] == 300 and p["model"] == "fake-model"
    assert p["operations"][0]["description"].startswith("Press de banca con barra: series 4 → 3")
    still = client.get("/v1/plans/active", headers=h).json()["days"][0]["exercises"][0]
    assert still["sets"] == bench["sets"] and still["suggestedLoadKg"] == bench["suggestedLoadKg"]      # nada cambió
    a = client.post(f"/v1/ai/proposals/{p['id']}/apply", headers=h)
    assert a.status_code == 200, a.text
    e = a.json()["days"][0]["exercises"][0]
    assert e["sets"] == bench["sets"] - 1 and e["suggestedLoadKg"] == bench["suggestedLoadKg"] - 5
    assert a.json()["days"][0]["isCustomized"] is True and a.json()["proposal"]["status"] == "APPLIED"
    assert client.post(f"/v1/ai/proposals/{p['id']}/apply", headers=h).status_code == 409   # ya resuelta


def test_personalize_replace_and_add_mark_origin_ai(client, fake):
    _, h, plan = setup_plan(client)
    day = plan["days"][0]
    bench = day["exercises"][0]
    fake.next = {"summary": "Cambié el press y agregué flexiones.", "operations": [
        {"op": "REPLACE", "itemId": bench["id"], "exerciseId": ex_id(client, h, "Press de banca con mancuernas"), "reason": "Más cómodo."},
        {"op": "ADD", "dayId": day["id"], "exerciseId": ex_id(client, h, "Flexiones"), "sets": 2, "reason": "Extra de empuje."}]}
    p = client.post("/v1/ai/proposals", json={"kind": "PERSONALIZE"}, headers=h).json()
    assert [o["op"] for o in p["operations"]] == ["REPLACE", "ADD"]
    d = client.post(f"/v1/ai/proposals/{p['id']}/apply", headers=h).json()["days"][0]
    names = [x["exercise"]["name"] for x in d["exercises"]]
    assert names[0] == "Press de banca con mancuernas" and names[-1] == "Flexiones"
    assert d["exercises"][0]["origin"] == "AI" and d["exercises"][-1]["origin"] == "AI" and d["exercises"][-1]["sets"] == 2
    assert [x["position"] for x in d["exercises"]] == list(range(len(names)))


def test_invalid_operations_are_discarded(client, fake):
    _, h, plan = setup_plan(client)
    day = plan["days"][0]
    bench, press = day["exercises"][0], day["exercises"][1]
    fake.next = {"summary": "x", "operations": [
        {"op": "UPDATE", "itemId": "id-inventado", "sets": 2},                                                # id inexistente
        {"op": "UPDATE", "itemId": bench["id"], "sets": bench["sets"] + 1},                                   # sube con intención LOWER
        {"op": "UPDATE", "itemId": press["id"], "loadKg": 500},                                               # carga absurda
        {"op": "UPDATE", "itemId": press["id"], "sets": 10},                                                  # salto de series > 2
        {"op": "REPLACE", "itemId": bench["id"], "exerciseId": ex_id(client, h, "Sentadilla con barra")},     # otro grupo muscular
        {"op": "REMOVE", "itemId": bench["id"]},                                                              # no se quita con LOWER
        {"op": "ADD", "dayId": day["id"], "exerciseId": ex_id(client, h, "Flexiones")},                       # no se agrega con LOWER
        {"op": "BORRAR_TODO"}]}
    p = propose(client, h).json()
    assert p["operations"] == [] and p["status"] == "REJECTED" and len(p["discarded"]) == 8
    assert client.post(f"/v1/ai/proposals/{p['id']}/apply", headers=h).status_code == 409


def test_valid_ops_survive_next_to_invalid_ones(client, fake):
    _, h, plan = setup_plan(client)
    bench = plan["days"][0]["exercises"][0]
    fake.next = {"summary": "ok", "operations": [
        {"op": "UPDATE", "itemId": "inventado", "sets": 2},
        {"op": "UPDATE", "itemId": bench["id"], "restSeconds": 120}]}
    p = propose(client, h).json()
    assert len(p["operations"]) == 1 and len(p["discarded"]) == 1 and p["status"] == "PENDING"


def test_max_ten_ops_and_min_two_exercises_per_day(client, fake):
    _, h, plan = setup_plan(client)
    items = plan["days"][0]["exercises"]                        # 5 ejercicios
    fake.next = {"summary": "recorte", "operations": [{"op": "REMOVE", "itemId": i["id"]} for i in items]}
    p = client.post("/v1/ai/proposals", json={"kind": "ADJUST", "intent": "SHORTEN_SESSION", "maxMinutes": 30}, headers=h).json()
    assert len(p["operations"]) == 3 and len(p["discarded"]) == 2       # deja al menos 2 ejercicios
    fake.next = {"summary": "x", "operations": [{"op": "UPDATE", "itemId": items[0]["id"], "restSeconds": 60 + i} for i in range(12)]}
    p = client.post("/v1/ai/proposals", json={"kind": "PERSONALIZE"}, headers=h).json()
    assert len(p["operations"]) == 1                             # el mismo ejercicio solo se toca una vez
    assert any("máximo 10" in d for d in p["discarded"])


def test_shorten_session_warns_when_still_over_the_limit(client, fake):
    _, h, plan = setup_plan(client)
    it = plan["days"][0]["exercises"][-1]
    fake.next = {"summary": "Quité una serie.", "operations": [{"op": "UPDATE", "itemId": it["id"], "sets": it["sets"] - 1}]}
    r = client.post("/v1/ai/proposals", json={"kind": "ADJUST", "intent": "SHORTEN_SESSION", "maxMinutes": 20}, headers=h)
    assert "Aviso" in r.json()["summary"] and "20 min" in r.json()["summary"]
    assert client.post("/v1/ai/proposals", json={"kind": "ADJUST", "intent": "SHORTEN_SESSION"}, headers=h).status_code == 422
    assert client.post("/v1/ai/proposals", json={"kind": "ADJUST"}, headers=h).status_code == 422
    assert client.post("/v1/ai/proposals", json={"kind": "ADJUST", "intent": "FREE"}, headers=h).status_code == 422


@pytest.mark.parametrize("msg", ["me duele el hombro derecho", "qué dieta me recomiendas", "tomo pastillas para la presión arterial",
                                 "necesito un suplemento de proteína", "tengo una lesión en la rodilla"])
def test_health_and_nutrition_messages_never_reach_the_model(client, fake, msg):
    _, h, _ = setup_plan(client)
    r = client.post("/v1/ai/proposals", json={"kind": "ADJUST", "intent": "FREE", "message": msg}, headers=h)
    assert r.status_code == 422 and "no cubre" in r.json()["message"]
    assert fake.calls == []


def test_prompt_is_anonymous_and_bounded(client, fake):
    email, h, _ = setup_plan(client, weightKg=81.5, goal="STRENGTH")
    fake.next = {"summary": "ok", "operations": []}
    client.post("/v1/ai/proposals", json={"kind": "PERSONALIZE", "message": "quiero algo más variado"}, headers=h)
    call = fake.calls[0]
    assert email not in call["user"] and "Alex" not in call["user"] and "Morgan" not in call["user"]
    sent = json.loads(call["user"])
    assert sent["perfil"]["pesoKg"] == 81.5 and sent["perfil"]["objetivo"] == "STRENGTH"
    assert sent["solicitud"]["mensaje_usuario"] == "quiero algo más variado"
    assert call["max_tokens"] == config.AI_MAX_OUTPUT_TOKENS and "PROHIBIDO dar consejos médicos" in call["system"]
    assert len(sent["catalogo"]) >= 30 and "token" not in call["user"].lower()


def test_provider_failure_and_garbage_output(client, fake):
    _, h, _ = setup_plan(client)
    fake.next = LLMError("anthropic HTTP 401")
    r = propose(client, h)
    assert r.status_code == 503 and "401" not in r.text and r.json()["code"] == "GT-5030"
    assert client.get("/v1/ai/proposals", headers=h).json() == []        # nada se guardó
    fake.next = "esto no es json"
    p = propose(client, h).json()
    assert p["status"] == "REJECTED" and p["operations"] == [] and p["discarded"]
    fake.next = "```json\n" + json.dumps({"summary": "con cercas", "operations": []}) + "\n```"
    assert propose(client, h).json()["summary"] == "con cercas"          # tolera bloques de código


def test_daily_limit_and_usage(client, fake, monkeypatch):
    monkeypatch.setattr(config, "AI_DAILY_LIMIT", 2)
    _, h, _ = setup_plan(client)
    fake.next = {"summary": "ok", "operations": []}
    assert propose(client, h).status_code == 201 and propose(client, h).status_code == 201
    r = propose(client, h)
    assert r.status_code == 429 and r.json()["code"] == "GT-4290"
    s = client.get("/v1/ai/status", headers=h).json()
    assert s == {"enabled": True, "provider": "fake", "model": "fake-model", "dailyLimit": 2, "usedToday": 2, "tokensToday": 3000}


def test_apply_revalidates_against_the_current_plan(client, fake):
    _, h, plan = setup_plan(client)
    bench = plan["days"][0]["exercises"][0]
    fake.next = {"summary": "x", "operations": [{"op": "UPDATE", "itemId": bench["id"], "sets": 3}]}
    p = propose(client, h).json()
    # el usuario ya dejó ese ejercicio en 3 series antes de aplicar: la propuesta ya no cambia nada
    client.patch(f"/v1/plans/active/exercises/{bench['id']}", json={"sets": 3}, headers=h)
    assert client.post(f"/v1/ai/proposals/{p['id']}/apply", headers=h).status_code == 409
    # y si el plan se reemplaza, las propuestas viejas ya no son aplicables
    fake.next = {"summary": "x", "operations": [{"op": "UPDATE", "itemId": bench["id"], "restSeconds": 100}]}
    p2 = propose(client, h).json()
    client.post("/v1/plans", json={"replaceActive": True}, headers=h)
    assert client.post(f"/v1/ai/proposals/{p2['id']}/apply", headers=h).status_code == 409


def test_reject_and_ownership(client, fake):
    _, h1, plan = setup_plan(client)
    _, h2, _ = setup_plan(client)
    fake.next = {"summary": "x", "operations": [{"op": "UPDATE", "itemId": plan["days"][0]["exercises"][0]["id"], "restSeconds": 100}]}
    p = propose(client, h1).json()
    assert client.get(f"/v1/ai/proposals/{p['id']}", headers=h2).status_code == 404
    assert client.post(f"/v1/ai/proposals/{p['id']}/apply", headers=h2).status_code == 404
    assert client.post(f"/v1/ai/proposals/{p['id']}/reject", headers=h1).json()["status"] == "REJECTED"
    assert client.post(f"/v1/ai/proposals/{p['id']}/apply", headers=h1).status_code == 409


def test_day_scope_limits_what_the_model_can_touch(client, fake):
    _, h, plan = setup_plan(client)
    d1, d2 = plan["days"][0], plan["days"][1]
    fake.next = {"summary": "x", "operations": [
        {"op": "UPDATE", "itemId": d1["exercises"][0]["id"], "restSeconds": 100},
        {"op": "UPDATE", "itemId": d2["exercises"][0]["id"], "restSeconds": 100}]}
    p = propose(client, h, dayId=d2["id"]).json()
    assert len(p["operations"]) == 1 and p["operations"][0]["dayId"] == d2["id"]
    assert json.loads(fake.calls[-1]["user"])["plan"]["dias"][0]["id"] == d2["id"] and len(json.loads(fake.calls[-1]["user"])["plan"]["dias"]) == 1
    assert propose(client, h, dayId="no-existe").status_code == 404
