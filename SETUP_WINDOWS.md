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

## 10. Atalhos de Teclado (Durante operação)

| Tecla | Função |
|-------|--------|
| **R** | Redefinir sessão (reset parcial) - salva lucro no acumulado |
| **T** | Testar slots de aposta |
| **C** | Alternar modo compacto/expandido |
| **Q** | Sair do bot |

### Comando R - Redefinir Sessão
Use quando redistribuir lucros:
1. Pressione **R** para abrir o menu
2. Escolha o novo modo:
   - `1` = NS9 (Agressivo)
   - `2` = NS10 (Conservador)
   - `3` = Manter modo atual
   - `0` = Cancelar
3. Digite **s** e pressione **ENTER** para confirmar

Isso salva o lucro atual no acumulado e reseta os contadores.

**Nota:** Se a confirmação não funcionar, verifique se digitou 's' (minúsculo) e pressionou ENTER.

---

## 11. Dashboard - Funcionalidades

### Labels Dinâmicos
O dashboard mostra o nome baseado no MODO, não na máquina:
- **NS9** → Aparece como "AGRESSIVA" (vermelho)
- **NS10** → Aparece como "CONSERVADORA" (cyan)

Se inverter os modos entre máquinas, os nomes também invertem.

### Gráfico Unificado
- Um gráfico no topo mostra o **% de lucro** de todas as máquinas
- Cada máquina tem uma cor diferente (vermelho, cyan, roxo)

### Métricas
- **Lucro Sessão**: Lucro desde o início da sessão atual (R$ e %)
- **Lucro Total**: Lucro sessão + lucro acumulado anterior
- **Últimos 10 Ciclos**: Mostra horário, tentativa (T1, T2...) e resultado

### Barra de Progresso NS9→NS10
- Aparece para qualquer máquina em modo NS9
- Mostra progresso da meta de lucro para migrar para NS10

---

## 12. Atualizar Código (Git Pull)

Quando houver atualizações no repositório:

```bash
cd C:\Users\SEU_USUARIO\MartingaleV2_Build
git pull
```

**Após atualizar:**
1. Reinicie o bot (`start_v2.py`)
2. Reinicie o sync client (`sync_client.py`)

---

## 13. Checklist Rápido

- [ ] Git clone feito
- [ ] venv criado e dependências instaladas
- [ ] Tailscale instalado e logado
- [ ] sync_client.py com MACHINE_ID correto
- [ ] templates_matching/ com PNGs
- [ ] machine_config.json criado
- [ ] Bot rodando (start_v2.py)
- [ ] Sync client rodando (sync_client.py)
- [ ] Máquina aparece no dashboard
