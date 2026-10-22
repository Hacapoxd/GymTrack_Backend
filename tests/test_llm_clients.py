"""Verifica la forma de las peticiones HTTP a cada proveedor y la lectura de tokens (servidor simulado, sin red)."""
import httpx
import pytest

from app import config
from app.services import llm


def fake_post(captured, response):
    def _post(url, **kw):
        captured.update(url=url, **kw)
        return response
    return _post


def test_anthropic_request_and_usage(monkeypatch):
    cap = {}
    resp = httpx.Response(200, json={"model": "m-real", "content": [{"type": "text", "text": '{"summary":"a"}'}],
                                     "usage": {"input_tokens": 111, "output_tokens": 22}})
    monkeypatch.setattr(httpx, "post", fake_post(cap, resp))
    r = llm.AnthropicClient("sk-test", "", timeout=5).complete("SYS", "USR", 700)
    assert cap["url"] == "https://api.anthropic.com/v1/messages"
    assert cap["headers"]["x-api-key"] == "sk-test" and cap["headers"]["anthropic-version"] == "2023-06-01"
    assert cap["json"] == {"model": llm.ANTHROPIC_DEFAULT_MODEL, "max_tokens": 700, "system": "SYS",
                           "messages": [{"role": "user", "content": "USR"}]}
    assert (r.text, r.input_tokens, r.output_tokens, r.model) == ('{"summary":"a"}', 111, 22, "m-real")


def test_openai_compatible_request_and_usage(monkeypatch):
    cap = {}
    resp = httpx.Response(200, json={"model": "gem", "choices": [{"message": {"content": '{"summary":"b"}'}}],
                                     "usage": {"prompt_tokens": 50, "completion_tokens": 9}})
    monkeypatch.setattr(httpx, "post", fake_post(cap, resp))
    r = llm.OpenAICompatClient("k", "gem", "https://generativelanguage.googleapis.com/v1beta/openai/").complete("S", "U", 300)
    assert cap["url"] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert cap["headers"]["Authorization"] == "Bearer k" and cap["json"]["max_tokens"] == 300
    assert cap["json"]["messages"][0] == {"role": "system", "content": "S"} and cap["json"]["response_format"] == {"type": "json_object"}
    assert (r.input_tokens, r.output_tokens) == (50, 9)
    llm.OpenAICompatClient("k", "gpt", "").complete("S", "U", 300)          # api.openai.com usa max_completion_tokens
    assert "max_completion_tokens" in cap["json"] and "max_tokens" not in cap["json"]


@pytest.mark.parametrize("cls,args", [(llm.AnthropicClient, ("k", "")), (llm.OpenAICompatClient, ("k", "m"))])
def test_http_errors_become_llmerror_without_leaking_body(monkeypatch, cls, args):
    monkeypatch.setattr(httpx, "post", fake_post({}, httpx.Response(401, text="invalid x-api-key: sk-SECRETO")))
    with pytest.raises(llm.LLMError) as e:
        cls(*args).complete("S", "U", 100)
    assert "SECRETO" not in str(e.value) and "401" in str(e.value)

    def boom(*a, **k):
        raise httpx.ConnectTimeout("tiempo agotado")
    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(llm.LLMError):
        cls(*args).complete("S", "U", 100)


def test_get_client_selection(monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "")
    assert llm.get_client() is None
    monkeypatch.setattr(config, "AI_API_KEY", "k")
    monkeypatch.setattr(config, "AI_PROVIDER", "anthropic")
    assert isinstance(llm.get_client(), llm.AnthropicClient)
    monkeypatch.setattr(config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(config, "AI_MODEL", "")
    assert llm.get_client() is None                      # openai-compatible exige modelo explícito
    monkeypatch.setattr(config, "AI_MODEL", "gpt-x")
    assert isinstance(llm.get_client(), llm.OpenAICompatClient)


def test_database_url_normalization(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
    assert config._db_url() == "postgresql+psycopg://u:p@h:5432/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert config._db_url() == "postgresql+psycopg://u:p@h/db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    assert config._db_url() == "sqlite:///x.db"
