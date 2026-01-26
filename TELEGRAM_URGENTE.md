# URGENTE: Configuração do Telegram por Máquina

## Problema Atual

Todas as máquinas estão enviando dados para o MESMO bot Telegram, causando mistura de dados.

## Solução

Cada máquina deve ter sua própria configuração:

---

## MÁQUINA: Windows DUAL (CONSERVADORA)

**Esta máquina NÃO deve usar Telegram.**

### Ação necessária:

Criar/editar o arquivo `telegram_config.json` na pasta do bot:

```json
{
  "enabled": false
}
```

Ou simplesmente **deletar** o arquivo `telegram_config.json`.

### Por quê?
- O Telegram do sistema dual roda no LINUX
- Esta máquina só envia dados via sync_client para o Linux
- O Linux agrega e mostra no Telegram

---

## MÁQUINA: Windows ISOLADA

**Esta máquina deve usar seu PRÓPRIO bot Telegram: @JaceNoiaBot**

### Ação necessária:

1. O usuário já criou o bot **@JaceNoiaBot** no @BotFather
2. Editar `telegram_config.json` com o token do JaceNoiaBot:

```json
{
  "token": "TOKEN_DO_JACENOIA_BOT",
  "chat_id": "7460639576",
  "enabled": true
}
```

### Para obter o token do JaceNoiaBot:

1. Abrir Telegram → @BotFather
2. Enviar `/mybots`
3. Selecionar @JaceNoiaBot
4. Clicar em "API Token"
5. Copiar o token

### IMPORTANTE:
- O token do JaceNoiaBot é DIFERENTE do Martingale_NS
- O chat_id permanece o mesmo (7460639576 - é o ID do usuário)
- Se o bot não responder, verificar se o token está correto

---

## Como verificar qual token está configurado

Ler o arquivo `telegram_config.json` e verificar o campo `token`.

Se o token começar com `8003112238:` → É o token ANTIGO (errado para Windows)

---

## Após configurar

1. Reiniciar o bot
2. O Telegram deve parar de mostrar dados misturados

---

## Resumo Visual

```
┌─────────────────────────────────────────────────┐
│           LINUX (AGRESSIVA)                     │
│  telegram_config.json:                          │
│  {                                              │
│    "token": "8003112238:AAH...",  ← Token antigo│
│    "chat_id": "7460639576",                     │
│    "enabled": true                              │
│  }                                              │
│  → Roda telegram_bot.py                         │
│  → Mostra dados do DUAL (Linux + Win Dual)      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│           WINDOWS DUAL (CONSERVADORA)           │
│  telegram_config.json:                          │
│  {                                              │
│    "enabled": false                             │
│  }                                              │
│  → NÃO roda telegram                            │
│  → Só envia dados via sync_client               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│           WINDOWS ISOLADA                       │
│  telegram_config.json:                          │
│  {                                              │
│    "token": "NOVO_TOKEN_DIFERENTE",             │
│    "chat_id": "7460639576",                     │
│    "enabled": true                              │
│  }                                              │
│  → Roda telegram_bot.py com BOT PRÓPRIO         │
│  → Mostra dados APENAS desta máquina            │
└─────────────────────────────────────────────────┘
```
