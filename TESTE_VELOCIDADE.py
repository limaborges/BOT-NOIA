#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE DE VELOCIDADE DE APOSTAS
Testa diferentes configuracoes de velocidade com humanizacao.

INSTRUCOES:
1. Abra o site de apostas e posicione na tela
2. Execute este script
3. Escolha o modo de velocidade
4. Observe se as apostas entram corretamente
"""

import time
import json
import os

# Carregar config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

from autonomous_betting_v2 import AutonomousBettingV2

# Modos de velocidade para teste
MODOS = {
    '1': {
        'nome': 'LENTO (Seguro)',
        'click_delay': (0.08, 0.15),
        'paste_delay': (0.06, 0.10),
        'between_fields': (0.10, 0.15),
        'confirm_delay': (0.12, 0.18),
        'mouse_speed': (0.12, 0.20),
        'pause': 0.03
    },
    '2': {
        'nome': 'BALANCEADO (Atual)',
        'click_delay': (0.04, 0.08),
        'paste_delay': (0.03, 0.06),
        'between_fields': (0.06, 0.10),
        'confirm_delay': (0.08, 0.12),
        'mouse_speed': (0.08, 0.15),
        'pause': 0.02
    },
    '3': {
        'nome': 'RAPIDO',
        'click_delay': (0.02, 0.05),
        'paste_delay': (0.02, 0.04),
        'between_fields': (0.03, 0.06),
        'confirm_delay': (0.04, 0.08),
        'mouse_speed': (0.05, 0.10),
        'pause': 0.01
    },
    '4': {
        'nome': 'ULTRA RAPIDO',
        'click_delay': (0.01, 0.03),
        'paste_delay': (0.01, 0.02),
        'between_fields': (0.02, 0.04),
        'confirm_delay': (0.02, 0.05),
        'mouse_speed': (0.03, 0.07),
        'pause': 0.005
    }
}

def aplicar_modo(betting: AutonomousBettingV2, modo: dict):
    """Aplica configuracoes de velocidade"""
    import pyautogui
    betting.click_delay_range = modo['click_delay']
    betting.paste_delay_range = modo['paste_delay']
    betting.between_fields_delay = modo['between_fields']
    betting.confirm_delay_range = modo['confirm_delay']
    betting.mouse_speed_range = modo['mouse_speed']
    pyautogui.PAUSE = modo['pause']

def main():
    print("="*60)
    print("    TESTE DE VELOCIDADE DE APOSTAS")
    print("="*60)

    # Listar perfis
    profiles = list(config.get('profiles', {}).keys())
    print("\nPerfis disponiveis:")
    for i, p in enumerate(profiles, 1):
        print(f"  {i}. {p}")

    escolha = input("\nEscolha o perfil (numero): ").strip()
    try:
        profile = profiles[int(escolha) - 1]
    except:
        print("Perfil invalido!")
        return

    # Criar executor
    betting = AutonomousBettingV2(config, verbose=True)
    betting.set_profile(profile)

    while True:
        print("\n" + "="*60)
        print("MODOS DE VELOCIDADE:")
        print("="*60)
        for k, v in MODOS.items():
            delays = f"click:{v['click_delay'][0]*1000:.0f}-{v['click_delay'][1]*1000:.0f}ms"
            print(f"  {k}. {v['nome']:20} ({delays})")
        print("  0. SAIR")

        modo_escolha = input("\nEscolha o modo: ").strip()

        if modo_escolha == '0':
            break

        if modo_escolha not in MODOS:
            print("Modo invalido!")
            continue

        modo = MODOS[modo_escolha]
        aplicar_modo(betting, modo)

        print(f"\n>>> Modo {modo['nome']} aplicado!")
        print(f">>> Valor de teste: R$ 0.50 @ 1.50x")
        print(f">>> ATENCAO: Posicione o mouse no site!")

        input("\nPressione ENTER para executar 2 apostas consecutivas...")

        # Teste AMBOS os slots consecutivamente (como no sistema real)
        print("\n--- EXECUTANDO 2 SLOTS CONSECUTIVOS ---")
        inicio_total = time.time()

        print(">>> Slot 1: R$ 0.50 @ 1.99x")
        inicio1 = time.time()
        result1 = betting.execute_bet(0.50, 1.99, bet_slot=1)
        tempo1 = time.time() - inicio1
        print(f"    {'OK' if result1.success else 'FALHOU'} em {tempo1:.2f}s")

        print(">>> Slot 2: R$ 0.50 @ 1.25x")
        inicio2 = time.time()
        result2 = betting.execute_bet(0.50, 1.25, bet_slot=2)
        tempo2 = time.time() - inicio2
        print(f"    {'OK' if result2.success else 'FALHOU'} em {tempo2:.2f}s")

        tempo_total = time.time() - inicio_total
        print(f"\n>>> TEMPO TOTAL 2 SLOTS: {tempo_total:.2f}s")
        print(f"    Slot 1: {tempo1:.2f}s | Slot 2: {tempo2:.2f}s")

        print("\n" + "-"*40)
        aprovado = input("Velocidade OK? (s/n): ").strip().lower()

        if aprovado == 's':
            print(f"\n>>> MODO {modo['nome']} APROVADO!")
            print(f">>> Para aplicar permanentemente, edite autonomous_betting_v2.py")
            print(f">>> Valores:")
            print(f"    click_delay_range = {modo['click_delay']}")
            print(f"    paste_delay_range = {modo['paste_delay']}")
            print(f"    between_fields_delay = {modo['between_fields']}")
            print(f"    confirm_delay_range = {modo['confirm_delay']}")
            print(f"    mouse_speed_range = {modo['mouse_speed']}")
            print(f"    pyautogui.PAUSE = {modo['pause']}")
            break

if __name__ == '__main__':
    main()
