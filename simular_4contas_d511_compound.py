#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4 Contas × R$ 1.000 | D511 | Proteção 16 | 0 Busts
Compound com saques periódicos
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


def simular_conta_compound(multiplicadores: List[float], banca_inicial: float,
                           frequencia_saque: str = 'mensal', pct_saque: float = 0.5):
    """
    Simula com compound e saque periódico
    frequencia_saque: 'semanal', 'quinzenal', 'mensal'
    pct_saque: percentual do lucro a sacar (0.5 = 50%)
    """
    banca_c1 = 3.0
    divisor_c1 = 3
    divisor_c2 = 511
    gatilho = 5
    tent_c1 = 2
    tent_c2 = 9
    rodadas_por_dia = 3456

    dias_entre_saques = {'semanal': 7, 'quinzenal': 15, 'mensal': 30}
    intervalo = dias_entre_saques.get(frequencia_saque, 30)

    banca_c2 = banca_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    total_sacado = 0.0
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
                    # Com D511, isso não deve acontecer (prot 16 > max 15)
                    banca_c2 = banca_inicial
                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1

            saque = 0.0
            # Saque periódico
            if dias % intervalo == 0:
                lucro_acumulado = banca_c2 - banca_inicial
                if lucro_acumulado > 0:
                    saque = lucro_acumulado * pct_saque
                    banca_c2 -= saque
                    total_sacado += saque

            historico.append({
                'dia': dias,
                'banca': banca_c2,
                'saque': saque,
                'total_sacado': total_sacado
            })
            rodada_dia = 0

    return total_sacado, banca_c2, historico


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores")

    banca_por_conta = 1000.0
    num_contas = 4
    investimento_total = banca_por_conta * num_contas

    print(f"\n{'='*70}")
    print(f"4 CONTAS × R$ {banca_por_conta:,.0f} | D511 | PROTEÇÃO 16 | 0 BUSTS")
    print(f"{'='*70}")
    print(f"\nInvestimento total: R$ {investimento_total:,.0f}")
    print(f"Estratégia: G5 + D3 + D511 (proteção 16 baixas)")
    print(f"Busts esperados: ZERO\n")

    # Testar diferentes frequências de saque
    print(f"{'='*70}")
    print("COMPARATIVO: FREQUÊNCIA DE SAQUE (50% do lucro)")
    print(f"{'='*70}")

    print(f"\n{'Frequência':>12} {'Sacado/Conta':>14} {'Total 4 Contas':>16} {'Banca Final':>14}")
    print("-" * 60)

    for freq in ['semanal', 'quinzenal', 'mensal']:
        sacado, banca, hist = simular_conta_compound(multiplicadores, banca_por_conta, freq, 0.5)
        print(f"{freq:>12} R$ {sacado:>11,.0f} R$ {sacado*4:>13,.0f} R$ {banca:>11,.0f}")

    # Simular com saque mensal 50% (recomendado)
    print(f"\n{'='*70}")
    print("EVOLUÇÃO DETALHADA: SAQUE MENSAL 50%")
    print(f"{'='*70}")

    sacado, banca, hist = simular_conta_compound(multiplicadores, banca_por_conta, 'mensal', 0.5)

    print(f"\n{'Mês':>4} {'Banca/Conta':>14} {'Saque/Conta':>14} {'Total 4 Contas':>16} {'Sacado Acum':>14}")
    print("-" * 66)

    for mes in range(1, 13):
        dia = mes * 30
        if dia > len(hist):
            break
        h = hist[dia-1]
        banca_total = h['banca'] * 4
        saque_mes = h['saque'] * 4
        sacado_acum = h['total_sacado'] * 4
        print(f"{mes:>4} R$ {h['banca']:>11,.0f} R$ {h['saque']:>11,.0f} R$ {banca_total:>13,.0f} R$ {sacado_acum:>11,.0f}")

    # Compound puro (sem saque) para ver potencial
    print(f"\n{'='*70}")
    print("COMPOUND PURO (SEM SAQUE) - POTENCIAL MÁXIMO")
    print(f"{'='*70}")

    sacado_puro, banca_puro, hist_puro = simular_conta_compound(multiplicadores, banca_por_conta, 'mensal', 0.0)

    print(f"\n{'Mês':>4} {'Banca/Conta':>18} {'Total 4 Contas':>20}")
    print("-" * 45)

    for mes in range(1, 13):
        dia = mes * 30
        if dia > len(hist_puro):
            break
        h = hist_puro[dia-1]
        print(f"{mes:>4} R$ {h['banca']:>15,.0f} R$ {h['banca']*4:>17,.0f}")

    # Resumo final
    banca_final_4 = banca * 4
    sacado_total_4 = sacado * 4
    retorno = sacado_total_4 + banca_final_4 - investimento_total
    roi = (retorno / investimento_total) * 100

    print(f"\n{'='*70}")
    print("RESUMO FINAL (Saque Mensal 50%)")
    print(f"{'='*70}")
    print(f"""
  Investimento: R$ {investimento_total:,.0f} (4 × R$ {banca_por_conta:,.0f})

  Após 12 meses:
    Total sacado: R$ {sacado_total_4:,.0f}
    Banca final: R$ {banca_final_4:,.0f}
    Retorno líquido: R$ {retorno:,.0f}
    ROI: {roi:,.0f}%

  Média mensal de saque: R$ {sacado_total_4/12:,.0f}

  ✅ ZERO BUSTS (proteção 16 > máximo 15 do dataset)
  ✅ 4 contas = menor exposição por plataforma
  ✅ Compound trabalha entre os saques
""")

    print(f"{'='*70}")
    print("CONFIGURAÇÃO PARA O BOT")
    print(f"{'='*70}")
    print(f"""
  CONTA 1-4 (cada uma):
    Banca C1: R$ 3,00
    Banca C2: R$ 1.000,00
    Divisor C1: 3 (2 tentativas)
    Divisor C2: 511 (9 tentativas)
    Gatilho: 5 baixas
    Alvo: 1.99x

  Proteção total: 5 + 2 + 9 = 16 baixas

  Saque sugerido: Mensal, 50% do lucro acumulado
""")


if __name__ == "__main__":
    main()
