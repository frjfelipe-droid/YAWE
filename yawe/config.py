"""Carrega a configuração do app a partir do ambiente e de um arquivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}

VERCEL_GATEWAY_URL = "https://ai-gateway.vercel.sh"

# Modelo padrão de cada provedor (o nome muda: a Vercel usa "anthropic/..." com ponto).
DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "vercel": "anthropic/claude-haiku-5.5",
    "gemini": "gemini-flash-latest",  # apelido do Google para o Flash mais recente
}


class ConfigError(RuntimeError):
    """Configuração ausente ou inválida."""


@dataclass(frozen=True)
class Settings:
    provider: str  # "anthropic" (API direta), "vercel" (Vercel AI Gateway) ou "gemini" (Google)
    api_key: str
    base_url: str | None
    model: str
    effort: str
    max_tokens: int
    system_prompt: str


def _detect_provider() -> tuple[str, str]:
    gemini_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    gateway_key = os.getenv("AI_GATEWAY_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if gemini_key:
        return "gemini", gemini_key
    # Chaves do Google começam com "AIza": aceita mesmo se colocada no nome errado.
    for key in (gateway_key, anthropic_key):
        if key.startswith("AIza"):
            return "gemini", key
    if gateway_key:
        return "vercel", gateway_key
    # Chaves da Vercel começam com "vck_": aceita mesmo se colocada no nome errado.
    if anthropic_key.startswith("vck_"):
        return "vercel", anthropic_key
    if anthropic_key:
        return "anthropic", anthropic_key

    raise ConfigError(
        "Nenhuma chave encontrada. No arquivo .env, coloque GEMINI_API_KEY=AIza... (Google, grátis), "
        "AI_GATEWAY_API_KEY=vck_... (Vercel) ou ANTHROPIC_API_KEY=sk-ant-... (Anthropic). "
        "Veja .env.example."
    )


def _model_for(provider: str) -> str:
    model = (os.getenv("AI_MODEL") or os.getenv("CLAUDE_MODEL") or "").strip()
    if provider == "gemini":
        # Aceita o nome no formato da Vercel ("google/gemini-...") e ignora modelos de outros provedores.
        model = model.removeprefix("google/")
        if not model.startswith(("gemini", "gemma")):
            model = ""
    return model or DEFAULT_MODELS[provider]


def load_settings(env_file: Path | None = None) -> Settings:
    # override=False: variáveis que já existem no ambiente NÃO são sobrescritas
    # pelo .env, e o .env nunca é modificado por este código.
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)

    provider, api_key = _detect_provider()

    effort = os.getenv("CLAUDE_EFFORT", "medium").strip().lower()
    if effort not in VALID_EFFORTS:
        raise ConfigError(
            f"CLAUDE_EFFORT inválido: {effort!r}. Use um de: {', '.join(sorted(VALID_EFFORTS))}."
        )

    try:
        max_tokens = int(os.getenv("CLAUDE_MAX_TOKENS", "16000"))
    except ValueError as exc:
        raise ConfigError("CLAUDE_MAX_TOKENS deve ser um número inteiro.") from exc

    return Settings(
        provider=provider,
        api_key=api_key,
        base_url=VERCEL_GATEWAY_URL if provider == "vercel" else None,
        model=_model_for(provider),
        effort=effort,
        max_tokens=max_tokens,
        system_prompt=os.getenv(
            "CLAUDE_SYSTEM_PROMPT",
            "Você é um assistente prestativo. Responda em português do Brasil.",
        ),
    )
