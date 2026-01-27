#!/usr/bin/env python3
"""
Reset de Sessão do Dashboard
============================
Execute este script quando iniciar uma nova sessão.

Opções:
  1. Usar saldo atual como depósito inicial (captura automaticamente)
  2. Definir valor manualmente
  3. Remover override (usar valor do session_state.json)
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'dashboard_config.json')
SESSION_FILE = os.path.join(BASE_DIR, 'session_state.json')


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Config salva em {CONFIG_FILE}")


def get_current_saldo():
    """Obtém saldo atual do session_state.json"""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r') as f:
            state = json.load(f)
        return state.get('saldo_atual', 0)
    return 0


def main():
    print("=" * 60)
    print("  RESET DE SESSÃO - Dashboard MartingaleV2")
    print("=" * 60)

    config = load_config()
    saldo_atual = get_current_saldo()

    print(f"\nSaldo atual (AGRESSIVA): R$ {saldo_atual:.2f}")
    print()
    print("Opções:")
    print(f"  1. Usar saldo atual (R$ {saldo_atual:.2f}) como depósito inicial")
    print("  2. Definir valor manualmente")
    print("  3. Remover override (usar session_state.json)")
    print("  4. Sair sem alterações")
    print()

    opcao = input("Escolha (1-4): ").strip()

    if opcao == '1':
        valor = saldo_atual
        print(f"\nUsando R$ {valor:.2f} como depósito inicial")
    elif opcao == '2':
        try:
            valor = float(input("Digite o valor do depósito inicial: R$ ").replace(',', '.'))
        except ValueError:
            print("Valor inválido!")
            return
    elif opcao == '3':
        valor = None
        print("\nRemovendo override - dashboard usará valor do session_state.json")
    else:
        print("Saindo sem alterações.")
        return

    # Perguntar para quais máquinas aplicar
    print()
    print("Aplicar para qual máquina?")
    print("  1. AGRESSIVA apenas")
    print("  2. CONSERVADORA apenas")
    print("  3. Ambas (DUAL)")
    print("  4. Todas (incluindo ISOLADA)")

    maquinas = input("Escolha (1-4): ").strip()

    if maquinas == '1':
        targets = ['agressiva']
    elif maquinas == '2':
        targets = ['conservadora']
    elif maquinas == '3':
        targets = ['agressiva', 'conservadora']
    elif maquinas == '4':
        targets = ['agressiva', 'conservadora', 'isolada']
    else:
        print("Opção inválida!")
        return

    # Aplicar
    for machine in targets:
        if machine not in config:
            config[machine] = {}
        config[machine]['deposito_inicial_override'] = valor

        if valor is not None:
            print(f"  {machine.upper()}: override = R$ {valor:.2f}")
        else:
            print(f"  {machine.upper()}: override removido")

    save_config(config)

    print()
    print("=" * 60)
    print("  IMPORTANTE: Reinicie o dashboard para aplicar!")
    print("  Comando: pkill -f dashboard_server && python3 dashboard_server.py &")
    print("=" * 60)


if __name__ == "__main__":
    main()
