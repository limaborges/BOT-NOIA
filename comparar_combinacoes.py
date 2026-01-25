#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparativo: Todas as combinações de Gatilho + NS
Proteção 15 e 16
"""

import csv
from typing import List, Dict

ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
ALVO = 1.99


def carregar_multiplicadores(arquivo: str) -> List[float]:
    multiplicadores = []
    with open(arquivo, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                mult = float(row.get('Número', row.get('numero', list(row.values())[0])))
                multiplicadores.append(mult)
            except:
                continue
    return multiplicadores


def calc_tentativas(divisor: int) -> int:
    """Calcula número de tentativas para um divisor"""
    n, soma = 0, 0
    while soma + (2 ** n) <= divisor:
        soma += 2 ** n
        n += 1
    return n


# Níveis de segurança
NIVEIS = {
    6: {'divisor': 63, 'tentativas': 6},
    7: {'divisor': 127, 'tentativas': 7},
    8: {'divisor': 255, 'tentativas': 8},
    9: {'divisor': 511, 'tentativas': 9},
    10: {'divisor': 1023, 'tentativas': 10},
}


def simular(multiplicadores: List[float], gatilho: int, nivel: int, banca_inicial: float = 10000.0) -> Dict:
    """Simula uma combinação gatilho + nível"""

    divisor = NIVEIS[nivel]['divisor']
    max_tent = NIVEIS[nivel]['tentativas']
    protecao = gatilho + max_tent
    rodadas_por_dia = 3456

    banca = banca_inicial
    em_ciclo = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    wins = 0
    busts = 0
    gatilhos_ativados = 0
    lucro_total = 0.0
    rodada_dia = 0
    dias = 0

    for mult in multiplicadores:
        is_baixa = mult < ALVO

        if is_baixa:
            baixas += 1
        else:
            baixas = 0

        if not em_ciclo:
            if baixas >= gatilho:
                em_ciclo = True
                tentativa = 1
                apostas_perdidas = 0.0
                gatilhos_ativados += 1

        else:
            aposta = banca * (2 ** (tentativa - 1)) / divisor

            if mult >= ALVO:
                lucro = aposta * (ALVO - 1) - apostas_perdidas
                wins += 1
                lucro_total += lucro
                banca += lucro  # Compound

                em_ciclo = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1

                if tentativa > max_tent:
                    busts += 1
                    lucro_total -= banca
                    banca = banca_inicial  # Reset

                    em_ciclo = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1
            rodada_dia = 0

    if dias == 0:
        dias = 1

    return {
        'gatilho': gatilho,
        'nivel': nivel,
        'divisor': divisor,
        'protecao': protecao,
        'dias': dias,
        'gatilhos_dia': gatilhos_ativados / dias,
        'wins': wins,
        'wins_dia': wins / dias,
        'busts': busts,
        'lucro_total': lucro_total,
        'lucro_dia': lucro_total / dias,
        'banca_final': banca,
        'roi': ((banca - banca_inicial + lucro_total) / banca_inicial) * 100 if busts == 0 else lucro_total / banca_inicial * 100,
    }


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    banca = 10000.0

    # Combinações para proteção 15
    combos_15 = [
        (5, 10),  # G5 + NS10
        (6, 9),   # G6 + NS9
        (7, 8),   # G7 + NS8
        (8, 7),   # G8 + NS7
        (9, 6),   # G9 + NS6
    ]

    # Combinações para proteção 16
    combos_16 = [
        (6, 10),  # G6 + NS10
        (7, 9),   # G7 + NS9
        (8, 8),   # G8 + NS8
        (9, 7),   # G9 + NS7
        (10, 6),  # G10 + NS6
    ]

    print(f"{'='*90}")
    print(f"PROTEÇÃO 15 (2 busts no dataset) - Banca R$ {banca:,.0f}")
    print(f"{'='*90}")
    print(f"\n{'Config':<12} {'Gatilhos/dia':>12} {'Wins/dia':>10} {'Busts':>7} {'Lucro/dia':>14} {'Banca Final':>16}")
    print("-" * 90)

    resultados_15 = []
    for g, n in combos_15:
        r = simular(multiplicadores, g, n, banca)
        resultados_15.append(r)
        config = f"G{g}+NS{n}"
        print(f"{config:<12} {r['gatilhos_dia']:>12.1f} {r['wins_dia']:>10.1f} {r['busts']:>7} R$ {r['lucro_dia']:>11,.0f} R$ {r['banca_final']:>13,.0f}")

    print(f"\n{'='*90}")
    print(f"PROTEÇÃO 16 (0 busts no dataset) - Banca R$ {banca:,.0f}")
    print(f"{'='*90}")
    print(f"\n{'Config':<12} {'Gatilhos/dia':>12} {'Wins/dia':>10} {'Busts':>7} {'Lucro/dia':>14} {'Banca Final':>16}")
    print("-" * 90)

    resultados_16 = []
    for g, n in combos_16:
        r = simular(multiplicadores, g, n, banca)
        resultados_16.append(r)
        config = f"G{g}+NS{n}"
        print(f"{config:<12} {r['gatilhos_dia']:>12.1f} {r['wins_dia']:>10.1f} {r['busts']:>7} R$ {r['lucro_dia']:>11,.0f} R$ {r['banca_final']:>13,.0f}")

    # Encontrar melhores
    melhor_15 = max(resultados_15, key=lambda x: x['lucro_dia'] if x['busts'] <= 2 else -float('inf'))
    melhor_16 = max(resultados_16, key=lambda x: x['lucro_dia'])

    print(f"\n{'='*90}")
    print("RECOMENDAÇÃO")
    print(f"{'='*90}")

    print(f"\n  CONTA AGRESSIVA (Proteção 15):")
    print(f"    Config: G{melhor_15['gatilho']} + NS{melhor_15['nivel']} (divisor {melhor_15['divisor']})")
    print(f"    Gatilhos/dia: {melhor_15['gatilhos_dia']:.1f}")
    print(f"    Lucro/dia: R$ {melhor_15['lucro_dia']:,.0f}")
    print(f"    Busts em 374 dias: {melhor_15['busts']}")

    print(f"\n  CONTA CONSERVADORA (Proteção 16):")
    print(f"    Config: G{melhor_16['gatilho']} + NS{melhor_16['nivel']} (divisor {melhor_16['divisor']})")
    print(f"    Gatilhos/dia: {melhor_16['gatilhos_dia']:.1f}")
    print(f"    Lucro/dia: R$ {melhor_16['lucro_dia']:,.0f}")
    print(f"    Busts em 374 dias: {melhor_16['busts']}")

    # Simular 2 contas
    print(f"\n{'='*90}")
    print("SIMULAÇÃO: 2 CONTAS SIMULTÂNEAS")
    print(f"{'='*90}")

    # Conta agressiva: menor banca
    # Conta conservadora: maior banca
    banca_agressiva = 3000.0
    banca_conservadora = 7000.0

    r_agr = simular(multiplicadores, melhor_15['gatilho'], melhor_15['nivel'], banca_agressiva)
    r_con = simular(multiplicadores, melhor_16['gatilho'], melhor_16['nivel'], banca_conservadora)

    print(f"\n  Investimento total: R$ {banca_agressiva + banca_conservadora:,.0f}")
    print(f"\n  AGRESSIVA (R$ {banca_agressiva:,.0f}):")
    print(f"    G{melhor_15['gatilho']}+NS{melhor_15['nivel']} | Lucro/dia: R$ {r_agr['lucro_dia']:,.0f} | Busts: {r_agr['busts']}")

    print(f"\n  CONSERVADORA (R$ {banca_conservadora:,.0f}):")
    print(f"    G{melhor_16['gatilho']}+NS{melhor_16['nivel']} | Lucro/dia: R$ {r_con['lucro_dia']:,.0f} | Busts: {r_con['busts']}")

    lucro_total_dia = r_agr['lucro_dia'] + r_con['lucro_dia']
    print(f"\n  TOTAL:")
    print(f"    Lucro combinado/dia: R$ {lucro_total_dia:,.0f}")
    print(f"    Lucro combinado/mês: R$ {lucro_total_dia * 30:,.0f}")


if __name__ == "__main__":
    main()
