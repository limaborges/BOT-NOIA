#!/usr/bin/env python3
"""
TESTE DE PARAMETROS DOS ALERTAS
Testa varias combinacoes para encontrar a que melhor funciona
"""

from simular_alertas_realtime import SimuladorRealtime, carregar_multiplicadores
from simular_alertas_realtime import (
    JANELA_MULTS, JANELA_GATILHOS,
    ALERTA_TAXA_ALTOS, ALERTA_TAXA_T5_PLUS, ALERTA_TAXA_T6_PLUS,
    ALERTA_VOLATILIDADE, ALERTAS_PARA_TROCAR
)
import simular_alertas_realtime as sim_module


def testar_configuracao(multiplicadores, config: dict) -> dict:
    """Testa uma configuracao especifica"""
    # Aplicar config
    sim_module.JANELA_MULTS = config.get('janela_mults', 300)
    sim_module.JANELA_GATILHOS = config.get('janela_gatilhos', 30)
    sim_module.ALERTA_TAXA_ALTOS = config.get('taxa_altos', 0.42)
    sim_module.ALERTA_TAXA_T5_PLUS = config.get('taxa_t5', 0.10)
    sim_module.ALERTA_TAXA_T6_PLUS = config.get('taxa_t6', 0.06)
    sim_module.ALERTA_VOLATILIDADE = config.get('volatilidade', 1.25)
    sim_module.ALERTAS_PARA_TROCAR = config.get('alertas_trocar', 2)

    # Simular com alertas
    sim = SimuladorRealtime(banca_inicial=1000.0, usar_alertas=True, usar_compound=False)
    rel = sim.simular(multiplicadores)

    return rel


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(csv_path)
    print(f"Total: {len(multiplicadores):,} multiplicadores")

    # Baseline NS7 pura
    print("\nCalculando baseline NS7 pura...")
    sim_ns7 = SimuladorRealtime(banca_inicial=1000.0, usar_alertas=False, usar_compound=False)
    rel_ns7 = sim_ns7.simular(multiplicadores)
    lucro_ns7 = rel_ns7['lucro']
    dd_ns7 = rel_ns7['drawdown_max_pct']

    print(f"  NS7 Pura: Lucro R$ {lucro_ns7:,.2f}, DD {dd_ns7:.2f}%")

    # Configuracoes para testar
    configs = []

    # Variar threshold de taxa de altos
    for taxa in [0.40, 0.42, 0.44, 0.46]:
        configs.append({
            'nome': f'TaxaAltos<{taxa*100:.0f}%',
            'taxa_altos': taxa,
            'alertas_trocar': 1  # Trocar com apenas 1 alerta
        })

    # Variar threshold de T5+
    for t5 in [0.08, 0.10, 0.12, 0.15]:
        configs.append({
            'nome': f'T5+>{t5*100:.0f}%',
            'taxa_t5': t5,
            'alertas_trocar': 1
        })

    # Variar threshold de T6+
    for t6 in [0.04, 0.06, 0.08]:
        configs.append({
            'nome': f'T6+>{t6*100:.0f}%',
            'taxa_t6': t6,
            'alertas_trocar': 1
        })

    # Combinacoes mais agressivas (1 alerta basta)
    configs.append({
        'nome': 'Agressivo1',
        'taxa_altos': 0.44,
        'taxa_t5': 0.08,
        'taxa_t6': 0.04,
        'alertas_trocar': 1
    })

    # Combinacoes mais conservadoras (precisa 2 alertas)
    configs.append({
        'nome': 'Conservador2',
        'taxa_altos': 0.40,
        'taxa_t5': 0.12,
        'taxa_t6': 0.06,
        'alertas_trocar': 2
    })

    # Muito conservador (3 alertas)
    configs.append({
        'nome': 'MuitoConserv3',
        'taxa_altos': 0.40,
        'taxa_t5': 0.10,
        'taxa_t6': 0.05,
        'alertas_trocar': 3
    })

    # Janelas diferentes
    for janela in [100, 200, 500]:
        configs.append({
            'nome': f'Janela{janela}',
            'janela_mults': janela,
            'janela_gatilhos': janela // 10,
            'alertas_trocar': 2
        })

    # Testar todas
    print("\n" + "=" * 120)
    print("TESTE DE PARAMETROS")
    print("=" * 120)
    print(f"{'CONFIG':<20} {'LUCRO':>15} {'DIFF':>12} {'DIFF%':>8} {'DD%':>8} {'DD_DIFF':>8} {'%NS8':>8} {'TROCAS':>8}")
    print("-" * 120)

    resultados = []

    for config in configs:
        rel = testar_configuracao(multiplicadores, config)

        diff = rel['lucro'] - lucro_ns7
        diff_pct = (diff / lucro_ns7) * 100 if lucro_ns7 > 0 else 0
        dd_diff = rel['drawdown_max_pct'] - dd_ns7
        pct_ns8 = (rel['gatilhos_ns8'] / rel['gatilhos'] * 100) if rel['gatilhos'] > 0 else 0

        resultados.append({
            'config': config['nome'],
            'lucro': rel['lucro'],
            'diff': diff,
            'diff_pct': diff_pct,
            'dd': rel['drawdown_max_pct'],
            'dd_diff': dd_diff,
            'pct_ns8': pct_ns8,
            'trocas': rel['trocas_para_ns8']
        })

        sinal = '+' if diff >= 0 else ''
        sinal_dd = '+' if dd_diff >= 0 else ''

        print(f"{config['nome']:<20} R${rel['lucro']:>12,.0f} {sinal}R${diff:>9,.0f} {sinal}{diff_pct:>6.1f}% "
              f"{rel['drawdown_max_pct']:>7.2f}% {sinal_dd}{dd_diff:>6.2f}pp {pct_ns8:>7.1f}% {rel['trocas_para_ns8']:>8}")

    # Ranking
    print("\n" + "=" * 120)
    print("RANKING POR LUCRO (melhores configs)")
    print("=" * 120)

    for i, r in enumerate(sorted(resultados, key=lambda x: x['lucro'], reverse=True)[:10], 1):
        sinal = '+' if r['diff'] >= 0 else ''
        print(f"{i:>2}. {r['config']:<20} Lucro: R${r['lucro']:>12,.0f} ({sinal}{r['diff_pct']:.1f}%) DD: {r['dd']:.2f}%")

    # Ranking por reducao de DD
    print("\n" + "-" * 120)
    print("RANKING POR REDUCAO DE DRAWDOWN")
    print("-" * 120)

    for i, r in enumerate(sorted(resultados, key=lambda x: x['dd_diff'])[:10], 1):
        sinal_dd = '+' if r['dd_diff'] >= 0 else ''
        print(f"{i:>2}. {r['config']:<20} DD: {r['dd']:.2f}% ({sinal_dd}{r['dd_diff']:.2f}pp) Lucro: R${r['lucro']:>12,.0f}")

    # Melhor tradeoff
    print("\n" + "-" * 120)
    print("MELHOR TRADEOFF (menor perda de lucro com reducao de DD)")
    print("-" * 120)

    # Score = reducao de DD - perda de lucro (em termos relativos)
    for r in resultados:
        # Se perdeu lucro mas reduziu DD, pode ser bom
        # Score positivo = bom (ganhou lucro ou reduziu DD)
        r['score'] = -r['dd_diff'] - (r['diff_pct'] / 10)  # Peso maior para DD

    for i, r in enumerate(sorted(resultados, key=lambda x: x['score'], reverse=True)[:10], 1):
        print(f"{i:>2}. {r['config']:<20} Score: {r['score']:>6.2f} "
              f"(Lucro: {r['diff_pct']:+.1f}%, DD: {r['dd_diff']:+.2f}pp)")


if __name__ == "__main__":
    main()
