# Git Workflow - BOT-NOIA

## Repositório

- **URL:** https://github.com/limaborges/BOT-NOIA.git
- **SSH:** git@github.com:limaborges/BOT-NOIA.git
- **Branch principal:** master
- **Visibilidade:** Público

---

## Máquinas Conectadas

| Máquina | Sistema | Função | Modo |
|---------|---------|--------|------|
| Acer Nitro Lima | Linux | AGRESSIVA + Sync Server | G6_NS9 |
| Windows Dual | Windows | CONSERVADORA | G6_NS10 |
| Windows Isolada | Windows | Opera independente | G6_NS10 |

---

## Configuração Inicial (Já Feita no Linux)

### SSH Key configurada:
```
~/.ssh/id_ed25519 (privada)
~/.ssh/id_ed25519.pub (pública - adicionada no GitHub)
```

### Usuário Git:
```
Nome: Linnaldo
Email: drlinnaldoborges@gmail.com
```

### Remote configurado:
```
origin -> git@github.com:limaborges/BOT-NOIA.git (SSH)
```

---

## Comandos Diários

### Ver status das alterações:
```bash
git status
```

### Enviar alterações para o GitHub:
```bash
git add -A && git commit -m "descrição do que mudou" && git push
```

### Receber alterações do GitHub:
```bash
git pull
```

### Ver histórico de commits:
```bash
git log --oneline -10
```

---

## Arquivos NÃO Versionados (.gitignore)

Estes arquivos são específicos de cada máquina:

- `session_state.json` - estado da sessão
- `reserva_state.json` - estado da reserva
- `sync_config.json` - config de sincronização dual
- `telegram_config.json` - config do Telegram
- `venv/` - ambiente virtual Python
- `*.log` - arquivos de log
- `__pycache__/` - cache Python

---

## Fluxo de Trabalho

### Alteração feita no Linux:
```bash
# 1. No Linux (após fazer alterações)
git add -A
git commit -m "descrição"
git push

# 2. Nas outras máquinas (para receber)
git pull
```

### Alteração feita no Windows:
```bash
# 1. No Windows (após fazer alterações)
git add -A
git commit -m "descrição"
git push

# 2. No Linux e outras máquinas (para receber)
git pull
```

---

## Resolução de Conflitos

Se duas máquinas alterarem o mesmo arquivo:

```bash
# Ao fazer pull, pode dar conflito
git pull

# Se houver conflito, edite os arquivos marcados
# Depois:
git add -A
git commit -m "resolve conflito"
git push
```

---

## Troubleshooting

### "Permission denied (publickey)"
A SSH key não está configurada ou não foi adicionada ao GitHub.
```bash
# Verificar se a chave existe
cat ~/.ssh/id_ed25519.pub

# Se não existir, criar:
ssh-keygen -t ed25519 -C "drlinnaldoborges@gmail.com"

# Adicionar a chave pública no GitHub:
# Settings → SSH and GPG keys → New SSH key
```

### "fatal: not a git repository"
Você está no diretório errado.
```bash
cd /home/linnaldonitro/MartingaleV2_Build
```

### "Your branch is behind"
Há commits no GitHub que você não tem localmente.
```bash
git pull
```

### "Your branch is ahead"
Você tem commits locais que não estão no GitHub.
```bash
git push
```

### "Merge conflict"
Duas pessoas alteraram o mesmo arquivo.
```bash
# Abra os arquivos com conflito (marcados com <<<<< e >>>>>)
# Edite manualmente para resolver
# Depois:
git add -A
git commit -m "resolve conflito"
git push
```

---

## Verificar Conexão com GitHub

```bash
# Testar SSH
ssh -T git@github.com

# Resposta esperada:
# Hi limaborges! You've successfully authenticated...
```

---

## Estrutura do Repositório

```
BOT-NOIA/
├── start_v2.py              # Ponto de entrada
├── hybrid_system_v2.py      # Lógica principal
├── hybrid_ui_rich.py        # Interface terminal
├── martingale_session.py    # Cálculos Martingale
├── vision_system.py         # Detecção via template matching
├── autonomous_betting_v2.py # Apostas automáticas
├── sync_server.py           # Servidor de sync (Linux)
├── sync_client.py           # Cliente de sync (Windows)
├── templates_matching/      # PNGs dos dígitos
├── iniciar.bat              # Iniciar no Windows
├── iniciar.sh               # Iniciar no Linux
├── SETUP_WINDOWS.md         # Guia setup Windows
├── GIT_WORKFLOW.md          # Este arquivo
└── .gitignore               # Arquivos ignorados
```

---

## Resumo Rápido

| Ação | Comando |
|------|---------|
| Ver mudanças | `git status` |
| Enviar | `git add -A && git commit -m "msg" && git push` |
| Receber | `git pull` |
| Histórico | `git log --oneline -10` |
| Testar SSH | `ssh -T git@github.com` |
