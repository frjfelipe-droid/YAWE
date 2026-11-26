"""Ponto de entrada do YAWE: chat de terminal com IA (Gemini, Claude via Anthropic ou Vercel)."""

from __future__ import annotations

import sys

from yawe.ai_client import AIError, create_chat
from yawe.config import ConfigError, Settings, load_settings

HELP = "Comandos: /modelos, /limpar (zera o histórico), /sair (encerra)."
VOICE_HELP = "Voz: /voz (liga/desliga), /vozes (lista as vozes da sua conta)."


def create_voice(settings: Settings):
    if not settings.elevenlabs_api_key:
        return None
    try:
        from yawe.voice import Voice
    except ImportError:
        print("[aviso] biblioteca de voz não instalada. Rode: pip install -r requirements.txt", file=sys.stderr)
        return None
    return Voice(settings.elevenlabs_api_key, settings.voice_id, settings.tts_model, settings.voice_max_chars)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"[configuração] {e}", file=sys.stderr)
        return 1

    chat = create_chat(
        settings,
        on_model_change=lambda old, new: print(
            f"\n[aviso] o modelo '{old}' não está disponível; usando '{new}'.", file=sys.stderr
        ),
    )
    voice = create_voice(settings)
    voice_on = voice is not None
    print(f"YAWE — conversando com {settings.model}. {HELP}")
    if voice:
        print(f"Voz da ElevenLabs LIGADA. {VOICE_HELP}")

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
        if user_input in {"/modelos", "/models"}:
            try:
                names = chat.list_models()
            except AIError as e:
                print(f"[erro] {e}", file=sys.stderr)
                continue
            print("Modelos disponíveis para a sua chave:")
            for name in names:
                print(f"  - {name}")
            print("Para usar um deles, coloque no .env: AI_MODEL=nome-do-modelo")
            continue
        if user_input in {"/voz", "/voice"}:
            if not voice:
                print("Voz indisponível: coloque ELEVENLABS_API_KEY=sua-chave no .env e reabra o app.")
                continue
            voice_on = not voice_on
            print(f"Voz {'LIGADA' if voice_on else 'DESLIGADA'}.")
            continue
        if user_input in {"/vozes", "/voices"}:
            if not voice:
                print("Voz indisponível: coloque ELEVENLABS_API_KEY=sua-chave no .env e reabra o app.")
                continue
            try:
                voices = voice.list_voices()
            except Exception as e:  # erros de voz nunca derrubam o chat
                print(f"[voz] {e}", file=sys.stderr)
                continue
            print("Vozes da sua conta (nome — ID). [grátis] = funciona no plano grátis da API:")
            for name, voice_id, free in voices:
                tag = "[grátis] " if free else "[pago]   "
                print(f"  {tag}{name} — {voice_id}")
            print("Para usar uma delas, coloque no .env: ELEVENLABS_VOICE_ID=ID-da-voz")
            continue
        if user_input in {"/limpar", "/reset"}:
            chat.reset()
            print("Histórico apagado.")
            continue

        # "pensando..." some assim que o primeiro pedaço da resposta chega.
        print("\nIA: pensando...", end="", flush=True)
        started = False

        def show(chunk: str) -> None:
            nonlocal started
            if not started:
                print("\rIA:            \rIA: ", end="")
                started = True
            print(chunk, end="", flush=True)

        try:
            reply = chat.send(user_input, on_text=show)
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
        if voice and voice_on:
            try:
                voice.speak(reply.text)
            except Exception as e:  # erros de voz nunca derrubam o chat
                print(f"[voz] {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
