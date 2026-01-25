#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador Resumido: 4 Contas com Saque Diário
Mostra apenas métricas finais para comparação rápida
"""

import csv
from typing import List, Tuple

ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
ALVO_LUCRO = 1.99


def carregar_multiplicadores(arquivo: str) -> List[float]:
    """Carrega apenas os multiplicadores"""
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


def simular_conta_rapido(
    multiplicadores: List[float],
    banca_c2_inicial: float,
    saque_diario: float,
    rodadas_por_dia: int = 3456
) -> Tuple[float, float, int, int]:
    """
    Simula uma conta e retorna: (total_sacado, banca_final, busts, dias_para_roi)
    """
    banca_c1 = 3.0
    divisor_c1 = 3
    divisor_c2 = 255
    gatilho = 5
    tent_c1 = 2
    tent_c2 = 8

    banca_c2 = banca_c2_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    total_sacado = 0.0
    busts = 0
    rodada_dia = 0
    dias = 0
    dias_para_roi = 0

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
                    banca_c2 = banca_c2_inicial
                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1

            # Saque
            if banca_c2 > banca_c2_inicial + saque_diario:
                total_sacado += saque_diario
                banca_c2 -= saque_diario
            elif banca_c2 > banca_c2_inicial * 1.5:
                saque = (banca_c2 - banca_c2_inicial) * 0.5
                total_sacado += saque
                banca_c2 -= saque

            # Verificar ROI
            if dias_para_roi == 0 and total_sacado >= banca_c2_inicial:
                dias_para_roi = dias

            rodada_dia = 0

    return total_sacado, banca_c2, busts, dias_para_roi


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores")

    print(f"\n{'='*80}")
    print(f"COMPARATIVO: 4 CONTAS COM SAQUE DE R$ 3.000/DIA")
    print(f"Estratégia: G5 + D3/D255 (proteção 15 baixas)")
    print(f"{'='*80}")

    print(f"\n{'Banca/Conta':>12} {'Investimento':>14} {'Sacado Total':>14} {'Saque/Dia':>12} {'ROI':>10} {'Dias ROI':>10} {'Busts':>7}")
    print("-" * 80)

    for banca_conta in [500, 1000, 2000, 5000, 10000]:
        investimento = banca_conta * 4
        saque_conta = 750.0  # 3000/4

        # Simular (todas veem mesmos mults = sincronizado)
        sacado, banca_final, busts, dias_roi = simular_conta_rapido(
            multiplicadores, banca_conta, saque_conta
        )

        # Multiplicar por 4 contas
        sacado_total = sacado * 4
        banca_final_total = banca_final * 4
        dias_simulados = len(multiplicadores) // 3456

        saque_dia_medio = sacado_total / dias_simulados
        roi = ((sacado_total + banca_final_total - investimento) / investimento) * 100

        print(f"R$ {banca_conta:>9,} R$ {investimento:>11,} R$ {sacado_total:>11,.0f} R$ {saque_dia_medio:>9,.0f} {roi:>9,.0f}% {dias_roi:>9} {busts:>7}")

    print(f"\n{'='*80}")
    print("LEGENDA:")
    print("  - Banca/Conta: Valor inicial por conta")
    print("  - Investimento: Total investido (4 contas)")
    print("  - Sacado Total: Total retirado em 374 dias")
    print("  - Saque/Dia: Média de saque diário efetivo")
    print("  - ROI: Retorno sobre investimento")
    print("  - Dias ROI: Dias para recuperar investimento")
    print("  - Busts: Número de busts (sincronizados em todas contas)")

    print(f"\n{'='*80}")
    print("INSIGHTS:")
    print("  ⚠️  BUSTS SÃO SINCRONIZADOS - quando uma busta, todas bustam!")
    print("  ⚠️  4 contas NÃO diversificam risco, apenas aumentam limite de saque")
    print("  ✅ Com R$ 2k/conta (R$ 8k total), média de ~R$ 500/dia de saque")
    print("  ✅ Com R$ 5k/conta (R$ 20k total), média de ~R$ 1.300/dia de saque")
    print("  ✅ Para R$ 3k/dia consistente, precisa ~R$ 10k/conta (R$ 40k total)")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
