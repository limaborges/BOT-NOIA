#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificação matemática passo a passo
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


def verificar_passo_a_passo(multiplicadores: List[float]):
    """Verifica a matemática com logs detalhados"""

    banca_c1 = 3.0
    banca_c2_inicial = 1000.0
    divisor_c1 = 3
    divisor_c2 = 511
    gatilho = 5
    tent_c1 = 2
    tent_c2 = 9
    rodadas_por_dia = 3456

    print(f"{'='*70}")
    print("VERIFICAÇÃO MATEMÁTICA DETALHADA")
    print(f"{'='*70}")

    print(f"\nConfiguração:")
    print(f"  C1: R$ {banca_c1} / {divisor_c1} = R$ {banca_c1/divisor_c1:.2f} aposta inicial")
    print(f"  C2: R$ {banca_c2_inicial} / {divisor_c2} = R$ {banca_c2_inicial/divisor_c2:.2f} aposta inicial")
    print(f"  Lucro por win C1: R$ {banca_c1/divisor_c1 * 0.99:.4f}")
    print(f"  Lucro por win C2: {0.99/divisor_c2*100:.4f}% da banca")

    # Simular apenas 30 dias com logs
    banca_c2 = banca_c2_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    wins_c1 = 0
    wins_c2 = 0
    lucro_c1_total = 0.0
    lucro_c2_total = 0.0
    rodada_dia = 0
    dias = 0

    # Só simular 30 dias
    max_rodadas = rodadas_por_dia * 30

    for i, mult in enumerate(multiplicadores[:max_rodadas]):
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
                lucro_c1_total += lucro
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
                lucro_c2_total += lucro
                banca_c2 += lucro
                em_ciclo_2 = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1
                if tentativa > tent_c2:
                    print(f"  !!! BUST na rodada {i} !!!")
                    banca_c2 = banca_c2_inicial
                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1
            rodada_dia = 0

    print(f"\n{'='*70}")
    print(f"RESULTADOS (30 dias)")
    print(f"{'='*70}")

    print(f"\n  Wins C1: {wins_c1} ({wins_c1/30:.1f}/dia)")
    print(f"  Wins C2: {wins_c2} ({wins_c2/30:.1f}/dia)")

    print(f"\n  Lucro total C1: R$ {lucro_c1_total:,.2f}")
    print(f"  Lucro total C2: R$ {lucro_c2_total:,.2f}")

    print(f"\n  Banca inicial: R$ {banca_c2_inicial:,.2f}")
    print(f"  Banca final: R$ {banca_c2:,.2f}")
    print(f"  Crescimento: {(banca_c2/banca_c2_inicial - 1)*100:.1f}%")

    # Verificar matemática
    print(f"\n{'='*70}")
    print("VERIFICAÇÃO DA MATEMÁTICA")
    print(f"{'='*70}")

    lucro_esperado_c1 = wins_c1 * (banca_c1/divisor_c1 * 0.99)
    print(f"\n  Lucro C1 esperado (simplificado): R$ {lucro_esperado_c1:,.2f}")
    print(f"  Lucro C1 real: R$ {lucro_c1_total:,.2f}")

    # C2 é mais complexo por causa do compound
    print(f"\n  Lucro C2 real: R$ {lucro_c2_total:,.2f}")

    crescimento_diario = (banca_c2 / banca_c2_inicial) ** (1/30) - 1
    print(f"\n  Taxa de crescimento diário: {crescimento_diario*100:.2f}%")
    print(f"  Projeção mensal: {((1+crescimento_diario)**30 - 1)*100:.1f}%")
    print(f"  Projeção anual: {((1+crescimento_diario)**365 - 1)*100:.1f}%")

    # Alerta
    print(f"\n{'='*70}")
    print("⚠️  PONTOS DE ATENÇÃO")
    print(f"{'='*70}")
    print("""
  1. DADOS HISTÓRICOS: Máximo de 15 baixas no dataset.
     Não garante que não haverá 16+ baixas no futuro.

  2. CRESCIMENTO EXPONENCIAL: Com 0 busts, compound é
     exponencial. Pequenas taxas diárias viram números
     astronômicos em meses.

  3. LIMITES DA PLATAFORMA:
     - Limites de aposta
     - Limites de saque
     - Possível ban de contas lucrativas

  4. LIQUIDEZ: Em bancas altas, consegue apostar rápido?

  5. REALIDADE: Se fosse tão fácil, todos fariam.
""")

    return banca_c2


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    verificar_passo_a_passo(multiplicadores)


if __name__ == "__main__":
    main()
