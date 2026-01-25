#!/usr/bin/env python3
"""
VALIDACAO OUT-OF-SAMPLE DOS ALERTAS
Treina em 2025, testa em Janeiro 2026

Isso evita overfitting - os alertas nao "conhecem" os dados de teste
"""

from simular_alertas_realtime import SimuladorRealtime, NIVEIS
from datetime import datetime
from collections import defaultdict
import simular_alertas_realtime as sim_module


def carregar_por_periodo(filepath: str) -> dict:
    """Carrega multiplicadores separados por periodo"""
    dados = {
        'treino': [],  # 2025 completo
        'teste': [],   # Janeiro 2026
    }

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()

                    dt = datetime.strptime(data, '%d/%m/%Y')

                    if dt.year == 2025:
                        dados['treino'].append(mult)
                    elif dt.year == 2026:
                        dados['teste'].append(mult)
            except:
                continue

    return dados


def simular_periodo(multiplicadores, usar_alertas: bool) -> dict:
    """Simula um periodo"""
    sim = SimuladorRealtime(banca_inicial=1000.0, usar_alertas=usar_alertas, usar_compound=False)
    return sim.simular(multiplicadores)


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("=" * 100)
    print("VALIDACAO OUT-OF-SAMPLE")
    print("Treino: 2025 completo | Teste: Janeiro 2026")
    print("=" * 100)

    print("\nCarregando dados...")
    dados = carregar_por_periodo(csv_path)

    print(f"  TREINO (2025): {len(dados['treino']):,} multiplicadores")
    print(f"  TESTE (Jan 2026): {len(dados['teste']):,} multiplicadores")

    # =====================================================================
    # FASE 1: TREINO EM 2025 - Encontrar melhores parametros
    # =====================================================================
    print("\n" + "=" * 100)
    print("FASE 1: TREINAMENTO (2025)")
    print("=" * 100)

    # Baseline NS7 em 2025
    print("\nBaseline NS7 pura em 2025...")
    rel_ns7_treino = simular_periodo(dados['treino'], usar_alertas=False)
    print(f"  Lucro: R$ {rel_ns7_treino['lucro']:,.2f}")
    print(f"  Drawdown: {rel_ns7_treino['drawdown_max_pct']:.2f}%")
    print(f"  Gatilhos: {rel_ns7_treino['gatilhos']:,}")

    # Testar diferentes configs em 2025
    configs_teste = [
        {'nome': 'Conservador', 'taxa_altos': 0.40, 'taxa_t5': 0.12, 'taxa_t6': 0.06, 'alertas_trocar': 2},
        {'nome': 'Moderado', 'taxa_altos': 0.42, 'taxa_t5': 0.10, 'taxa_t6': 0.05, 'alertas_trocar': 2},
        {'nome': 'Agressivo', 'taxa_altos': 0.44, 'taxa_t5': 0.08, 'taxa_t6': 0.04, 'alertas_trocar': 1},
        {'nome': 'SoTaxaAltos', 'taxa_altos': 0.40, 'alertas_trocar': 1},
        {'nome': 'SoT5', 'taxa_t5': 0.08, 'alertas_trocar': 1},
        {'nome': 'Janela100', 'janela_mults': 100, 'janela_gatilhos': 10, 'alertas_trocar': 2},
        {'nome': 'Janela500', 'janela_mults': 500, 'janela_gatilhos': 50, 'alertas_trocar': 2},
    ]

    print("\nTestando configs em 2025:")
    print(f"{'CONFIG':<15} {'LUCRO':>15} {'DIFF':>12} {'DD%':>8} {'DD_DIFF':>10} {'%NS8':>8}")
    print("-" * 75)

    resultados_treino = []
    melhor_config = None
    melhor_score = -999999

    for config in configs_teste:
        # Aplicar config
        sim_module.JANELA_MULTS = config.get('janela_mults', 300)
        sim_module.JANELA_GATILHOS = config.get('janela_gatilhos', 30)
        sim_module.ALERTA_TAXA_ALTOS = config.get('taxa_altos', 0.42)
        sim_module.ALERTA_TAXA_T5_PLUS = config.get('taxa_t5', 0.10)
        sim_module.ALERTA_TAXA_T6_PLUS = config.get('taxa_t6', 0.06)
        sim_module.ALERTAS_PARA_TROCAR = config.get('alertas_trocar', 2)

        rel = simular_periodo(dados['treino'], usar_alertas=True)

        diff = rel['lucro'] - rel_ns7_treino['lucro']
        dd_diff = rel['drawdown_max_pct'] - rel_ns7_treino['drawdown_max_pct']
        pct_ns8 = (rel['gatilhos_ns8'] / rel['gatilhos'] * 100) if rel['gatilhos'] > 0 else 0

        # Score: priorizamos reducao de DD se lucro nao cair muito
        score = -dd_diff - (diff / rel_ns7_treino['lucro'] * 100) / 5  # Peso menor para perda de lucro

        if score > melhor_score:
            melhor_score = score
            melhor_config = config.copy()
            melhor_config['resultado_treino'] = rel

        resultados_treino.append({
            'config': config,
            'lucro': rel['lucro'],
            'diff': diff,
            'dd': rel['drawdown_max_pct'],
            'dd_diff': dd_diff,
            'pct_ns8': pct_ns8,
            'score': score
        })

        sinal = '+' if diff >= 0 else ''
        sinal_dd = '+' if dd_diff >= 0 else ''
        print(f"{config['nome']:<15} R${rel['lucro']:>12,.0f} {sinal}R${diff:>9,.0f} "
              f"{rel['drawdown_max_pct']:>7.2f}% {sinal_dd}{dd_diff:>8.2f}pp {pct_ns8:>7.1f}%")

    print("\n" + "-" * 75)
    print(f"MELHOR CONFIG EM 2025: {melhor_config['nome']}")
    print(f"  Score: {melhor_score:.2f}")

    # =====================================================================
    # FASE 2: TESTE EM JANEIRO 2026 (OUT-OF-SAMPLE)
    # =====================================================================
    print("\n" + "=" * 100)
    print("FASE 2: TESTE OUT-OF-SAMPLE (Janeiro 2026)")
    print("=" * 100)

    # Aplicar melhor config encontrada em 2025
    sim_module.JANELA_MULTS = melhor_config.get('janela_mults', 300)
    sim_module.JANELA_GATILHOS = melhor_config.get('janela_gatilhos', 30)
    sim_module.ALERTA_TAXA_ALTOS = melhor_config.get('taxa_altos', 0.42)
    sim_module.ALERTA_TAXA_T5_PLUS = melhor_config.get('taxa_t5', 0.10)
    sim_module.ALERTA_TAXA_T6_PLUS = melhor_config.get('taxa_t6', 0.06)
    sim_module.ALERTAS_PARA_TROCAR = melhor_config.get('alertas_trocar', 2)

    print(f"\nUsando config: {melhor_config['nome']}")
    print(f"  Taxa altos: < {sim_module.ALERTA_TAXA_ALTOS*100:.0f}%")
    print(f"  Taxa T5+: > {sim_module.ALERTA_TAXA_T5_PLUS*100:.0f}%")
    print(f"  Taxa T6+: > {sim_module.ALERTA_TAXA_T6_PLUS*100:.0f}%")
    print(f"  Alertas para trocar: {sim_module.ALERTAS_PARA_TROCAR}")

    # NS7 pura em Jan 2026
    print("\nSimulando NS7 pura em Janeiro 2026...")
    rel_ns7_teste = simular_periodo(dados['teste'], usar_alertas=False)

    # Com alertas em Jan 2026
    print("Simulando com alertas em Janeiro 2026...")
    rel_alerta_teste = simular_periodo(dados['teste'], usar_alertas=True)

    # Resultados
    print("\n" + "-" * 100)
    print("RESULTADO JANEIRO 2026 (OUT-OF-SAMPLE)")
    print("-" * 100)

    print(f"\n{'METRICA':<30} {'NS7 PURA':>20} {'NS7+ALERTAS':>20}")
    print("-" * 75)
    print(f"{'Lucro':<30} R${rel_ns7_teste['lucro']:>17,.2f} R${rel_alerta_teste['lucro']:>17,.2f}")
    print(f"{'Ganho %':<30} {rel_ns7_teste['ganho_pct']:>19.2f}% {rel_alerta_teste['ganho_pct']:>19.2f}%")
    print(f"{'Drawdown Max':<30} {rel_ns7_teste['drawdown_max_pct']:>19.2f}% {rel_alerta_teste['drawdown_max_pct']:>19.2f}%")
    print(f"{'Busts':<30} {rel_ns7_teste['busts']:>20} {rel_alerta_teste['busts']:>20}")
    print(f"{'Gatilhos':<30} {rel_ns7_teste['gatilhos']:>20,} {rel_alerta_teste['gatilhos']:>20,}")
    print(f"{'Gatilhos em NS8':<30} {0:>20} {rel_alerta_teste['gatilhos_ns8']:>20,}")

    if rel_alerta_teste['gatilhos'] > 0:
        pct_ns8 = rel_alerta_teste['gatilhos_ns8'] / rel_alerta_teste['gatilhos'] * 100
        print(f"{'% em NS8':<30} {'-':>20} {pct_ns8:>19.1f}%")

    # Diferencas
    diff_lucro = rel_alerta_teste['lucro'] - rel_ns7_teste['lucro']
    diff_dd = rel_alerta_teste['drawdown_max_pct'] - rel_ns7_teste['drawdown_max_pct']

    print("\n" + "-" * 75)
    print("DIFERENCAS:")
    print(f"  Lucro: {'+'if diff_lucro>=0 else ''}R$ {diff_lucro:,.2f}")
    print(f"  Drawdown: {'+'if diff_dd>=0 else ''}{diff_dd:.2f} pp")

    # =====================================================================
    # VEREDITO FINAL
    # =====================================================================
    print("\n" + "=" * 100)
    print("VEREDITO FINAL")
    print("=" * 100)

    print("\nPERFORMANCE EM 2025 (TREINO):")
    treino_diff = melhor_config['resultado_treino']['lucro'] - rel_ns7_treino['lucro']
    treino_dd_diff = melhor_config['resultado_treino']['drawdown_max_pct'] - rel_ns7_treino['drawdown_max_pct']
    print(f"  Lucro: {'+'if treino_diff>=0 else ''}R$ {treino_diff:,.0f}")
    print(f"  Drawdown: {'+'if treino_dd_diff>=0 else ''}{treino_dd_diff:.2f} pp")

    print("\nPERFORMANCE EM JAN 2026 (TESTE):")
    print(f"  Lucro: {'+'if diff_lucro>=0 else ''}R$ {diff_lucro:,.2f}")
    print(f"  Drawdown: {'+'if diff_dd>=0 else ''}{diff_dd:.2f} pp")

    print("\n" + "-" * 100)

    # Verificar se validou out-of-sample
    if diff_lucro >= 0 and diff_dd <= 0:
        print(">> ALERTAS VALIDADOS: Funcionaram bem em dados nao vistos!")
    elif diff_lucro >= 0:
        print(f">> ALERTAS LUCRATIVOS em Jan/26, mas DD aumentou {diff_dd:.2f}pp")
    elif diff_dd < -5:
        print(f">> ALERTAS REDUZIRAM RISCO: -{-diff_dd:.2f}pp de DD, custou R$ {-diff_lucro:,.0f}")
    else:
        print(">> ALERTAS NAO FUNCIONARAM: Perdeu lucro sem reduzir DD significativamente")

    # Comparar com NS8 pura em Jan 2026
    print("\n" + "-" * 100)
    print("BONUS: COMPARANDO COM NS8 PURA EM JAN 2026")
    print("-" * 100)

    # Simular NS8 pura
    sim_module.ALERTAS_PARA_TROCAR = 0  # Forcar sempre NS8

    class SimuladorNS8Pura(SimuladorRealtime):
        def _decidir_nivel_para_proximo_gatilho(self):
            return 8, 0, []

    sim_ns8 = SimuladorNS8Pura(banca_inicial=1000.0, usar_alertas=True, usar_compound=False)
    rel_ns8_teste = sim_ns8.simular(dados['teste'])

    print(f"\n{'METRICA':<25} {'NS7 PURA':>15} {'NS7+ALERTAS':>15} {'NS8 PURA':>15}")
    print("-" * 75)
    print(f"{'Lucro':<25} R${rel_ns7_teste['lucro']:>12,.2f} R${rel_alerta_teste['lucro']:>12,.2f} R${rel_ns8_teste['lucro']:>12,.2f}")
    print(f"{'DD Max':<25} {rel_ns7_teste['drawdown_max_pct']:>14.2f}% {rel_alerta_teste['drawdown_max_pct']:>14.2f}% {rel_ns8_teste['drawdown_max_pct']:>14.2f}%")
    print(f"{'Busts':<25} {rel_ns7_teste['busts']:>15} {rel_alerta_teste['busts']:>15} {rel_ns8_teste['busts']:>15}")


if __name__ == "__main__":
    main()
