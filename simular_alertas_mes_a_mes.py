#!/usr/bin/env python3
"""
SIMULACAO MES A MES COM ALERTAS
Cada mes inicia com R$ 1000, compound dentro do mes
Comparativo NS7 pura vs NS7+Alertas
"""

from simular_alertas_realtime import SimuladorRealtime
from datetime import datetime
from collections import defaultdict
import simular_alertas_realtime as sim_module


def carregar_por_mes(filepath: str) -> dict:
    """Carrega multiplicadores agrupados por mes"""
    meses = defaultdict(list)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()
                    dt = datetime.strptime(data, '%d/%m/%Y')
                    chave = dt.strftime('%Y-%m')
                    meses[chave].append(mult)
            except:
                continue

    return dict(meses)


def simular_mes(multiplicadores: list, usar_alertas: bool) -> dict:
    """Simula um mes com compound"""
    sim = SimuladorRealtime(banca_inicial=1000.0, usar_alertas=usar_alertas, usar_compound=True)
    return sim.simular(multiplicadores)


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("=" * 130)
    print("SIMULACAO MES A MES - NS7 PURA vs NS7+ALERTAS")
    print("Cada mes inicia com R$ 1000, COM COMPOUND dentro do mes")
    print("=" * 130)

    # Parametros dos alertas
    sim_module.JANELA_MULTS = 300
    sim_module.JANELA_GATILHOS = 30
    sim_module.ALERTA_TAXA_ALTOS = 0.42
    sim_module.ALERTA_TAXA_T5_PLUS = 0.10
    sim_module.ALERTA_TAXA_T6_PLUS = 0.06
    sim_module.ALERTAS_PARA_TROCAR = 2

    print(f"\nPARAMETROS DOS ALERTAS:")
    print(f"  Taxa altos: < {sim_module.ALERTA_TAXA_ALTOS*100:.0f}%")
    print(f"  Taxa T5+: > {sim_module.ALERTA_TAXA_T5_PLUS*100:.0f}%")
    print(f"  Taxa T6+: > {sim_module.ALERTA_TAXA_T6_PLUS*100:.0f}%")
    print(f"  Alertas para trocar: {sim_module.ALERTAS_PARA_TROCAR}+")

    print("\nCarregando dados...")
    meses = carregar_por_mes(csv_path)
    meses_2025_26 = {k: v for k, v in sorted(meses.items()) if k >= '2025-01'}

    print(f"Meses encontrados: {len(meses_2025_26)}")

    # Header
    print("\n" + "=" * 130)
    print(f"{'MES':<10} {'MULTS':>8} │ {'NS7 LUCRO':>12} {'NS7 %':>8} {'NS7 DD':>8} │ "
          f"{'ALERTA LUCRO':>12} {'ALERTA %':>8} {'ALERTA DD':>8} {'%NS8':>6} │ {'DIFF':>12} {'MELHOR':>8}")
    print("-" * 130)

    # Acumuladores
    total_ns7 = 0
    total_alerta = 0
    total_ns7_dd = []
    total_alerta_dd = []
    meses_ns7_melhor = 0
    meses_alerta_melhor = 0

    resultados = []

    for mes, multiplicadores in meses_2025_26.items():
        # NS7 pura
        rel_ns7 = simular_mes(multiplicadores, usar_alertas=False)

        # NS7 + alertas
        rel_alerta = simular_mes(multiplicadores, usar_alertas=True)

        # Diferenca
        diff = rel_alerta['lucro'] - rel_ns7['lucro']

        # % em NS8
        pct_ns8 = (rel_alerta['gatilhos_ns8'] / rel_alerta['gatilhos'] * 100) if rel_alerta['gatilhos'] > 0 else 0

        # Melhor
        if rel_alerta['lucro'] > rel_ns7['lucro'] * 1.01:  # 1% margem
            melhor = "ALERTA"
            meses_alerta_melhor += 1
        elif rel_ns7['lucro'] > rel_alerta['lucro'] * 1.01:
            melhor = "NS7"
            meses_ns7_melhor += 1
        else:
            melhor = "EMPATE"

        # Acumular
        total_ns7 += rel_ns7['lucro']
        total_alerta += rel_alerta['lucro']
        total_ns7_dd.append(rel_ns7['drawdown_max_pct'])
        total_alerta_dd.append(rel_alerta['drawdown_max_pct'])

        resultados.append({
            'mes': mes,
            'ns7': rel_ns7,
            'alerta': rel_alerta,
            'diff': diff,
            'pct_ns8': pct_ns8,
            'melhor': melhor
        })

        # Formatar diff
        diff_str = f"+R${diff:,.0f}" if diff >= 0 else f"-R${-diff:,.0f}"

        print(f"{mes:<10} {len(multiplicadores):>8,} │ "
              f"R${rel_ns7['lucro']:>10,.0f} {rel_ns7['ganho_pct']:>7.1f}% {rel_ns7['drawdown_max_pct']:>7.1f}% │ "
              f"R${rel_alerta['lucro']:>10,.0f} {rel_alerta['ganho_pct']:>7.1f}% {rel_alerta['drawdown_max_pct']:>7.1f}% {pct_ns8:>5.1f}% │ "
              f"{diff_str:>12} {melhor:>8}")

    # Totais
    print("-" * 130)
    n = len(meses_2025_26)
    media_ns7_dd = sum(total_ns7_dd) / n
    media_alerta_dd = sum(total_alerta_dd) / n
    diff_total = total_alerta - total_ns7
    diff_str = f"+R${diff_total:,.0f}" if diff_total >= 0 else f"-R${-diff_total:,.0f}"

    print(f"{'TOTAL':<10} {'-':>8} │ "
          f"R${total_ns7:>10,.0f} {'-':>7} {media_ns7_dd:>7.1f}% │ "
          f"R${total_alerta:>10,.0f} {'-':>7} {media_alerta_dd:>7.1f}% {'-':>5} │ "
          f"{diff_str:>12} {'-':>8}")

    # Resumo
    print("\n" + "=" * 130)
    print("RESUMO")
    print("=" * 130)

    print(f"\n{'Metrica':<35} {'NS7 PURA':>20} {'NS7+ALERTAS':>20}")
    print("-" * 80)
    print(f"{'Lucro Total (todos meses)':<35} R${total_ns7:>17,.2f} R${total_alerta:>17,.2f}")
    print(f"{'Lucro Medio/Mes':<35} R${total_ns7/n:>17,.2f} R${total_alerta/n:>17,.2f}")
    print(f"{'Drawdown Medio':<35} {media_ns7_dd:>19.1f}% {media_alerta_dd:>19.1f}%")
    print(f"{'Meses vencidos':<35} {meses_ns7_melhor:>20} {meses_alerta_melhor:>20}")

    # Diferenca
    print("\n" + "-" * 80)
    print("VEREDITO:")
    print("-" * 80)

    diff_pct = ((total_alerta / total_ns7) - 1) * 100 if total_ns7 > 0 else 0
    dd_diff = media_alerta_dd - media_ns7_dd

    print(f"  Diferenca de lucro total: {'+'if diff_total>=0 else ''}R$ {diff_total:,.2f} ({diff_pct:+.1f}%)")
    print(f"  Diferenca de drawdown medio: {'+'if dd_diff>=0 else ''}{dd_diff:.1f}pp")
    print(f"  Meses NS7 melhor: {meses_ns7_melhor}")
    print(f"  Meses ALERTA melhor: {meses_alerta_melhor}")

    if total_alerta > total_ns7 and media_alerta_dd <= media_ns7_dd:
        print("\n  >> ALERTAS SUPERIORES: Mais lucro com igual ou menos drawdown")
    elif total_alerta > total_ns7:
        print(f"\n  >> ALERTAS MAIS LUCRATIVOS, mas DD medio {dd_diff:+.1f}pp")
    elif media_alerta_dd < media_ns7_dd - 5:
        print(f"\n  >> ALERTAS MAIS SEGUROS: -{-dd_diff:.1f}pp de DD, custou {-diff_pct:.1f}% de lucro")
    else:
        print("\n  >> NS7 PURA FOI MELHOR")

    # Janeiro 2026 em destaque
    print("\n" + "-" * 80)
    print("JANEIRO 2026 (mes mais recente):")
    print("-" * 80)
    jan26 = [r for r in resultados if r['mes'] == '2026-01']
    if jan26:
        r = jan26[0]
        print(f"  NS7 Pura: R$ {r['ns7']['lucro']:,.2f} ({r['ns7']['ganho_pct']:.1f}%), DD {r['ns7']['drawdown_max_pct']:.1f}%")
        print(f"  Alertas:  R$ {r['alerta']['lucro']:,.2f} ({r['alerta']['ganho_pct']:.1f}%), DD {r['alerta']['drawdown_max_pct']:.1f}%")
        print(f"  % em NS8: {r['pct_ns8']:.1f}%")
        print(f"  Melhor: {r['melhor']}")

    print("\n" + "=" * 130)


if __name__ == "__main__":
    main()
