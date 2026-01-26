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
│              Token: CRIAR NOVO no @BotFather            │
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

**telegram_config.json:** CRIAR COM NOVO TOKEN
```json
{
  "token": "TOKEN_DO_BOT_ISOLADO",
  "chat_id": "SEU_CHAT_ID",
  "enabled": true
}
```

**sync_config.json:** NÃO CRIAR

**Serviços ativos:**
- `telegram_bot.py` ✅ (com token diferente)
- `sync_client.py` ❌ (desabilitado)

---

## Criar Novo Bot no Telegram

1. Abra o Telegram e procure @BotFather
2. Envie `/newbot`
3. Dê um nome: `MartingaleIsolado` (ou outro)
4. Dê um username: `MartingaleIsolado_bot` (deve terminar com _bot)
5. Copie o token gerado
6. Use esse token no `telegram_config.json` da máquina isolada

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
