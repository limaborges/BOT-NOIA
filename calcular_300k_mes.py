#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta: R$ 300k/mês com 4 contas
"""

import csv
from typing import List

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


def simular(multiplicadores: List[float], gatilho: int, divisor: int,
            tentativas: int, banca_inicial: float, saque_alvo_dia: float) -> dict:
    """Simula com saque diário alvo"""

    rodadas_por_dia = 3456

    banca = banca_inicial
    em_ciclo = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    busts = 0
    total_sacado = 0.0
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
                banca += lucro

                em_ciclo = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1

                if tentativa > tentativas:
                    busts += 1
                    banca = banca_inicial

                    em_ciclo = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1

            # Saque diário (até o alvo, restante fica como compound)
            if banca > banca_inicial:
                lucro_disponivel = banca - banca_inicial
                saque = min(lucro_disponivel, saque_alvo_dia)
                banca -= saque
                total_sacado += saque

            rodada_dia = 0

    return {
        'dias': dias,
        'busts': busts,
        'total_sacado': total_sacado,
        'saque_dia_medio': total_sacado / dias if dias > 0 else 0,
        'banca_final': banca,
    }


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    # Meta: R$ 300k/mês = R$ 10k/dia = R$ 2.5k/dia por conta
    meta_mes = 300000
    meta_dia = meta_mes / 30
    meta_dia_conta = meta_dia / 4

    print(f"{'='*70}")
    print(f"META: R$ {meta_mes:,.0f}/MÊS COM 4 CONTAS")
    print(f"{'='*70}")
    print(f"\n  R$ {meta_mes:,.0f}/mês ÷ 30 dias = R$ {meta_dia:,.0f}/dia")
    print(f"  R$ {meta_dia:,.0f}/dia ÷ 4 contas = R$ {meta_dia_conta:,.0f}/dia por conta")

    # G6+NS10 (proteção 16, 0 busts)
    gatilho = 6
    divisor = 1023
    tentativas = 10

    # Taxa teórica: 40.2 wins/dia * 0.99 / 1023 = 3.89%
    taxa = 40.2 * 0.99 / divisor
    banca_teorica = meta_dia_conta / taxa

    print(f"\n  Estratégia: G{gatilho}+NS{tentativas} (0 busts)")
    print(f"  Taxa diária: {taxa*100:.2f}%")
    print(f"  Banca teórica por conta: R$ {banca_teorica:,.0f}")

    print(f"\n{'='*70}")
    print(f"SIMULAÇÃO: ENCONTRAR BANCA IDEAL")
    print(f"{'='*70}")

    # Testar diferentes bancas
    print(f"\n{'Banca/Conta':>14} {'Saque/Dia':>12} {'Saque/Mês':>14} {'4 Contas/Mês':>16} {'Meta?':>8}")
    print("-" * 68)

    banca_ideal = None
    for banca in [40000, 50000, 60000, 70000, 80000, 100000, 120000, 150000]:
        r = simular(multiplicadores, gatilho, divisor, tentativas, banca, meta_dia_conta * 1.5)
        saque_mes_conta = r['saque_dia_medio'] * 30
        saque_mes_total = saque_mes_conta * 4
        atingiu = "✅" if saque_mes_total >= meta_mes else "❌"

        print(f"R$ {banca:>11,} R$ {r['saque_dia_medio']:>9,.0f} R$ {saque_mes_conta:>11,.0f} R$ {saque_mes_total:>13,.0f} {atingiu:>8}")

        if banca_ideal is None and saque_mes_total >= meta_mes:
            banca_ideal = banca

    # Refinar a banca ideal
    print(f"\n{'='*70}")
    print(f"REFINANDO BANCA IDEAL")
    print(f"{'='*70}")

    if banca_ideal:
        for banca in range(banca_ideal - 20000, banca_ideal + 10000, 5000):
            if banca < 10000:
                continue
            r = simular(multiplicadores, gatilho, divisor, tentativas, banca, meta_dia_conta * 1.5)
            saque_mes_total = r['saque_dia_medio'] * 30 * 4

            if saque_mes_total >= meta_mes * 0.95:  # 95% da meta
                banca_ideal = banca
                break

    r_ideal = simular(multiplicadores, gatilho, divisor, tentativas, banca_ideal, meta_dia_conta * 1.5)

    print(f"\n{'='*70}")
    print(f"CONFIGURAÇÃO PARA R$ 300K/MÊS")
    print(f"{'='*70}")
    print(f"""
  BANCA POR CONTA: R$ {banca_ideal:,.0f}
  INVESTIMENTO TOTAL: R$ {banca_ideal * 4:,.0f}

  RETORNO (G6+NS10, 0 busts):
    Por conta/dia: R$ {r_ideal['saque_dia_medio']:,.0f}
    Por conta/mês: R$ {r_ideal['saque_dia_medio']*30:,.0f}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    TOTAL 4 CONTAS/MÊS: R$ {r_ideal['saque_dia_medio']*30*4:,.0f}

  ROI:
    Mensal: {(r_ideal['saque_dia_medio']*30)/(banca_ideal)*100:.0f}%
    Anual: {(r_ideal['saque_dia_medio']*365)/(banca_ideal)*100:.0f}%

  RISCO:
    Busts em 374 dias: {r_ideal['busts']}
""")

    # Comparar com G6+NS9 (mais agressivo)
    print(f"{'='*70}")
    print(f"ALTERNATIVA AGRESSIVA: G6+NS9 (2 busts)")
    print(f"{'='*70}")

    # G6+NS9 tem taxa maior: 40.2 * 0.99 / 511 = 7.78%
    taxa_agr = 40.2 * 0.99 / 511
    banca_agr = meta_dia_conta / taxa_agr

    print(f"\n  Taxa diária: {taxa_agr*100:.2f}%")
    print(f"  Banca teórica por conta: R$ {banca_agr:,.0f}")

    # Simular
    r_agr = simular(multiplicadores, 6, 511, 9, int(banca_agr), meta_dia_conta * 1.5)

    print(f"""
  BANCA POR CONTA: R$ {int(banca_agr):,}
  INVESTIMENTO TOTAL: R$ {int(banca_agr) * 4:,}

  RETORNO:
    Por conta/mês: R$ {r_agr['saque_dia_medio']*30:,.0f}
    TOTAL 4 CONTAS/MÊS: R$ {r_agr['saque_dia_medio']*30*4:,.0f}

  ⚠️  RISCO: {r_agr['busts']} busts em 374 dias
      Precisa de R$ {int(banca_agr):,} de reserva por conta
      Total com reserva: R$ {int(banca_agr) * 8:,}
""")


if __name__ == "__main__":
    main()
