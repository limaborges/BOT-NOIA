#!/usr/bin/env python3
"""
SIMULACAO: ESTRATEGIA RECOVERY 3.0x
Compara NS7 puro vs Recovery (mirar 3.0x apos T5)

Estrategia Recovery:
- T1-T5: normal (1.99x), 1 slot cada
- Se perdeu T5: em vez de T6/T7 com defesa, mirar 3.0x ate acertar
- Aposta fixa de 12.2% da banca (recupera os 24.4% investidos em T1-T5)
"""

from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Tuple

# Constantes
THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6

# Alvos
ALVO_NORMAL = 1.99
ALVO_RECOVERY = 2.0  # 95% de acerto em 3 tentativas!

# NS7 config
NS7_DIVISOR = 127
NS7_TENTATIVAS = 7

# Recovery config
MAX_TENTATIVAS_RECOVERY = 15  # Maximo de tentativas mirando 3.0x


class SimuladorComparativo:
    def __init__(self, banca_inicial: float = 1000.0):
        self.banca_inicial = banca_inicial

    def _simular_ns7_puro(self, multiplicadores: List[float]) -> Dict:
        """Simula NS7 puro com T6 e T7 com defesa"""
        banca = self.banca_inicial
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
                    # Gatilho ativado
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
                            # T1-T5: 1 slot @ 1.99x
                            aposta = aposta_base * (2 ** (t-1))
                            investido += aposta

                            if m >= ALVO_NORMAL:
                                retorno = aposta * ALVO_NORMAL
                                wins += 1
                                i = idx
                                break

                        elif t == 6:
                            # T6: 2 slots - PARAR em cenario B
                            aposta = aposta_base * 32 * 2  # 2^5 * 2 slots
                            investido += aposta

                            if m >= ALVO_NORMAL:
                                retorno = aposta * ALVO_NORMAL
                                wins += 1
                                i = idx
                                break
                            elif m >= 1.10:
                                retorno = aposta * 1.10
                                wins += 1  # Parcial
                                i = idx
                                break

                        elif t == 7:
                            # T7: 2 slots - ultima
                            aposta = aposta_base * 64 * 2
                            investido += aposta

                            if m >= 2.50:
                                retorno = aposta * 2.50
                                wins += 1
                            elif m >= 1.10:
                                retorno = aposta * 1.10
                                wins += 1  # Parcial
                            else:
                                busts += 1

                            i = idx
                            break

                    lucro = retorno - investido
                    banca += lucro

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
            'lucro': banca - self.banca_inicial,
            'ganho_pct': ((banca / self.banca_inicial) - 1) * 100,
            'gatilhos': gatilhos,
            'wins': wins,
            'busts': busts,
            'drawdown_max': drawdown_max
        }

    def _simular_recovery(self, multiplicadores: List[float], alvo_recovery: float = 3.0) -> Dict:
        """Simula estrategia Recovery: T1-T5 normal, depois mirar alvo_recovery"""
        banca = self.banca_inicial
        banca_maxima = banca

        gatilhos = 0
        wins_t1_t5 = 0
        wins_recovery = 0
        falhas_recovery = 0
        drawdown_max = 0

        tentativas_recovery_hist = []  # Quantas tentativas levou cada recovery

        baixos = 0
        i = 0

        while i < len(multiplicadores):
            mult = multiplicadores[i]

            if mult < THRESHOLD_BAIXO:
                baixos += 1

                if baixos == GATILHO_SIZE:
                    gatilhos += 1
                    aposta_base = banca / NS7_DIVISOR

                    # Fase 1: T1-T5 normal
                    investido_fase1 = 0
                    ganhou_fase1 = False
                    pos_final_fase1 = i

                    for t in range(1, 6):
                        idx = i + t
                        if idx >= len(multiplicadores):
                            break

                        m = multiplicadores[idx]
                        aposta = aposta_base * (2 ** (t-1))
                        investido_fase1 += aposta
                        pos_final_fase1 = idx

                        if m >= ALVO_NORMAL:
                            # Ganhou em T1-T5
                            lucro = aposta * ALVO_NORMAL - investido_fase1
                            banca += lucro
                            wins_t1_t5 += 1
                            ganhou_fase1 = True
                            i = idx
                            break

                    if not ganhou_fase1:
                        # Perdeu T1-T5, entrar em modo recovery
                        # Estrategia: Martingale mirando 3.0x
                        # Aposta inicial = valor que recupera tudo se acertar de primeira
                        # Se perder, dobra a aposta (mantendo mesma logica martingale)

                        # Banca disponivel para recovery = banca atual (ja descontou investido_fase1)
                        banca_pre_recovery = banca - investido_fase1

                        # Aposta inicial: precisa recuperar investido_fase1
                        # Se acertar 3.0x: retorno = aposta * 3, lucro = aposta * 2
                        # Para lucro = investido_fase1: aposta = investido_fase1 / 2
                        aposta_base_rec = investido_fase1 / (alvo_recovery - 1)

                        acertou_recovery = False
                        tentativas_recovery = 0
                        investido_recovery = 0

                        for t_rec in range(MAX_TENTATIVAS_RECOVERY):
                            idx = pos_final_fase1 + 1 + t_rec
                            if idx >= len(multiplicadores):
                                break

                            m = multiplicadores[idx]

                            # Aposta desta tentativa: martingale (dobra a cada tentativa)
                            # Mas ajustada para recuperar TUDO (investido_fase1 + investido_recovery)
                            total_a_recuperar = investido_fase1 + investido_recovery
                            aposta = total_a_recuperar / (alvo_recovery - 1)

                            # Verificar se tem banca suficiente
                            if aposta > banca_pre_recovery - investido_recovery:
                                # Nao tem banca, parar
                                break

                            investido_recovery += aposta
                            tentativas_recovery += 1

                            if m >= alvo_recovery:
                                # Acertou!
                                retorno = aposta * alvo_recovery
                                lucro = retorno - investido_fase1 - investido_recovery
                                banca = banca_pre_recovery + lucro
                                wins_recovery += 1
                                acertou_recovery = True
                                tentativas_recovery_hist.append(tentativas_recovery)
                                i = idx
                                break

                        if not acertou_recovery:
                            # Nao acertou - loss total do investido
                            banca = banca_pre_recovery - investido_recovery
                            falhas_recovery += 1
                            i = pos_final_fase1 + tentativas_recovery

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

        media_tent_recovery = sum(tentativas_recovery_hist) / len(tentativas_recovery_hist) if tentativas_recovery_hist else 0

        return {
            'banca_final': banca,
            'lucro': banca - self.banca_inicial,
            'ganho_pct': ((banca / self.banca_inicial) - 1) * 100,
            'gatilhos': gatilhos,
            'wins_t1_t5': wins_t1_t5,
            'wins_recovery': wins_recovery,
            'falhas_recovery': falhas_recovery,
            'drawdown_max': drawdown_max,
            'media_tent_recovery': media_tent_recovery,
            'total_recovery': len(tentativas_recovery_hist)
        }

    def simular(self, multiplicadores: List[float]) -> Tuple[Dict, Dict]:
        """Simula ambas estrategias e retorna resultados"""
        rel_ns7 = self._simular_ns7_puro(multiplicadores)
        rel_recovery = self._simular_recovery(multiplicadores, ALVO_RECOVERY)
        return rel_ns7, rel_recovery


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

    print("=" * 100)
    print("SIMULACAO: NS7 PURO vs RECOVERY 2.0x")
    print("=" * 100)
    print()
    print("NS7 PURO: T1-T5 @ 1.99x, T6-T7 com defesa 1.10x")
    print("RECOVERY: T1-T5 @ 1.99x, depois mirar 2.0x ate acertar (95% em 3 tent!)")
    print()

    print("Carregando dados...")
    meses = carregar_por_mes(csv_path)
    meses_2025 = {k: v for k, v in sorted(meses.items()) if k >= '2025-01'}

    print(f"Meses: {len(meses_2025)}")
    print()

    # Simular mes a mes
    print("=" * 120)
    print(f"{'MES':<10} │ {'--- NS7 PURO ---':^30} │ {'--- RECOVERY 2.0x ---':^45} │ {'DIFF':>10}")
    print(f"{'':10} │ {'Lucro':>12} {'DD%':>8} {'Bust':>6} │ {'Lucro':>12} {'DD%':>8} {'RecWin':>8} {'RecFail':>8} {'MedTent':>7} │ {'':>10}")
    print("-" * 120)

    total_ns7 = 0
    total_recovery = 0
    total_busts_ns7 = 0
    total_falhas_rec = 0

    resultados = []

    for mes, multiplicadores in meses_2025.items():
        sim = SimuladorComparativo(banca_inicial=1000.0)
        rel_ns7, rel_rec = sim.simular(multiplicadores)

        diff = rel_rec['lucro'] - rel_ns7['lucro']
        diff_str = f"+R${diff:,.0f}" if diff >= 0 else f"-R${-diff:,.0f}"

        total_ns7 += rel_ns7['lucro']
        total_recovery += rel_rec['lucro']
        total_busts_ns7 += rel_ns7['busts']
        total_falhas_rec += rel_rec['falhas_recovery']

        resultados.append({
            'mes': mes,
            'ns7': rel_ns7,
            'recovery': rel_rec,
            'diff': diff
        })

        print(f"{mes:<10} │ "
              f"R${rel_ns7['lucro']:>10,.0f} {rel_ns7['drawdown_max']:>7.1f}% {rel_ns7['busts']:>6} │ "
              f"R${rel_rec['lucro']:>10,.0f} {rel_rec['drawdown_max']:>7.1f}% {rel_rec['wins_recovery']:>8} {rel_rec['falhas_recovery']:>8} {rel_rec['media_tent_recovery']:>6.1f}t │ "
              f"{diff_str:>10}")

    # Totais
    print("-" * 120)
    diff_total = total_recovery - total_ns7
    diff_str = f"+R${diff_total:,.0f}" if diff_total >= 0 else f"-R${-diff_total:,.0f}"

    print(f"{'TOTAL':<10} │ "
          f"R${total_ns7:>10,.0f} {'-':>7} {total_busts_ns7:>6} │ "
          f"R${total_recovery:>10,.0f} {'-':>7} {'-':>8} {total_falhas_rec:>8} {'-':>6} │ "
          f"{diff_str:>10}")

    # Resumo
    print("\n" + "=" * 100)
    print("RESUMO")
    print("=" * 100)

    n_meses = len(meses_2025)

    print(f"\n{'Metrica':<35} {'NS7 PURO':>20} {'RECOVERY 2.0x':>20}")
    print("-" * 80)
    print(f"{'Lucro Total':<35} R${total_ns7:>17,.2f} R${total_recovery:>17,.2f}")
    print(f"{'Lucro Medio/Mes':<35} R${total_ns7/n_meses:>17,.2f} R${total_recovery/n_meses:>17,.2f}")
    print(f"{'Busts / Falhas Recovery':<35} {total_busts_ns7:>20} {total_falhas_rec:>20}")

    # Diferencas
    print("\n" + "-" * 80)
    diff_pct = ((total_recovery / total_ns7) - 1) * 100 if total_ns7 > 0 else 0
    print(f"Diferenca: {'+'if diff_total>=0 else ''}R$ {diff_total:,.2f} ({diff_pct:+.1f}%)")

    if diff_total > 0:
        print("\n>> RECOVERY 3.0x SUPERIOR!")
    else:
        print("\n>> NS7 PURO SUPERIOR")

    # Meses onde recovery foi melhor
    print("\n" + "-" * 80)
    print("MESES ONDE RECOVERY FOI MELHOR:")
    for r in resultados:
        if r['diff'] > 0:
            print(f"  {r['mes']}: +R$ {r['diff']:,.0f}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
