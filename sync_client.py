#!/usr/bin/env python3
"""
Sync Client para MartingaleV2 Dashboard
========================================
Envia dados da máquina local para o dashboard centralizado no Linux.

USO NAS MÁQUINAS WINDOWS:
1. Copie este arquivo para a pasta do bot
2. Ajuste MACHINE_ID conforme a máquina:
   - "conservadora" para Windows Dual NS10
   - "isolada" para Windows Solo NS10
3. Ajuste DASHBOARD_SERVER com o IP do Linux
4. Execute: python sync_client.py
"""

import json
import time
import os
import sys
from datetime import datetime
from pathlib import Path

# Usar urllib (já incluso no Python) ao invés de requests
import urllib.request
import urllib.error

# ============================================================
# CONFIGURAÇÃO - AJUSTE CONFORME SUA MÁQUINA
# ============================================================

# IP do servidor Linux onde o dashboard está rodando
DASHBOARD_SERVER = "192.168.0.200"
DASHBOARD_PORT = 8080

# Identificador desta máquina (escolha UM):
# - "conservadora" para Windows Dual NS10
# - "isolada" para Windows Solo NS10
MACHINE_ID = "conservadora"  # <-- AJUSTE AQUI

# Intervalo de envio em segundos
SYNC_INTERVAL = 5

# Caminho do session_state.json (padrão: mesmo diretório do script)
SESSION_STATE_PATH = Path(__file__).parent / "session_state.json"

# ============================================================
# FIM DA CONFIGURAÇÃO
# ============================================================

def load_session_state():
    """Carrega o estado da sessão do arquivo JSON."""
    if not SESSION_STATE_PATH.exists():
        return None

    try:
        with open(SESSION_STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERRO] Falha ao ler session_state.json: {e}")
        return None


def calcular_aposta_base(saldo: float, modo: str) -> float:
    """Calcula a aposta base baseado no saldo e modo (mesmo cálculo do bot)."""
    # NS9: divisor 511, NS10: divisor 1023
    if modo.lower() in ['g6_ns9', 'ns9']:
        divisor = 511
    else:  # NS10 (padrão)
        divisor = 1023

    return saldo / divisor if saldo > 0 else 0


def extract_data_from_state(state: dict) -> dict:
    """Extrai dados relevantes do session_state para enviar ao dashboard."""

    saldo = state.get("saldo_atual", 0)
    modo = state.get("config_modo", {}).get("modo", "g6_ns10")

    # Calcula aposta_base se não estiver no state
    aposta_base = state.get("aposta_base")
    if aposta_base is None or aposta_base == 0:
        aposta_base = calcular_aposta_base(saldo, modo)

    # Dados básicos
    data = {
        "saldo": saldo,
        "deposito_inicial": state.get("deposito_inicial", 0),
        "aposta_base": aposta_base,
        "nivel": state.get("nivel_atual", 10),
        "modo": modo,
        "lucro_para_subir": state.get("config_modo", {}).get("lucro_para_subir", 5.8),
        "total_rodadas": state.get("total_rodadas", 0),
        "sessoes_win": state.get("sessoes_win", 0),
        "sessoes_loss": state.get("sessoes_loss", 0),
        "uptime_start": state.get("sessao_inicio"),
    }

    # Último multiplicador
    ultimo_mult = state.get("ultimo_mult")
    ultimo_mult_time = state.get("ultimo_mult_time")

    if ultimo_mult:
        data["last_mult"] = ultimo_mult
        data["last_mult_time"] = ultimo_mult_time

    # Histórico de saldo
    historico = state.get("historico_saldo", [])
    data["historico_saldo"] = historico[-50:] if historico else []

    # Últimos gatilhos
    gatilhos = state.get("ultimos_gatilhos", [])
    data["ultimos_gatilhos"] = gatilhos[-10:] if gatilhos else []

    return data


def send_to_dashboard(data: dict) -> bool:
    """Envia dados para o dashboard via HTTP POST usando urllib."""
    url = f"http://{DASHBOARD_SERVER}:{DASHBOARD_PORT}/api/update/{MACHINE_ID}"

    try:
        json_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read().decode())

        if result.get('status') == 'ok':
            return True
        else:
            print(f"[ERRO] Servidor retornou: {result}")
            return False

    except urllib.error.URLError as e:
        print(f"[ERRO] Não foi possível conectar ao dashboard: {e.reason}")
        return False
    except Exception as e:
        print(f"[ERRO] Falha ao enviar dados: {e}")
        return False


def format_timedelta(start_time: str) -> str:
    """Formata o tempo desde o início como string legível."""
    if not start_time:
        return "N/A"

    try:
        start = datetime.fromisoformat(start_time)
        delta = datetime.now() - start
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}min"
    except:
        return "N/A"


def main():
    """Loop principal do sync client."""

    print("=" * 60)
    print("  SYNC CLIENT - MartingaleV2 Dashboard")
    print("=" * 60)
    print(f"  Maquina: {MACHINE_ID.upper()}")
    print(f"  Servidor: {DASHBOARD_SERVER}:{DASHBOARD_PORT}")
    print(f"  Intervalo: {SYNC_INTERVAL}s")
    print("=" * 60)
    print()

    # Verificar se session_state.json existe
    if not SESSION_STATE_PATH.exists():
        print(f"[AVISO] session_state.json nao encontrado em:")
        print(f"        {SESSION_STATE_PATH}")
        print(f"        Aguardando criacao do arquivo...")

    consecutive_errors = 0
    last_success_time = None

    while True:
        try:
            # Carregar estado
            state = load_session_state()

            if state is None:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Aguardando session_state.json...")
                time.sleep(SYNC_INTERVAL)
                continue

            # Extrair dados
            data = extract_data_from_state(state)

            # Enviar para dashboard
            success = send_to_dashboard(data)

            if success:
                consecutive_errors = 0
                last_success_time = datetime.now()

                # Log compacto de sucesso
                saldo = data.get("saldo", 0)
                lucro = saldo - data.get("deposito_inicial", saldo)
                deposito = data.get("deposito_inicial", 0)
                lucro_pct = (lucro / deposito) * 100 if deposito > 0 else 0
                uptime = format_timedelta(data.get("uptime_start"))

                print(f"[{datetime.now().strftime('%H:%M:%S')}] OK | "
                      f"Saldo: R$ {saldo:.2f} | "
                      f"Lucro: {lucro_pct:+.2f}% | "
                      f"Uptime: {uptime}")
            else:
                consecutive_errors += 1

                if consecutive_errors >= 5:
                    print(f"[AVISO] {consecutive_errors} erros consecutivos. Verificar conexao.")

                    if consecutive_errors >= 20:
                        print("[ERRO] Muitos erros consecutivos. Aguardando 30s...")
                        time.sleep(30)

            time.sleep(SYNC_INTERVAL)

        except KeyboardInterrupt:
            print("\n[INFO] Sync client encerrado pelo usuario.")
            break
        except Exception as e:
            print(f"[ERRO] Excecao no loop principal: {e}")
            time.sleep(SYNC_INTERVAL)


if __name__ == "__main__":
    main()
