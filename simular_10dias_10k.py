#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulação detalhada: 10 primeiros dias com R$ 10.000
G5 + D3 + D511
"""

import csv
from typing import List

ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
ALVO_LUCRO = 1.99


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


def simular_detalhado(multiplicadores: List[float], banca_inicial: float = 10000.0):
    banca_c1 = 3.0
    divisor_c1 = 3
    divisor_c2 = 511
    gatilho = 5
    tent_c1 = 2
    tent_c2 = 9
    rodadas_por_dia = 3456

    print(f"{'='*70}")
    print(f"SIMULAÇÃO DETALHADA: 10 DIAS | BANCA R$ {banca_inicial:,.0f}")
    print(f"{'='*70}")
    print(f"\nEstratégia: G5 + D3 + D511 (proteção 16)")
    print(f"C1: R$ {banca_c1} / {divisor_c1} = R$ {banca_c1/divisor_c1:.2f} aposta base")
    print(f"C2: R$ {banca_inicial:,.0f} / {divisor_c2} = R$ {banca_inicial/divisor_c2:.2f} aposta base")

    banca_c2 = banca_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    rodada_dia = 0
    dias = 0

    # Contadores diários
    wins_c1_dia = 0
    wins_c2_dia = 0
    lucro_c1_dia = 0.0
    lucro_c2_dia = 0.0
    gatilhos_dia = 0
    banca_inicio_dia = banca_c2

    print(f"\n{'='*70}")
    print(f"EVOLUÇÃO DIA A DIA")
    print(f"{'='*70}")

    for mult in multiplicadores:
        is_baixa = mult < ALVO_LUCRO
        if is_baixa:
            baixas += 1
        else:
            baixas = 0

        if not em_ciclo_1 and not em_ciclo_2:
            if baixas >= gatilho:
                em_ciclo_1 = True
                tentativa = 1
                apostas_perdidas = 0.0
                gatilhos_dia += 1

        elif em_ciclo_1:
            aposta = banca_c1 * (2 ** (tentativa - 1)) / divisor_c1
            if mult >= ALVO_LUCRO:
                lucro = aposta * (ALVO_LUCRO - 1) - apostas_perdidas
                wins_c1_dia += 1
                lucro_c1_dia += lucro
                banca_c2 += lucro
                em_ciclo_1 = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1
                if tentativa > tent_c1:
                    em_ciclo_1 = False
                    em_ciclo_2 = True
                    tentativa = 1
                    apostas_perdidas = 0.0

        elif em_ciclo_2:
            aposta = banca_c2 * (2 ** (tentativa - 1)) / divisor_c2
            if mult >= ALVO_LUCRO:
                lucro = aposta * (ALVO_LUCRO - 1) - apostas_perdidas - banca_c1
                wins_c2_dia += 1
                lucro_c2_dia += lucro
                banca_c2 += lucro
                em_ciclo_2 = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1
                if tentativa > tent_c2:
                    # Bust (não deve acontecer com prot 16)
                    banca_c2 = banca_inicial
                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1
            lucro_total_dia = lucro_c1_dia + lucro_c2_dia
            pct_dia = (lucro_total_dia / banca_inicio_dia) * 100

            print(f"\n--- DIA {dias} ---")
            print(f"  Banca início: R$ {banca_inicio_dia:,.2f}")
            print(f"  Gatilhos G5: {gatilhos_dia}")
            print(f"  Wins C1: {wins_c1_dia} → Lucro: R$ {lucro_c1_dia:,.2f}")
            print(f"  Wins C2: {wins_c2_dia} → Lucro: R$ {lucro_c2_dia:,.2f}")
            print(f"  Lucro total: R$ {lucro_total_dia:,.2f} ({pct_dia:.2f}%)")
            print(f"  Banca fim: R$ {banca_c2:,.2f}")

            if dias >= 10:
                break

            # Reset contadores
            wins_c1_dia = 0
            wins_c2_dia = 0
            lucro_c1_dia = 0.0
            lucro_c2_dia = 0.0
            gatilhos_dia = 0
            banca_inicio_dia = banca_c2
            rodada_dia = 0

    # Resumo
    lucro_total = banca_c2 - banca_inicial
    pct_total = (lucro_total / banca_inicial) * 100

    print(f"\n{'='*70}")
    print(f"RESUMO 10 DIAS")
    print(f"{'='*70}")
    print(f"\n  Banca inicial: R$ {banca_inicial:,.2f}")
    print(f"  Banca final: R$ {banca_c2:,.2f}")
    print(f"  Lucro: R$ {lucro_total:,.2f} ({pct_total:.2f}%)")
    print(f"  Média/dia: R$ {lucro_total/10:,.2f} ({pct_total/10:.2f}%/dia)")

    # Projeção
    print(f"\n{'='*70}")
    print(f"PROJEÇÃO (se mantiver média)")
    print(f"{'='*70}")

    taxa_diaria = (banca_c2 / banca_inicial) ** (1/10) - 1
    print(f"\n  Taxa diária média: {taxa_diaria*100:.2f}%")

    banca_proj = banca_inicial
    print(f"\n  {'Período':>12} {'Banca':>18} {'Lucro':>18}")
    print("-" * 52)
    for dias_proj, nome in [(10, "10 dias"), (30, "1 mês"), (60, "2 meses"), (90, "3 meses")]:
        banca_proj = banca_inicial * ((1 + taxa_diaria) ** dias_proj)
        lucro_proj = banca_proj - banca_inicial
        print(f"  {nome:>12} R$ {banca_proj:>15,.2f} R$ {lucro_proj:>15,.2f}")


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    simular_detalhado(multiplicadores, banca_inicial=10000.0)


if __name__ == "__main__":
    main()
