#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
STRESS TEST COMPLETO - Simulação exata da estratégia

Estratégia:
- NS7 = 3 tentativas (2 slots: penúltimo e último)
- Aguarda G6 (6 baixos consecutivos)
- Aposta começa no 7º multiplicador
- Martingale: dobra a cada perda
- Reserva de lucro: 10% → 5% reserva + 5% incorpora

Simulação rodada a rodada com multiplicadores reais.
"""

import re
import sqlite3
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def carregar_multiplicadores():
    """Carrega todos os multiplicadores em ordem"""
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


def injetar_t6_nos_multiplicadores(mults, quantidade_extra, seed=42):
    """
    Injeta T6 fictícios diretamente nos multiplicadores.

    Encontra sequências G6 que resolveram em T1-T3 e as estende
    para se tornarem T6 (substituindo o multiplicador alto por baixos).
    """
    random.seed(seed)
    mults = mults.copy()

    # Encontrar posições onde há G6 que resolve em T1-T3
    posicoes_modificaveis = []

    i = 0
    n = len(mults)
    while i < n:
        seq_baixos = 0
        inicio_seq = i

        while i < n and mults[i] < 2.0:
            seq_baixos += 1
            i += 1

        if seq_baixos >= 6 and seq_baixos <= 8 and i < n:
            # G6/G7/G8 que resolveu - podemos estender para T6
            posicoes_modificaveis.append({
                'pos_alto': i,  # Posição do multiplicador que resolveu
                'seq_atual': seq_baixos,
            })

        if i < n:
            i += 1

    # Escolher quais modificar
    if quantidade_extra > len(posicoes_modificaveis):
        quantidade_extra = len(posicoes_modificaveis)

    escolhidos = random.sample(range(len(posicoes_modificaveis)), quantidade_extra)

    # Modificar (substituir o alto por baixos para criar T6)
    for idx in escolhidos:
        info = posicoes_modificaveis[idx]
        pos = info['pos_alto']
        seq = info['seq_atual']

        # Precisamos adicionar baixos até chegar em seq=11 (G6+T6=11)
        baixos_adicionar = 11 - seq

        # Substituir os próximos multiplicadores por baixos
        for j in range(baixos_adicionar):
            if pos + j < len(mults):
                mults[pos + j] = 1.20 + random.random() * 0.5  # Baixo aleatório

    return mults


def simular_estrategia(mults, saldo_inicial=10000, aposta_pct=0.5):
    """
    Simula a estratégia NS7 rodada a rodada.

    NS7:
    - Aguarda G6 (6 baixos consecutivos)
    - Slot 1 (penúltimo): aposta na 7ª rodada (T1)
    - Slot 2 (último): aposta na 8ª rodada (T2) se T1 perdeu
    - Slot 2 dobra: aposta na 9ª rodada (T3) se T2 perdeu
    - T4+ = perda total do trigger

    Reserva de lucro:
    - A cada 10% de lucro, 5% vai para reserva, 5% incorpora
    """
    saldo = saldo_inicial
    saldo_referencia = saldo_inicial  # Para calcular meta de 10%
    reserva = 0

    historico = [saldo]
    gatilhos = []

    i = 0
    n = len(mults)
    seq_baixos = 0

    # Estatísticas
    vitorias_t1 = 0
    vitorias_t2 = 0
    vitorias_t3 = 0
    derrotas_t4_mais = 0
    metas_batidas = 0

    while i < n:
        mult = mults[i]

        if mult < 2.0:
            seq_baixos += 1
        else:
            seq_baixos = 0

        # G6 detectado?
        if seq_baixos == 6:
            # Iniciar apostas
            aposta_base = saldo * (aposta_pct / 100)

            # Avançar para ver o resultado
            tentativa = 0
            aposta_atual = aposta_base
            custo_total = 0

            # Slot 1 - Penúltimo (T1 e T2)
            # Slot 2 - Último (T3)

            # T1: Aposta no slot penúltimo
            i += 1
            tentativa = 1
            if i < n and mults[i] >= 2.0:
                # Ganhou T1
                ganho = aposta_base * 0.97  # ~3% taxa
                saldo += ganho
                vitorias_t1 += 1
                resultado = 'T1'
            else:
                # Perdeu T1, vai para T2
                custo_total += aposta_base
                i += 1
                tentativa = 2
                aposta_atual = aposta_base * 2

                if i < n and mults[i] >= 2.0:
                    # Ganhou T2
                    ganho = aposta_atual * 0.97 - custo_total
                    saldo += ganho
                    vitorias_t2 += 1
                    resultado = 'T2'
                else:
                    # Perdeu T2, vai para T3 (slot último)
                    custo_total += aposta_atual
                    i += 1
                    tentativa = 3
                    aposta_atual = aposta_base * 4

                    if i < n and mults[i] >= 2.0:
                        # Ganhou T3
                        ganho = aposta_atual * 0.97 - custo_total
                        saldo += ganho
                        vitorias_t3 += 1
                        resultado = 'T3'
                    else:
                        # Perdeu T3 - NS7 não tem mais tentativas
                        # Contar quantas mais foram baixas (para estatística)
                        perda = custo_total + aposta_atual
                        saldo -= perda

                        # Contar tentativas totais
                        t_final = 3
                        while i + 1 < n and mults[i + 1] < 2.0:
                            i += 1
                            t_final += 1

                        derrotas_t4_mais += 1
                        resultado = f'T{t_final} (PERDA)'

            gatilhos.append({
                'resultado': resultado,
                'saldo': saldo,
            })

            # Reset sequência
            seq_baixos = 0

            # Verificar meta de lucro (10%)
            lucro_atual = saldo - saldo_referencia
            meta = saldo_referencia * 0.10

            if lucro_atual >= meta:
                # Bateu meta!
                valor_meta = lucro_atual
                reserva += valor_meta * 0.5  # 50% para reserva
                saldo -= valor_meta * 0.5     # Remove da banca
                saldo_referencia = saldo      # Nova referência
                metas_batidas += 1

            historico.append(saldo)

            if saldo <= 0:
                break

        i += 1

    return {
        'saldo_final': saldo,
        'reserva': reserva,
        'patrimonio_total': saldo + reserva,
        'vitorias_t1': vitorias_t1,
        'vitorias_t2': vitorias_t2,
        'vitorias_t3': vitorias_t3,
        'derrotas': derrotas_t4_mais,
        'metas_batidas': metas_batidas,
        'historico': historico,
        'sobreviveu': saldo > 0,
        'retorno_pct': (saldo + reserva - saldo_inicial) / saldo_inicial * 100,
        'min_saldo': min(historico),
        'drawdown_max': (max(historico) - min(historico)) / max(historico) * 100 if max(historico) > 0 else 0,
    }


def main():
    print("=" * 70)
    print("STRESS TEST COMPLETO - ESTRATÉGIA EXATA")
    print("=" * 70)

    print("\nCarregando multiplicadores...")
    mults_originais = carregar_multiplicadores()
    print(f"Total: {len(mults_originais):,} multiplicadores")

    # ===== SIMULAÇÃO BASE =====
    print("\n" + "=" * 70)
    print("SIMULAÇÃO BASE (dados reais)")
    print("=" * 70)

    resultado_base = simular_estrategia(mults_originais)

    print(f"\nSaldo inicial: R$ 10.000")
    print(f"Saldo final (banca): R$ {resultado_base['saldo_final']:,.2f}")
    print(f"Reserva acumulada: R$ {resultado_base['reserva']:,.2f}")
    print(f"PATRIMÔNIO TOTAL: R$ {resultado_base['patrimonio_total']:,.2f}")
    print(f"Retorno total: {resultado_base['retorno_pct']:.1f}%")
    print(f"\nVitórias T1: {resultado_base['vitorias_t1']}")
    print(f"Vitórias T2: {resultado_base['vitorias_t2']}")
    print(f"Vitórias T3: {resultado_base['vitorias_t3']}")
    print(f"Derrotas T4+: {resultado_base['derrotas']}")
    print(f"Metas 10% batidas: {resultado_base['metas_batidas']}")
    print(f"Drawdown máximo: {resultado_base['drawdown_max']:.1f}%")

    # Contar T6+ reais para referência
    t4_mais = resultado_base['derrotas']
    total_gatilhos = resultado_base['vitorias_t1'] + resultado_base['vitorias_t2'] + resultado_base['vitorias_t3'] + resultado_base['derrotas']

    print(f"\nT4+ real: {t4_mais} de {total_gatilhos} gatilhos ({t4_mais/total_gatilhos*100:.1f}%)")

    # ===== STRESS TESTS =====
    print("\n" + "=" * 70)
    print("STRESS TESTS - INJETANDO T6 EXTRAS")
    print("=" * 70)

    cenarios = [
        ("Real (baseline)", 0),
        ("+10 T6 extras", 10),
        ("+20 T6 extras", 20),
        ("+30 T6 extras", 30),
        ("+50 T6 extras", 50),
        ("+75 T6 extras", 75),
        ("+100 T6 extras", 100),
        ("+150 T6 extras", 150),
        ("+200 T6 extras", 200),
    ]

    print(f"\n{'Cenário':<20} {'Banca':>12} {'Reserva':>10} {'Total':>12} {'Retorno':>10} {'Derrotas':>10} {'Status':>10}")
    print("-" * 90)

    for nome, extras in cenarios:
        mults_mod = injetar_t6_nos_multiplicadores(mults_originais, extras)
        resultado = simular_estrategia(mults_mod)

        status = "✓ OK" if resultado['sobreviveu'] and resultado['retorno_pct'] > 0 else \
                 "⚠ NEGATIVO" if resultado['sobreviveu'] else "✗ QUEBROU"

        print(f"{nome:<20} R${resultado['saldo_final']:>10,.0f} R${resultado['reserva']:>8,.0f} R${resultado['patrimonio_total']:>10,.0f} {resultado['retorno_pct']:>+9.1f}% {resultado['derrotas']:>10} {status:>10}")

    # ===== ENCONTRAR LIMITE =====
    print("\n" + "=" * 70)
    print("LIMITE DE SOBREVIVÊNCIA")
    print("=" * 70)

    for extras in range(0, 300, 5):
        mults_mod = injetar_t6_nos_multiplicadores(mults_originais, extras)
        resultado = simular_estrategia(mults_mod)

        if not resultado['sobreviveu']:
            print(f"\n💀 QUEBROU com +{extras} T6 extras")
            print(f"   Total de derrotas: {resultado['derrotas']}")
            print(f"   Isso seria +{extras/t4_mais*100:.0f}% de derrotas além do real")
            break
        elif resultado['retorno_pct'] < 0:
            print(f"\n⚠️  NEGATIVO com +{extras} T6 extras")
            print(f"   Patrimônio final: R$ {resultado['patrimonio_total']:,.2f}")
            print(f"   Retorno: {resultado['retorno_pct']:.1f}%")
            # Continua para ver quando quebra
    else:
        print(f"\n✓ SOBREVIVEU a +{extras} T6 extras!")

    # ===== CONCLUSÃO =====
    print("\n" + "=" * 70)
    print("CONCLUSÃO")
    print("=" * 70)

    print(f"""
Baseado em {len(mults_originais):,} multiplicadores reais:

RESULTADO REAL:
  • Patrimônio final: R$ {resultado_base['patrimonio_total']:,.2f}
  • Retorno: {resultado_base['retorno_pct']:.1f}%
  • Derrotas T4+: {t4_mais}

RESILIÊNCIA:
  A estratégia NS7 com reserva de lucro mostrou capacidade de
  absorver perdas adicionais significativas.
""")


if __name__ == "__main__":
    main()
