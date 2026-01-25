#!/usr/bin/env python3
"""
Simulador NS8 - Periodo 08/01/2026 a 20/01/2026
Banca: R$ 1000
Defesa: 1.10x
"""

from simulador_ns8 import Simulador, comparar_ns7_ns8, ALVO_DEFESA, NIVEIS
from datetime import datetime

def carregar_multiplicadores_periodo(filepath: str, data_inicio: str, data_fim: str):
    """
    Carrega multiplicadores de um periodo especifico.
    Formato data: DD/MM/YYYY
    """
    multiplicadores = []
    count_total = 0
    count_periodo = 0

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        header = next(f)  # Skip header

        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()  # Coluna Data (DD/MM/YYYY)

                    count_total += 1

                    # Converter para comparacao
                    try:
                        dt = datetime.strptime(data, '%d/%m/%Y')
                        dt_inicio = datetime.strptime(data_inicio, '%d/%m/%Y')
                        dt_fim = datetime.strptime(data_fim, '%d/%m/%Y')

                        if dt_inicio <= dt <= dt_fim:
                            multiplicadores.append(mult)
                            count_periodo += 1
                    except:
                        pass
            except:
                continue

    print(f"  Total no arquivo: {count_total:,}")
    print(f"  Periodo {data_inicio} a {data_fim}: {count_periodo:,}")

    return multiplicadores


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'
    banca = 1000.0

    print("=" * 80)
    print("SIMULACAO NS8 - PERIODO 08/01/2026 a 20/01/2026")
    print("=" * 80)
    print(f"Banca: R$ {banca:,.2f}")
    print(f"Defesa: {ALVO_DEFESA}x")
    print()

    print(f"Carregando dados de: {csv_path}")
    multiplicadores = carregar_multiplicadores_periodo(
        csv_path,
        data_inicio='08/01/2026',
        data_fim='20/01/2026'
    )

    if not multiplicadores:
        print("ERRO: Nenhum multiplicador encontrado no periodo!")
        return

    print(f"\nMultiplicadores no periodo: {len(multiplicadores):,}")

    # Calcular dias
    dias = 13  # 08 a 20 janeiro = 13 dias
    mults_por_dia = len(multiplicadores) / dias
    print(f"Media por dia: {mults_por_dia:,.0f} multiplicadores")

    # Comparativo NS7 vs NS8
    print("\n")
    rel7, rel8 = comparar_ns7_ns8(multiplicadores, banca=banca)

    # Analise adicional NS8
    print("\n" + "=" * 80)
    print("ANALISE DETALHADA NS8")
    print("=" * 80)

    if rel8['gatilhos'] > 0:
        lucro_por_gatilho = rel8['lucro'] / rel8['gatilhos']
        lucro_por_dia = rel8['lucro'] / dias
        lucro_pct_dia = rel8['ganho_pct'] / dias

        print(f"\nPerformance NS8:")
        print(f"  Lucro total: R$ {rel8['lucro']:,.2f} ({rel8['ganho_pct']:.2f}%)")
        print(f"  Lucro por dia: R$ {lucro_por_dia:,.2f} ({lucro_pct_dia:.2f}%/dia)")
        print(f"  Lucro por gatilho: R$ {lucro_por_gatilho:,.2f}")
        print(f"  Gatilhos por dia: {rel8['gatilhos']/dias:.1f}")

        # Analise de risco
        print(f"\nRisco NS8:")
        print(f"  Busts: {rel8['busts']}")
        print(f"  Drawdown maximo: {rel8['drawdown_max_pct']:.2f}%")

        if rel8['busts'] > 0:
            bust_rate = rel8['busts'] / rel8['gatilhos'] * 100
            print(f"  Taxa de bust: {bust_rate:.4f}%")
            print(f"  1 bust a cada: {rel8['gatilhos']/rel8['busts']:.0f} gatilhos")

        # Comparativo direto
        print(f"\nComparativo NS8 vs NS7:")
        diff_lucro = rel8['lucro'] - rel7['lucro']
        diff_pct = rel8['ganho_pct'] - rel7['ganho_pct']
        diff_busts = rel8['busts'] - rel7['busts']
        diff_dd = rel8['drawdown_max_pct'] - rel7['drawdown_max_pct']

        sinal_lucro = "+" if diff_lucro >= 0 else ""
        sinal_pct = "+" if diff_pct >= 0 else ""
        sinal_busts = "+" if diff_busts >= 0 else ""
        sinal_dd = "+" if diff_dd >= 0 else ""

        print(f"  Diferenca lucro: {sinal_lucro}R$ {diff_lucro:,.2f} ({sinal_pct}{diff_pct:.2f}%)")
        print(f"  Diferenca busts: {sinal_busts}{diff_busts}")
        print(f"  Diferenca DD: {sinal_dd}{diff_dd:.2f}pp")

        # Conclusao
        print("\n" + "-" * 80)
        print("CONCLUSAO:")
        if rel8['ganho_pct'] > rel7['ganho_pct'] and rel8['busts'] <= rel7['busts']:
            print("  NS8 MELHOR: Maior lucro com igual ou menos busts")
        elif rel8['ganho_pct'] > rel7['ganho_pct']:
            print(f"  NS8 tem +{diff_pct:.2f}% lucro, mas {diff_busts} busts a mais")
        elif rel8['busts'] < rel7['busts']:
            print(f"  NS8 tem menos busts ({rel8['busts']} vs {rel7['busts']}), mas menor lucro")
        else:
            print("  NS7 parece melhor neste periodo")


if __name__ == "__main__":
    main()
