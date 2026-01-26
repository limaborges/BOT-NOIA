# Setup BOT-NOIA no Windows

## Contexto do Projeto

Sistema Martingale dual-account com dois modos:
- **G6_NS9** (Agressivo) - divisor 511 - roda no Linux
- **G6_NS10** (Conservador) - divisor 1023 - roda no Windows

### Cálculo da Aposta Base
- NS9: `saldo / 511` (ex: R$2000 → R$3.91)
- NS10: `saldo / 1023` (ex: R$2000 → R$1.96)

**IMPORTANTE:** O sistema de "Reserva de Lucros" deve estar DESATIVADO para G6_NS9 e G6_NS10. Se aparecer "Reserva de Lucros" na interface ou a aposta base estiver pela metade do esperado, há um bug.

---

## 1. Clonar o Repositório

Abra o terminal (CMD ou PowerShell) no diretório desejado:

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

## 3. Copiar Templates de Dígitos

A pasta `templates_matching/` contém os PNGs para detecção de multiplicadores via template matching.

Se não existir no clone, crie a pasta e adicione os arquivos:
- `0.png` até `9.png` - dígitos
- `ponto.png` - ponto decimal

Esses templates devem ser capturados da tela do jogo na resolução específica da máquina Windows.

---

## 4. Arquivos de Configuração da Máquina (Não versionados)

Estes arquivos são específicos de cada máquina e não vão pro Git:

- `session_state.json` - estado da sessão atual
- `reserva_state.json` - estado da reserva (deve estar zerado para G6_NS9/G6_NS10)
- `telegram_config.json` - configuração do Telegram
- `sync_config.json` - configuração de sync dual account
- `machine_config.json` - configuração da máquina (navegador, etc)

### Configuração do Navegador (machine_config.json)

Crie o arquivo `machine_config.json`:

**Para Firefox:**
```json
{
  "browser": "firefox",
  "machine_name": "Windows Dual"
}
```

**Para Chrome:**
```json
{
  "browser": "chrome",
  "machine_name": "Windows Isolada"
}
```

Se o arquivo não existir, o padrão é Firefox.

Se `reserva_state.json` existir com valores, zere-o:
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

## 5. Executar o Bot

```bash
venv\Scripts\python start_v2.py
```

Selecione o modo **G6_NS10** (conservador) para Windows.

---

## 6. Sincronizar Alterações via Git

### Receber alterações do Linux:
```bash
git pull
```

### Enviar alterações para o Linux:
```bash
git add -A
git commit -m "descrição da alteração"
git push
```

---

## 7. Troubleshooting

### Aposta base está pela metade do esperado
- Verifique se `reserva_state.json` está zerado
- Verifique se o modo é G6_NS9 ou G6_NS10
- O código em `hybrid_system_v2.py` deve ter G6_NS9/G6_NS10 na lista `modos_sem_reserva`

### Template matching não funciona
- Verifique se a pasta `templates_matching/` existe com os PNGs
- Os templates devem corresponder à resolução/escala do jogo nesta máquina
- Pode ser necessário recapturar os templates

### Autonomous betting não executa
- Verifique se `pyautogui` está instalado
- No Windows, pode precisar rodar como administrador
- Verifique as coordenadas do campo de aposta em `config.json`

### Git pede credenciais
Configure SSH key ou use token:
```bash
git remote set-url origin https://SEU_TOKEN@github.com/limaborges/BOT-NOIA.git
```

---

## 8. Estrutura de Arquivos Importantes

```
MartingaleV2_Build/
├── start_v2.py              # Ponto de entrada
├── hybrid_system_v2.py      # Lógica principal do bot
├── hybrid_ui_rich.py        # Interface terminal
├── martingale_session.py    # Cálculos Martingale (DIVISOR por nível)
├── vision_system.py         # Detecção de multiplicadores (template matching)
├── autonomous_betting_v2.py # Apostas automáticas
├── templates_matching/      # PNGs dos dígitos (específico da máquina)
├── config.json              # Coordenadas de tela
├── session_state.json       # Estado da sessão (não versionado)
├── reserva_state.json       # Estado da reserva (não versionado)
└── venv/                    # Ambiente virtual (não versionado)
```

---

## 9. Configuração de Coordenadas

O arquivo `config.json` contém as coordenadas de tela. Se o layout do jogo for diferente no Windows, ajuste:

- Região do saldo
- Região do multiplicador
- Campo de aposta
- Botão de apostar

Use `ocr_debug.py` para testar as regiões.

---

## 10. Sincronização em Tempo Real (Dual Account)

O sistema permite sincronizar estado entre máquinas para o Telegram unificado.

### Quando HABILITAR (máquina participa do dual):

Crie o arquivo `sync_config.json` na pasta do bot:
```json
{
  "server_ip": "192.168.0.200",
  "server_port": 5555,
  "enabled": true
}
```

- `server_ip`: IP da máquina Linux que roda o `sync_server.py`
- `server_port`: Porta do servidor (padrão 5555)
- `enabled`: true para ativar sincronização

### Quando NÃO HABILITAR (máquina opera isolada):

**Não crie o arquivo `sync_config.json`.**

Sem o arquivo, o sync fica automaticamente desabilitado e a máquina opera de forma independente, sem interferir no sistema dual.

### Resumo:

| Máquina | sync_config.json | Resultado |
|---------|------------------|-----------|
| Linux (servidor) | Não precisa | Roda `sync_server.py` |
| Windows (dual) | **Criar** | Envia dados para Linux |
| Windows (isolada) | **Não criar** | Opera independente |

### Testar conexão:

```bash
python sync_client.py
```

Se configurado corretamente, mostrará "Servidor online!".
