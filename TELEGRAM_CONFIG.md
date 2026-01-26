# Configuração Telegram - BOT-NOIA

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    BOT DUAL (Bot 1)                     │
│              Token: Martingale_NS (atual)               │
├─────────────────────────────────────────────────────────┤
│  Linux (AGRESSIVA)     ←──sync──→    Windows (CONSERV)  │
│  - Roda telegram_bot.py              - Roda sync_client │
│  - Roda sync_server.py               - SEM telegram     │
│  - Mostra dados das DUAS contas                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  BOT ISOLADO (Bot 2)                    │
│              Token: @JaceNoiaBot                        │
├─────────────────────────────────────────────────────────┤
│  Windows Isolada                                        │
│  - Roda telegram_bot.py                                 │
│  - SEM sync (não criar sync_config.json)                │
│  - Mostra dados APENAS desta máquina                    │
└─────────────────────────────────────────────────────────┘
```

---

## Configuração por Máquina

### 1. Linux (AGRESSIVA - Dual)

**telegram_config.json:**
```json
{
  "token": "TOKEN_DO_BOT_DUAL",
  "chat_id": "SEU_CHAT_ID",
  "enabled": true
}
```

**Serviços ativos:**
- `telegram_bot.py` ✅
- `sync_server.py` ✅

---

### 2. Windows Dual (CONSERVADORA)

**telegram_config.json:** NÃO CRIAR ou `enabled: false`
```json
{
  "enabled": false
}
```

**Ou simplesmente delete o arquivo `telegram_config.json`**

**sync_config.json:** CRIAR
```json
{
  "server_ip": "192.168.0.200",
  "server_port": 5555,
  "enabled": true
}
```

**Serviços ativos:**
- `telegram_bot.py` ❌ (desabilitado)
- `sync_client.py` ✅ (integrado no bot)

---

### 3. Windows Isolada

**telegram_config.json:** USAR TOKEN DO @JaceNoiaBot
```json
{
  "token": "TOKEN_DO_JACENOIA_BOT",
  "chat_id": "7460639576",
  "enabled": true
}
```

**sync_config.json:** NÃO CRIAR

**Serviços ativos:**
- `telegram_bot.py` ✅ (com token do JaceNoiaBot)
- `sync_client.py` ❌ (desabilitado)

---

## Como obter o token do @JaceNoiaBot

1. Abrir Telegram → @BotFather
2. Enviar `/mybots`
3. Selecionar @JaceNoiaBot
4. Clicar em "API Token"
5. Copiar o token

---

## Comandos do Bot Dual

| Comando | Descrição |
|---------|-----------|
| `/status` | Status da conta local (AGRESSIVA) |
| `/dual` | Status combinado AGRESSIVA + CONSERVADORA |
| `/help` | Lista de comandos |

---

## Comandos do Bot Isolado

| Comando | Descrição |
|---------|-----------|
| `/status` | Status da conta isolada |
| `/help` | Lista de comandos |

O comando `/dual` não faz sentido na máquina isolada.

---

## Verificar se está correto

### No Linux:
```bash
# Telegram rodando?
ps aux | grep telegram_bot

# Sync server rodando?
ps aux | grep sync_server
```

### No Windows Dual:
- `telegram_config.json` NÃO existe ou `enabled: false`
- `sync_config.json` existe com `enabled: true`

### No Windows Isolado:
- `telegram_config.json` existe com TOKEN DIFERENTE
- `sync_config.json` NÃO existe
