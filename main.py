"""Ponto de entrada do YAWE: chat de terminal com IA (Gemini, Claude via Anthropic ou Vercel)."""

from __future__ import annotations

import sys

from yawe.ai_client import AIError, create_chat
from yawe.config import ConfigError, load_settings

HELP = "Comandos: /limpar (zera o histórico), /sair (encerra)."


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"[configuração] {e}", file=sys.stderr)
        return 1

    chat = create_chat(
        settings,
        on_model_change=lambda old, new: print(
            f"[aviso] o modelo '{old}' não está disponível; usando '{new}'.", file=sys.stderr
        ),
    )
    print(f"YAWE — conversando com {settings.model}. {HELP}")

    while True:
        try:
            user_input = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_input:
            continue
        if user_input in {"/sair", "/exit"}:
            return 0
        if user_input in {"/limpar", "/reset"}:
            chat.reset()
            print("Histórico apagado.")
            continue

        print("\nIA: ", end="", flush=True)
        try:
            reply = chat.send(user_input, on_text=lambda t: print(t, end="", flush=True))
        except AIError as e:
            print(f"\n[erro] {e}", file=sys.stderr)
            if e.request_id:
                print(f"        request-id: {e.request_id}", file=sys.stderr)
            continue
        except KeyboardInterrupt:
            # Resposta interrompida (Ctrl+C): a mensagem já saiu do histórico.
            print("\n[interrompido]")
            continue

        print()
        if reply.truncated:
            print("[aviso] resposta cortada por atingir CLAUDE_MAX_TOKENS.", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
