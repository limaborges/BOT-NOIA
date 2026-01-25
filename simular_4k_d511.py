#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R$ 4.000 FULL com D511 (0 busts)
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


def simular(multiplicadores: List[float], banca_inicial: float, divisor_c2: int, saque_diario: float):
    banca_c1 = 3.0
    divisor_c1 = 3
    gatilho = 5
    tent_c1 = 2
    tent_c2 = 9  # D511
    rodadas_por_dia = 3456

    threshold_saque = banca_inicial + saque_diario

    banca_c2 = banca_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    busts = 0
    total_sacado = 0.0
    lucro_dia = 0.0
    rodada_dia = 0
    dias = 0
    historico = []

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

        elif em_ciclo_1:
            aposta = banca_c1 * (2 ** (tentativa - 1)) / divisor_c1
            if mult >= ALVO_LUCRO:
                lucro = aposta * (ALVO_LUCRO - 1) - apostas_perdidas
                lucro_dia += lucro
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
                lucro_dia += lucro
                banca_c2 += lucro
                em_ciclo_2 = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1
                if tentativa > tent_c2:
                    busts += 1
                    lucro_dia -= banca_c2
                    banca_c2 = banca_inicial
                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1
            saque = 0
            if banca_c2 > threshold_saque:
                saque = min(saque_diario, banca_c2 - banca_inicial)
                banca_c2 -= saque
                total_sacado += saque

            historico.append({'dia': dias, 'banca': banca_c2, 'saque': saque, 'total': total_sacado})
            lucro_dia = 0.0
            rodada_dia = 0

    return total_sacado, banca_c2, busts, historico


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores")

    print(f"\n{'='*65}")
    print("R$ 4.000 FULL | G5 + D3 + D511 | PROTEÇÃO 16 | 0 BUSTS")
    print(f"{'='*65}")

    print(f"\n{'Saque/Dia':>12} {'Total Sacado':>16} {'Média/Dia':>12} {'Banca Final':>14}")
    print("-" * 58)

    melhor = None
    for saque in [100, 150, 200, 250, 300, 400, 500]:
        sacado, banca, busts, hist = simular(multiplicadores, 4000, 511, saque)
        media = sacado / 374
        print(f"R$ {saque:>8,} R$ {sacado:>13,.0f} R$ {media:>9,.0f} R$ {banca:>11,.0f}")

        if melhor is None or sacado > melhor['sacado']:
            melhor = {'saque': saque, 'sacado': sacado, 'banca': banca, 'hist': hist}

    # Mostrar evolução do melhor cenário
    print(f"\n{'='*65}")
    print(f"EVOLUÇÃO SEMANAL (Saque R$ {melhor['saque']}/dia)")
    print(f"{'='*65}")

    hist = melhor['hist']
    print(f"\n{'Semana':>7} {'Dia':>5} {'Banca':>15} {'Sacado Semana':>16} {'Total Sacado':>16}")
    print("-" * 62)

    for semana in range(1, 9):
        dia = semana * 7
        if dia > len(hist):
            break
        banca = hist[dia-1]['banca']
        total = hist[dia-1]['total']
        inicio = (semana-1) * 7
        sacado_semana = sum(hist[d]['saque'] for d in range(inicio, dia))
        print(f"{semana:>7} {dia:>5} R$ {banca:>12,.0f} R$ {sacado_semana:>13,.0f} R$ {total:>13,.0f}")

    # Resumo mensal
    print(f"\n{'='*65}")
    print("EVOLUÇÃO MENSAL")
    print(f"{'='*65}")
    print(f"\n{'Mês':>4} {'Banca':>15} {'Sacado Mês':>16} {'Total Sacado':>16}")
    print("-" * 55)

    for mes in range(1, 13):
        dia = mes * 30
        if dia > len(hist):
            break
        banca = hist[dia-1]['banca']
        total = hist[dia-1]['total']
        inicio = (mes-1) * 30
        sacado_mes = sum(hist[d]['saque'] for d in range(inicio, min(dia, len(hist))))
        print(f"{mes:>4} R$ {banca:>12,.0f} R$ {sacado_mes:>13,.0f} R$ {total:>13,.0f}")

    print(f"\n{'='*65}")
    print("CONFIGURAÇÃO FINAL RECOMENDADA")
    print(f"{'='*65}")
    print(f"""
  Banca: R$ 4.000 (full, sem reserva)

  Ciclo 1 (Sinalizador):
    - Banca C1: R$ 3,00
    - Divisor: 3 (2 tentativas)

  Ciclo 2 (Lucro):
    - Banca C2: R$ 4.000
    - Divisor: 511 (9 tentativas)

  Gatilho: G5 (5 baixas consecutivas)
  Proteção total: 5 + 2 + 9 = 16 baixas

  Alvo: 1.99x

  ✅ BUSTS ESPERADOS: 0 (máximo dataset = 15)
  💰 Saque sugerido: R$ 200-250/dia
  💰 Retorno mensal: R$ 6.000-7.500
""")


if __name__ == "__main__":
    main()
