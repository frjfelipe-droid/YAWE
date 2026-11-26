"""Voz com a ElevenLabs: transforma a resposta da IA em fala e toca no computador."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

# WAV toca nativamente no Windows (winsound), sem instalar nada.
OUTPUT_FORMAT = "wav_22050"


class VoiceError(Exception):
    """Erro amigável da parte de voz (não interrompe o chat)."""


def clean_for_speech(text: str, max_chars: int) -> str:
    """Remove marcações (markdown) que soariam estranhas e limita o tamanho para poupar créditos."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)  # blocos de código não são lidos
    text = re.sub(r"[*_`#>|~]+", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [texto](link) -> texto
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        cut = text[:max_chars]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = cut[: end + 1] if end > max_chars // 2 else cut
    return text


class Voice:
    def __init__(self, api_key: str, voice_id: str, model_id: str, max_chars: int = 1000):
        self.client = ElevenLabs(api_key=api_key, timeout=60)
        self.voice_id = voice_id
        self.model_id = model_id
        self.max_chars = max_chars
        self._tmp_dir = Path(tempfile.gettempdir()) / "yawe-voz"
        self._tmp_dir.mkdir(exist_ok=True)
        self._turn = 0

    def speak(self, text: str) -> None:
        speech = clean_for_speech(text, self.max_chars)
        if not speech:
            return
        audio = self._synthesize(speech)
        self._play(audio)

    def list_voices(self) -> list[tuple[str, str, bool]]:
        """(nome, ID, é voz padrão) — as vozes padrão ("premade") funcionam no plano grátis."""
        voices = []
        token = None
        try:
            while True:
                page = self.client.voices.search(page_size=100, next_page_token=token)
                voices.extend(page.voices)
                token = getattr(page, "next_page_token", None)
                if not getattr(page, "has_more", False) or not token:
                    break
        except ApiError as e:
            raise self._api_error(e) from e
        except httpx.HTTPError as e:
            raise VoiceError("Falha de conexão com a ElevenLabs.") from e
        items = [(v.name or "?", v.voice_id, v.category == "premade") for v in voices]
        return sorted(items, key=lambda item: (not item[2], item[0].lower()))

    def _synthesize(self, text: str) -> bytes:
        try:
            chunks = self.client.text_to_speech.convert(
                self.voice_id,
                text=text,
                model_id=self.model_id,
                output_format=OUTPUT_FORMAT,
            )
            return b"".join(chunks)
        except ApiError as e:
            raise self._api_error(e) from e
        except httpx.TimeoutException as e:
            raise VoiceError("A ElevenLabs demorou demais para gerar o áudio.") from e
        except httpx.HTTPError as e:
            raise VoiceError("Falha de conexão com a ElevenLabs. Verifique sua internet.") from e

    def _play(self, audio: bytes) -> None:
        # Alterna entre 2 arquivos para não sobrescrever um áudio que ainda está tocando.
        self._turn = (self._turn + 1) % 2
        path = self._tmp_dir / f"resposta-{self._turn}.wav"
        path.write_bytes(audio)

        if sys.platform == "win32":
            import winsound

            # SND_ASYNC: toca em segundo plano, então você já pode digitar a próxima mensagem.
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        for player in (["afplay"], ["aplay", "-q"], ["paplay"]):
            if shutil.which(player[0]):
                subprocess.Popen([*player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        raise VoiceError(f"Não encontrei um reprodutor de áudio. O áudio foi salvo em {path}")

    def _api_error(self, e: ApiError) -> VoiceError:
        detail = e.body.get("detail") if isinstance(e.body, dict) else None
        status = detail.get("status", "") if isinstance(detail, dict) else ""
        message = detail.get("message", "") if isinstance(detail, dict) else str(e.body or "")

        if status == "quota_exceeded":
            return VoiceError("Os créditos de voz da ElevenLabs acabaram este mês.")
        if status == "missing_permissions":
            return VoiceError(
                "Sua chave da ElevenLabs não tem permissão de Text to Speech. "
                "Crie uma chave com essa permissão no site da ElevenLabs."
            )
        if e.status_code == 401 or status == "invalid_api_key" or "api key is invalid" in message.lower():
            return VoiceError("Chave da ElevenLabs inválida. Confira ELEVENLABS_API_KEY no .env.")
        if e.status_code == 404 or status == "voice_not_found":
            return VoiceError("Voz não encontrada. Use /vozes e troque ELEVENLABS_VOICE_ID no .env.")
        if e.status_code == 402 and "library voices" in message:
            return VoiceError(
                "Essa voz é da biblioteca da ElevenLabs e exige plano pago. No plano grátis, "
                "use uma voz marcada como [grátis] no comando /vozes."
            )
        if e.status_code == 429:
            return VoiceError("Muitas requisições de voz seguidas. Espere um pouco.")
        return VoiceError(f"Erro da ElevenLabs ({e.status_code}): {message}")
