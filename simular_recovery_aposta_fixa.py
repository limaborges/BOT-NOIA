#!/usr/bin/env python3
"""
SIMULACAO - RECOVERY COM APOSTA FIXA
Compara NS7 puro vs Recovery onde a aposta NAO dobra

NS7: martingale normal (T1-T7)
Recovery: T1-T5 martingale, depois aposta FIXA mirando 2.0x/2.5x/3.0x
"""

from typing import List, Dict
from collections import defaultdict

THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6
ALVO_NORMAL = 1.99
NS7_DIVISOR = 127


def simular_ns7_puro(multiplicadores: List[float], banca_inicial: float = 1000.0) -> Dict:
    """NS7 puro com compound"""
    banca = banca_inicial

    gatilhos = 0
    wins = 0
    busts = 0

    baixos = 0
    i = 0

    while i < len(multiplicadores):
        mult = multiplicadores[i]

        if mult < THRESHOLD_BAIXO:
            baixos += 1

            if baixos == GATILHO_SIZE:
                gatilhos += 1
                aposta_base = banca / NS7_DIVISOR

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
                            wins += 1
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
                            wins += 1
                        else:
                            busts += 1
                        i = idx
                        break

                banca += (retorno - investido)
                baixos = 0

                if banca <= 0:
                    break
        else:
            baixos = 0

        i += 1

    return {
        'banca_final': banca,
        'lucro': banca - banca_inicial,
        'gatilhos': gatilhos,
        'wins': wins,
        'busts': busts
    }


def simular_recovery_fixo(multiplicadores: List[float], banca_inicial: float = 1000.0,
                          alvo_rec: float = 2.0, max_tent: int = 10) -> Dict:
    """
    Recovery com aposta FIXA:
    - T1-T5: martingale normal (compound)
    - Se perdeu T5: aposta FIXA mirando alvo_rec ate acertar
    - Aposta fixa = mesmo valor da T5 (16 * base)
    """
    banca = banca_inicial

    gatilhos = 0
    wins_t1_t5 = 0
    wins_recovery = 0
    falhas = 0
    tentativas_rec = []

    baixos = 0
    i = 0

    while i < len(multiplicadores):
        mult = multiplicadores[i]

        if mult < THRESHOLD_BAIXO:
            baixos += 1

            if baixos == GATILHO_SIZE:
                gatilhos += 1
                aposta_base = banca / NS7_DIVISOR

                investido_t1_t5 = 0
                ganhou = False
                pos_final = i

                # Fase 1: T1-T5 (martingale normal)
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
                        banca += (retorno - investido_t1_t5)
                        wins_t1_t5 += 1
                        ganhou = True
                        i = idx
                        break

                if not ganhou:
                    # Fase 2: Recovery com aposta FIXA
                    # Aposta = mesmo que T5 (16 * base) - nao dobra!
                    aposta_rec = aposta_base * 16  # Fixa!

                    investido_rec = 0
                    acertou = False
                    tent = 0

                    for t_rec in range(max_tent):
                        idx = pos_final + 1 + t_rec
                        if idx >= len(multiplicadores):
                            break

                        m = multiplicadores[idx]
                        investido_rec += aposta_rec
                        tent += 1

                        if m >= alvo_rec:
                            retorno = aposta_rec * alvo_rec
                            # Lucro = retorno - (investido T1-T5 + investido recovery)
                            lucro = retorno - investido_t1_t5 - investido_rec
                            banca += lucro
                            wins_recovery += 1
                            acertou = True
                            tentativas_rec.append(tent)
                            i = idx
                            break

                    if not acertou:
                        # Perdeu tudo
                        banca -= (investido_t1_t5 + investido_rec)
                        falhas += 1
                        i = pos_final + tent

                baixos = 0

                if banca <= 0:
                    break
        else:
            baixos = 0

        i += 1

    media_tent = sum(tentativas_rec) / len(tentativas_rec) if tentativas_rec else 0

    return {
        'banca_final': banca,
        'lucro': banca - banca_inicial,
        'gatilhos': gatilhos,
        'wins_t1_t5': wins_t1_t5,
        'wins_recovery': wins_recovery,
        'falhas': falhas,
        'media_tent': media_tent
    }


def carregar_por_mes(filepath: str) -> Dict[str, List[float]]:
    from datetime import datetime
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


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("=" * 110)
    print("SIMULACAO - NS7 vs RECOVERY COM APOSTA FIXA")
    print("Ambos com COMPOUND - comparacao justa")
    print("=" * 110)
    print()
    print("NS7 PURO: T1-T5 @ 1.99x, T6-T7 com defesa")
    print("RECOVERY: T1-T5 @ 1.99x, depois aposta FIXA mirando Xx (nao dobra)")
    print()

    print("Carregando dados...")
    meses = carregar_por_mes(csv_path)
    meses_2025 = {k: v for k, v in sorted(meses.items()) if k >= '2025-01'}
    print(f"Meses: {len(meses_2025)}")

    # Header
    print("\n" + "=" * 130)
    print(f"{'MES':<10} │ {'NS7 PURO':^25} │ {'REC 2.0x':^25} │ {'REC 2.5x':^25} │ {'REC 3.0x':^25}")
    print("-" * 130)

    totais = {
        'ns7': {'lucro': 0, 'busts': 0},
        2.0: {'lucro': 0, 'falhas': 0},
        2.5: {'lucro': 0, 'falhas': 0},
        3.0: {'lucro': 0, 'falhas': 0},
    }

    for mes, multiplicadores in meses_2025.items():
        # NS7
        rel_ns7 = simular_ns7_puro(multiplicadores)
        totais['ns7']['lucro'] += rel_ns7['lucro']
        totais['ns7']['busts'] += rel_ns7['busts']

        # Recovery com diferentes alvos
        rels_rec = {}
        for alvo in [2.0, 2.5, 3.0]:
            rels_rec[alvo] = simular_recovery_fixo(multiplicadores, alvo_rec=alvo)
            totais[alvo]['lucro'] += rels_rec[alvo]['lucro']
            totais[alvo]['falhas'] += rels_rec[alvo]['falhas']

        print(f"{mes:<10} │ "
              f"R${rel_ns7['lucro']:>12,.0f} B:{rel_ns7['busts']:>2} │ "
              f"R${rels_rec[2.0]['lucro']:>12,.0f} F:{rels_rec[2.0]['falhas']:>2} │ "
              f"R${rels_rec[2.5]['lucro']:>12,.0f} F:{rels_rec[2.5]['falhas']:>2} │ "
              f"R${rels_rec[3.0]['lucro']:>12,.0f} F:{rels_rec[3.0]['falhas']:>2}")

    # Totais
    print("-" * 130)
    print(f"{'TOTAL':<10} │ "
          f"R${totais['ns7']['lucro']:>12,.0f} B:{totais['ns7']['busts']:>2} │ "
          f"R${totais[2.0]['lucro']:>12,.0f} F:{totais[2.0]['falhas']:>2} │ "
          f"R${totais[2.5]['lucro']:>12,.0f} F:{totais[2.5]['falhas']:>2} │ "
          f"R${totais[3.0]['lucro']:>12,.0f} F:{totais[3.0]['falhas']:>2}")

    # Resumo
    print("\n" + "=" * 110)
    print("RESUMO")
    print("=" * 110)

    print(f"\n{'ESTRATEGIA':<20} {'LUCRO TOTAL':>20} {'FALHAS':>12} {'vs NS7':>15}")
    print("-" * 70)

    lucro_ns7 = totais['ns7']['lucro']
    print(f"{'NS7 PURO':<20} R${lucro_ns7:>17,.2f} {totais['ns7']['busts']:>12} {'-':>15}")

    for alvo in [2.0, 2.5, 3.0]:
        lucro = totais[alvo]['lucro']
        diff_pct = ((lucro / lucro_ns7) - 1) * 100 if lucro_ns7 > 0 else 0
        print(f"{'Recovery ' + str(alvo) + 'x':<20} R${lucro:>17,.2f} {totais[alvo]['falhas']:>12} {diff_pct:>+14.1f}%")

    print("\n" + "=" * 110)


if __name__ == "__main__":
    main()
