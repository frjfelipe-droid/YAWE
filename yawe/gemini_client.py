"""Integração com a API do Google Gemini (plano grátis do Google AI Studio)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx2
from google import genai
from google.genai import errors, types

from .ai_client import AIError, ChatReply
from .config import Settings

# Motivos de parada que indicam bloqueio por política de conteúdo.
_BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY"}

@dataclass
class GeminiChat:
    """Sessão de conversa com o Gemini que mantém o histórico entre mensagens."""

    settings: Settings
    client: genai.Client | None = None
    history: list[types.Content] = field(default_factory=list)
    model: str = ""
    on_model_change: Callable[[str, str], None] | None = None

    def __post_init__(self) -> None:
        self.model = self.model or self.settings.model
        if self.client is None:
            self.client = genai.Client(
                api_key=self.settings.api_key,
                # Repete automaticamente erros temporários (limite, servidor, rede).
                # Limite de tempo (ms) para não ficar esperando para sempre; 2 tentativas no máximo.
                http_options=types.HttpOptions(
                    timeout=90_000,
                    retry_options=types.HttpRetryOptions(attempts=2, max_delay=10.0),
                ),
            )

    def reset(self) -> None:
        self.history.clear()

    def send(self, user_message: str, on_text: Callable[[str], None] | None = None) -> ChatReply:
        """Envia uma mensagem, transmite a resposta via `on_text` e atualiza o histórico.

        Se a chamada falhar, a mensagem do usuário é removida do histórico para que
        a conversa continue válida e possa ser repetida.
        """
        if not user_message.strip():
            raise AIError("A mensagem está vazia.")

        self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
        try:
            try:
                text, finish, usage, blocked_prompt = self._stream(on_text)
            except _ModelNotFound:
                # O Google aposenta modelos com frequência: escolhe outro disponível e tenta de novo.
                old_model, self.model = self.model, self._pick_available_model()
                if self.on_model_change:
                    self.on_model_change(old_model, self.model)
                text, finish, usage, blocked_prompt = self._stream(on_text)
        except _ModelNotFound as e:
            self.history.pop()
            raise AIError(
                f"Modelo '{self.model}' não encontrado. Detalhe: {e}. "
                "Coloque outro modelo do Gemini na linha AI_MODEL do .env."
            ) from e
        except BaseException:
            self.history.pop()
            raise

        if blocked_prompt or finish in _BLOCKED:
            self.history.pop()
            raise AIError("O modelo bloqueou esta mensagem pelas regras de conteúdo do Google.")
        if not text:
            self.history.pop()
            raise AIError("O modelo não devolveu nenhuma resposta. Tente reformular a mensagem.")

        self.history.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
        return ChatReply(
            text=text,
            stop_reason=finish,
            truncated=finish == "MAX_TOKENS",
            model=self.model,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
        )

    def _stream(self, on_text: Callable[[str], None] | None):
        assert self.client is not None
        config = types.GenerateContentConfig(
            system_instruction=self.settings.system_prompt,
            max_output_tokens=self.settings.max_tokens,
        )
        parts: list[str] = []
        finish = None
        usage = None
        blocked_prompt = False
        try:
            for chunk in self.client.models.generate_content_stream(
                model=self.model, contents=self.history, config=config
            ):
                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    blocked_prompt = True
                if chunk.usage_metadata:
                    usage = chunk.usage_metadata
                if chunk.candidates and chunk.candidates[0].finish_reason:
                    finish = chunk.candidates[0].finish_reason.name
                if chunk.text:
                    parts.append(chunk.text)
                    if on_text:
                        on_text(chunk.text)
        except errors.ClientError as e:
            raise self._client_error(e) from e
        except errors.ServerError as e:
            raise AIError(
                f"O serviço do Google está instável no momento ({e.code}). Tente novamente.",
                retryable=True,
            ) from e
        except errors.APIError as e:
            raise AIError(f"Erro da API do Google ({e.code}): {e.message}") from e
        except httpx2.TimeoutException as e:
            raise AIError("A requisição expirou. Tente novamente.", retryable=True) from e
        except httpx2.TransportError as e:
            raise AIError("Falha de conexão com o Google. Verifique sua internet.", retryable=True) from e
        return "".join(parts), finish, usage, blocked_prompt

    def _client_error(self, e: errors.ClientError) -> Exception:
        message = e.message or ""
        if e.code == 400 and "API key" in message:
            return AIError("Chave do Gemini inválida. Confira a chave no arquivo .env.")
        if e.code in (401, 403):
            return AIError(f"Sua chave não tem permissão para usar '{self.model}'. Resposta do Google: {message}")
        if e.code == 404:
            return _ModelNotFound(message)
        if e.code == 429:
            return AIError(
                "Limite do plano grátis atingido. Espere um minuto e tente de novo "
                "(o limite diário renova no dia seguinte).",
                retryable=True,
            )
        return AIError(f"Requisição inválida ({e.code}): {message}")

    def list_models(self) -> list[str]:
        """Modelos de conversa que esta chave pode usar."""
        assert self.client is not None
        try:
            return sorted(
                (m.name or "").removeprefix("models/")
                for m in self.client.models.list()
                if "generateContent" in (m.supported_actions or [])
            )
        except errors.APIError as e:
            raise AIError(f"Não foi possível listar os modelos ({e.code}): {e.message}") from e
        except httpx2.TransportError as e:
            raise AIError("Falha de conexão com o Google. Verifique sua internet.") from e

    def _pick_available_model(self) -> str:
        """Escolhe o melhor modelo "flash" estável que a chave pode usar para conversar."""
        assert self.client is not None
        try:
            names = [
                (m.name or "").removeprefix("models/")
                for m in self.client.models.list()
                if "generateContent" in (m.supported_actions or [])
            ]
        except errors.APIError as e:
            raise _ModelNotFound(str(e)) from e

        names = [n for n in names if n != self.model]  # o atual acabou de falhar
        if not names:
            raise _ModelNotFound("a chave não lista nenhum modelo de conversa")

        def version(name: str) -> tuple[float, ...]:
            return tuple(float(x) for x in re.findall(r"\d+(?:\.\d+)?", name)) or (0.0,)

        skip = ("preview", "exp", "lite", "image", "tts", "audio", "live", "embedding", "thinking")
        gemini = [n for n in names if n.startswith("gemini")]
        stable_flash = [n for n in gemini if "flash" in n and not any(w in n for w in skip)]
        if "gemini-flash-latest" in names:
            return "gemini-flash-latest"
        if stable_flash:
            return max(stable_flash, key=version)
        # Sem Flash estável: aceita qualquer Gemini de texto (preview/lite incluídos).
        text_models = [n for n in gemini if not any(w in n for w in ("image", "tts", "audio", "live", "embedding"))]
        if text_models:
            return max(text_models, key=version)
        raise _ModelNotFound("modelos disponíveis: " + ", ".join(names[:8]))


class _ModelNotFound(Exception):
    """O modelo pedido não existe (ou foi aposentado) para esta chave."""
