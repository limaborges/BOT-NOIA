#!/usr/bin/env python3
"""
SIMULACAO SEM COMPOUND - NS7 vs RECOVERY
Banca fixa para comparacao justa
"""

from typing import List, Dict
from collections import defaultdict
from datetime import datetime

THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6
ALVO_NORMAL = 1.99
NS7_DIVISOR = 127


def simular_ns7_puro(multiplicadores: List[float], banca_fixa: float = 1000.0) -> Dict:
    """NS7 puro com banca fixa"""
    lucro_total = 0
    gatilhos = 0
    wins = 0
    busts = 0
    cenarios_b = 0

    aposta_base = banca_fixa / NS7_DIVISOR  # Sempre a mesma

    baixos = 0
    i = 0

    while i < len(multiplicadores):
        mult = multiplicadores[i]

        if mult < THRESHOLD_BAIXO:
            baixos += 1

            if baixos == GATILHO_SIZE:
                gatilhos += 1
                investido = 0
                retorno = 0

                for t in range(1, 8):
                    idx = i + t
                    if idx >= len(multiplicadores):
                        break

                    m = multiplicadores[idx]

                    if t <= 5:
                        aposta = aposta_base * (2 ** (t-1))
                        investido += aposta
                        if m >= ALVO_NORMAL:
                            retorno = aposta * ALVO_NORMAL
                            wins += 1
                            i = idx
                            break
                    elif t == 6:
                        aposta = aposta_base * 32 * 2
                        investido += aposta
                        if m >= ALVO_NORMAL:
                            retorno = aposta * ALVO_NORMAL
                            wins += 1
                            i = idx
                            break
                        elif m >= 1.10:
                            retorno = aposta * 1.10
                            cenarios_b += 1
                            i = idx
                            break
                    elif t == 7:
                        aposta = aposta_base * 64 * 2
                        investido += aposta
                        if m >= 2.50:
                            retorno = aposta * 2.50
                            wins += 1
                        elif m >= 1.10:
                            retorno = aposta * 1.10
                            cenarios_b += 1
                        else:
                            busts += 1
                        i = idx
                        break

                lucro_total += (retorno - investido)
                baixos = 0
        else:
            baixos = 0

        i += 1

    return {
        'lucro': lucro_total,
        'gatilhos': gatilhos,
        'wins': wins,
        'busts': busts,
        'cenarios_b': cenarios_b
    }


def simular_recovery(multiplicadores: List[float], banca_fixa: float = 1000.0, alvo_rec: float = 2.0) -> Dict:
    """Recovery: T1-T5 normal, depois mirar alvo_rec"""
    lucro_total = 0
    gatilhos = 0
    wins_t1_t5 = 0
    wins_recovery = 0
    falhas = 0
    tentativas_rec_total = []

    aposta_base = banca_fixa / NS7_DIVISOR

    baixos = 0
    i = 0

    while i < len(multiplicadores):
        mult = multiplicadores[i]

        if mult < THRESHOLD_BAIXO:
            baixos += 1

            if baixos == GATILHO_SIZE:
                gatilhos += 1
                investido_t1_t5 = 0
                retorno = 0
                ganhou_t1_t5 = False
                pos_final = i

                # Fase 1: T1-T5
                for t in range(1, 6):
                    idx = i + t
                    if idx >= len(multiplicadores):
                        break

                    m = multiplicadores[idx]
                    aposta = aposta_base * (2 ** (t-1))
                    investido_t1_t5 += aposta
                    pos_final = idx

                    if m >= ALVO_NORMAL:
                        retorno = aposta * ALVO_NORMAL
                        wins_t1_t5 += 1
                        ganhou_t1_t5 = True
                        i = idx
                        break

                if ganhou_t1_t5:
                    lucro_total += (retorno - investido_t1_t5)
                else:
                    # Recovery: mirar alvo_rec
                    # Aposta = valor que recupera investido_t1_t5 se acertar
                    # lucro = aposta * (alvo - 1) = investido_t1_t5
                    # aposta = investido_t1_t5 / (alvo - 1)

                    investido_rec = 0
                    acertou = False
                    tentativas = 0

                    for t_rec in range(10):  # Max 10 tentativas
                        idx = pos_final + 1 + t_rec
                        if idx >= len(multiplicadores):
                            break

                        m = multiplicadores[idx]

                        # Aposta que recupera TUDO (investido_t1_t5 + investido_rec ate agora)
                        total_a_recuperar = investido_t1_t5 + investido_rec
                        aposta_rec = total_a_recuperar / (alvo_rec - 1)

                        investido_rec += aposta_rec
                        tentativas += 1

                        if m >= alvo_rec:
                            retorno = aposta_rec * alvo_rec
                            lucro = retorno - investido_t1_t5 - investido_rec
                            lucro_total += lucro
                            wins_recovery += 1
                            acertou = True
                            tentativas_rec_total.append(tentativas)
                            i = idx
                            break

                    if not acertou:
                        lucro_total -= (investido_t1_t5 + investido_rec)
                        falhas += 1
                        i = pos_final + tentativas

                baixos = 0
        else:
            baixos = 0

        i += 1

    media_tent = sum(tentativas_rec_total) / len(tentativas_rec_total) if tentativas_rec_total else 0

    return {
        'lucro': lucro_total,
        'gatilhos': gatilhos,
        'wins_t1_t5': wins_t1_t5,
        'wins_recovery': wins_recovery,
        'falhas': falhas,
        'media_tentativas': media_tent
    }


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


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("=" * 100)
    print("SIMULACAO SEM COMPOUND - NS7 vs RECOVERY")
    print("Banca fixa R$ 1000 para comparacao justa")
    print("=" * 100)

    print("\nCarregando dados...")
    multiplicadores = carregar_multiplicadores(csv_path)
    print(f"Total: {len(multiplicadores):,} multiplicadores")

    # NS7 puro
    print("\nSimulando NS7 PURO...")
    rel_ns7 = simular_ns7_puro(multiplicadores)

    # Recovery com diferentes alvos
    alvos = [2.0, 2.5, 3.0]
    resultados_rec = {}

    for alvo in alvos:
        print(f"Simulando RECOVERY {alvo}x...")
        resultados_rec[alvo] = simular_recovery(multiplicadores, alvo_rec=alvo)

    # Resultado
    print("\n" + "=" * 100)
    print("RESULTADO")
    print("=" * 100)

    print(f"\n{'ESTRATEGIA':<25} {'LUCRO':>15} {'GATILHOS':>12} {'WINS':>10} {'FALHAS':>10} {'MEDIA TENT':>12}")
    print("-" * 90)

    print(f"{'NS7 PURO':<25} R${rel_ns7['lucro']:>12,.2f} {rel_ns7['gatilhos']:>12,} {rel_ns7['wins']:>10,} {rel_ns7['busts']:>10} {'-':>12}")

    for alvo in alvos:
        r = resultados_rec[alvo]
        total_wins = r['wins_t1_t5'] + r['wins_recovery']
        print(f"{'RECOVERY ' + str(alvo) + 'x':<25} R${r['lucro']:>12,.2f} {r['gatilhos']:>12,} {total_wins:>10,} {r['falhas']:>10} {r['media_tentativas']:>11.1f}t")

    # Comparativo
    print("\n" + "-" * 90)
    print("COMPARATIVO COM NS7 PURO:")
    print("-" * 90)

    for alvo in alvos:
        r = resultados_rec[alvo]
        diff = r['lucro'] - rel_ns7['lucro']
        diff_pct = (diff / abs(rel_ns7['lucro'])) * 100 if rel_ns7['lucro'] != 0 else 0
        sinal = '+' if diff >= 0 else ''
        print(f"  Recovery {alvo}x: {sinal}R$ {diff:,.2f} ({sinal}{diff_pct:.1f}%)")

    # Detalhes NS7
    print("\n" + "-" * 90)
    print("DETALHES NS7 PURO:")
    print("-" * 90)
    print(f"  Wins T1-T5: estimado ~{rel_ns7['wins'] - rel_ns7['cenarios_b']}")
    print(f"  Cenarios B (T6/T7 defesa): {rel_ns7['cenarios_b']}")
    print(f"  Busts: {rel_ns7['busts']}")

    # Lucro por gatilho
    print("\n" + "-" * 90)
    print("LUCRO MEDIO POR GATILHO:")
    print("-" * 90)

    lucro_por_gatilho_ns7 = rel_ns7['lucro'] / rel_ns7['gatilhos'] if rel_ns7['gatilhos'] > 0 else 0
    print(f"  NS7 PURO: R$ {lucro_por_gatilho_ns7:.2f}/gatilho")

    for alvo in alvos:
        r = resultados_rec[alvo]
        lpg = r['lucro'] / r['gatilhos'] if r['gatilhos'] > 0 else 0
        print(f"  Recovery {alvo}x: R$ {lpg:.2f}/gatilho")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
