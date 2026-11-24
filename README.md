# YAWE

Chat de terminal integrado ao Claude via SDK oficial da Anthropic (`anthropic`).

## Estrutura

```
main.py            # fluxo principal (loop de chat no terminal)
yawe/config.py     # leitura do .env / variáveis de ambiente
yawe/ai_client.py  # integração com a API: histórico, streaming, tratamento de erros
```

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # só se você ainda não tiver um .env; depois coloque sua chave
python main.py
```

Comandos no chat: `/limpar` zera o histórico, `/sair` encerra.

## Configuração

| Variável | Padrão | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | — (obrigatória) | Sua chave da API |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Modelo |
| `CLAUDE_EFFORT` | `medium` | `low` / `medium` / `high` / `xhigh` / `max` |
| `CLAUDE_MAX_TOKENS` | `64000` | Limite de tokens por resposta |
| `CLAUDE_SYSTEM_PROMPT` | assistente em pt-BR | Prompt de sistema |

Variáveis já exportadas no ambiente têm prioridade: o `.env` nunca as sobrescreve, e o código nunca escreve no `.env`.
