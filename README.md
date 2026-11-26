# YAWE

Chat de terminal com IA, com histórico de conversa e tratamento de erros. Funciona com:

- **Google Gemini** (grátis, chave em aistudio.google.com) — SDK `google-genai`
- **Anthropic / Claude** (pago) — SDK oficial `anthropic`
- **Vercel AI Gateway** — mesmo SDK `anthropic`, apontando para o gateway

O app escolhe o provedor sozinho conforme a chave que estiver no `.env`.

## Estrutura

```
main.py                # fluxo principal (loop de chat no terminal)
yawe/config.py         # leitura do .env e detecção do provedor
yawe/ai_client.py      # Claude (Anthropic ou Vercel) + create_chat()
yawe/gemini_client.py  # Google Gemini
```

## Como rodar

```bash
pip install -r requirements.txt
python main.py         # no Windows, se 'python' não funcionar: py main.py
```

Antes, crie um arquivo `.env` na pasta (veja `.env.example`) com **uma** destas linhas:

```
GEMINI_API_KEY=AIza...          # Google, grátis
AI_GATEWAY_API_KEY=vck_...      # Vercel
ANTHROPIC_API_KEY=sk-ant-...    # Anthropic
```

Comandos no chat: `/limpar` zera o histórico, `/sair` encerra.

## Configuração opcional

| Variável | Padrão | Descrição |
|---|---|---|
| `AI_MODEL` (ou `CLAUDE_MODEL`) | Google: `gemini-2.5-flash`; Vercel: `anthropic/claude-haiku-5.5`; Anthropic: `claude-opus-5-5` | Modelo |
| `CLAUDE_EFFORT` | `medium` | Só na Anthropic: `low` / `medium` / `high` / `xhigh` / `max` |
| `CLAUDE_MAX_TOKENS` | `16000` | Limite de tokens por resposta |
| `CLAUDE_SYSTEM_PROMPT` | assistente em pt-BR | Prompt de sistema |

Variáveis já exportadas no ambiente têm prioridade: o `.env` nunca as sobrescreve, e o código nunca escreve no `.env`.
