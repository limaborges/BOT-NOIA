#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE DE VELOCIDADE - 2 SLOTS
Testa a velocidade de execucao de 2 apostas simultaneas.

USO:
1. Abra o site de apostas na tela
2. Execute este script
3. Ele vai tentar colocar 2 apostas e medir o tempo

IMPORTANTE: Use valores baixos para teste!
"""

import time
import json
import sys
from colorama import Fore, init

init(autoreset=True)

# Importar o executor de apostas
from autonomous_betting_v2 import AutonomousBettingV2

def carregar_config():
    """Carrega configuracao"""
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def listar_perfis(config):
    """Lista perfis disponiveis"""
    perfis = list(config.get('profiles', {}).keys())
    print(f"\n{Fore.CYAN}PERFIS DISPONIVEIS:")
    for i, p in enumerate(perfis, 1):
        # Verificar se tem slot 2 configurado
        profile_data = config['profiles'][p]
        tem_slot2 = profile_data.get('bet_value_area_2') is not None
        marca = f"{Fore.GREEN}[2 SLOTS]" if tem_slot2 else f"{Fore.YELLOW}[1 SLOT]"
        print(f"  {i}. {p} {marca}")
    return perfis

def teste_velocidade_1slot(betting, valor, alvo):
    """Testa velocidade de 1 aposta"""
    print(f"\n{Fore.YELLOW}=== TESTE 1 SLOT ==={Fore.WHITE}")
    print(f"Valor: R$ {valor:.2f} | Alvo: {alvo}x")

    input(f"\n{Fore.CYAN}Pressione ENTER para iniciar o teste...{Fore.WHITE}")

    inicio = time.time()
    resultado = betting.execute_bet(valor, alvo, bet_slot=1)
    fim = time.time()

    tempo = fim - inicio

    if resultado.success:
        print(f"\n{Fore.GREEN}SUCESSO! Tempo: {tempo:.2f}s{Fore.WHITE}")
    else:
        print(f"\n{Fore.RED}FALHA: {resultado.error_message}{Fore.WHITE}")
        print(f"Tempo: {tempo:.2f}s")

    return tempo, resultado.success

def teste_velocidade_2slots(betting, valor1, alvo1, valor2, alvo2):
    """Testa velocidade de 2 apostas sequenciais"""
    print(f"\n{Fore.YELLOW}=== TESTE 2 SLOTS ==={Fore.WHITE}")
    print(f"Slot 1: R$ {valor1:.2f} @ {alvo1}x")
    print(f"Slot 2: R$ {valor2:.2f} @ {alvo2}x")

    input(f"\n{Fore.CYAN}Pressione ENTER para iniciar o teste...{Fore.WHITE}")

    inicio_total = time.time()

    # Slot 1
    print(f"\n{Fore.WHITE}Executando Slot 1...")
    inicio1 = time.time()
    resultado1 = betting.execute_bet(valor1, alvo1, bet_slot=1)
    fim1 = time.time()
    tempo1 = fim1 - inicio1

    # Slot 2
    print(f"{Fore.WHITE}Executando Slot 2...")
    inicio2 = time.time()
    resultado2 = betting.execute_bet(valor2, alvo2, bet_slot=2)
    fim2 = time.time()
    tempo2 = fim2 - inicio2

    fim_total = time.time()
    tempo_total = fim_total - inicio_total

    print(f"\n{Fore.CYAN}=== RESULTADOS ==={Fore.WHITE}")
    print(f"Slot 1: {'OK' if resultado1.success else 'FALHA'} em {tempo1:.2f}s")
    print(f"Slot 2: {'OK' if resultado2.success else 'FALHA'} em {tempo2:.2f}s")
    print(f"\n{Fore.GREEN}TEMPO TOTAL: {tempo_total:.2f}s{Fore.WHITE}")

    if tempo_total < 2.0:
        print(f"{Fore.GREEN}EXCELENTE! Menos de 2 segundos.{Fore.WHITE}")
    elif tempo_total < 3.0:
        print(f"{Fore.YELLOW}BOM. Entre 2-3 segundos.{Fore.WHITE}")
    elif tempo_total < 4.0:
        print(f"{Fore.YELLOW}ACEITAVEL. Entre 3-4 segundos.{Fore.WHITE}")
    else:
        print(f"{Fore.RED}LENTO! Mais de 4 segundos. Pode ser arriscado.{Fore.WHITE}")

    return tempo_total, resultado1.success and resultado2.success

def teste_velocidade_2slots_fast(betting, valor1, alvo1, valor2, alvo2):
    """Testa velocidade de 2 apostas com modo FAST"""
    print(f"\n{Fore.YELLOW}=== TESTE 2 SLOTS (MODO RAPIDO) ==={Fore.WHITE}")
    print(f"Slot 1: R$ {valor1:.2f} @ {alvo1}x")
    print(f"Slot 2: R$ {valor2:.2f} @ {alvo2}x")

    input(f"\n{Fore.CYAN}Pressione ENTER para iniciar o teste...{Fore.WHITE}")

    inicio_total = time.time()

    # Slot 1 - FAST
    print(f"\n{Fore.WHITE}Executando Slot 1 (FAST)...")
    inicio1 = time.time()
    resultado1 = betting.execute_bet_fast(valor1, alvo1, bet_slot=1)
    fim1 = time.time()
    tempo1 = fim1 - inicio1

    # Slot 2 - FAST
    print(f"{Fore.WHITE}Executando Slot 2 (FAST)...")
    inicio2 = time.time()
    resultado2 = betting.execute_bet_fast(valor2, alvo2, bet_slot=2)
    fim2 = time.time()
    tempo2 = fim2 - inicio2

    fim_total = time.time()
    tempo_total = fim_total - inicio_total

    print(f"\n{Fore.CYAN}=== RESULTADOS (MODO RAPIDO) ==={Fore.WHITE}")
    print(f"Slot 1: {'OK' if resultado1.success else 'FALHA'} em {tempo1:.2f}s")
    print(f"Slot 2: {'OK' if resultado2.success else 'FALHA'} em {tempo2:.2f}s")
    print(f"\n{Fore.GREEN}TEMPO TOTAL: {tempo_total:.2f}s{Fore.WHITE}")

    if tempo_total < 1.0:
        print(f"{Fore.GREEN}EXCELENTE! Menos de 1 segundo.{Fore.WHITE}")
    elif tempo_total < 1.5:
        print(f"{Fore.GREEN}MUITO BOM! Entre 1-1.5 segundos.{Fore.WHITE}")
    elif tempo_total < 2.0:
        print(f"{Fore.YELLOW}BOM. Entre 1.5-2 segundos.{Fore.WHITE}")
    else:
        print(f"{Fore.YELLOW}Aceitavel. {tempo_total:.2f} segundos.{Fore.WHITE}")

    return tempo_total, resultado1.success and resultado2.success

def main():
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}   TESTE DE VELOCIDADE - 2 SLOTS")
    print(f"{Fore.CYAN}{'='*60}")

    # Carregar config
    config = carregar_config()
    perfis = listar_perfis(config)

    # Selecionar perfil
    print(f"\n{Fore.WHITE}Selecione o perfil (numero): ", end="")
    try:
        idx = int(input().strip()) - 1
        if idx < 0 or idx >= len(perfis):
            print(f"{Fore.RED}Indice invalido!")
            return
        perfil = perfis[idx]
    except ValueError:
        print(f"{Fore.RED}Entrada invalida!")
        return

    print(f"\n{Fore.GREEN}Perfil selecionado: {perfil}")

    # Inicializar betting
    betting = AutonomousBettingV2(config, verbose=True)
    if not betting.set_profile(perfil):
        print(f"{Fore.RED}Erro ao configurar perfil!")
        return

    # Verificar se tem slot 2
    profile_data = config['profiles'][perfil]
    tem_slot2 = profile_data.get('bet_value_area_2') is not None

    if not tem_slot2:
        print(f"\n{Fore.RED}AVISO: Este perfil NAO tem slot 2 configurado!")
        print(f"{Fore.YELLOW}Apenas teste de 1 slot disponivel.")

    # Menu de testes
    while True:
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}   MENU DE TESTES")
        print(f"{Fore.CYAN}{'='*60}")
        print(f"\n{Fore.WHITE}1. Teste 1 slot (modo normal)")
        if tem_slot2:
            print(f"{Fore.WHITE}2. Teste 2 slots (modo normal)")
            print(f"{Fore.WHITE}3. Teste 2 slots (modo RAPIDO)")
            print(f"{Fore.WHITE}4. Comparar normal vs rapido")
        print(f"{Fore.WHITE}0. Sair")

        print(f"\n{Fore.WHITE}Opcao: ", end="")
        try:
            opcao = int(input().strip())
        except ValueError:
            continue

        if opcao == 0:
            print(f"\n{Fore.CYAN}Ate logo!")
            break

        # Valores de teste (BAIXOS!)
        valor_teste = 0.50  # 50 centavos
        alvo_teste = 1.10   # Alvo baixo pra quase garantir que entra

        if opcao == 1:
            teste_velocidade_1slot(betting, valor_teste, alvo_teste)

        elif opcao == 2 and tem_slot2:
            # T5 simulado: 6/16 @ 1.99x + 10/16 @ 1.25x
            valor1 = valor_teste * 6 / 16  # ~0.19
            valor2 = valor_teste * 10 / 16  # ~0.31
            teste_velocidade_2slots(betting, valor1, 1.99, valor2, 1.25)

        elif opcao == 3 and tem_slot2:
            valor1 = valor_teste * 6 / 16
            valor2 = valor_teste * 10 / 16
            teste_velocidade_2slots_fast(betting, valor1, 1.99, valor2, 1.25)

        elif opcao == 4 and tem_slot2:
            print(f"\n{Fore.YELLOW}=== COMPARACAO: NORMAL vs RAPIDO ==={Fore.WHITE}")

            valor1 = valor_teste * 6 / 16
            valor2 = valor_teste * 10 / 16

            # Teste normal
            tempo_normal, ok_normal = teste_velocidade_2slots(betting, valor1, 1.99, valor2, 1.25)

            input(f"\n{Fore.CYAN}Pressione ENTER para o teste RAPIDO...{Fore.WHITE}")

            # Teste rapido
            tempo_rapido, ok_rapido = teste_velocidade_2slots_fast(betting, valor1, 1.99, valor2, 1.25)

            # Comparacao
            print(f"\n{Fore.CYAN}{'='*60}")
            print(f"{Fore.CYAN}   COMPARACAO FINAL")
            print(f"{Fore.CYAN}{'='*60}")
            print(f"\n{Fore.WHITE}Modo Normal: {tempo_normal:.2f}s {'OK' if ok_normal else 'FALHA'}")
            print(f"{Fore.WHITE}Modo Rapido: {tempo_rapido:.2f}s {'OK' if ok_rapido else 'FALHA'}")

            if tempo_rapido < tempo_normal:
                diff = tempo_normal - tempo_rapido
                pct = (diff / tempo_normal) * 100
                print(f"\n{Fore.GREEN}Modo rapido e {pct:.0f}% mais veloz ({diff:.2f}s mais rapido)")

            # Recomendacao
            print(f"\n{Fore.YELLOW}RECOMENDACAO:{Fore.WHITE}")
            if tempo_rapido < 1.5 and ok_rapido:
                print(f"  -> Usar modo RAPIDO para 2 slots")
            elif tempo_normal < 2.5 and ok_normal:
                print(f"  -> Modo normal e aceitavel")
            else:
                print(f"  -> ATENCAO: Tempos elevados. Pode precisar otimizar.")


if __name__ == "__main__":
    main()
