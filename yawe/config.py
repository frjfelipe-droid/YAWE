"""Carrega a configuração do app a partir do ambiente e de um arquivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


class ConfigError(RuntimeError):
    """Configuração ausente ou inválida."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    effort: str
    max_tokens: int
    system_prompt: str


def load_settings(env_file: Path | None = None) -> Settings:
    # override=False: variáveis que já existem no ambiente NÃO são sobrescritas
    # pelo .env, e o .env nunca é modificado por este código.
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ConfigError(
            "ANTHROPIC_API_KEY não encontrada. Adicione-a ao seu .env "
            "(veja .env.example) ou exporte-a no ambiente."
        )

    effort = os.getenv("CLAUDE_EFFORT", "medium").strip().lower()
    if effort not in VALID_EFFORTS:
        raise ConfigError(
            f"CLAUDE_EFFORT inválido: {effort!r}. Use um de: {', '.join(sorted(VALID_EFFORTS))}."
        )

    try:
        max_tokens = int(os.getenv("CLAUDE_MAX_TOKENS", "64000"))
    except ValueError as exc:
        raise ConfigError("CLAUDE_MAX_TOKENS deve ser um número inteiro.") from exc

    return Settings(
        api_key=api_key,
        model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5").strip(),
        effort=effort,
        max_tokens=max_tokens,
        system_prompt=os.getenv(
            "CLAUDE_SYSTEM_PROMPT",
            "Você é um assistente prestativo. Responda em português do Brasil.",
        ),
    )
