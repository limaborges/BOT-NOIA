#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tradeoff: Entrar cedo (divisor maior) vs Entrar tarde (divisor menor)
Com saque diário para números realistas
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


NIVEIS = {
    6: {'divisor': 63, 'tentativas': 6},
    7: {'divisor': 127, 'tentativas': 7},
    8: {'divisor': 255, 'tentativas': 8},
    9: {'divisor': 511, 'tentativas': 9},
    10: {'divisor': 1023, 'tentativas': 10},
}


def simular_com_saque(multiplicadores: List[float], gatilho: int, nivel: int,
                       banca_inicial: float, saque_pct: float = 0.5) -> Dict:
    """
    Simula com saque diário de X% do lucro
    """

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
    total_sacado = 0.0
    lucro_dia = 0.0
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

        else:
            aposta = banca * (2 ** (tentativa - 1)) / divisor

            if mult >= ALVO:
                lucro = aposta * (ALVO - 1) - apostas_perdidas
                wins += 1
                lucro_dia += lucro
                banca += lucro

                em_ciclo = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1

                if tentativa > max_tent:
                    busts += 1
                    lucro_dia -= banca
                    banca = banca_inicial

                    em_ciclo = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1

            # Saque diário
            if banca > banca_inicial:
                lucro_disponivel = banca - banca_inicial
                saque = lucro_disponivel * saque_pct
                banca -= saque
                total_sacado += saque

            lucro_dia = 0.0
            rodada_dia = 0

    if dias == 0:
        dias = 1

    return {
        'gatilho': gatilho,
        'nivel': nivel,
        'divisor': divisor,
        'protecao': protecao,
        'dias': dias,
        'wins': wins,
        'wins_dia': wins / dias,
        'busts': busts,
        'total_sacado': total_sacado,
        'saque_dia': total_sacado / dias,
        'banca_final': banca,
    }


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    banca = 10000.0

    print(f"{'='*100}")
    print(f"TRADEOFF: GATILHO BAIXO + DIVISOR ALTO vs GATILHO ALTO + DIVISOR BAIXO")
    print(f"Banca: R$ {banca:,.0f} | Saque diário: 50% do lucro")
    print(f"{'='*100}")

    # Todas as combinações de proteção 15 e 16
    combos = [
        # Proteção 15
        (5, 10, 15), (6, 9, 15), (7, 8, 15), (8, 7, 15), (9, 6, 15),
        # Proteção 16
        (6, 10, 16), (7, 9, 16), (8, 8, 16), (9, 7, 16), (10, 6, 16),
    ]

    print(f"\n{'Config':<12} {'Prot':>5} {'Divisor':>8} {'Wins/dia':>10} {'Busts':>6} {'Saque/dia':>14} {'Saque/mês':>14} {'Banca Fim':>14}")
    print("-" * 100)

    resultados = []
    for g, n, prot in combos:
        r = simular_com_saque(multiplicadores, g, n, banca, 0.5)
        resultados.append(r)
        config = f"G{g}+NS{n}"
        saque_mes = r['saque_dia'] * 30
        print(f"{config:<12} {prot:>5} {r['divisor']:>8} {r['wins_dia']:>10.1f} {r['busts']:>6} R$ {r['saque_dia']:>11,.0f} R$ {saque_mes:>11,.0f} R$ {r['banca_final']:>11,.0f}")

    # Análise do tradeoff
    print(f"\n{'='*100}")
    print("ANÁLISE DO TRADEOFF")
    print(f"{'='*100}")

    # Comparar dentro de cada nível de proteção
    for prot in [15, 16]:
        print(f"\n  PROTEÇÃO {prot}:")
        grupo = [r for r in resultados if r['protecao'] == prot]
        melhor = max(grupo, key=lambda x: x['saque_dia'])

        print(f"    Melhor: G{melhor['gatilho']}+NS{melhor['nivel']} (divisor {melhor['divisor']})")
        print(f"    Wins/dia: {melhor['wins_dia']:.1f}")
        print(f"    Saque/dia: R$ {melhor['saque_dia']:,.0f}")
        print(f"    Saque/mês: R$ {melhor['saque_dia']*30:,.0f}")
        print(f"    Busts: {melhor['busts']}")

    # Análise detalhada
    print(f"\n{'='*100}")
    print("INSIGHT: LUCRO POR WIN vs FREQUÊNCIA")
    print(f"{'='*100}")

    print(f"\n  {'Config':<12} {'Lucro/Win':>12} {'Wins/dia':>10} {'Lucro teórico':>15}")
    print("-" * 55)

    for r in resultados:
        lucro_por_win = banca * 0.99 / r['divisor']
        lucro_teorico = lucro_por_win * r['wins_dia']
        config = f"G{r['gatilho']}+NS{r['nivel']}"
        print(f"  {config:<12} R$ {lucro_por_win:>9,.2f} {r['wins_dia']:>10.1f} R$ {lucro_teorico:>12,.0f}")

    print(f"""
  CONCLUSÃO:
  - Divisor MENOR = mais lucro por win
  - Gatilho MAIOR = menos frequência
  - O ponto ótimo depende do produto: (lucro/win) × (wins/dia)
""")


if __name__ == "__main__":
    main()
