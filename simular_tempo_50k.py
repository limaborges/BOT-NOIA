#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador: Tempo para atingir R$ 50k de lucro diário

Pergunta: Com C2 = R$ 10.000, quanto tempo para ter banca
suficiente para lucrar R$ 50k/dia?
"""

import csv
from datetime import datetime, timedelta
from typing import List, Dict

ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
ALVO_LUCRO = 1.99


def carregar_dados_com_data(arquivo: str) -> List[Dict]:
    """Carrega multiplicadores com data/hora"""
    print(f"Carregando {arquivo}...")
    dados = []

    with open(arquivo, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                mult = float(row.get('Número', row.get('numero', list(row.values())[0])))
                dt_str = row.get('DateTime', '')
                dados.append({'mult': mult, 'datetime': dt_str})
            except:
                continue

    print(f"Carregados {len(dados):,} registros")
    return dados


def analisar_frequencia_diaria(dados: List[Dict]) -> Dict:
    """Analisa frequência de rodadas e gatilhos por dia"""

    # Agrupar por dia
    dias = {}
    for d in dados:
        try:
            dt = d['datetime'][:10]  # YYYY-MM-DD
            if dt not in dias:
                dias[dt] = []
            dias[dt].append(d['mult'])
        except:
            continue

    # Calcular estatísticas por dia
    stats_dias = []
    for dia, mults in dias.items():
        if len(mults) < 100:  # Ignorar dias incompletos
            continue

        # Contar gatilhos G5
        baixas = 0
        gatilhos_g5 = 0
        for mult in mults:
            if mult < ALVO_LUCRO:
                baixas += 1
                if baixas == 5:
                    gatilhos_g5 += 1
            else:
                baixas = 0

        stats_dias.append({
            'dia': dia,
            'rodadas': len(mults),
            'gatilhos_g5': gatilhos_g5
        })

    # Médias
    total_dias = len(stats_dias)
    media_rodadas = sum(s['rodadas'] for s in stats_dias) / total_dias
    media_gatilhos = sum(s['gatilhos_g5'] for s in stats_dias) / total_dias

    return {
        'total_dias': total_dias,
        'media_rodadas_dia': media_rodadas,
        'media_gatilhos_g5_dia': media_gatilhos,
        'min_gatilhos': min(s['gatilhos_g5'] for s in stats_dias),
        'max_gatilhos': max(s['gatilhos_g5'] for s in stats_dias),
        'stats_dias': stats_dias
    }


def simular_crescimento_banca(
    multiplicadores: List[float],
    banca_c1: float = 7.0,
    banca_c2_inicial: float = 10000.0,
    divisor_c1: int = 7,
    divisor_c2: int = 255,
    gatilho: int = 5,
    rodadas_por_dia: int = 3400,
    meta_lucro_diario: float = 50000.0
):
    """
    Simula crescimento da banca e calcula quando atinge meta de lucro diário
    """

    # Calcular tentativas
    def calc_tentativas(div):
        n, soma = 0, 0
        while soma + (2 ** n) <= div:
            soma += 2 ** n
            n += 1
        return n

    tent_c1 = calc_tentativas(divisor_c1)
    tent_c2 = calc_tentativas(divisor_c2)

    print(f"\n{'='*70}")
    print(f"SIMULAÇÃO DE CRESCIMENTO DE BANCA")
    print(f"{'='*70}")
    print(f"\nConfiguração:")
    print(f"  C1: R$ {banca_c1:.2f}, Divisor {divisor_c1} ({tent_c1} tentativas)")
    print(f"  C2: R$ {banca_c2_inicial:.2f}, Divisor {divisor_c2} ({tent_c2} tentativas)")
    print(f"  Gatilho: G{gatilho}")
    print(f"  Proteção total: {gatilho + tent_c1 + tent_c2} baixas para bust")
    print(f"  Meta: R$ {meta_lucro_diario:,.2f} lucro/dia")

    # Estado
    banca_c2 = banca_c2_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    # Contadores
    wins_c1 = 0
    wins_c2 = 0
    losses_c1 = 0
    busts = 0
    lucro_total = 0.0

    # Tracking diário
    lucro_dia_atual = 0.0
    rodada_dia = 0
    dias_simulados = 0
    dia_meta_atingida = None
    banca_quando_atingiu = None

    # Histórico para análise
    historico = []

    for i, mult in enumerate(multiplicadores):
        is_baixa = mult < ALVO_LUCRO

        if is_baixa:
            baixas += 1
        else:
            baixas = 0

        # Não está em ciclo
        if not em_ciclo_1 and not em_ciclo_2:
            if baixas >= gatilho:
                em_ciclo_1 = True
                tentativa = 1
                apostas_perdidas = 0.0

        # Ciclo 1
        elif em_ciclo_1:
            aposta = banca_c1 * (2 ** (tentativa - 1)) / divisor_c1

            if mult >= ALVO_LUCRO:
                lucro = aposta * (ALVO_LUCRO - 1) - apostas_perdidas
                wins_c1 += 1
                lucro_total += lucro
                lucro_dia_atual += lucro
                banca_c2 += lucro  # Compound

                em_ciclo_1 = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1

                if tentativa > tent_c1:
                    losses_c1 += 1
                    em_ciclo_1 = False
                    em_ciclo_2 = True
                    tentativa = 1
                    apostas_perdidas = 0.0

        # Ciclo 2
        elif em_ciclo_2:
            aposta = banca_c2 * (2 ** (tentativa - 1)) / divisor_c2

            if mult >= ALVO_LUCRO:
                lucro = aposta * (ALVO_LUCRO - 1) - apostas_perdidas - banca_c1
                wins_c2 += 1
                lucro_total += lucro
                lucro_dia_atual += lucro
                banca_c2 += lucro  # Compound

                em_ciclo_2 = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1

                if tentativa > tent_c2:
                    busts += 1
                    lucro_total -= banca_c2
                    lucro_dia_atual -= banca_c2
                    banca_c2 = banca_c2_inicial  # Reset

                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        # Fim do dia
        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias_simulados += 1

            # Calcular lucro potencial diário com banca atual
            # Lucro por win C1 ≈ 0.99/7 * banca_c1 = ~14% de banca_c1
            # Lucro por win C2 ≈ 0.99/255 * banca_c2 = ~0.39% de banca_c2
            # Com ~20 gatilhos/dia G5, ~90% resolvem em C1

            gatilhos_estimados = 20  # G5 por dia
            taxa_c1_win = 0.88  # ~88% resolve em C1
            lucro_por_win_c1 = banca_c1 * 0.99 / divisor_c1
            lucro_por_win_c2 = banca_c2 * 0.99 / divisor_c2

            lucro_potencial_diario = (
                gatilhos_estimados * taxa_c1_win * lucro_por_win_c1 +
                gatilhos_estimados * (1 - taxa_c1_win) * lucro_por_win_c2
            )

            historico.append({
                'dia': dias_simulados,
                'banca_c2': banca_c2,
                'lucro_dia': lucro_dia_atual,
                'lucro_potencial': lucro_potencial_diario,
                'wins_c1': wins_c1,
                'wins_c2': wins_c2,
                'busts': busts
            })

            # Verificar se atingiu meta
            if lucro_potencial_diario >= meta_lucro_diario and dia_meta_atingida is None:
                dia_meta_atingida = dias_simulados
                banca_quando_atingiu = banca_c2

            # Reset contadores diários
            lucro_dia_atual = 0.0
            rodada_dia = 0

    # Resultados
    print(f"\n{'='*70}")
    print(f"RESULTADOS ({dias_simulados} dias simulados)")
    print(f"{'='*70}")

    print(f"\nEstatísticas gerais:")
    print(f"  Wins C1: {wins_c1:,}")
    print(f"  Wins C2: {wins_c2:,}")
    print(f"  Busts: {busts}")
    print(f"  Lucro total: R$ {lucro_total:,.2f}")
    print(f"  Banca final: R$ {banca_c2:,.2f}")

    if dia_meta_atingida:
        print(f"\n{'='*70}")
        print(f"META ATINGIDA!")
        print(f"{'='*70}")
        print(f"  Dia: {dia_meta_atingida}")
        print(f"  Banca necessária: R$ {banca_quando_atingiu:,.2f}")
        print(f"  Para lucrar R$ {meta_lucro_diario:,.2f}/dia")

    # Mostrar evolução
    print(f"\n{'='*70}")
    print(f"EVOLUÇÃO DA BANCA")
    print(f"{'='*70}")
    print(f"\n{'Dia':>6} {'Banca C2':>18} {'Lucro Dia':>15} {'Lucro Potencial':>18}")
    print("-" * 60)

    # Mostrar primeiros 30 dias e últimos 10
    for h in historico[:30]:
        print(f"{h['dia']:>6} R$ {h['banca_c2']:>15,.2f} R$ {h['lucro_dia']:>12,.2f} R$ {h['lucro_potencial']:>15,.2f}")

    if len(historico) > 40:
        print(f"{'...':>6}")
        for h in historico[-10:]:
            print(f"{h['dia']:>6} R$ {h['banca_c2']:>15,.2f} R$ {h['lucro_dia']:>12,.2f} R$ {h['lucro_potencial']:>15,.2f}")

    # Calcular banca necessária para 50k/dia
    # Lucro diário ≈ gatilhos * taxa_win * lucro_por_win
    # Com G5: ~20 gatilhos/dia, ~88% C1, ~12% C2
    # Lucro ≈ 20 * 0.88 * (7*0.99/7) + 20 * 0.12 * (banca*0.99/255)
    # 50000 ≈ 17.42 + 0.00933 * banca
    # banca ≈ 50000 / 0.00933 ≈ R$ 5.36 milhões

    print(f"\n{'='*70}")
    print(f"CÁLCULO TEÓRICO")
    print(f"{'='*70}")

    # Fórmula mais precisa
    gatilhos_dia = 20
    taxa_c1 = 0.88
    lucro_pct_c2 = 0.99 / divisor_c2  # ~0.388%

    # Para lucrar X por dia apenas com C2 (conservador):
    # X = gatilhos * (1-taxa_c1) * banca * lucro_pct
    # banca = X / (gatilhos * (1-taxa_c1) * lucro_pct)

    banca_necessaria = meta_lucro_diario / (gatilhos_dia * (1 - taxa_c1) * lucro_pct_c2)

    print(f"\nPara lucrar R$ {meta_lucro_diario:,.2f}/dia:")
    print(f"  Gatilhos G5 estimados/dia: ~{gatilhos_dia}")
    print(f"  Taxa de resolução C1: ~{taxa_c1*100:.0f}%")
    print(f"  Lucro por win C2: ~{lucro_pct_c2*100:.3f}% da banca")
    print(f"  Banca C2 necessária: R$ {banca_necessaria:,.2f}")

    # Tempo para atingir essa banca com compound
    # Crescimento diário ≈ 0.5% a 1% com compound
    crescimento_diario = 0.007  # ~0.7% ao dia (conservador)
    dias_necessarios = 0
    banca_temp = banca_c2_inicial
    while banca_temp < banca_necessaria and dias_necessarios < 1000:
        banca_temp *= (1 + crescimento_diario)
        dias_necessarios += 1

    print(f"\n  Com banca inicial de R$ {banca_c2_inicial:,.2f}:")
    print(f"  Crescimento estimado: ~{crescimento_diario*100:.1f}%/dia")
    print(f"  Dias para atingir meta: ~{dias_necessarios} dias")
    print(f"  (~{dias_necessarios // 30} meses)")

    return historico


def main():
    dados = carregar_dados_com_data(ARQUIVO_DADOS)

    # Analisar frequência
    print("\nAnalisando frequência diária...")
    freq = analisar_frequencia_diaria(dados)

    print(f"\n{'='*70}")
    print(f"ESTATÍSTICAS DIÁRIAS")
    print(f"{'='*70}")
    print(f"  Total de dias: {freq['total_dias']}")
    print(f"  Média de rodadas/dia: {freq['media_rodadas_dia']:.0f}")
    print(f"  Média de gatilhos G5/dia: {freq['media_gatilhos_g5_dia']:.1f}")
    print(f"  Min gatilhos G5/dia: {freq['min_gatilhos']}")
    print(f"  Max gatilhos G5/dia: {freq['max_gatilhos']}")

    # Simular crescimento
    multiplicadores = [d['mult'] for d in dados]

    simular_crescimento_banca(
        multiplicadores,
        banca_c1=7.0,
        banca_c2_inicial=10000.0,
        divisor_c1=7,
        divisor_c2=255,
        gatilho=5,
        rodadas_por_dia=int(freq['media_rodadas_dia']),
        meta_lucro_diario=50000.0
    )


if __name__ == "__main__":
    main()
