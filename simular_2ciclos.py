#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMULADOR 2 CICLOS - Estratégia Cascata com Compound

Conceito:
- Ciclo 1 (Scout): Banca pequena, divisor 7 (3 tentativas)
- Ciclo 2 (Principal): Banca grande, divisor 127 (7 tentativas)
- Compound: Lucros são reinvestidos na banca

Estatística importante:
- Frequência de gatilhos dobra a cada nível abaixo
- G4 = 2x G5 = 4x G6 = 8x G7
"""

import csv
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# Configuração
ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'

# Alvos
ALVO_LUCRO = 1.99
ALVO_DEFESA = 1.25


def carregar_multiplicadores(arquivo: str) -> List[float]:
    """Carrega multiplicadores do CSV"""
    print(f"Carregando {arquivo}...")
    multiplicadores = []

    with open(arquivo, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Tentar diferentes nomes de coluna
                if 'Número' in row:
                    mult = float(row['Número'])
                elif 'numero' in row:
                    mult = float(row['numero'])
                elif 'multiplicador' in row:
                    mult = float(row['multiplicador'])
                else:
                    # Pegar primeira coluna numérica
                    mult = float(list(row.values())[0])
                multiplicadores.append(mult)
            except (ValueError, TypeError):
                continue

    print(f"Carregados {len(multiplicadores):,} multiplicadores")
    return multiplicadores


@dataclass
class EstadoSimulacao:
    """Estado atual da simulação"""
    # Bancas
    banca_c1: float = 7.0
    banca_c2: float = 15000.0
    banca_inicial_c2: float = 15000.0

    # Estado do ciclo
    em_ciclo_1: bool = False
    em_ciclo_2: bool = False
    tentativa_atual: int = 0
    apostas_perdidas_ciclo: float = 0.0

    # Contadores de baixas
    baixas_consecutivas: int = 0

    # Estatísticas
    gatilhos_c1: int = 0
    wins_c1: int = 0
    losses_c1: int = 0

    gatilhos_c2: int = 0
    wins_c2: int = 0
    losses_c2: int = 0  # Busts

    # Financeiro
    lucro_realizado: float = 0.0
    custo_scouts: float = 0.0

    # Tracking
    max_drawdown_pct: float = 0.0
    pico_banca: float = 0.0
    min_banca: float = float('inf')

    # Histórico para análise
    historico_banca: List[float] = field(default_factory=list)
    max_baixas_vistas: int = 0


def calcular_tentativas(divisor: int) -> int:
    """Calcula quantas tentativas cabem no divisor"""
    # Progressão: 1 + 2 + 4 + 8 + ... = 2^n - 1
    # Então n = log2(divisor + 1)
    n = 0
    soma = 0
    while soma + (2 ** n) <= divisor:
        soma += 2 ** n
        n += 1
    return n


def calcular_aposta(banca: float, divisor: int, tentativa: int) -> float:
    """Calcula valor da aposta para a tentativa (1-indexed)"""
    multiplicador = 2 ** (tentativa - 1)  # 1, 2, 4, 8, ...
    return banca * multiplicador / divisor


def simular_2ciclos_compound(
    multiplicadores: List[float],
    banca_c1_inicial: float = 7.0,
    banca_c2_inicial: float = 15000.0,
    divisor_c1: int = 7,
    divisor_c2: int = 127,
    gatilho: int = 6,
    compound_pct: float = 100.0,  # % do lucro reinvestido
    verbose: bool = False,
    max_rodadas: Optional[int] = None
) -> EstadoSimulacao:
    """
    Simula estratégia 2 ciclos com compound

    Args:
        multiplicadores: Lista de multiplicadores
        banca_c1_inicial: Banca inicial do Ciclo 1
        banca_c2_inicial: Banca inicial do Ciclo 2
        divisor_c1: Divisor do Ciclo 1 (7 = 3 tentativas)
        divisor_c2: Divisor do Ciclo 2 (127 = 7 tentativas)
        gatilho: Quantas baixas para ativar Ciclo 1
        compound_pct: % do lucro a reinvestir (100 = tudo)
        verbose: Imprimir detalhes
        max_rodadas: Limitar número de rodadas
    """

    tentativas_c1 = calcular_tentativas(divisor_c1)
    tentativas_c2 = calcular_tentativas(divisor_c2)

    if verbose:
        print(f"\nConfiguração:")
        print(f"  Ciclo 1: Divisor {divisor_c1} = {tentativas_c1} tentativas, Banca R$ {banca_c1_inicial:.2f}")
        print(f"  Ciclo 2: Divisor {divisor_c2} = {tentativas_c2} tentativas, Banca R$ {banca_c2_inicial:.2f}")
        print(f"  Gatilho: G{gatilho} ({gatilho} baixas consecutivas)")
        print(f"  Compound: {compound_pct:.0f}%")
        print(f"  Proteção total: {gatilho + tentativas_c1 + tentativas_c2} baixas para bust")

    estado = EstadoSimulacao(
        banca_c1=banca_c1_inicial,
        banca_c2=banca_c2_inicial,
        banca_inicial_c2=banca_c2_inicial,
        pico_banca=banca_c2_inicial
    )

    n_rodadas = len(multiplicadores) if max_rodadas is None else min(max_rodadas, len(multiplicadores))

    for i in range(n_rodadas):
        mult = multiplicadores[i]
        is_baixa = mult < ALVO_LUCRO

        # Atualizar contagem de baixas
        if is_baixa:
            estado.baixas_consecutivas += 1
            if estado.baixas_consecutivas > estado.max_baixas_vistas:
                estado.max_baixas_vistas = estado.baixas_consecutivas
        else:
            estado.baixas_consecutivas = 0

        # ========== NÃO ESTÁ EM NENHUM CICLO ==========
        if not estado.em_ciclo_1 and not estado.em_ciclo_2:
            if estado.baixas_consecutivas >= gatilho:
                # Ativar Ciclo 1
                estado.em_ciclo_1 = True
                estado.tentativa_atual = 1
                estado.apostas_perdidas_ciclo = 0.0
                estado.gatilhos_c1 += 1

                if verbose and estado.gatilhos_c1 <= 10:
                    print(f"[{i:,}] GATILHO C1 #{estado.gatilhos_c1} - {estado.baixas_consecutivas} baixas")

        # ========== CICLO 1 ATIVO ==========
        elif estado.em_ciclo_1:
            aposta = calcular_aposta(estado.banca_c1, divisor_c1, estado.tentativa_atual)

            if mult >= ALVO_LUCRO:
                # WIN no Ciclo 1
                lucro_bruto = aposta * (ALVO_LUCRO - 1)
                lucro_liquido = lucro_bruto - estado.apostas_perdidas_ciclo

                estado.wins_c1 += 1
                estado.lucro_realizado += lucro_liquido

                # Compound: adicionar lucro à banca C2
                compound_valor = lucro_liquido * (compound_pct / 100)
                estado.banca_c2 += compound_valor

                if verbose and estado.wins_c1 <= 5:
                    print(f"[{i:,}] C1 WIN T{estado.tentativa_atual} mult={mult:.2f} lucro={lucro_liquido:.2f}")

                # Reset
                estado.em_ciclo_1 = False
                estado.tentativa_atual = 0
                estado.apostas_perdidas_ciclo = 0.0
                estado.baixas_consecutivas = 0

            else:
                # LOSS nesta tentativa
                estado.apostas_perdidas_ciclo += aposta
                estado.tentativa_atual += 1

                if estado.tentativa_atual > tentativas_c1:
                    # Ciclo 1 PERDEU - ativar Ciclo 2
                    estado.losses_c1 += 1
                    estado.custo_scouts += estado.banca_c1

                    estado.em_ciclo_1 = False
                    estado.em_ciclo_2 = True
                    estado.tentativa_atual = 1
                    estado.apostas_perdidas_ciclo = 0.0
                    estado.gatilhos_c2 += 1

                    if verbose:
                        print(f"[{i:,}] C1 LOSS -> C2 ATIVADO (já {estado.baixas_consecutivas} baixas)")

        # ========== CICLO 2 ATIVO ==========
        elif estado.em_ciclo_2:
            aposta = calcular_aposta(estado.banca_c2, divisor_c2, estado.tentativa_atual)

            if mult >= ALVO_LUCRO:
                # WIN no Ciclo 2
                lucro_bruto = aposta * (ALVO_LUCRO - 1)
                lucro_liquido = lucro_bruto - estado.apostas_perdidas_ciclo

                # Descontar custo do scout que falhou E repor o C1
                custo_c1 = estado.banca_c1
                lucro_liquido -= custo_c1  # Desconta o C1 que perdeu
                # O C1 é reposto automaticamente (já está na banca_c1)

                estado.wins_c2 += 1
                estado.lucro_realizado += lucro_liquido

                # Compound: lucro vai para C2, mas C1 continua fixo
                compound_valor = lucro_liquido * (compound_pct / 100)
                estado.banca_c2 += compound_valor

                if verbose:
                    print(f"[{i:,}] C2 WIN T{estado.tentativa_atual} mult={mult:.2f} lucro={lucro_liquido:.2f} banca={estado.banca_c2:.2f} (C1 reposto)")

                # Reset
                estado.em_ciclo_2 = False
                estado.tentativa_atual = 0
                estado.apostas_perdidas_ciclo = 0.0
                estado.baixas_consecutivas = 0

            else:
                # LOSS nesta tentativa
                estado.apostas_perdidas_ciclo += aposta
                estado.tentativa_atual += 1

                if estado.tentativa_atual > tentativas_c2:
                    # BUST - Ciclo 2 perdeu
                    estado.losses_c2 += 1
                    estado.lucro_realizado -= estado.banca_c2

                    if verbose:
                        print(f"[{i:,}] *** BUST *** C2 perdeu! Baixas consecutivas: {estado.baixas_consecutivas}")

                    # Reset banca C2 (simula novo depósito)
                    estado.banca_c2 = estado.banca_inicial_c2

                    # Reset
                    estado.em_ciclo_2 = False
                    estado.tentativa_atual = 0
                    estado.apostas_perdidas_ciclo = 0.0
                    estado.baixas_consecutivas = 0

        # Tracking de banca
        if estado.banca_c2 > estado.pico_banca:
            estado.pico_banca = estado.banca_c2
        if estado.banca_c2 < estado.min_banca:
            estado.min_banca = estado.banca_c2

        drawdown = (estado.pico_banca - estado.banca_c2) / estado.pico_banca * 100 if estado.pico_banca > 0 else 0
        if drawdown > estado.max_drawdown_pct:
            estado.max_drawdown_pct = drawdown

        # Salvar histórico a cada 10k rodadas
        if i % 10000 == 0:
            estado.historico_banca.append(estado.banca_c2)

    return estado


def simular_ns7_puro(
    multiplicadores: List[float],
    banca_inicial: float = 15000.0,
    divisor: int = 127,
    gatilho: int = 7,
    compound_pct: float = 100.0,
    verbose: bool = False
) -> EstadoSimulacao:
    """Simula NS7 puro para comparação"""

    tentativas = calcular_tentativas(divisor)

    estado = EstadoSimulacao(
        banca_c1=0,
        banca_c2=banca_inicial,
        banca_inicial_c2=banca_inicial,
        pico_banca=banca_inicial
    )

    em_martingale = False
    tentativa_atual = 0
    apostas_perdidas = 0.0
    baixas_consecutivas = 0

    for i, mult in enumerate(multiplicadores):
        is_baixa = mult < ALVO_LUCRO

        if is_baixa:
            baixas_consecutivas += 1
            if baixas_consecutivas > estado.max_baixas_vistas:
                estado.max_baixas_vistas = baixas_consecutivas
        else:
            baixas_consecutivas = 0

        if not em_martingale:
            if baixas_consecutivas >= gatilho:
                em_martingale = True
                tentativa_atual = 1
                apostas_perdidas = 0.0
                estado.gatilhos_c2 += 1

        elif em_martingale:
            aposta = calcular_aposta(estado.banca_c2, divisor, tentativa_atual)

            if mult >= ALVO_LUCRO:
                lucro_bruto = aposta * (ALVO_LUCRO - 1)
                lucro_liquido = lucro_bruto - apostas_perdidas

                estado.wins_c2 += 1
                estado.lucro_realizado += lucro_liquido

                compound_valor = lucro_liquido * (compound_pct / 100)
                estado.banca_c2 += compound_valor

                em_martingale = False
                tentativa_atual = 0
                apostas_perdidas = 0.0
                baixas_consecutivas = 0
            else:
                apostas_perdidas += aposta
                tentativa_atual += 1

                if tentativa_atual > tentativas:
                    estado.losses_c2 += 1
                    estado.lucro_realizado -= estado.banca_c2
                    estado.banca_c2 = estado.banca_inicial_c2

                    em_martingale = False
                    tentativa_atual = 0
                    apostas_perdidas = 0.0
                    baixas_consecutivas = 0

        if estado.banca_c2 > estado.pico_banca:
            estado.pico_banca = estado.banca_c2

        drawdown = (estado.pico_banca - estado.banca_c2) / estado.pico_banca * 100 if estado.pico_banca > 0 else 0
        if drawdown > estado.max_drawdown_pct:
            estado.max_drawdown_pct = drawdown

    estado.gatilhos_c1 = estado.gatilhos_c2  # Para compatibilidade
    return estado


def main():
    """Execução principal"""

    print("="*70)
    print("SIMULADOR 2 CICLOS COM COMPOUND")
    print("="*70)

    # Carregar dados
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)

    print(f"\nAnalisando frequência de baixas consecutivas...")

    # Contar frequência de sequências
    baixas = 0
    contagem = {}
    for mult in multiplicadores:
        if mult < ALVO_LUCRO:
            baixas += 1
        else:
            if baixas > 0:
                contagem[baixas] = contagem.get(baixas, 0) + 1
            baixas = 0

    print(f"\nFrequência de sequências de baixas (< {ALVO_LUCRO}x):")
    print(f"{'Baixas':>8} {'Ocorrências':>12} {'% do total':>12} {'Razão':>10}")
    print("-"*45)

    total = sum(contagem.values())
    prev_count = None
    for n in sorted(contagem.keys()):
        if n >= 3 and n <= 15:
            pct = contagem[n] / total * 100
            razao = f"{prev_count/contagem[n]:.2f}x" if prev_count else "-"
            print(f"{n:>8} {contagem[n]:>12,} {pct:>11.2f}% {razao:>10}")
            prev_count = contagem[n]

    # Comparar estratégias
    print("\n" + "="*70)
    print("COMPARAÇÃO: NS7 PURO vs 2 CICLOS")
    print("="*70)

    # NS7 Puro (baseline)
    print("\n[1/2] Simulando NS7 Puro (G7, D127)...")
    res_ns7 = simular_ns7_puro(
        multiplicadores,
        banca_inicial=15000.0,
        divisor=127,
        gatilho=7,
        compound_pct=100.0
    )

    # 2 Ciclos com G6
    print("[2/2] Simulando 2 Ciclos (G6, D7/D127)...")
    res_2c = simular_2ciclos_compound(
        multiplicadores,
        banca_c1_inicial=7.0,
        banca_c2_inicial=15000.0,
        divisor_c1=7,
        divisor_c2=127,
        gatilho=6,
        compound_pct=100.0,
        verbose=True
    )

    # Resultados
    print("\n" + "-"*70)
    print("RESULTADOS COMPARATIVOS")
    print("-"*70)

    print(f"\n{'Métrica':<35} {'NS7 Puro':>15} {'2 Ciclos':>15}")
    print("-"*70)

    print(f"{'Gatilhos ativados':<35} {res_ns7.gatilhos_c2:>15,} {res_2c.gatilhos_c1:>15,}")
    print(f"{'Entradas Ciclo 2':<35} {res_ns7.gatilhos_c2:>15,} {res_2c.gatilhos_c2:>15,}")

    print(f"\n{'Wins Ciclo 1 (scout)':<35} {'-':>15} {res_2c.wins_c1:>15,}")
    print(f"{'Wins Ciclo 2 (principal)':<35} {res_ns7.wins_c2:>15,} {res_2c.wins_c2:>15,}")
    print(f"{'BUSTS':<35} {res_ns7.losses_c2:>15,} {res_2c.losses_c2:>15,}")

    taxa_win_ns7 = res_ns7.wins_c2 / res_ns7.gatilhos_c2 * 100 if res_ns7.gatilhos_c2 > 0 else 0
    taxa_win_2c_c1 = res_2c.wins_c1 / res_2c.gatilhos_c1 * 100 if res_2c.gatilhos_c1 > 0 else 0
    taxa_win_2c_c2 = res_2c.wins_c2 / res_2c.gatilhos_c2 * 100 if res_2c.gatilhos_c2 > 0 else 0

    print(f"\n{'Taxa Win C1':<35} {'-':>15} {taxa_win_2c_c1:>14.1f}%")
    print(f"{'Taxa Win C2':<35} {taxa_win_ns7:>14.1f}% {taxa_win_2c_c2:>14.1f}%")

    taxa_bust_ns7 = res_ns7.losses_c2 / res_ns7.gatilhos_c2 * 100 if res_ns7.gatilhos_c2 > 0 else 0
    taxa_bust_2c = res_2c.losses_c2 / res_2c.gatilhos_c1 * 100 if res_2c.gatilhos_c1 > 0 else 0
    print(f"{'Taxa BUST':<35} {taxa_bust_ns7:>14.2f}% {taxa_bust_2c:>14.2f}%")

    print(f"\n{'Banca final':<35} R$ {res_ns7.banca_c2:>12,.2f} R$ {res_2c.banca_c2:>12,.2f}")
    print(f"{'Lucro realizado':<35} R$ {res_ns7.lucro_realizado:>12,.2f} R$ {res_2c.lucro_realizado:>12,.2f}")
    print(f"{'Custo dos scouts perdidos':<35} {'-':>15} R$ {res_2c.custo_scouts:>12,.2f}")

    print(f"\n{'Pico de banca':<35} R$ {res_ns7.pico_banca:>12,.2f} R$ {res_2c.pico_banca:>12,.2f}")
    print(f"{'Max drawdown':<35} {res_ns7.max_drawdown_pct:>14.1f}% {res_2c.max_drawdown_pct:>14.1f}%")
    print(f"{'Max baixas consecutivas vistas':<35} {res_ns7.max_baixas_vistas:>15} {res_2c.max_baixas_vistas:>15}")

    # Testar variantes
    print("\n" + "="*70)
    print("TESTANDO VARIANTES DE GATILHO")
    print("="*70)

    variantes = [
        (4, 7, 127, "G4 + D7/D127"),
        (5, 7, 127, "G5 + D7/D127"),
        (6, 7, 127, "G6 + D7/D127"),
        (5, 7, 255, "G5 + D7/D255"),
        (6, 7, 255, "G6 + D7/D255"),
        (4, 15, 127, "G4 + D15/D127"),
        (5, 15, 127, "G5 + D15/D127"),
    ]

    print(f"\n{'Variante':<18} {'Gatilhos':>10} {'Wins C1':>10} {'C2 Ent':>8} {'Wins C2':>10} {'Busts':>7} {'Banca Final':>15}")
    print("-"*85)

    for gatilho, div_c1, div_c2, nome in variantes:
        res = simular_2ciclos_compound(
            multiplicadores,
            banca_c1_inicial=7.0,
            banca_c2_inicial=15000.0,
            divisor_c1=div_c1,
            divisor_c2=div_c2,
            gatilho=gatilho,
            compound_pct=100.0
        )
        print(f"{nome:<18} {res.gatilhos_c1:>10,} {res.wins_c1:>10,} {res.gatilhos_c2:>8,} {res.wins_c2:>10,} {res.losses_c2:>7} R$ {res.banca_c2:>12,.2f}")

    print("\n" + "="*70)
    print("SIMULAÇÃO CONCLUÍDA")
    print("="*70)


if __name__ == "__main__":
    main()
