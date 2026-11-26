"""Integração com a API da Anthropic (Claude): chat com histórico e tratamento de erros."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .config import Settings

# Fallback do lado do servidor: se o modelo recusar por política, a própria API
# reexecuta a requisição em um modelo de fallback adequado, na mesma chamada.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIError(Exception):
    """Erro amigável para exibir ao usuário final."""

    def __init__(self, message: str, *, retryable: bool = False, request_id: str | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.request_id = request_id


@dataclass
class ChatReply:
    text: str
    stop_reason: str | None
    truncated: bool
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class ClaudeChat:
    """Sessão de conversa com o Claude que mantém o histórico entre mensagens."""

    settings: Settings
    client: anthropic.Anthropic | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.client is None:
            # O SDK já faz retry automático (com backoff) em 408/409/429/5xx e falhas de rede.
            self.client = anthropic.Anthropic(
                api_key=self.settings.api_key,
                base_url=self.settings.base_url,  # None = API da Anthropic; senão, Vercel AI Gateway
                max_retries=3,
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

        self.history.append({"role": "user", "content": user_message})
        try:
            final = self._stream(on_text)
        except BaseException:  # inclui Ctrl+C: a mensagem não respondida sai do histórico
            self.history.pop()
            raise

        if final.stop_reason == "refusal":
            # Toda a cadeia (incluindo o fallback) recusou: não guardamos essa troca.
            self.history.pop()
            details = getattr(final, "stop_details", None)
            explanation = getattr(details, "explanation", None) if details else None
            raise AIError(
                "O modelo recusou esta solicitação."
                + (f" Motivo: {explanation}" if explanation else ""),
                request_id=getattr(final, "_request_id", None),
            )

        # Guarda o conteúdo completo (inclui blocos de thinking/fallback), sem editar,
        # para que os próximos turnos reaproveitem o raciocínio e o cache.
        self.history.append({"role": "assistant", "content": final.content})

        text = "".join(b.text for b in final.content if b.type == "text")
        return ChatReply(
            text=text,
            stop_reason=final.stop_reason,
            truncated=final.stop_reason == "max_tokens",
            model=final.model,
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
        )

    def _open_stream(self):
        assert self.client is not None
        common = dict(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            system=self.settings.system_prompt,
            messages=self.history,
        )
        if self.settings.provider == "vercel":
            # O Vercel AI Gateway aceita só os parâmetros padrão da Messages API
            # (sem recursos beta como fallbacks, nem output_config).
            return self.client.messages.stream(**common)
        return self.client.beta.messages.stream(
            **common,
            output_config={"effort": self.settings.effort},
            cache_control={"type": "ephemeral"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    def _stream(self, on_text: Callable[[str], None] | None):
        assert self.client is not None
        try:
            with self._open_stream() as stream:
                for chunk in stream.text_stream:
                    if on_text:
                        on_text(chunk)
                return stream.get_final_message()
        except anthropic.AuthenticationError as e:
            raise AIError("Chave de API inválida ou revogada. Confira a chave no arquivo .env.", request_id=e.request_id) from e
        except anthropic.PermissionDeniedError as e:
            raise AIError(
                f"Sua chave não tem permissão para usar '{self.settings.model}'. "
                f"Resposta do servidor: {e.message}",
                request_id=e.request_id,
            ) from e
        except anthropic.NotFoundError as e:
            raise AIError(
                f"Modelo '{self.settings.model}' não encontrado ou indisponível para sua conta.",
                request_id=e.request_id,
            ) from e
        except anthropic.RateLimitError as e:
            retry_after = e.response.headers.get("retry-after")
            wait = f" Tente novamente em {retry_after}s." if retry_after else " Tente novamente em instantes."
            raise AIError("Limite de requisições atingido." + wait, retryable=True, request_id=e.request_id) from e
        except anthropic.BadRequestError as e:
            raise AIError(f"Requisição inválida: {e.message}", request_id=e.request_id) from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise AIError(
                    f"Serviço da Anthropic indisponível no momento ({e.status_code}). Tente novamente.",
                    retryable=True,
                    request_id=e.request_id,
                ) from e
            raise AIError(f"Erro da API ({e.status_code}): {e.message}", request_id=e.request_id) from e
        except anthropic.APITimeoutError as e:
            raise AIError("A requisição expirou. Tente novamente.", retryable=True) from e
        except anthropic.APIConnectionError as e:
            raise AIError("Falha de conexão com a API. Verifique sua internet.", retryable=True) from e



def create_chat(settings: Settings):
    """Cria a sessão de chat do provedor configurado (Anthropic, Vercel ou Gemini)."""
    if settings.provider == "gemini":
        from .gemini_client import GeminiChat

        return GeminiChat(settings)
    return ClaudeChat(settings)
