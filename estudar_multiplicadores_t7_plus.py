#!/usr/bin/env python3
"""
ESTUDO DOS MULTIPLICADORES T7+
Quando um gatilho chega em T6 e perde, quais multiplicadores aparecem nas rodadas seguintes?
Objetivo: encontrar um alvo que SEMPRE aparece em algum momento
"""

from collections import defaultdict
from typing import List, Dict
import statistics

THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6
ALVO_LUCRO = 1.99


def carregar_multiplicadores(filepath: str) -> List[float]:
    mults = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)
        for line in f:
            try:
                parts = line.strip().split(',')
                if parts:
                    mults.append(float(parts[0]))
            except:
                continue
    return mults


def encontrar_gatilhos_t6_plus(multiplicadores: List[float]) -> List[int]:
    """Encontra posicoes onde gatilhos chegaram em T6 ou alem (perderam T5)"""
    posicoes_t6 = []

    baixos = 0
    i = 0

    while i < len(multiplicadores) - 20:  # Margem para analisar T7+
        mult = multiplicadores[i]

        if mult < THRESHOLD_BAIXO:
            baixos += 1

            if baixos == GATILHO_SIZE:
                # Gatilho ativado! Verificar se chegou em T6+
                pos_t1 = i + 1

                # Simular ate T5
                chegou_t6 = True
                for t in range(1, 6):  # T1 a T5
                    if pos_t1 + t - 1 < len(multiplicadores):
                        m = multiplicadores[pos_t1 + t - 1]
                        if m >= ALVO_LUCRO:
                            chegou_t6 = False
                            break

                if chegou_t6:
                    # Posicao do T6 (primeiro mult apos T5)
                    pos_t6 = pos_t1 + 5
                    if pos_t6 < len(multiplicadores) - 15:
                        posicoes_t6.append(pos_t6)

                baixos = 0
        else:
            baixos = 0

        i += 1

    return posicoes_t6


def analisar_multiplicadores_apos_t6(multiplicadores: List[float], posicoes_t6: List[int]):
    """Analisa os multiplicadores que aparecem apos T6"""

    # Para cada alvo, contar em quantas tentativas ele aparece
    alvos = [1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]

    # Estatisticas por alvo
    resultados = {}

    for alvo in alvos:
        tentativas_para_acertar = []
        acertou_em_n = defaultdict(int)  # Em quantos casos acertou em exatamente N tentativas

        for pos_t6 in posicoes_t6:
            # Procurar o alvo nas proximas 20 rodadas (T6 a T25)
            acertou = False
            for t in range(20):
                pos = pos_t6 + t
                if pos < len(multiplicadores):
                    m = multiplicadores[pos]
                    if m >= alvo:
                        tentativas_para_acertar.append(t + 1)  # T6 = tentativa 1
                        acertou_em_n[t + 1] += 1
                        acertou = True
                        break

            if not acertou:
                tentativas_para_acertar.append(999)  # Nao acertou em 20 tentativas

        # Calcular estatisticas
        acertou_total = sum(1 for t in tentativas_para_acertar if t < 999)
        taxa_acerto = acertou_total / len(posicoes_t6) * 100 if posicoes_t6 else 0

        # Acerto acumulado por tentativa
        acerto_acumulado = {}
        acumulado = 0
        for t in range(1, 21):
            acumulado += acertou_em_n[t]
            acerto_acumulado[t] = acumulado / len(posicoes_t6) * 100 if posicoes_t6 else 0

        resultados[alvo] = {
            'taxa_acerto_20t': taxa_acerto,
            'media_tentativas': statistics.mean([t for t in tentativas_para_acertar if t < 999]) if acertou_total > 0 else 999,
            'acerto_acumulado': acerto_acumulado,
            'acertou_em_n': dict(acertou_em_n)
        }

    return resultados


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("=" * 100)
    print("ESTUDO DOS MULTIPLICADORES T7+")
    print("Quando gatilho chega em T6, quais multiplicadores aparecem nas rodadas seguintes?")
    print("=" * 100)

    print("\nCarregando dados...")
    multiplicadores = carregar_multiplicadores(csv_path)
    print(f"Total: {len(multiplicadores):,} multiplicadores")

    print("\nEncontrando gatilhos que chegaram em T6+...")
    posicoes_t6 = encontrar_gatilhos_t6_plus(multiplicadores)
    print(f"Total de gatilhos T6+: {len(posicoes_t6):,}")

    print("\nAnalisando multiplicadores apos T6...")
    resultados = analisar_multiplicadores_apos_t6(multiplicadores, posicoes_t6)

    # Relatorio 1: Taxa de acerto em 20 tentativas
    print("\n" + "=" * 100)
    print("TAXA DE ACERTO POR ALVO (em ate 20 tentativas apos T6)")
    print("=" * 100)
    print(f"{'ALVO':>8} {'TAXA 20T':>12} {'MEDIA TENT':>12}")
    print("-" * 35)

    for alvo in sorted(resultados.keys()):
        r = resultados[alvo]
        media = f"{r['media_tentativas']:.1f}" if r['media_tentativas'] < 999 else "N/A"
        print(f"{alvo:>7.2f}x {r['taxa_acerto_20t']:>11.1f}% {media:>12}")

    # Relatorio 2: Acerto acumulado por tentativa
    print("\n" + "=" * 100)
    print("TAXA DE ACERTO ACUMULADA POR TENTATIVA")
    print("(% de chance de o alvo ter aparecido ATE aquela tentativa)")
    print("=" * 100)

    # Header
    alvos_principais = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    header = f"{'TENT':>6}"
    for alvo in alvos_principais:
        header += f" {alvo:>7.1f}x"
    print(header)
    print("-" * (6 + 8 * len(alvos_principais)))

    for t in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]:
        linha = f"T{t+5:>4}"  # T6, T7, T8...
        for alvo in alvos_principais:
            taxa = resultados[alvo]['acerto_acumulado'][t]
            linha += f" {taxa:>7.1f}%"
        print(linha)

    # Encontrar o alvo "magico" - proximo de 100% em poucas tentativas
    print("\n" + "=" * 100)
    print("ANALISE: QUAL ALVO USAR?")
    print("=" * 100)

    print("\nBuscando alvo com ~100% de acerto em poucas tentativas...")

    for alvo in sorted(resultados.keys()):
        r = resultados[alvo]

        # Em quantas tentativas atinge 95%?
        tent_95 = None
        tent_99 = None
        for t in range(1, 21):
            if r['acerto_acumulado'][t] >= 95 and tent_95 is None:
                tent_95 = t
            if r['acerto_acumulado'][t] >= 99 and tent_99 is None:
                tent_99 = t

        if tent_95 and tent_95 <= 10:
            print(f"\n  {alvo:.2f}x:")
            print(f"    95% de acerto em {tent_95} tentativas (T{tent_95+5})")
            if tent_99:
                print(f"    99% de acerto em {tent_99} tentativas (T{tent_99+5})")
            print(f"    Media: {r['media_tentativas']:.1f} tentativas")

    # Analise de recuperacao
    print("\n" + "=" * 100)
    print("SIMULACAO DE RECUPERACAO")
    print("Se chegou em T6 (consumiu 24.4% da banca), quanto precisa para recuperar?")
    print("=" * 100)

    consumido_ate_t5 = 24.41  # %
    banca_restante = 100 - consumido_ate_t5

    print(f"\nConsumo ate T5: {consumido_ate_t5:.1f}%")
    print(f"Banca restante: {banca_restante:.1f}%")

    print(f"\n{'ALVO':>8} {'APOSTA NECESSARIA':>20} {'SOBRA SE GANHAR':>20} {'TENT P/ 95%':>15}")
    print("-" * 70)

    for alvo in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
        # Para recuperar consumido_ate_t5, precisa apostar X onde X * (alvo - 1) = consumido_ate_t5
        # X = consumido_ate_t5 / (alvo - 1)
        aposta_pct = consumido_ate_t5 / (alvo - 1)
        sobra = banca_restante - aposta_pct

        r = resultados[alvo]
        tent_95 = None
        for t in range(1, 21):
            if r['acerto_acumulado'][t] >= 95:
                tent_95 = t
                break

        tent_str = f"T{tent_95+5}" if tent_95 else ">T25"

        print(f"{alvo:>7.1f}x {aposta_pct:>19.1f}% {sobra:>19.1f}% {tent_str:>15}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
