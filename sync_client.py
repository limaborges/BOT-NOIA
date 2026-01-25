#!/usr/bin/env python3
"""
Cliente HTTP para sincronizar estado com o servidor Linux.
Roda no Windows e envia atualizações para o Linux.

USO NO WINDOWS:
1. Copie este arquivo para a pasta do bot CONSERVADORA
2. Configure o IP do Linux abaixo
3. Importe e use as funções para enviar atualizações
"""

import urllib.request
import urllib.error
import json
from datetime import datetime
from typing import Optional, Dict

# ========== CONFIGURAÇÃO VIA ARQUIVO ==========
# Crie o arquivo sync_config.json com:
# {"server_ip": "192.168.0.200", "server_port": 5555, "enabled": true}
# Se o arquivo não existir, sync fica DESABILITADO
# ===============================================

import os

SYNC_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "sync_config.json")
SYNC_ENABLED = False
LINUX_SERVER_IP = ""
LINUX_SERVER_PORT = 5555

# Carregar config se existir
if os.path.exists(SYNC_CONFIG_FILE):
    try:
        with open(SYNC_CONFIG_FILE, 'r') as f:
            _config = json.load(f)
            LINUX_SERVER_IP = _config.get('server_ip', '')
            LINUX_SERVER_PORT = _config.get('server_port', 5555)
            SYNC_ENABLED = _config.get('enabled', False) and LINUX_SERVER_IP
            if SYNC_ENABLED:
                print(f"[SYNC] Habilitado - servidor: {LINUX_SERVER_IP}:{LINUX_SERVER_PORT}")
    except Exception as e:
        print(f"[SYNC] Erro ao ler config: {e}")
        SYNC_ENABLED = False
else:
    print("[SYNC] Desabilitado - sync_config.json não encontrado")

BASE_URL = f"http://{LINUX_SERVER_IP}:{LINUX_SERVER_PORT}" if SYNC_ENABLED else ""


def ping_server() -> bool:
    """Verifica se o servidor Linux está online"""
    if not SYNC_ENABLED:
        return False
    try:
        req = urllib.request.urlopen(f"{BASE_URL}/ping", timeout=5)
        data = json.loads(req.read().decode())
        return data.get('status') == 'ok'
    except Exception as e:
        print(f"[SYNC] Erro ao conectar com Linux: {e}")
        return False


def enviar_estado_conservadora(
    saldo_inicial: float,
    saldo_atual: float,
    modo: str = "NS10",
    ciclos_completos: int = 0,
    ciclo_atual: int = 0,
    operando: bool = True,
    info_extra: Optional[Dict] = None
) -> bool:
    """
    Envia o estado atual da conta CONSERVADORA para o servidor Linux.

    Args:
        saldo_inicial: Saldo inicial do dia
        saldo_atual: Saldo atual
        modo: Modo de operação (sempre NS10 para conservadora)
        ciclos_completos: Número de ciclos completos
        ciclo_atual: Posição no ciclo atual (0-6 gatilho)
        operando: Se está operando ou pausado
        info_extra: Informações adicionais opcionais

    Returns:
        True se enviou com sucesso, False caso contrário
    """
    estado = {
        'conta': 'CONSERVADORA',
        'saldo_inicial': saldo_inicial,
        'saldo_atual': saldo_atual,
        'modo': modo,
        'ciclos_completos': ciclos_completos,
        'ciclo_atual': ciclo_atual,
        'operando': operando,
        'lucro_dia': saldo_atual - saldo_inicial,
        'lucro_percentual': ((saldo_atual / saldo_inicial) - 1) * 100 if saldo_inicial > 0 else 0,
        'timestamp': datetime.now().isoformat()
    }

    if info_extra:
        estado.update(info_extra)

    try:
        data = json.dumps(estado).encode('utf-8')
        req = urllib.request.Request(
            f"{BASE_URL}/update",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read().decode())

        if result.get('status') == 'ok':
            print(f"[SYNC] Estado enviado: R$ {saldo_atual:.2f} ({estado['lucro_percentual']:+.2f}%)")
            return True
        else:
            print(f"[SYNC] Erro na resposta: {result}")
            return False

    except urllib.error.URLError as e:
        print(f"[SYNC] Erro de conexão: {e}")
        return False
    except Exception as e:
        print(f"[SYNC] Erro ao enviar estado: {e}")
        return False


def enviar_atualizacao_simples(saldo_atual: float, saldo_inicial: float = None) -> bool:
    """
    Versão simplificada - só precisa do saldo atual.
    Se saldo_inicial não for informado, usa o último enviado.
    """
    # Tenta ler o último estado para pegar o saldo_inicial
    if saldo_inicial is None:
        try:
            req = urllib.request.urlopen(f"{BASE_URL}/status", timeout=5)
            data = json.loads(req.read().decode())
            saldo_inicial = data.get('saldo_inicial', saldo_atual)
        except:
            saldo_inicial = saldo_atual

    return enviar_estado_conservadora(
        saldo_inicial=saldo_inicial,
        saldo_atual=saldo_atual
    )


# ========== EXEMPLO DE USO ==========
if __name__ == '__main__':
    print("Testando conexão com servidor Linux...")

    if ping_server():
        print("Servidor online! Enviando estado de teste...")

        # Exemplo: enviar estado
        sucesso = enviar_estado_conservadora(
            saldo_inicial=2000.00,
            saldo_atual=2050.00,
            ciclos_completos=5,
            ciclo_atual=3
        )

        if sucesso:
            print("Estado enviado com sucesso!")
        else:
            print("Falha ao enviar estado.")
    else:
        print("Servidor Linux offline ou inacessível.")
        print(f"Verifique se o servidor está rodando em {LINUX_SERVER_IP}:{LINUX_SERVER_PORT}")
