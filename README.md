# YAWE

Chat de terminal com IA, com histórico de conversa e tratamento de erros. Funciona com:

- **Google Gemini** (grátis, chave em aistudio.google.com) — SDK `google-genai`
- **Anthropic / Claude** (pago) — SDK oficial `anthropic`
- **Vercel AI Gateway** — mesmo SDK `anthropic`, apontando para o gateway

O app escolhe o provedor sozinho conforme a chave que estiver no `.env`.

Opcional: com `ELEVENLABS_API_KEY` no `.env`, a IA **fala as respostas** com uma voz da ElevenLabs.

## App no celular

`web.py` abre o assistente como um app web, pensado para o celular: chat com respostas em tempo real,
voz da ElevenLabs, microfone (reconhecimento de voz do navegador) e senha.

1. No `.env`, adicione `APP_PASSWORD=uma-senha-forte` (e, se quiser, `ASSISTANT_NAME=JARVIS`).
2. Rode `py web.py` ou dê dois cliques em **Abrir YAWE.bat**.
3. No celular, conectado no **mesmo Wi-Fi** do PC, abra o endereço mostrado na tela (ex.: `http://192.168.0.10:8000`).
4. Opcional: no menu do navegador, escolha **Adicionar à tela inicial** para ter o ícone do app.

## Estrutura

```
main.py                # chat no terminal
web.py                 # app web para o celular (Flask)
static/                # tela do app (HTML), ícones e manifest
yawe/config.py         # leitura do .env e detecção do provedor
yawe/ai_client.py      # Claude (Anthropic ou Vercel) + create_chat()
yawe/gemini_client.py  # Google Gemini
yawe/voice.py          # voz com a ElevenLabs (texto -> fala)
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

Comandos no chat: `/modelos` lista os modelos da sua chave, `/voz` liga/desliga a voz, `/vozes` lista as vozes da ElevenLabs, `/limpar` zera o histórico, `/sair` encerra.

## Configuração opcional

| Variável | Padrão | Descrição |
|---|---|---|
| `AI_MODEL` (ou `CLAUDE_MODEL`) | Google: `gemini-flash-latest` (se sumir, o app escolhe outro Flash disponível); Vercel: `anthropic/claude-haiku-5.5`; Anthropic: `claude-opus-5-5` | Modelo |
| `CLAUDE_EFFORT` | `medium` | Só na Anthropic: `low` / `medium` / `high` / `xhigh` / `max` |
| `CLAUDE_MAX_TOKENS` | `16000` | Limite de tokens por resposta |
| `AI_SYSTEM_PROMPT` | assistente em pt-BR, texto simples | Prompt de sistema |
| `ELEVENLABS_API_KEY` | — | Liga a voz da ElevenLabs |
| `ELEVENLABS_VOICE_ID` | `JBFqnCBsd6RMkjVDRZzb` (George) | Voz usada |
| `ELEVENLABS_MODEL` | `eleven_flash_v2_5` | Modelo de voz |
| `ELEVENLABS_MAX_CHARS` | `1000` | Máximo de caracteres falados por resposta |
| `APP_PASSWORD` | — (obrigatória no app web) | Senha para entrar no app |
| `ASSISTANT_NAME` | `YAWE` | Nome exibido no app |
| `PORT` | `8000` | Porta do app web |

Variáveis já exportadas no ambiente têm prioridade: o `.env` nunca as sobrescreve, e o código nunca escreve no `.env`.
