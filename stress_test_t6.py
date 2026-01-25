#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
STRESS TEST - Sobrevivemos com T6 extras?

Simula a estratégia NS7 nos 130k multiplicadores reais,
mas injeta T6 fictícios acima da estatística normal para
testar a resiliência da estratégia.

NS7 = 3 tentativas após G6
- T1, T2, T3 = vitória
- T4+ = perda (para NS7, T4 já é perda)
"""

import re
import sqlite3
import os
from datetime import datetime
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def carregar_multiplicadores():
    """Carrega todos os multiplicadores"""
    mults = []

    arquivo1 = os.path.join(BASE_DIR, '16.10.25--27.11.25.txt')
    if os.path.exists(arquivo1):
        pattern = r'Rodada salva: ([\d.]+)x'
        with open(arquivo1, 'r', encoding='utf-8', errors='ignore') as f:
            for linha in f:
                match = re.search(pattern, linha)
                if match:
                    mults.append(float(match.group(1)))

    arquivo2 = os.path.join(BASE_DIR, '28.11.25--15.12.25.txt')
    if os.path.exists(arquivo2):
        with open(arquivo2, 'r', encoding='utf-8', errors='ignore') as f:
            for linha in f:
                match = re.search(pattern, linha)
                if match:
                    mults.append(float(match.group(1)))

    db_path = os.path.join(BASE_DIR, 'database', 'rounds.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT multiplier FROM rounds WHERE multiplier IS NOT NULL ORDER BY id')
        for row in cursor.fetchall():
            mults.append(float(row[0]))
        conn.close()

    return mults


def encontrar_gatilhos(mults):
    """
    Encontra todos os gatilhos G6+ e retorna posição e tamanho.
    Retorna lista de (posição_inicio, tamanho_sequencia)
    """
    gatilhos = []
    i = 0
    n = len(mults)

    while i < n:
        seq = 0
        inicio = i

        # Contar baixos consecutivos
        while i < n and mults[i] < 2.0:
            seq += 1
            i += 1

        if seq >= 6:
            gatilhos.append({
                'pos': inicio,
                'tamanho': seq,
                'tentativa': seq - 5,  # T1 = seq 6, T2 = seq 7, etc
            })

        if i < n:
            i += 1  # Pular o multiplicador alto

    return gatilhos


def injetar_t6_extras(gatilhos, quantidade_extra, seed=42):
    """
    Injeta T6 fictícios transformando gatilhos existentes
    (T1, T2, T3) em T6.
    """
    random.seed(seed)

    # Encontrar gatilhos que podem ser transformados (T1-T3)
    transformaveis = [i for i, g in enumerate(gatilhos) if g['tentativa'] <= 3]

    if quantidade_extra > len(transformaveis):
        print(f"AVISO: Pedido {quantidade_extra} T6 extras, mas só há {len(transformaveis)} gatilhos transformáveis")
        quantidade_extra = len(transformaveis)

    # Escolher aleatoriamente quais transformar
    escolhidos = random.sample(transformaveis, quantidade_extra)

    # Criar cópia modificada
    gatilhos_modificados = []
    for i, g in enumerate(gatilhos):
        novo = g.copy()
        if i in escolhidos:
            novo['tentativa'] = 6  # Transformar em T6
            novo['tamanho'] = 11  # G6 + 5 tentativas = seq 11
            novo['ficticio'] = True
        else:
            novo['ficticio'] = False
        gatilhos_modificados.append(novo)

    return gatilhos_modificados


def simular_ns7(gatilhos, saldo_inicial=10000, aposta_base_pct=0.5):
    """
    Simula estratégia NS7 (3 tentativas).

    Martingale:
    - Aposta base = X% do saldo
    - T1: ganha aposta
    - T2: ganha após perder 1 (dobrou)
    - T3: ganha após perder 2 (dobrou 2x)
    - T4+: perde tudo (para NS7)

    NS7 usa 2 slots: penúltimo e último
    - Slot 1 (penúltimo): aposta na T2
    - Slot 2 (último): aposta na T3

    Simplificação: NS7 = perde se T4+
    """
    saldo = saldo_inicial
    historico = [saldo]

    vitorias = 0
    derrotas = 0

    for g in gatilhos:
        t = g['tentativa']
        aposta = saldo * (aposta_base_pct / 100)

        if t <= 3:
            # Vitória no NS7
            # Ganho depende da tentativa (mais tarde = mais custo antes)
            if t == 1:
                lucro = aposta * 0.94  # Sem custo anterior
            elif t == 2:
                lucro = aposta * 0.94 - aposta  # Perdeu 1 antes
            else:  # T3
                lucro = aposta * 0.94 - aposta - aposta * 2  # Perdeu 2 antes (dobradas)

            saldo += lucro
            vitorias += 1
        else:
            # Derrota no NS7 (T4+)
            # Perdeu: aposta (T2) + aposta*2 (T3) = 3 apostas
            perda = aposta + aposta * 2
            saldo -= perda
            derrotas += 1

        historico.append(saldo)

        if saldo <= 0:
            break

    return {
        'saldo_final': saldo,
        'vitorias': vitorias,
        'derrotas': derrotas,
        'historico': historico,
        'sobreviveu': saldo > 0,
        'retorno_pct': (saldo - saldo_inicial) / saldo_inicial * 100,
        'min_saldo': min(historico),
        'drawdown_max': (saldo_inicial - min(historico)) / saldo_inicial * 100,
    }


def main():
    print("=" * 70)
    print("STRESS TEST - SOBREVIVEMOS COM T6 EXTRAS?")
    print("=" * 70)

    print("\nCarregando multiplicadores...")
    mults = carregar_multiplicadores()
    print(f"Total: {len(mults):,} multiplicadores")

    # Encontrar gatilhos reais
    gatilhos_reais = encontrar_gatilhos(mults)
    print(f"Gatilhos G6+ encontrados: {len(gatilhos_reais)}")

    # Estatísticas reais
    t_dist = {}
    for g in gatilhos_reais:
        t = min(g['tentativa'], 9)  # Agrupar T9+
        t_dist[t] = t_dist.get(t, 0) + 1

    print("\nDistribuição real de tentativas:")
    for t in sorted(t_dist.keys()):
        pct = t_dist[t] / len(gatilhos_reais) * 100
        print(f"  T{t}: {t_dist[t]} ({pct:.1f}%)")

    t4_mais_real = sum(v for k, v in t_dist.items() if k >= 4)
    print(f"\nT4+ real (perdas NS7): {t4_mais_real} ({t4_mais_real/len(gatilhos_reais)*100:.1f}%)")

    # ===== SIMULAÇÃO BASE (SEM EXTRAS) =====
    print("\n" + "=" * 70)
    print("SIMULAÇÃO BASE (dados reais, sem T6 extras)")
    print("=" * 70)

    resultado_base = simular_ns7(gatilhos_reais)
    print(f"\nSaldo inicial: R$ 10.000")
    print(f"Saldo final: R$ {resultado_base['saldo_final']:,.2f}")
    print(f"Retorno: {resultado_base['retorno_pct']:.1f}%")
    print(f"Vitórias: {resultado_base['vitorias']}")
    print(f"Derrotas: {resultado_base['derrotas']}")
    print(f"Drawdown máximo: {resultado_base['drawdown_max']:.1f}%")
    print(f"Sobreviveu: {'SIM' if resultado_base['sobreviveu'] else 'NÃO'}")

    # ===== STRESS TESTS =====
    print("\n" + "=" * 70)
    print("STRESS TESTS - INJETANDO T6 EXTRAS")
    print("=" * 70)

    # Calcular quantos T6 extras para diferentes cenários
    t6_real = t_dist.get(6, 0) + t_dist.get(7, 0) + t_dist.get(8, 0) + t_dist.get(9, 0)
    t4_real = t_dist.get(4, 0)
    t5_real = t_dist.get(5, 0)

    print(f"\nT4 real: {t4_real}")
    print(f"T5 real: {t5_real}")
    print(f"T6+ real: {t6_real}")

    cenarios = [
        ("Real (baseline)", 0),
        ("+50% T6", int(t6_real * 0.5)),
        ("+100% T6 (2x)", int(t6_real * 1.0)),
        ("+150% T6", int(t6_real * 1.5)),
        ("+200% T6 (3x)", int(t6_real * 2.0)),
        ("+300% T6 (4x)", int(t6_real * 3.0)),
        ("+500% T6 (6x)", int(t6_real * 5.0)),
        ("Apocalipse (+1000%)", int(t6_real * 10.0)),
    ]

    print("\n" + "-" * 80)
    print(f"{'Cenário':<25} {'T6 Total':>10} {'Saldo Final':>15} {'Retorno':>10} {'Drawdown':>10} {'Status':>10}")
    print("-" * 80)

    for nome, extras in cenarios:
        gatilhos_mod = injetar_t6_extras(gatilhos_reais, extras)
        resultado = simular_ns7(gatilhos_mod)

        t6_total = sum(1 for g in gatilhos_mod if g['tentativa'] >= 6)

        status = "✓ OK" if resultado['sobreviveu'] and resultado['retorno_pct'] > 0 else \
                 "⚠ NEGATIVO" if resultado['sobreviveu'] else "✗ QUEBROU"

        print(f"{nome:<25} {t6_total:>10} R$ {resultado['saldo_final']:>12,.0f} {resultado['retorno_pct']:>+9.1f}% {resultado['drawdown_max']:>9.1f}% {status:>10}")

    # ===== ENCONTRAR LIMITE =====
    print("\n" + "=" * 70)
    print("ENCONTRANDO O LIMITE - Quantos T6 extras até quebrar?")
    print("=" * 70)

    for extras in range(0, 500, 10):
        gatilhos_mod = injetar_t6_extras(gatilhos_reais, extras)
        resultado = simular_ns7(gatilhos_mod)

        if not resultado['sobreviveu'] or resultado['retorno_pct'] < -50:
            print(f"\n⚠️  LIMITE ENCONTRADO: {extras} T6 extras")
            print(f"   T6 total: {sum(1 for g in gatilhos_mod if g['tentativa'] >= 6)}")
            print(f"   Isso seria {extras/t6_real*100:.0f}% a mais que o real")
            break
    else:
        print("\n✓ Sobreviveu a todos os cenários testados (até +500 T6)")

    # ===== CONCLUSÃO =====
    print("\n" + "=" * 70)
    print("CONCLUSÃO")
    print("=" * 70)

    print(f"""
Baseado nos ~{len(mults):,} multiplicadores reais:

• T6+ real: {t6_real} ocorrências ({t6_real/len(gatilhos_reais)*100:.1f}% dos gatilhos)
• Estratégia NS7 com aposta 0.5% do saldo

RESILIÊNCIA:
""")


if __name__ == "__main__":
    main()
