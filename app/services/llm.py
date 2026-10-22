"""Cliente de modelos de lenguaje por token. Dos adaptadores y una interfaz minima, para no depender de un proveedor.

- anthropic: API Messages de Anthropic (Claude).
- openai:    cualquier API compatible con /chat/completions (OpenAI, Gemini en modo compatible, Groq, etc.).
El token (AI_API_KEY) vive solo en variables de entorno del servidor; nunca llega al navegador."""
from dataclasses import dataclass

import httpx

from .. import config

ANTHROPIC_URL = "https://api.anthropic.com"
ANTHROPIC_DEFAULT_MODEL = "claude-haiku-5-5"   # verifica el nombre vigente en la documentacion de Anthropic


class LLMError(Exception):
    """Fallo del proveedor (red, token invalido, limite, respuesta rara). El mensaje es interno: no se muestra al usuario."""


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMClient:
    provider = ""
    model = ""

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResult:  # pragma: no cover
        raise NotImplementedError


class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(self, api_key: str, model: str, base_url: str = "", timeout: int = 30):
        self.key, self.model = api_key, model or ANTHROPIC_DEFAULT_MODEL
        self.base, self.timeout = (base_url or ANTHROPIC_URL).rstrip("/"), timeout

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResult:
        try:
            r = httpx.post(f"{self.base}/v1/messages", timeout=self.timeout,
                           headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                           json={"model": self.model, "max_tokens": max_tokens, "system": system,
                                 "messages": [{"role": "user", "content": user}]})
        except httpx.HTTPError as e:
            raise LLMError(f"red: {e.__class__.__name__}") from e
        if r.status_code >= 400:
            raise LLMError(f"anthropic HTTP {r.status_code}")
        d = r.json()
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        u = d.get("usage", {})
        return LLMResult(text, int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)), d.get("model", self.model))


class OpenAICompatClient(LLMClient):
    provider = "openai"

    def __init__(self, api_key: str, model: str, base_url: str = "", timeout: int = 30):
        self.key, self.model = api_key, model
        self.base, self.timeout = (base_url or "https://api.openai.com/v1").rstrip("/"), timeout

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResult:
        limit_key = "max_completion_tokens" if "api.openai.com" in self.base else "max_tokens"
        try:
            r = httpx.post(f"{self.base}/chat/completions", timeout=self.timeout,
                           headers={"Authorization": f"Bearer {self.key}", "content-type": "application/json"},
                           json={"model": self.model, limit_key: max_tokens, "response_format": {"type": "json_object"},
                                 "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        except httpx.HTTPError as e:
            raise LLMError(f"red: {e.__class__.__name__}") from e
        if r.status_code >= 400:
            raise LLMError(f"openai-compat HTTP {r.status_code}")
        d = r.json()
        try:
            text = d["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("respuesta sin contenido") from e
        u = d.get("usage", {})
        return LLMResult(text, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), d.get("model", self.model))


def get_client() -> LLMClient | None:
    """None = IA apagada (falta el token o el modelo)."""
    if not config.AI_API_KEY:
        return None
    if config.AI_PROVIDER == "anthropic":
        return AnthropicClient(config.AI_API_KEY, config.AI_MODEL, config.AI_BASE_URL, config.AI_TIMEOUT_SECONDS)
    if config.AI_PROVIDER == "openai" and config.AI_MODEL:
        return OpenAICompatClient(config.AI_API_KEY, config.AI_MODEL, config.AI_BASE_URL, config.AI_TIMEOUT_SECONDS)
    return None
