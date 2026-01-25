#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
STRESS TEST NS7 - ESTRATÉGIA V4 CORRIGIDA

Configuração REAL:
- Divisor: 127
- 7 tentativas
- T1-T5: 1 slot @ 1.99x
- T6: 2 slots (6/16 @ 1.99x + 10/16 @ 1.25x) - PARAR no Cenário B
- T7: 1 slot @ 1.25x (sobrevivência)

Progressão: 1, 2, 4, 8, 16, 32, 64 = 127 unidades
"""

import re
import sqlite3
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def carregar_multiplicadores():
    mults = []
    for arquivo in ['16.10.25--27.11.25.txt', '28.11.25--15.12.25.txt']:
        path = os.path.join(BASE_DIR, arquivo)
        if os.path.exists(path):
            pattern = r'Rodada salva: ([\d.]+)x'
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
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


def injetar_baixos_extras(mults, quantidade, seed=42):
    """
    Injeta multiplicadores baixos extras para criar mais T6/T7.
    Transforma sequências G6 que resolveram cedo em sequências maiores.
    """
    random.seed(seed)
    mults = mults.copy()

    # Encontrar posições onde podemos estender sequências
    posicoes = []
    i = 0
    n = len(mults)
    while i < n:
        seq = 0
        inicio = i
        while i < n and mults[i] < 2.0:
            seq += 1
            i += 1

        if 6 <= seq <= 10 and i < n:
            # Sequência que resolveu - podemos estender
            posicoes.append(i)

        if i < n:
            i += 1

    # Escolher quais estender
    escolhidos = random.sample(posicoes, min(quantidade, len(posicoes)))

    for pos in escolhidos:
        # Substituir o multiplicador alto por baixo para estender a sequência
        # Até criar T6+ (precisamos que chegue até T6 ou T7)
        for j in range(6):  # Adicionar até 6 baixos para garantir T6/T7
            if pos + j < len(mults):
                mults[pos + j] = 1.10 + random.random() * 0.5  # Entre 1.10 e 1.60

    return mults


def simular_ns7(mults, saldo_inicial=10000):
    """
    Simula a estratégia NS7 V4 CORRIGIDA
    """
    saldo = saldo_inicial
    saldo_ref = saldo_inicial
    reserva = 0

    historico = []

    i = 0
    n = len(mults)
    seq = 0

    stats = {
        't1_win': 0, 't2_win': 0, 't3_win': 0, 't4_win': 0, 't5_win': 0,
        't6_cenA': 0, 't6_cenB': 0, 't6_cenC': 0,
        't7_sobrevive': 0, 't7_bust': 0,
        'metas': 0,
    }

    gatilho_num = 0

    while i < n:
        if mults[i] < 2.0:
            seq += 1
        else:
            seq = 0

        if seq == 6:
            gatilho_num += 1

            # Unidade base = saldo / 127
            unidade = saldo / 127
            custo_acumulado = 0
            resultado = None

            # ===== T1-T5: 1 slot @ 1.99x =====
            for t in range(1, 6):
                i += 1
                if i >= n:
                    break

                aposta = unidade * (2 ** (t - 1))  # 1, 2, 4, 8, 16

                if mults[i] >= 1.99:
                    # Ganhou!
                    ganho = aposta * 1.99 * 0.97 - custo_acumulado - aposta
                    saldo += ganho
                    stats[f't{t}_win'] += 1
                    resultado = f'T{t}_WIN'
                    break
                else:
                    # Perdeu, próxima tentativa
                    custo_acumulado += aposta

            if resultado:
                pass  # Já resolveu em T1-T5
            elif i < n:
                # ===== T6: 2 slots =====
                i += 1
                if i < n:
                    aposta_t6 = unidade * 32  # 32/127
                    slot1 = aposta_t6 * (6/16)   # @ 1.99x
                    slot2 = aposta_t6 * (10/16)  # @ 1.25x

                    mult_t6 = mults[i]

                    if mult_t6 >= 1.99:
                        # Cenário A: ambos ganham
                        ganho_s1 = slot1 * 1.99 * 0.97
                        ganho_s2 = slot2 * 1.25 * 0.97
                        ganho_total = ganho_s1 + ganho_s2 - slot1 - slot2 - custo_acumulado
                        saldo += ganho_total
                        stats['t6_cenA'] += 1
                        resultado = 'T6_A'

                    elif mult_t6 >= 1.25:
                        # Cenário B: slot2 ganha, slot1 perde - PARAR
                        ganho_s2 = slot2 * 1.25 * 0.97
                        perda = custo_acumulado + slot1 + slot2 - ganho_s2
                        saldo -= perda
                        stats['t6_cenB'] += 1
                        resultado = 'T6_B_PARAR'

                    else:
                        # Cenário C: ambos perdem, vai T7
                        custo_acumulado += aposta_t6

                        # ===== T7: 1 slot @ 1.25x =====
                        i += 1
                        if i < n:
                            aposta_t7 = unidade * 64  # 64/127
                            mult_t7 = mults[i]

                            if mult_t7 >= 1.25:
                                # Sobrevive com -37%
                                ganho_t7 = aposta_t7 * 1.25 * 0.97
                                perda = custo_acumulado + aposta_t7 - ganho_t7
                                saldo -= perda
                                stats['t7_sobrevive'] += 1
                                resultado = 'T7_SOBREVIVE'
                            else:
                                # BUST!
                                saldo -= custo_acumulado + aposta_t7
                                stats['t7_bust'] += 1
                                resultado = 'T7_BUST'

            seq = 0

            # Verificar meta 10%
            lucro = saldo - saldo_ref
            if lucro >= saldo_ref * 0.10:
                reserva += lucro * 0.5
                saldo -= lucro * 0.5
                saldo_ref = saldo
                stats['metas'] += 1

            historico.append({
                'num': gatilho_num,
                'saldo': saldo,
                'reserva': reserva,
                'resultado': resultado,
            })

            if saldo <= 0:
                break

        i += 1

    return {
        'saldo': saldo,
        'reserva': reserva,
        'total': saldo + reserva,
        'stats': stats,
        'historico': historico,
        'sobreviveu': saldo > 0,
    }


def main():
    print("=" * 70)
    print("STRESS TEST NS7 - ESTRATÉGIA V4 CORRIGIDA")
    print("=" * 70)

    mults_originais = carregar_multiplicadores()
    print(f"\nTotal multiplicadores: {len(mults_originais):,}")

    # ===== SIMULAÇÃO BASE =====
    print("\n" + "=" * 70)
    print("SIMULAÇÃO BASE (dados reais)")
    print("=" * 70)

    resultado = simular_ns7(mults_originais)
    s = resultado['stats']

    print(f"\nSaldo inicial:     R$ 10.000,00")
    print(f"Saldo final:       R$ {resultado['saldo']:,.2f}")
    print(f"Reserva:           R$ {resultado['reserva']:,.2f}")
    print(f"PATRIMÔNIO TOTAL:  R$ {resultado['total']:,.2f}")
    print(f"Retorno:           {(resultado['total'] - 10000) / 10000 * 100:+.1f}%")

    print(f"\n--- Distribuição de Resultados ---")
    print(f"T1 wins: {s['t1_win']}")
    print(f"T2 wins: {s['t2_win']}")
    print(f"T3 wins: {s['t3_win']}")
    print(f"T4 wins: {s['t4_win']}")
    print(f"T5 wins: {s['t5_win']}")
    print(f"T6 Cenário A (-5.6%): {s['t6_cenA']}")
    print(f"T6 Cenário B PARAR (-15.1%): {s['t6_cenB']}")
    print(f"T6 Cenário C (→T7): {s['t6_cenC']}")
    print(f"T7 Sobrevive (-37%): {s['t7_sobrevive']}")
    print(f"T7 BUST (-100%): {s['t7_bust']}")
    print(f"\nMetas 10% batidas: {s['metas']}")

    total_gatilhos = sum([s['t1_win'], s['t2_win'], s['t3_win'], s['t4_win'], s['t5_win'],
                         s['t6_cenA'], s['t6_cenB'], s['t7_sobrevive'], s['t7_bust']])

    chegaram_t6 = s['t6_cenA'] + s['t6_cenB'] + s['t7_sobrevive'] + s['t7_bust']

    print(f"\nTotal gatilhos: {total_gatilhos}")
    print(f"Chegaram T6: {chegaram_t6} ({chegaram_t6/total_gatilhos*100:.1f}%)")
    print(f"Chegaram T7: {s['t7_sobrevive'] + s['t7_bust']} ({(s['t7_sobrevive'] + s['t7_bust'])/total_gatilhos*100:.2f}%)")

    # ===== STRESS TESTS =====
    print("\n" + "=" * 70)
    print("STRESS TESTS - INJETANDO MAIS T6/T7")
    print("=" * 70)

    cenarios = [
        ("Real (baseline)", 0),
        ("+10 perdas extras", 10),
        ("+20 perdas extras", 20),
        ("+30 perdas extras", 30),
        ("+50 perdas extras", 50),
        ("+75 perdas extras", 75),
        ("+100 perdas extras", 100),
        ("+150 perdas extras", 150),
        ("+200 perdas extras", 200),
    ]

    print(f"\n{'Cenário':<22} {'Banca':>12} {'Reserva':>10} {'Total':>12} {'Retorno':>10} {'BUSTs':>6} {'Status':>10}")
    print("-" * 90)

    for nome, extras in cenarios:
        mults_mod = injetar_baixos_extras(mults_originais, extras)
        resultado = simular_ns7(mults_mod)
        s = resultado['stats']

        status = "✓ OK" if resultado['sobreviveu'] and resultado['total'] > 10000 else \
                 "⚠ NEGATIVO" if resultado['sobreviveu'] else "✗ QUEBROU"

        retorno = (resultado['total'] - 10000) / 10000 * 100

        print(f"{nome:<22} R${resultado['saldo']:>10,.0f} R${resultado['reserva']:>8,.0f} R${resultado['total']:>10,.0f} {retorno:>+9.1f}% {s['t7_bust']:>6} {status:>10}")

    # ===== EVOLUÇÃO DO SALDO =====
    print("\n" + "=" * 70)
    print("EVOLUÇÃO DO PATRIMÔNIO (dados reais)")
    print("=" * 70)

    resultado_base = simular_ns7(mults_originais)

    print("\nA cada 200 gatilhos:")
    for h in resultado_base['historico'][::200]:
        total = h['saldo'] + h['reserva']
        print(f"  Gatilho {h['num']:>4}: Banca R${h['saldo']:>10,.0f} | Reserva R${h['reserva']:>8,.0f} | Total R${total:>10,.0f}")

    # Último
    h = resultado_base['historico'][-1]
    total = h['saldo'] + h['reserva']
    print(f"  Gatilho {h['num']:>4}: Banca R${h['saldo']:>10,.0f} | Reserva R${h['reserva']:>8,.0f} | Total R${total:>10,.0f}")


if __name__ == "__main__":
    main()
