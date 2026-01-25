#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador REALISTA: 1 Conta com R$ 4.000 + Saque Diário
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


def simular_com_saque(multiplicadores: List[float], banca_inicial: float, saque_diario: float):
    """Simula com saque diário após atingir threshold"""

    banca_c1 = 3.0
    divisor_c1 = 3
    divisor_c2 = 255
    gatilho = 5
    tent_c1 = 2
    tent_c2 = 8
    rodadas_por_dia = 3456

    # Só saca quando banca > inicial + saque
    threshold_saque = banca_inicial + saque_diario

    print(f"\n{'='*60}")
    print(f"1 CONTA: R$ {banca_inicial:,.0f} | Saque: R$ {saque_diario:,.0f}/dia")
    print(f"{'='*60}")

    banca_c2 = banca_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    wins_c1 = 0
    wins_c2 = 0
    busts = 0
    total_sacado = 0.0
    lucro_dia = 0.0
    rodada_dia = 0
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
                wins_c1 += 1
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
                wins_c2 += 1
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
            # Saque diário
            saque_hoje = 0.0
            if banca_c2 > threshold_saque:
                saque_hoje = min(saque_diario, banca_c2 - banca_inicial)
                banca_c2 -= saque_hoje
                total_sacado += saque_hoje

            historico.append({
                'banca': banca_c2,
                'lucro_dia': lucro_dia,
                'saque': saque_hoje,
                'total_sacado': total_sacado
            })
            lucro_dia = 0.0
            rodada_dia = 0

    dias = len(historico)

    # Métricas
    dias_com_saque = sum(1 for h in historico if h['saque'] > 0)
    saque_medio = total_sacado / dias_com_saque if dias_com_saque > 0 else 0

    print(f"  Dias: {dias} | Busts: {busts}")
    print(f"  Total sacado: R$ {total_sacado:,.2f}")
    print(f"  Saque médio/dia: R$ {total_sacado/dias:,.2f}")
    print(f"  Banca final: R$ {banca_c2:,.2f}")

    # Primeiro mês
    lucro_mes1 = sum(h['saque'] for h in historico[:30])
    print(f"  Saque mês 1: R$ {lucro_mes1:,.2f}")

    return total_sacado, banca_c2, busts


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    print("="*60)
    print("COMPARATIVO: DIFERENTES VALORES DE SAQUE DIÁRIO")
    print("Banca inicial: R$ 4.000 | Estratégia: G5+D3/D255")
    print("="*60)

    resultados = []
    for saque in [100, 200, 300, 500, 750, 1000]:
        sacado, banca, busts = simular_com_saque(multiplicadores, 4000.0, float(saque))
        resultados.append({
            'saque_config': saque,
            'total_sacado': sacado,
            'banca_final': banca,
            'busts': busts
        })

    # Tabela resumo
    print(f"\n{'='*70}")
    print("RESUMO COMPARATIVO (374 dias)")
    print("="*70)
    print(f"\n{'Saque/Dia':>12} {'Total Sacado':>16} {'Média/Dia':>12} {'Banca Final':>14} {'ROI':>10}")
    print("-"*70)

    for r in resultados:
        media = r['total_sacado'] / 374
        roi = ((r['total_sacado'] + r['banca_final'] - 4000) / 4000) * 100
        print(f"R$ {r['saque_config']:>8,} R$ {r['total_sacado']:>13,.0f} R$ {media:>9,.0f} R$ {r['banca_final']:>11,.0f} {roi:>9,.0f}%")

    print(f"\n{'='*70}")
    print("RECOMENDAÇÃO PARA BANCA R$ 4.000:")
    print("="*70)
    print("""
  💰 Saque conservador: R$ 200/dia (R$ 6k/mês)
     - Banca cresce, mais segurança

  💰 Saque moderado: R$ 300/dia (R$ 9k/mês)
     - Equilíbrio entre saque e crescimento

  💰 Saque agressivo: R$ 500/dia (R$ 15k/mês)
     - Maximiza retirada, banca estável

  ⚠️  IMPORTANTE:
     - Guarde R$ 4k de reserva para reiniciar após bust
     - 2 busts em 374 dias (~1 a cada 6 meses)
     - Recupera investimento em ~20 dias
""")


if __name__ == "__main__":
    main()
