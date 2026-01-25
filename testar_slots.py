#!/usr/bin/env python3
"""
TESTE DE APOSTAS DUPLAS
Aposta R$1,00 @ 1,01x em ambos os slots para verificar coordenadas
"""

import time
import json
from colorama import Fore, init
from autonomous_betting_v2 import AutonomousBettingV2

init(autoreset=True)

def main():
    print(f"\n{'='*50}")
    print(f"  TESTE DE APOSTAS DUPLAS - SLOTS 1 e 2")
    print(f"{'='*50}")
    print(f"\n{Fore.YELLOW}Este teste vai apostar R$1,00 @ 1,01x em cada slot.")
    print(f"{Fore.YELLOW}Total: R$2,00 (recuperável com multiplicador >= 1,01x)")
    print(f"\n{Fore.CYAN}Certifique-se que:")
    print(f"  1. A plataforma está aberta e visível")
    print(f"  2. O jogo está em fase de APOSTAS")
    print(f"  3. Você tem saldo suficiente")

    input(f"\n{Fore.WHITE}Pressione ENTER para iniciar o teste...")

    # Carregar perfil
    with open('config.json', 'r') as f:
        config = json.load(f)

    perfil_nome = 'LG FULL 90% 2 SLOTS'
    perfil = config['profiles'].get(perfil_nome)

    if not perfil:
        print(f"{Fore.RED}Perfil '{perfil_nome}' não encontrado!")
        return

    print(f"\n{Fore.GREEN}Perfil carregado: {perfil_nome}")

    # Inicializar betting
    betting = AutonomousBettingV2()
    betting.set_profile(perfil)

    valor = 1.00
    alvo = 1.01

    # ===== TESTE SLOT 1 =====
    print(f"\n{Fore.CYAN}{'='*40}")
    print(f"{Fore.CYAN}TESTANDO SLOT 1")
    print(f"{Fore.CYAN}{'='*40}")
    print(f"Valor: R${valor:.2f} | Alvo: {alvo:.2f}x")

    input(f"{Fore.YELLOW}Pressione ENTER para apostar no SLOT 1...")

    result1 = betting.execute_bet(valor, alvo, bet_slot=1)

    if result1.success:
        print(f"{Fore.GREEN}✓ Slot 1: Aposta enviada!")
        if result1.confirmed:
            print(f"{Fore.GREEN}✓ Slot 1: CONFIRMADA (saldo diminuiu)")
        else:
            print(f"{Fore.YELLOW}? Slot 1: Não confirmada (verificar manualmente)")
    else:
        print(f"{Fore.RED}✗ Slot 1: FALHOU - {result1.error}")

    time.sleep(1)

    # ===== TESTE SLOT 2 =====
    print(f"\n{Fore.CYAN}{'='*40}")
    print(f"{Fore.CYAN}TESTANDO SLOT 2")
    print(f"{Fore.CYAN}{'='*40}")
    print(f"Valor: R${valor:.2f} | Alvo: {alvo:.2f}x")

    input(f"{Fore.YELLOW}Pressione ENTER para apostar no SLOT 2...")

    result2 = betting.execute_bet(valor, alvo, bet_slot=2)

    if result2.success:
        print(f"{Fore.GREEN}✓ Slot 2: Aposta enviada!")
        if result2.confirmed:
            print(f"{Fore.GREEN}✓ Slot 2: CONFIRMADA (saldo diminuiu)")
        else:
            print(f"{Fore.YELLOW}? Slot 2: Não confirmada (verificar manualmente)")
    else:
        print(f"{Fore.RED}✗ Slot 2: FALHOU - {result2.error}")

    # ===== RESUMO =====
    print(f"\n{Fore.WHITE}{'='*50}")
    print(f"{Fore.WHITE}  RESUMO DO TESTE")
    print(f"{'='*50}")
    print(f"  Slot 1: {'OK' if result1.success else 'FALHOU'} - {result1.error if result1.error else 'Sem erros'}")
    print(f"  Slot 2: {'OK' if result2.success else 'FALHOU'} - {result2.error if result2.error else 'Sem erros'}")
    print(f"\n{Fore.YELLOW}Verifique visualmente se ambos os slots foram preenchidos corretamente!")

if __name__ == '__main__':
    main()
