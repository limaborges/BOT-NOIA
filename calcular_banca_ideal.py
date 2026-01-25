#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calcular banca ideal para 4 contas com limite de saque R$ 50k/dia
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


def simular_com_limite_saque(multiplicadores: List[float], gatilho: int, divisor: int,
                              tentativas: int, banca_inicial: float,
                              limite_saque_dia: float) -> dict:
    """Simula com limite de saque diário"""

    rodadas_por_dia = 3456

    banca = banca_inicial
    em_ciclo = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    busts = 0
    total_sacado = 0.0
    lucro_dia = 0.0
    rodada_dia = 0
    dias = 0
    dias_limite_atingido = 0

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
                lucro_dia += lucro
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
                    lucro_dia -= banca
                    banca = banca_inicial

                    em_ciclo = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1

            # Saque com limite
            if banca > banca_inicial:
                lucro_disponivel = banca - banca_inicial
                saque = min(lucro_disponivel, limite_saque_dia)

                if lucro_disponivel >= limite_saque_dia:
                    dias_limite_atingido += 1

                banca -= saque
                total_sacado += saque

            lucro_dia = 0.0
            rodada_dia = 0

    return {
        'banca_inicial': banca_inicial,
        'dias': dias,
        'busts': busts,
        'total_sacado': total_sacado,
        'saque_dia_medio': total_sacado / dias if dias > 0 else 0,
        'banca_final': banca,
        'dias_limite': dias_limite_atingido,
        'pct_dias_limite': (dias_limite_atingido / dias * 100) if dias > 0 else 0,
    }


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    # Configuração: 4 contas, limite total R$ 50k/dia
    # Assumindo limite por conta: R$ 12.5k/dia (50k / 4)
    # Ou se limite é por saque de R$ 5k, e 10 saques/dia total:
    # - 4 contas = 2.5 saques/conta = R$ 12.5k/conta

    limite_por_conta = 12500.0  # R$ 12.5k/dia por conta
    num_contas = 4

    print(f"{'='*80}")
    print(f"CÁLCULO: BANCA IDEAL PARA 4 CONTAS")
    print(f"{'='*80}")
    print(f"\n  Limite saque/dia total: R$ 50.000")
    print(f"  Limite por conta: R$ {limite_por_conta:,.0f}/dia")
    print(f"  Número de contas: {num_contas}")

    # Testar G6+NS10 (proteção 16, 0 busts)
    gatilho = 6
    divisor = 1023
    tentativas = 10

    print(f"\n  Estratégia: G{gatilho} + NS{tentativas} (divisor {divisor})")
    print(f"  Proteção: {gatilho + tentativas} baixas (0 busts)")

    # Calcular lucro teórico por dia
    # Lucro/win = banca * 0.99 / divisor
    # Wins/dia ≈ 40.2 (do G6)
    # Lucro/dia = 40.2 * banca * 0.99 / 1023 = 0.0389 * banca = 3.89%

    taxa_lucro_dia = 40.2 * 0.99 / divisor
    print(f"\n  Taxa de lucro teórica: {taxa_lucro_dia*100:.2f}%/dia")

    # Banca para atingir limite de saque
    banca_para_limite = limite_por_conta / taxa_lucro_dia
    print(f"  Banca para atingir limite: R$ {banca_para_limite:,.0f}")

    print(f"\n{'='*80}")
    print(f"SIMULAÇÃO: DIFERENTES BANCAS POR CONTA")
    print(f"{'='*80}")

    bancas_teste = [25000, 50000, 75000, 100000, 150000, 200000, 300000, 400000, 500000]

    print(f"\n{'Banca/Conta':>14} {'Saque/Dia':>12} {'% do Limite':>12} {'Saque/Mês':>14} {'4 Contas/Mês':>16}")
    print("-" * 72)

    for banca in bancas_teste:
        r = simular_com_limite_saque(multiplicadores, gatilho, divisor, tentativas, banca, limite_por_conta)
        pct_limite = (r['saque_dia_medio'] / limite_por_conta) * 100
        saque_mes = r['saque_dia_medio'] * 30
        total_4_contas = saque_mes * 4

        print(f"R$ {banca:>11,} R$ {r['saque_dia_medio']:>9,.0f} {pct_limite:>11.0f}% R$ {saque_mes:>11,.0f} R$ {total_4_contas:>13,.0f}")

    # Encontrar banca ótima (que atinge ~100% do limite)
    print(f"\n{'='*80}")
    print(f"ANÁLISE: BANCA ÓTIMA")
    print(f"{'='*80}")

    # Testar mais granularmente
    melhor = None
    for banca in range(50000, 500001, 25000):
        r = simular_com_limite_saque(multiplicadores, gatilho, divisor, tentativas, banca, limite_por_conta)
        pct_limite = (r['saque_dia_medio'] / limite_por_conta) * 100

        if melhor is None or (pct_limite <= 100 and r['saque_dia_medio'] > melhor['saque_dia_medio']):
            melhor = r
            melhor['pct_limite'] = pct_limite

        if pct_limite >= 95:
            break

    print(f"\n  Banca ótima por conta: R$ {melhor['banca_inicial']:,.0f}")
    print(f"  Saque médio/dia: R$ {melhor['saque_dia_medio']:,.0f}")
    print(f"  % do limite: {melhor['pct_limite']:.0f}%")
    print(f"  Dias que atingiu limite: {melhor['dias_limite']} de {melhor['dias']} ({melhor['pct_dias_limite']:.0f}%)")

    investimento_total = melhor['banca_inicial'] * 4
    saque_mensal_total = melhor['saque_dia_medio'] * 30 * 4

    print(f"\n{'='*80}")
    print(f"CONFIGURAÇÃO FINAL: 4 CONTAS")
    print(f"{'='*80}")
    print(f"""
  INVESTIMENTO:
    Por conta: R$ {melhor['banca_inicial']:,.0f}
    Total (4 contas): R$ {investimento_total:,.0f}

  RETORNO ESPERADO:
    Por conta/dia: R$ {melhor['saque_dia_medio']:,.0f}
    Por conta/mês: R$ {melhor['saque_dia_medio']*30:,.0f}
    Total 4 contas/mês: R$ {saque_mensal_total:,.0f}

  ESTRATÉGIA:
    G6 + NS10 (divisor 1023)
    Proteção: 16 baixas
    Alvo: 1.99x
    Busts esperados: 0

  LIMITE DE SAQUE:
    Máximo/dia: R$ 50.000
    Utilizando: ~{melhor['pct_limite']:.0f}%
""")

    # Alternativa com G6+NS9 (mais lucro, mas 2 busts)
    print(f"{'='*80}")
    print(f"ALTERNATIVA: G6+NS9 (Proteção 15, 2 busts)")
    print(f"{'='*80}")

    r_agr = simular_com_limite_saque(multiplicadores, 6, 511, 9, melhor['banca_inicial'], limite_por_conta)
    print(f"\n  Mesma banca: R$ {melhor['banca_inicial']:,.0f}")
    print(f"  Saque/dia: R$ {r_agr['saque_dia_medio']:,.0f}")
    print(f"  Saque/mês (4 contas): R$ {r_agr['saque_dia_medio']*30*4:,.0f}")
    print(f"  Busts: {r_agr['busts']}")
    print(f"  ⚠️  Com busts, precisa de reserva para reiniciar")


if __name__ == "__main__":
    main()
