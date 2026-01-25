#!/usr/bin/env python3
"""
Simulacao Mes a Mes - NS7 vs NS8
Cada mes inicia com banca de R$ 1000
Analise dos 12 meses de 2025
"""

from simular_ns8_completo import SimuladorCompleto, ALVO_DEFESA
from datetime import datetime
from collections import defaultdict

def carregar_por_mes(filepath: str) -> dict:
    """Carrega multiplicadores agrupados por mes (YYYY-MM)"""
    meses = defaultdict(list)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)  # Skip header

        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()  # DD/MM/YYYY

                    dt = datetime.strptime(data, '%d/%m/%Y')
                    chave = dt.strftime('%Y-%m')

                    meses[chave].append(mult)
            except:
                continue

    return dict(meses)


def simular_mes(multiplicadores: list, nivel: int, banca: float = 1000.0) -> dict:
    """Simula um mes com nivel especifico"""
    sim = SimuladorCompleto(banca_inicial=banca, nivel=nivel)
    return sim.simular(multiplicadores)


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'
    banca_mensal = 1000.0

    print("=" * 100)
    print("SIMULACAO MES A MES - NS7 vs NS8")
    print("Cada mes inicia com banca de R$ 1.000")
    print(f"Defesa: {ALVO_DEFESA}x")
    print("=" * 100)

    print("\nCarregando dados...")
    meses = carregar_por_mes(csv_path)

    # Filtrar apenas 2025
    meses_2025 = {k: v for k, v in meses.items() if k.startswith('2025')}
    meses_2025 = dict(sorted(meses_2025.items()))

    print(f"Meses de 2025 encontrados: {len(meses_2025)}")

    # Header da tabela
    print("\n" + "=" * 100)
    print(f"{'MES':<10} {'MULTS':>8} {'GATILHOS':>10} │ {'NS7 LUCRO':>12} {'NS7 %':>8} {'NS7 DD':>8} {'NS7 B':>6} │ {'NS8 LUCRO':>12} {'NS8 %':>8} {'NS8 DD':>8} {'NS8 B':>6} │ {'MELHOR':>8}")
    print("-" * 100)

    # Acumuladores
    total_ns7_lucro = 0
    total_ns8_lucro = 0
    total_ns7_busts = 0
    total_ns8_busts = 0
    meses_ns7_melhor = 0
    meses_ns8_melhor = 0
    meses_empate = 0

    resultados = []

    for mes, multiplicadores in meses_2025.items():
        # Simular NS7
        rel7 = simular_mes(multiplicadores, nivel=7, banca=banca_mensal)

        # Simular NS8
        rel8 = simular_mes(multiplicadores, nivel=8, banca=banca_mensal)

        # Determinar melhor
        if rel7['ganho_pct'] > rel8['ganho_pct'] + 1:  # Margem de 1%
            melhor = "NS7"
            meses_ns7_melhor += 1
        elif rel8['ganho_pct'] > rel7['ganho_pct'] + 1:
            melhor = "NS8"
            meses_ns8_melhor += 1
        else:
            melhor = "EMPATE"
            meses_empate += 1

        # Acumular
        total_ns7_lucro += rel7['lucro']
        total_ns8_lucro += rel8['lucro']
        total_ns7_busts += rel7['busts']
        total_ns8_busts += rel8['busts']

        # Guardar resultado
        resultados.append({
            'mes': mes,
            'mults': len(multiplicadores),
            'gatilhos': rel7['gatilhos'],
            'ns7': rel7,
            'ns8': rel8,
            'melhor': melhor
        })

        # Formatar busts
        b7 = f"{rel7['busts']}" if rel7['busts'] == 0 else f"*{rel7['busts']}*"
        b8 = f"{rel8['busts']}" if rel8['busts'] == 0 else f"*{rel8['busts']}*"

        # Imprimir linha
        print(f"{mes:<10} {len(multiplicadores):>8,} {rel7['gatilhos']:>10,} │ "
              f"R$ {rel7['lucro']:>9,.0f} {rel7['ganho_pct']:>7.1f}% {rel7['drawdown_max_pct']:>7.1f}% {b7:>6} │ "
              f"R$ {rel8['lucro']:>9,.0f} {rel8['ganho_pct']:>7.1f}% {rel8['drawdown_max_pct']:>7.1f}% {b8:>6} │ "
              f"{melhor:>8}")

    # Totais
    print("-" * 100)
    total_mults = sum(len(m) for m in meses_2025.values())
    total_gatilhos = sum(r['gatilhos'] for r in resultados)

    print(f"{'TOTAL':<10} {total_mults:>8,} {total_gatilhos:>10,} │ "
          f"R$ {total_ns7_lucro:>9,.0f} {'-':>7} {'-':>7} {total_ns7_busts:>6} │ "
          f"R$ {total_ns8_lucro:>9,.0f} {'-':>7} {'-':>7} {total_ns8_busts:>6} │ {'-':>8}")

    # Medias
    n_meses = len(meses_2025)
    media_ns7_lucro = total_ns7_lucro / n_meses
    media_ns8_lucro = total_ns8_lucro / n_meses
    media_ns7_pct = sum(r['ns7']['ganho_pct'] for r in resultados) / n_meses
    media_ns8_pct = sum(r['ns8']['ganho_pct'] for r in resultados) / n_meses
    media_ns7_dd = sum(r['ns7']['drawdown_max_pct'] for r in resultados) / n_meses
    media_ns8_dd = sum(r['ns8']['drawdown_max_pct'] for r in resultados) / n_meses

    print(f"{'MEDIA':<10} {'-':>8} {'-':>10} │ "
          f"R$ {media_ns7_lucro:>9,.0f} {media_ns7_pct:>7.1f}% {media_ns7_dd:>7.1f}% {'-':>6} │ "
          f"R$ {media_ns8_lucro:>9,.0f} {media_ns8_pct:>7.1f}% {media_ns8_dd:>7.1f}% {'-':>6} │ {'-':>8}")

    # Resumo final
    print("\n" + "=" * 100)
    print("RESUMO ANUAL 2025")
    print("=" * 100)

    print(f"\n{'Metrica':<30} {'NS7':>20} {'NS8':>20}")
    print("-" * 75)
    print(f"{'Lucro Total (12 meses)':<30} R$ {total_ns7_lucro:>16,.2f} R$ {total_ns8_lucro:>16,.2f}")
    print(f"{'Lucro Medio/Mes':<30} R$ {media_ns7_lucro:>16,.2f} R$ {media_ns8_lucro:>16,.2f}")
    print(f"{'Ganho % Medio/Mes':<30} {media_ns7_pct:>19.1f}% {media_ns8_pct:>19.1f}%")
    print(f"{'Drawdown Medio':<30} {media_ns7_dd:>19.1f}% {media_ns8_dd:>19.1f}%")
    print(f"{'Total Busts':<30} {total_ns7_busts:>20} {total_ns8_busts:>20}")
    print("-" * 75)
    print(f"{'Meses com melhor performance':<30} {meses_ns7_melhor:>20} {meses_ns8_melhor:>20}")
    print(f"{'Meses empate':<30} {meses_empate:>20}")

    # Diferenca
    diff_lucro = total_ns8_lucro - total_ns7_lucro
    diff_busts = total_ns8_busts - total_ns7_busts

    print("\n" + "-" * 75)
    print("VEREDITO:")
    print("-" * 75)
    print(f"  Diferenca de lucro anual: {'+'if diff_lucro>=0 else ''}R$ {diff_lucro:,.2f}")
    print(f"  Diferenca de busts: {'+'if diff_busts>=0 else ''}{diff_busts}")

    if total_ns8_lucro > total_ns7_lucro and total_ns8_busts <= total_ns7_busts:
        print("\n  >> NS8 SUPERIOR no ano: Mais lucro com igual ou menos busts")
    elif total_ns8_lucro > total_ns7_lucro:
        print(f"\n  >> NS8 mais lucrativo (+R$ {diff_lucro:,.0f}), mas com +{diff_busts} busts")
    elif total_ns8_busts < total_ns7_busts:
        print(f"\n  >> NS8 mais seguro ({-diff_busts} busts a menos)")
    else:
        print("\n  >> NS7 foi melhor no ano")

    # Meses com bust
    print("\n" + "-" * 75)
    print("MESES COM BUST:")
    for r in resultados:
        if r['ns7']['busts'] > 0 or r['ns8']['busts'] > 0:
            print(f"  {r['mes']}: NS7={r['ns7']['busts']} busts, NS8={r['ns8']['busts']} busts")

    if total_ns7_busts == 0 and total_ns8_busts == 0:
        print("  Nenhum bust em 2025!")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
