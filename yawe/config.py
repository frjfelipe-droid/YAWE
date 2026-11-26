"""Carrega a configuração do app a partir do ambiente e de um arquivo .env."""

from __future__ import annotations

import io
import logging
import os
import re
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


DEFAULT_SYSTEM_PROMPT = (
    "Você é um assistente prestativo. Responda em português do Brasil, em texto simples "
    "(sem markdown, sem asteriscos e sem tabelas), de forma clara e natural, como numa conversa."
)


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
    # Voz (ElevenLabs) — opcional
    elevenlabs_api_key: str | None = None
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # "George", voz pronta da ElevenLabs
    tts_model: str = "eleven_flash_v2_5"  # rápido, fala português e gasta menos créditos
    voice_max_chars: int = 1000
    # App web (celular)
    assistant_name: str = "YAWE"
    app_password: str | None = None


# Formatos de chave conhecidos, usados para achar a chave mesmo num .env mal formatado.
_KEY_PATTERNS = (
    ("gemini", re.compile(r"AIza[0-9A-Za-z_\-]{20,}")),
    ("vercel", re.compile(r"vck_[0-9A-Za-z_\-]{20,}")),
    ("anthropic", re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}")),
)


def _read_env_text(path: Path) -> str | None:
    """Lê o .env aceitando as codificações que o Bloco de Notas pode usar."""
    if not path.is_file():
        return None
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeError:
            continue
    return None


def _find_key_in_text(text: str | None) -> tuple[str, str] | None:
    for provider, pattern in _KEY_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return provider, match.group(0)
    return None


_ELEVENLABS_PATTERN = re.compile(r"\bsk_[0-9a-f]{40,}\b")


def _elevenlabs_key(env_text: str | None) -> str | None:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key
    match = _ELEVENLABS_PATTERN.search(env_text or "")
    return match.group(0) if match else None


def _detect_provider(env_text: str | None = None) -> tuple[str, str]:
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

    # .env fora do formato NOME=valor (ex.: "GEMINI API KEY: AIza..."): procura a chave no texto.
    found = _find_key_in_text(env_text)
    if found:
        return found

    raise ConfigError(
        "Nenhuma chave encontrada. No arquivo .env, coloque GEMINI_API_KEY=AIza... (Google, grátis), "
        "AI_GATEWAY_API_KEY=vck_... (Vercel) ou ANTHROPIC_API_KEY=sk-ant-... (Anthropic). "
        "Veja .env.example."
    )


def _model_for(provider: str, env_text: str | None = None) -> str:
    model = (os.getenv("AI_MODEL") or os.getenv("CLAUDE_MODEL") or "").strip()
    if not model and provider == "gemini":
        match = re.search(r"\b(gemini-[0-9A-Za-z.\-]+)", env_text or "")
        model = match.group(1) if match else ""
    if provider == "gemini":
        # Aceita o nome no formato da Vercel ("google/gemini-...") e ignora modelos de outros provedores.
        model = model.removeprefix("google/")
        if not model.startswith(("gemini", "gemma")):
            model = ""
    return model or DEFAULT_MODELS[provider]


def load_settings(env_file: Path | None = None) -> Settings:
    # override=False: variáveis que já existem no ambiente NÃO são sobrescritas
    # pelo .env, e o .env nunca é modificado por este código.
    env_text = _read_env_text(env_file or PROJECT_ROOT / ".env")
    if env_text:
        # Silencia os avisos em inglês do dotenv; linhas fora do padrão são tratadas abaixo.
        logging.getLogger("dotenv.main").setLevel(logging.ERROR)
        load_dotenv(stream=io.StringIO(env_text), override=False)

    provider, api_key = _detect_provider(env_text)

    effort = os.getenv("CLAUDE_EFFORT", "medium").strip().lower()
    if effort not in VALID_EFFORTS:
        raise ConfigError(
            f"CLAUDE_EFFORT inválido: {effort!r}. Use um de: {', '.join(sorted(VALID_EFFORTS))}."
        )

    try:
        max_tokens = int(os.getenv("CLAUDE_MAX_TOKENS", "16000"))
    except ValueError as exc:
        raise ConfigError("CLAUDE_MAX_TOKENS deve ser um número inteiro.") from exc

    try:
        voice_max_chars = int(os.getenv("ELEVENLABS_MAX_CHARS", "1000"))
    except ValueError as exc:
        raise ConfigError("ELEVENLABS_MAX_CHARS deve ser um número inteiro.") from exc

    return Settings(
        provider=provider,
        api_key=api_key,
        base_url=VERCEL_GATEWAY_URL if provider == "vercel" else None,
        model=_model_for(provider, env_text),
        effort=effort,
        max_tokens=max_tokens,
        system_prompt=os.getenv("AI_SYSTEM_PROMPT") or os.getenv("CLAUDE_SYSTEM_PROMPT") or DEFAULT_SYSTEM_PROMPT,
        elevenlabs_api_key=_elevenlabs_key(env_text),
        voice_id=os.getenv("ELEVENLABS_VOICE_ID", "").strip() or "JBFqnCBsd6RMkjVDRZzb",
        tts_model=os.getenv("ELEVENLABS_MODEL", "").strip() or "eleven_flash_v2_5",
        voice_max_chars=voice_max_chars,
        assistant_name=os.getenv("ASSISTANT_NAME", "").strip() or "YAWE",
        app_password=os.getenv("APP_PASSWORD", "").strip() or None,
    )
