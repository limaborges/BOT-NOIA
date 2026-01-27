#!/usr/bin/env python3
"""
Setup automático do Dashboard Sync para Windows
Execute: python setup_dashboard.py

Este script:
1. Detecta qual máquina é (pergunta ao usuário)
2. Configura o sync_client.py com o MACHINE_ID correto
3. Testa conexão com o dashboard
4. Instruções para instalar Tailscale se necessário
"""

import os
import sys
import subprocess
import json
from pathlib import Path

DASHBOARD_SERVER = "192.168.0.200"
DASHBOARD_PORT = 8080

def get_machine_choice():
    """Pergunta qual máquina é esta."""
    print("\n" + "=" * 60)
    print("  SETUP DASHBOARD - MartingaleV2")
    print("=" * 60)
    print("\nQual é esta máquina?\n")
    print("  1. CONSERVADORA (Windows Dual NS10)")
    print("  2. ISOLADA (Windows Solo NS10)")
    print()

    while True:
        choice = input("Digite 1 ou 2: ").strip()
        if choice == "1":
            return "conservadora"
        elif choice == "2":
            return "isolada"
        else:
            print("Opção inválida. Digite 1 ou 2.")


def configure_sync_client(machine_id: str):
    """Configura o sync_client.py com o MACHINE_ID correto."""
    sync_client_path = Path(__file__).parent / "sync_client.py"

    if not sync_client_path.exists():
        print(f"[ERRO] sync_client.py não encontrado em {sync_client_path}")
        return False

    # Ler arquivo
    with open(sync_client_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Substituir MACHINE_ID
    import re
    new_content = re.sub(
        r'MACHINE_ID = "[^"]*"',
        f'MACHINE_ID = "{machine_id}"',
        content
    )

    # Salvar
    with open(sync_client_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[OK] sync_client.py configurado com MACHINE_ID = \"{machine_id}\"")
    return True


def test_connection():
    """Testa conexão com o dashboard."""
    import urllib.request
    import urllib.error

    url = f"http://{DASHBOARD_SERVER}:{DASHBOARD_PORT}/api/status"

    print(f"\nTestando conexão com {url}...")

    try:
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read().decode())
        print("[OK] Dashboard acessível!")
        return True
    except urllib.error.URLError as e:
        print(f"[ERRO] Não foi possível conectar: {e.reason}")
        return False
    except Exception as e:
        print(f"[ERRO] {e}")
        return False


def check_tailscale():
    """Verifica se Tailscale está instalado e conectado."""
    try:
        result = subprocess.run(
            ["tailscale", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("[OK] Tailscale instalado e conectado")
            return True
        else:
            return False
    except FileNotFoundError:
        return False
    except Exception:
        return False


def main():
    # 1. Escolher máquina
    machine_id = get_machine_choice()
    print(f"\nConfigurando como: {machine_id.upper()}")

    # 2. Configurar sync_client.py
    print("\n--- Configurando sync_client.py ---")
    if not configure_sync_client(machine_id):
        sys.exit(1)

    # 3. Verificar Tailscale
    print("\n--- Verificando Tailscale ---")
    if not check_tailscale():
        print("[AVISO] Tailscale não detectado ou não conectado")
        print("\nPara instalar Tailscale:")
        print("  1. Acesse: https://tailscale.com/download/windows")
        print("  2. Instale e faça login com: drlinnaldoborges@gmail.com")
        print("  3. Execute este script novamente")
        print("\nOu continue se estiver na rede local (192.168.0.x)")

    # 4. Testar conexão
    print("\n--- Testando conexão com Dashboard ---")
    if test_connection():
        print("\n" + "=" * 60)
        print("  SETUP COMPLETO!")
        print("=" * 60)
        print(f"\nPara iniciar o sync, execute em um terminal separado:")
        print(f"  python sync_client.py")
        print(f"\nDashboard: http://{DASHBOARD_SERVER}:{DASHBOARD_PORT}")
        print("=" * 60)
    else:
        print("\n[AVISO] Conexão falhou, mas a configuração está pronta.")
        print("Verifique se:")
        print("  - O Linux está ligado e o dashboard rodando")
        print("  - Você está na mesma rede OU Tailscale conectado")
        print(f"\nQuando resolver, execute: python sync_client.py")


if __name__ == "__main__":
    main()
