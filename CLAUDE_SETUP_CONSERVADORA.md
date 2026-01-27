# INSTRUÇÕES PARA CLAUDE CODE - MÁQUINA CONSERVADORA

## EXECUTE ESTAS TAREFAS NA ORDEM:

### 1. Configurar sync_client.py
Edite o arquivo `sync_client.py` e altere a linha 38 de:
```python
MACHINE_ID = "conservadora"  # <-- AJUSTE AQUI
```
Para:
```python
MACHINE_ID = "conservadora"
```
(Confirme que está "conservadora")

### 2. Instalar Tailscale
Execute no terminal:
```bash
winget install Tailscale.Tailscale
```

Se winget não funcionar, informe o usuário para baixar manualmente de:
https://tailscale.com/download/windows

### 3. Instruir usuário sobre Tailscale
Diga ao usuário:
"Abra o Tailscale e faça login com a conta drlinnaldoborges@gmail.com (mesma conta do Linux e iPhone)"

### 4. Testar conexão com dashboard
Execute:
```bash
curl http://192.168.0.200:8080/api/status
```
Ou se curl não existir:
```bash
python -c "import urllib.request; print(urllib.request.urlopen('http://192.168.0.200:8080/api/status', timeout=5).read().decode())"
```

### 5. Iniciar sync client em background
Crie o arquivo `start_sync.bat` com o conteúdo:
```batch
@echo off
start /min python sync_client.py
```

Depois execute:
```bash
start_sync.bat
```

### 6. Confirmar funcionamento
Diga ao usuário:
"Setup completo! A máquina CONSERVADORA deve aparecer no dashboard em http://100.78.98.1:8080"

---

## RESUMO DO QUE ESTA MÁQUINA É:
- Nome: CONSERVADORA
- Tipo: Windows Dual NS10
- Função: Conta conservadora do sistema dual
- MACHINE_ID: conservadora
