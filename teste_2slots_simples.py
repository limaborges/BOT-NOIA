#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE SIMPLES - 2 SLOTS SEQUENCIAIS
R$ 1,00 @ 1.01x em cada slot

Fluxo por slot:
1. Clicar campo valor
2. Ctrl+A -> Delete -> Ctrl+V (colar valor)
3. Clicar campo alvo
4. Ctrl+A -> Delete -> Ctrl+V (colar alvo)
5. Clicar botao APOSTAR
"""

import time
import json
from colorama import Fore, init

init(autoreset=True)

from autonomous_betting_v2 import AutonomousBettingV2

def main():
    print(f"{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}  TESTE 2 SLOTS - R$ 1,00 @ 1.01x cada")
    print(f"{Fore.CYAN}{'='*50}")

    # Carregar config
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Usar perfil LG FULL 90% 2 SLOTS
    perfil = "LG FULL 90% 2 SLOTS"

    print(f"\n{Fore.WHITE}Perfil: {perfil}")

    # Inicializar
    betting = AutonomousBettingV2(config, verbose=True)
    if not betting.set_profile(perfil):
        print(f"{Fore.RED}Erro ao configurar perfil!")
        return

    # Valores de teste
    valor = 1.00
    alvo = 1.01

    print(f"\n{Fore.YELLOW}ATENCAO: Vai apostar R$ 1,00 @ 1.01x em CADA slot!")
    print(f"{Fore.YELLOW}Total: R$ 2,00")
    print(f"\n{Fore.WHITE}Certifique-se que:")
    print(f"  - O site esta aberto e visivel")
    print(f"  - Nao ha aposta pendente")
    print(f"  - A rodada ainda nao comecou")

    input(f"\n{Fore.CYAN}Pressione ENTER para iniciar...{Fore.WHITE}")

    print(f"\n{Fore.GREEN}INICIANDO TESTE...")

    inicio_total = time.time()

    # ===== SLOT 1 =====
    print(f"\n{Fore.YELLOW}--- SLOT 1 ---{Fore.WHITE}")
    inicio1 = time.time()
    resultado1 = betting.execute_bet(valor, alvo, bet_slot=1)
    tempo1 = time.time() - inicio1

    if resultado1.success:
        print(f"{Fore.GREEN}Slot 1: OK em {tempo1:.2f}s")
    else:
        print(f"{Fore.RED}Slot 1: FALHA - {resultado1.error_message}")
        print(f"{Fore.RED}Abortando teste.")
        return

    # ===== SLOT 2 =====
    print(f"\n{Fore.YELLOW}--- SLOT 2 ---{Fore.WHITE}")
    inicio2 = time.time()
    resultado2 = betting.execute_bet(valor, alvo, bet_slot=2)
    tempo2 = time.time() - inicio2

    if resultado2.success:
        print(f"{Fore.GREEN}Slot 2: OK em {tempo2:.2f}s")
    else:
        print(f"{Fore.RED}Slot 2: FALHA - {resultado2.error_message}")

    tempo_total = time.time() - inicio_total

    # ===== RESULTADO =====
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}  RESULTADO")
    print(f"{Fore.CYAN}{'='*50}")
    print(f"\n{Fore.WHITE}Slot 1: {tempo1:.2f}s")
    print(f"{Fore.WHITE}Slot 2: {tempo2:.2f}s")
    print(f"\n{Fore.GREEN}TEMPO TOTAL: {tempo_total:.2f}s{Fore.WHITE}")

    if tempo_total < 2.0:
        print(f"\n{Fore.GREEN}EXCELENTE! Rapido o suficiente.")
    elif tempo_total < 3.0:
        print(f"\n{Fore.YELLOW}BOM. Aceitavel.")
    else:
        print(f"\n{Fore.RED}LENTO. Pode precisar otimizar.")


if __name__ == "__main__":
    main()
