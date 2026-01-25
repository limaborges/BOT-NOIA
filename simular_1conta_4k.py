#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador: 1 Conta com R$ 4.000 inicial
Estratégia: G5 + D3/D255 (proteção 15 baixas)
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


def simular_1_conta(multiplicadores: List[float], banca_inicial: float = 4000.0):
    """Simula 1 conta com compound e análise detalhada"""

    banca_c1 = 3.0
    divisor_c1 = 3
    divisor_c2 = 255
    gatilho = 5
    tent_c1 = 2
    tent_c2 = 8
    rodadas_por_dia = 3456

    print(f"\n{'='*60}")
    print(f"SIMULAÇÃO: 1 CONTA COM R$ {banca_inicial:,.2f}")
    print(f"{'='*60}")
    print(f"\nEstratégia: G5 + D3/D255")
    print(f"  C1: R$ {banca_c1:.2f}, {tent_c1} tentativas (sinalizador)")
    print(f"  C2: R$ {banca_inicial:,.2f}, {tent_c2} tentativas (lucro)")
    print(f"  Proteção: {gatilho} + {tent_c1} + {tent_c2} = {gatilho + tent_c1 + tent_c2} baixas")

    # Estado
    banca_c2 = banca_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    # Contadores
    wins_c1 = 0
    wins_c2 = 0
    busts = 0
    lucro_total = 0.0

    # Tracking diário
    lucro_dia = 0.0
    rodada_dia = 0
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
                wins_c1 += 1
                lucro_total += lucro
                lucro_dia += lucro
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
                lucro_total += lucro
                lucro_dia += lucro
                banca_c2 += lucro

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
                    lucro_dia -= banca_c2
                    banca_c2 = banca_inicial  # Reset

                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        # Fim do dia
        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            historico.append({
                'banca': banca_c2,
                'lucro_dia': lucro_dia,
                'wins_c1': wins_c1,
                'wins_c2': wins_c2,
                'busts': busts
            })
            lucro_dia = 0.0
            rodada_dia = 0

    dias = len(historico)

    # Resultados
    print(f"\n{'='*60}")
    print(f"RESULTADOS ({dias} dias)")
    print(f"{'='*60}")
    print(f"\n  Wins C1: {wins_c1:,} (lucro pequeno, frequente)")
    print(f"  Wins C2: {wins_c2:,} (lucro maior, menos frequente)")
    print(f"  Busts: {busts}")
    print(f"  Banca final: R$ {banca_c2:,.2f}")

    # Evolução por semana (primeiros 2 meses)
    print(f"\n{'='*60}")
    print(f"EVOLUÇÃO SEMANAL (primeiros 60 dias)")
    print(f"{'='*60}")
    print(f"\n{'Semana':>7} {'Dia':>5} {'Banca':>18} {'Lucro Semana':>15}")
    print("-" * 50)

    for semana in range(1, 10):
        dia = semana * 7
        if dia > len(historico):
            break
        banca = historico[dia-1]['banca']

        # Lucro da semana
        dia_inicio = (semana-1) * 7
        lucro_semana = sum(historico[d]['lucro_dia'] for d in range(dia_inicio, dia))

        print(f"{semana:>7} {dia:>5} R$ {banca:>15,.2f} R$ {lucro_semana:>12,.2f}")

    # Evolução mensal
    print(f"\n{'='*60}")
    print(f"EVOLUÇÃO MENSAL (ano completo)")
    print(f"{'='*60}")
    print(f"\n{'Mês':>4} {'Banca':>18} {'Lucro Mês':>15} {'Status':>12}")
    print("-" * 55)

    for mes in range(1, 14):
        dia = mes * 30
        if dia > len(historico):
            break
        banca = historico[dia-1]['banca']

        dia_inicio = (mes-1) * 30
        lucro_mes = sum(historico[d]['lucro_dia'] for d in range(dia_inicio, min(dia, len(historico))))

        # Detectar bust
        status = "✅ OK"
        if mes > 1:
            banca_ant = historico[(mes-1)*30 - 1]['banca']
            if banca < banca_ant * 0.5:
                status = "💥 BUST"

        print(f"{mes:>4} R$ {banca:>15,.2f} R$ {lucro_mes:>12,.2f} {status:>12}")

    # Métricas finais
    print(f"\n{'='*60}")
    print(f"MÉTRICAS PARA DECISÃO")
    print(f"{'='*60}")

    # Lucro médio por dia (excluindo dias de bust)
    lucros_positivos = [h['lucro_dia'] for h in historico if h['lucro_dia'] > -banca_inicial/2]
    lucro_medio_dia = sum(lucros_positivos) / len(lucros_positivos) if lucros_positivos else 0

    print(f"\n  Lucro médio/dia (sem busts): R$ {lucro_medio_dia:,.2f}")
    print(f"  Lucro médio/mês (sem busts): R$ {lucro_medio_dia * 30:,.2f}")

    # Quando pode começar a sacar
    dia_pode_sacar = 0
    for i, h in enumerate(historico):
        if h['banca'] >= banca_inicial * 2:  # Dobrou a banca
            dia_pode_sacar = i + 1
            break

    if dia_pode_sacar:
        print(f"\n  📈 Banca dobra no dia: {dia_pode_sacar}")
        print(f"     A partir daí, pode sacar ~50% do lucro diário")

    # Sugestão de saque
    saque_sugerido = lucro_medio_dia * 0.5  # 50% do lucro
    print(f"\n  💰 Saque sugerido/dia: R$ {saque_sugerido:,.2f}")
    print(f"     (50% do lucro, mantendo compound)")
    print(f"     Saque/mês: R$ {saque_sugerido * 30:,.2f}")

    # Risco
    print(f"\n  ⚠️  Risco: {busts} busts em {dias} dias")
    if busts > 0:
        dias_entre_busts = dias / busts
        print(f"     Média: 1 bust a cada {dias_entre_busts:.0f} dias")
        print(f"     Recomendação: manter R$ {banca_inicial:,.2f} de reserva")

    return historico


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores")

    simular_1_conta(multiplicadores, banca_inicial=4000.0)


if __name__ == "__main__":
    main()
