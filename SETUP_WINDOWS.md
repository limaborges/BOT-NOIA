# Setup BOT-NOIA no Windows

## Contexto do Projeto

Sistema Martingale dual-account com dois modos:
- **G6_NS9** (Agressivo) - divisor 511 - roda no Linux
- **G6_NS10** (Conservador) - divisor 1023 - roda no Windows

### Cálculo da Aposta Base
- NS9: `saldo / 511` (ex: R$2000 → R$3.91)
- NS10: `saldo / 1023` (ex: R$2000 → R$1.96)

**IMPORTANTE:** O sistema de "Reserva de Lucros" deve estar DESATIVADO para G6_NS9 e G6_NS10.

---

## 1. Clonar o Repositório

```bash
cd C:\Users\SEU_USUARIO
git clone https://github.com/limaborges/BOT-NOIA.git MartingaleV2_Build
cd MartingaleV2_Build
```

---

## 2. Criar Ambiente Virtual

```bash
python -m venv venv
venv\Scripts\activate
pip install rich pyautogui opencv-python numpy pillow mss
```

---

## 3. Configuração do Dashboard (NOVO)

### 3.1 Instalar Tailscale

1. Baixe e instale: https://tailscale.com/download/windows
2. Abra o Tailscale e faça login com:
   - **Conta:** drlinnaldoborges@gmail.com (mesma do Linux)
3. Verifique: ícone Tailscale deve ficar verde (Connected)

### 3.2 Configurar sync_client.py

Edite o arquivo `sync_client.py` linha 38:

**Para CONSERVADORA (Windows Dual NS10):**
```python
MACHINE_ID = "conservadora"
```

**Para ISOLADA (Windows Solo NS10):**
```python
MACHINE_ID = "isolada"
```

### 3.3 Executar Sync Client

Abra um terminal separado e execute:

```bash
python sync_client.py
```

Saída esperada:
```
============================================================
  SYNC CLIENT - MartingaleV2 Dashboard
============================================================
  Maquina: CONSERVADORA
  Servidor: 192.168.0.200:8080
  Intervalo: 5s
============================================================

[21:45:00] OK | Saldo: R$ 2500.00 | Lucro: +2.50% | Uptime: 5h 30min
```

### 3.4 Rodar Sync em Background (Opcional)

Crie `start_sync.bat`:
```batch
@echo off
start /min python sync_client.py
```

---

## 4. Copiar Templates de Dígitos

A pasta `templates_matching/` deve conter:
- `0.png` até `9.png` - dígitos
- `ponto.png` - ponto decimal

Capturar da tela do jogo na resolução da máquina Windows.

---

## 5. Arquivos de Configuração (Não versionados)

- `session_state.json` - estado da sessão
- `reserva_state.json` - deve estar zerado para G6
- `machine_config.json` - configuração do navegador

### machine_config.json

**Firefox:**
```json
{
  "browser": "firefox",
  "machine_name": "Windows Dual"
}
```

**Chrome:**
```json
{
  "browser": "chrome",
  "machine_name": "Windows Isolada"
}
```

### reserva_state.json (zerado)
```json
{
  "banca_base": 0,
  "reserva_total": 0,
  "total_metas_batidas": 0,
  "lucro_acumulado": 0,
  "divida_reserva": 0.0,
  "total_emprestimos": 0,
  "total_emprestado": 0.0
}
```

---

## 6. Executar o Bot

```bash
venv\Scripts\python start_v2.py
```

Selecione o modo **G6_NS10** (conservador).

---

## 7. Sincronizar via Git

```bash
git pull                           # Receber alterações
git add -A && git commit -m "msg"  # Enviar alterações
git push
```

---

## 8. Troubleshooting

### Sync client não conecta
- Verificar Tailscale conectado (ícone verde)
- Testar: `ping 192.168.0.200`

### Dashboard não mostra a máquina
- Verificar sync_client.py rodando
- Verificar MACHINE_ID correto

### Aposta base pela metade
- Verificar `reserva_state.json` zerado
- Verificar modo G6_NS10

### Template matching não funciona
- Recapturar templates na resolução da máquina

---

## 9. IPs de Referência

| Dispositivo | IP Local | IP Tailscale |
|-------------|----------|--------------|
| Linux (Dashboard) | 192.168.0.200 | 100.78.98.1 |
| iPhone | - | 100.119.74.70 |

**Dashboard:** http://192.168.0.200:8080 (local) ou http://100.78.98.1:8080 (remoto)

---

## 10. Checklist Rápido

- [ ] Git clone feito
- [ ] venv criado e dependências instaladas
- [ ] Tailscale instalado e logado
- [ ] sync_client.py com MACHINE_ID correto
- [ ] templates_matching/ com PNGs
- [ ] machine_config.json criado
- [ ] Bot rodando (start_v2.py)
- [ ] Sync client rodando (sync_client.py)
- [ ] Máquina aparece no dashboard
