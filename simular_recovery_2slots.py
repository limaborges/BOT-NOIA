#!/usr/bin/env python3
"""
SIMULACAO - RECOVERY COM 2 SLOTS
Comparacao justa: ambos com compound e 2 slots em T6+

NS7 PURO: T1-T5 (1 slot), T6-T7 (2 slots) com defesa 1.10x
RECOVERY: T1-T5 (1 slot), T6+ (2 slots) mirando Xx (sem defesa)

Objetivo: Ver se mirar multiplicador maior com 2 slots sangra menos
"""

from typing import List, Dict
from collections import defaultdict
from datetime import datetime

THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6
ALVO_NORMAL = 1.99
NS7_DIVISOR = 127


def simular_ns7_puro(multiplicadores: List[float], banca_inicial: float = 1000.0) -> Dict:
    """NS7 puro com compound"""
    banca = banca_inicial
    banca_maxima = banca

    gatilhos = 0
    wins = 0
    busts = 0
    drawdown_max = 0

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
                        aposta = aposta_base * 32 * 2  # 2 slots
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
                        aposta = aposta_base * 64 * 2  # 2 slots
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

                if banca > banca_maxima:
                    banca_maxima = banca
                dd = ((banca_maxima - banca) / banca_maxima) * 100 if banca_maxima > 0 else 0
                if dd > drawdown_max:
                    drawdown_max = dd

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
        'busts': busts,
        'drawdown_max': drawdown_max
    }


def simular_recovery_2slots(multiplicadores: List[float], banca_inicial: float = 1000.0,
                            alvo_rec: float = 2.0, max_tent_rec: int = 10) -> Dict:
    """
    Recovery com 2 SLOTS:
    - T1-T5: martingale normal (1 slot, 1.99x)
    - T6+: 2 slots mirando alvo_rec (progressao martingale)
    """
    banca = banca_inicial
    banca_maxima = banca

    gatilhos = 0
    wins_t1_t5 = 0
    wins_recovery = 0
    falhas = 0
    drawdown_max = 0
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

                # Fase 1: T1-T5 (1 slot cada)
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
                    # Fase 2: Recovery com 2 SLOTS mirando alvo_rec
                    # Progressao: T6 = 32*2, T7 = 64*2, T8 = 128*2, etc.
                    investido_rec = 0
                    acertou = False
                    tent = 0

                    for t_rec in range(max_tent_rec):
                        idx = pos_final + 1 + t_rec
                        if idx >= len(multiplicadores):
                            break

                        m = multiplicadores[idx]

                        # Aposta: 2 slots, progressao martingale
                        # T6 = 32*2, T7 = 64*2, T8 = 128*2...
                        multiplicador_aposta = (2 ** (5 + t_rec)) * 2
                        aposta = aposta_base * multiplicador_aposta

                        investido_rec += aposta
                        tent += 1

                        if m >= alvo_rec:
                            retorno = aposta * alvo_rec
                            lucro = retorno - investido_t1_t5 - investido_rec
                            banca += lucro
                            wins_recovery += 1
                            acertou = True
                            tentativas_rec.append(tent)
                            i = idx
                            break

                    if not acertou:
                        banca -= (investido_t1_t5 + investido_rec)
                        falhas += 1
                        i = pos_final + tent

                # Atualizar metricas
                if banca > banca_maxima:
                    banca_maxima = banca
                dd = ((banca_maxima - banca) / banca_maxima) * 100 if banca_maxima > 0 else 0
                if dd > drawdown_max:
                    drawdown_max = dd

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
        'drawdown_max': drawdown_max,
        'media_tent': media_tent,
        'total_recovery': len(tentativas_rec)
    }


def carregar_por_mes(filepath: str) -> Dict[str, List[float]]:
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

    print("=" * 130)
    print("SIMULACAO - NS7 vs RECOVERY COM 2 SLOTS")
    print("=" * 130)
    print()
    print("NS7 PURO: T1-T5 (1 slot @ 1.99x), T6-T7 (2 slots com defesa 1.10x)")
    print("RECOVERY: T1-T5 (1 slot @ 1.99x), T6+ (2 slots mirando Xx, SEM defesa)")
    print()

    print("Carregando dados...")
    meses = carregar_por_mes(csv_path)
    meses_2025 = {k: v for k, v in sorted(meses.items()) if k >= '2025-01'}
    print(f"Meses: {len(meses_2025)}")

    # Header
    print("\n" + "=" * 150)
    print(f"{'MES':<10} │ {'--- NS7 PURO ---':^25} │ {'--- REC 2.0x ---':^28} │ {'--- REC 2.5x ---':^28} │ {'--- REC 3.0x ---':^28}")
    print(f"{'':10} │ {'Lucro':>12} {'DD%':>6} {'B':>4} │ {'Lucro':>12} {'DD%':>6} {'F':>3} {'Tent':>5} │ {'Lucro':>12} {'DD%':>6} {'F':>3} {'Tent':>5} │ {'Lucro':>12} {'DD%':>6} {'F':>3} {'Tent':>5}")
    print("-" * 150)

    totais = {
        'ns7': {'lucro': 0, 'busts': 0, 'dd': []},
        2.0: {'lucro': 0, 'falhas': 0, 'dd': []},
        2.5: {'lucro': 0, 'falhas': 0, 'dd': []},
        3.0: {'lucro': 0, 'falhas': 0, 'dd': []},
    }

    for mes, multiplicadores in meses_2025.items():
        rel_ns7 = simular_ns7_puro(multiplicadores)
        totais['ns7']['lucro'] += rel_ns7['lucro']
        totais['ns7']['busts'] += rel_ns7['busts']
        totais['ns7']['dd'].append(rel_ns7['drawdown_max'])

        rels = {}
        for alvo in [2.0, 2.5, 3.0]:
            rels[alvo] = simular_recovery_2slots(multiplicadores, alvo_rec=alvo)
            totais[alvo]['lucro'] += rels[alvo]['lucro']
            totais[alvo]['falhas'] += rels[alvo]['falhas']
            totais[alvo]['dd'].append(rels[alvo]['drawdown_max'])

        print(f"{mes:<10} │ "
              f"R${rel_ns7['lucro']:>10,.0f} {rel_ns7['drawdown_max']:>5.1f}% {rel_ns7['busts']:>4} │ "
              f"R${rels[2.0]['lucro']:>10,.0f} {rels[2.0]['drawdown_max']:>5.1f}% {rels[2.0]['falhas']:>3} {rels[2.0]['media_tent']:>4.1f}t │ "
              f"R${rels[2.5]['lucro']:>10,.0f} {rels[2.5]['drawdown_max']:>5.1f}% {rels[2.5]['falhas']:>3} {rels[2.5]['media_tent']:>4.1f}t │ "
              f"R${rels[3.0]['lucro']:>10,.0f} {rels[3.0]['drawdown_max']:>5.1f}% {rels[3.0]['falhas']:>3} {rels[3.0]['media_tent']:>4.1f}t")

    # Totais
    print("-" * 150)
    dd_ns7 = sum(totais['ns7']['dd']) / len(totais['ns7']['dd'])
    dd_20 = sum(totais[2.0]['dd']) / len(totais[2.0]['dd'])
    dd_25 = sum(totais[2.5]['dd']) / len(totais[2.5]['dd'])
    dd_30 = sum(totais[3.0]['dd']) / len(totais[3.0]['dd'])

    print(f"{'TOTAL':<10} │ "
          f"R${totais['ns7']['lucro']:>10,.0f} {dd_ns7:>5.1f}% {totais['ns7']['busts']:>4} │ "
          f"R${totais[2.0]['lucro']:>10,.0f} {dd_20:>5.1f}% {totais[2.0]['falhas']:>3} {'-':>5} │ "
          f"R${totais[2.5]['lucro']:>10,.0f} {dd_25:>5.1f}% {totais[2.5]['falhas']:>3} {'-':>5} │ "
          f"R${totais[3.0]['lucro']:>10,.0f} {dd_30:>5.1f}% {totais[3.0]['falhas']:>3} {'-':>5}")

    # Resumo
    print("\n" + "=" * 100)
    print("RESUMO COMPARATIVO")
    print("=" * 100)

    print(f"\n{'ESTRATEGIA':<20} {'LUCRO':>20} {'DD MEDIO':>12} {'FALHAS':>10} {'vs NS7':>15}")
    print("-" * 80)

    lucro_ns7 = totais['ns7']['lucro']
    print(f"{'NS7 PURO':<20} R${lucro_ns7:>17,.0f} {dd_ns7:>11.1f}% {totais['ns7']['busts']:>10} {'-':>15}")

    for alvo in [2.0, 2.5, 3.0]:
        lucro = totais[alvo]['lucro']
        dd = sum(totais[alvo]['dd']) / len(totais[alvo]['dd'])
        diff_pct = ((lucro / lucro_ns7) - 1) * 100 if lucro_ns7 > 0 else 0
        diff_dd = dd - dd_ns7

        melhor_dd = "MENOS DD" if diff_dd < -5 else ""

        print(f"{'Recovery ' + str(alvo) + 'x':<20} R${lucro:>17,.0f} {dd:>11.1f}% {totais[alvo]['falhas']:>10} {diff_pct:>+14.1f}% {melhor_dd}")

    # Conclusao
    print("\n" + "-" * 100)
    print("ANALISE:")
    print("-" * 100)

    for alvo in [2.0, 2.5, 3.0]:
        dd = sum(totais[alvo]['dd']) / len(totais[alvo]['dd'])
        diff_dd = dd - dd_ns7

        if diff_dd < -5:
            print(f"  Recovery {alvo}x: MENOS {-diff_dd:.1f}pp de drawdown")
        elif diff_dd > 5:
            print(f"  Recovery {alvo}x: MAIS {diff_dd:.1f}pp de drawdown")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
