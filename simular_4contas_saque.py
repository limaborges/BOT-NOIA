#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador: 4 Contas com Saque Diário de R$ 3.000

Estratégia: G5 + D3/D255 (proteção até 15 baixas)
- 4 contas de R$ 500 cada (total R$ 2.000)
- Saque de R$ 3.000/dia quando banca permitir
- Busts sincronizados (mesmo jogo)
"""

import csv
from typing import List, Tuple

ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
ALVO_LUCRO = 1.99


def carregar_multiplicadores(arquivo: str) -> List[float]:
    """Carrega apenas os multiplicadores"""
    print(f"Carregando {arquivo}...")
    multiplicadores = []

    with open(arquivo, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                mult = float(row.get('Número', row.get('numero', list(row.values())[0])))
                multiplicadores.append(mult)
            except:
                continue

    print(f"Carregados {len(multiplicadores):,} multiplicadores")
    return multiplicadores


def simular_conta(
    multiplicadores: List[float],
    banca_c1: float,
    banca_c2_inicial: float,
    divisor_c1: int,
    divisor_c2: int,
    gatilho: int,
    rodadas_por_dia: int,
    saque_diario: float
) -> Tuple[List[dict], float, int]:
    """
    Simula uma conta e retorna histórico diário, total sacado e busts
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

    # Estado
    banca_c2 = banca_c2_inicial
    em_ciclo_1 = False
    em_ciclo_2 = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    # Contadores
    total_sacado = 0.0
    busts = 0

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
                lucro_dia += lucro
                banca_c2 += lucro  # Compound

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

        # Ciclo 2
        elif em_ciclo_2:
            aposta = banca_c2 * (2 ** (tentativa - 1)) / divisor_c2

            if mult >= ALVO_LUCRO:
                lucro = aposta * (ALVO_LUCRO - 1) - apostas_perdidas - banca_c1
                lucro_dia += lucro
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
                    lucro_dia -= banca_c2
                    banca_c2 = banca_c2_inicial  # Reset

                    em_ciclo_2 = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        # Fim do dia
        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            # Saque diário (se tiver banca suficiente)
            saque_hoje = 0.0
            if banca_c2 > banca_c2_inicial + saque_diario:
                saque_hoje = saque_diario
                banca_c2 -= saque_diario
                total_sacado += saque_diario
            elif banca_c2 > banca_c2_inicial * 1.5:
                # Saque parcial
                saque_hoje = (banca_c2 - banca_c2_inicial) * 0.5
                banca_c2 -= saque_hoje
                total_sacado += saque_hoje

            historico.append({
                'banca': banca_c2,
                'lucro_dia': lucro_dia,
                'saque': saque_hoje,
                'total_sacado': total_sacado
            })

            lucro_dia = 0.0
            rodada_dia = 0

    return historico, total_sacado, busts


def simular_4_contas(
    multiplicadores: List[float],
    banca_por_conta: float = 500.0,
    saque_total_diario: float = 3000.0,
    rodadas_por_dia: int = 3456
):
    """
    Simula 4 contas com saque diário total
    """

    num_contas = 4
    saque_por_conta = saque_total_diario / num_contas

    print(f"\n{'='*70}")
    print(f"SIMULAÇÃO: 4 CONTAS COM SAQUE DIÁRIO")
    print(f"{'='*70}")
    print(f"\nConfiguração:")
    print(f"  Estratégia: G5 + D3/D255 (proteção 15 baixas)")
    print(f"  Contas: {num_contas}")
    print(f"  Banca por conta: R$ {banca_por_conta:,.2f}")
    print(f"  Banca total: R$ {banca_por_conta * num_contas:,.2f}")
    print(f"  Saque diário total: R$ {saque_total_diario:,.2f}")
    print(f"  Saque por conta: R$ {saque_por_conta:,.2f}")
    print(f"  Rodadas/dia: {rodadas_por_dia:,}")

    # Simular cada conta (todas veem os mesmos multiplicadores = busts sincronizados)
    resultados = []
    for i in range(num_contas):
        historico, sacado, busts = simular_conta(
            multiplicadores,
            banca_c1=3.0,
            banca_c2_inicial=banca_por_conta,
            divisor_c1=3,
            divisor_c2=255,
            gatilho=5,
            rodadas_por_dia=rodadas_por_dia,
            saque_diario=saque_por_conta
        )
        resultados.append({
            'historico': historico,
            'total_sacado': sacado,
            'busts': busts
        })

    # Consolidar resultados
    dias = len(resultados[0]['historico'])
    total_sacado_todas = sum(r['total_sacado'] for r in resultados)
    busts_por_conta = resultados[0]['busts']  # Sincronizados

    print(f"\n{'='*70}")
    print(f"RESULTADOS ({dias} dias simulados)")
    print(f"{'='*70}")

    print(f"\n  Busts (sincronizados): {busts_por_conta}")
    print(f"  Total sacado (4 contas): R$ {total_sacado_todas:,.2f}")
    print(f"  Média sacada/dia: R$ {total_sacado_todas/dias:,.2f}")

    # Banca final
    banca_final_total = sum(r['historico'][-1]['banca'] for r in resultados)
    print(f"  Banca final total: R$ {banca_final_total:,.2f}")

    # Mostrar evolução mensal consolidada
    print(f"\n{'='*70}")
    print(f"EVOLUÇÃO MENSAL (4 CONTAS CONSOLIDADAS)")
    print(f"{'='*70}")
    print(f"\n{'Mês':>4} {'Banca Total':>18} {'Sacado Mês':>15} {'Sacado Acum':>18} {'Status':>10}")
    print("-" * 70)

    mes = 0
    sacado_acum = 0.0
    for dia in range(0, dias, 30):
        mes += 1
        if dia >= dias:
            break

        # Somar banca das 4 contas nesse dia
        banca_total = sum(r['historico'][min(dia, len(r['historico'])-1)]['banca'] for r in resultados)

        # Sacado no mês
        inicio_mes = max(0, dia - 30)
        sacado_mes = sum(
            sum(r['historico'][d]['saque'] for d in range(inicio_mes, min(dia, len(r['historico']))))
            for r in resultados
        )
        sacado_acum += sacado_mes

        # Verificar se houve bust neste período
        # Detectar bust por queda brusca na banca
        status = "OK"
        if dia > 0:
            banca_anterior = sum(r['historico'][max(0, dia-30)]['banca'] for r in resultados)
            if banca_total < banca_anterior * 0.3:
                status = "BUST!"

        print(f"{mes:>4} R$ {banca_total:>15,.2f} R$ {sacado_mes:>12,.2f} R$ {sacado_acum:>15,.2f} {status:>10}")

    # Resumo final
    print(f"\n{'='*70}")
    print(f"RESUMO FINAL")
    print(f"{'='*70}")

    investimento = banca_por_conta * num_contas
    retorno_total = total_sacado_todas + banca_final_total - investimento
    roi = (retorno_total / investimento) * 100 if investimento > 0 else 0
    roi_mensal = roi / (dias / 30) if dias > 0 else 0

    print(f"\n  Investimento inicial: R$ {investimento:,.2f}")
    print(f"  Total sacado: R$ {total_sacado_todas:,.2f}")
    print(f"  Banca final: R$ {banca_final_total:,.2f}")
    print(f"  Retorno líquido: R$ {retorno_total:,.2f}")
    print(f"  ROI total: {roi:,.1f}%")
    print(f"  ROI médio/mês: {roi_mensal:,.1f}%")
    print(f"  Período: {dias} dias (~{dias/30:.1f} meses)")

    # Análise de risco
    print(f"\n{'='*70}")
    print(f"ANÁLISE DE RISCO")
    print(f"{'='*70}")
    print(f"\n  Busts no período: {busts_por_conta}")
    print(f"  ⚠️  Busts são SINCRONIZADOS em todas as 4 contas!")
    print(f"  ⚠️  Quando uma conta busta, TODAS bustam!")
    print(f"\n  Estratégia de proteção:")
    print(f"    - Sacar consistentemente para recuperar investimento")
    print(f"    - Após bust, reiniciar com nova banca")
    print(f"    - Manter reserva para reinício")

    # Calcular dias até recuperar investimento
    dias_para_roi = 0
    sacado_acum_temp = 0.0
    for dia in range(dias):
        for r in resultados:
            if dia < len(r['historico']):
                sacado_acum_temp += r['historico'][dia]['saque']
        if sacado_acum_temp >= investimento:
            dias_para_roi = dia + 1
            break

    if dias_para_roi > 0:
        print(f"\n  ✅ Investimento recuperado em {dias_para_roi} dias")
        print(f"     Após isso, tudo é lucro!")

    return resultados


def main():
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)

    # Calcular rodadas por dia
    # ~3456 rodadas/dia baseado em análise anterior
    rodadas_dia = 3456

    # Testar diferentes bancas iniciais
    print("\n" + "="*70)
    print("COMPARATIVO: DIFERENTES BANCAS INICIAIS")
    print("="*70)

    for banca in [500, 1000, 2000, 5000]:
        print(f"\n>>> BANCA POR CONTA: R$ {banca:,}")
        simular_4_contas(
            multiplicadores,
            banca_por_conta=float(banca),
            saque_total_diario=3000.0,
            rodadas_por_dia=rodadas_dia
        )


if __name__ == "__main__":
    main()
