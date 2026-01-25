#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANALISE DO PADRÃO DE PERIGO

Descoberta: T5+ vem após sequências de T1 fáceis + T3 + ausência de T4

Vamos quantificar:
1. Quantos T1 consecutivos antes de T5+?
2. Após quantos T1 o risco aumenta?
3. O papel do T3 no padrão
4. Score de risco baseado nos últimos resultados
"""

import re
import sqlite3
import os
from datetime import datetime
import statistics
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def extrair_multiplicadores_log(filepath):
    dados = []
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Rodada salva: ([\d.]+)x'
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for linha in f:
            match = re.search(pattern, linha)
            if match:
                try:
                    timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    mult = float(match.group(2))
                    dados.append((timestamp, mult))
                except:
                    pass
    return dados


def extrair_multiplicadores_db(db_path):
    dados = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT timestamp, multiplier FROM rounds WHERE multiplier IS NOT NULL ORDER BY id')
        for row in cursor.fetchall():
            try:
                if isinstance(row[0], str):
                    timestamp = datetime.strptime(row[0][:19], '%Y-%m-%d %H:%M:%S')
                else:
                    timestamp = row[0]
                mult = float(row[1])
                dados.append((timestamp, mult))
            except:
                pass
        conn.close()
    except Exception as e:
        print(f"Erro ao ler DB: {e}")
    return dados


def carregar_dados():
    dados_total = []

    arquivo1 = os.path.join(BASE_DIR, '16.10.25--27.11.25.txt')
    if os.path.exists(arquivo1):
        dados_total.extend(extrair_multiplicadores_log(arquivo1))

    arquivo2 = os.path.join(BASE_DIR, '28.11.25--15.12.25.txt')
    if os.path.exists(arquivo2):
        dados_total.extend(extrair_multiplicadores_log(arquivo2))

    db_path = os.path.join(BASE_DIR, 'database', 'rounds.db')
    if os.path.exists(db_path):
        dados_total.extend(extrair_multiplicadores_db(db_path))

    dados_total.sort(key=lambda x: x[0])

    dados_unicos = []
    ultimo_ts = None
    for ts, mult in dados_total:
        if ts != ultimo_ts:
            dados_unicos.append((ts, mult))
            ultimo_ts = ts

    return dados_unicos


def simular_estrategia(mults):
    """Simula a estratégia G6 e retorna os resultados"""
    resultados = []
    i = 0
    n = len(mults)

    while i < n - 15:
        seq_baixos = 0
        while i < n and seq_baixos < 6:
            if mults[i] < 2.0:
                seq_baixos += 1
            else:
                seq_baixos = 0
            i += 1

        if seq_baixos >= 6 and i < n - 10:
            inicio_g6 = i - 6
            tentativa = 0
            while i < n and mults[i] < 2.0:
                tentativa += 1
                i += 1

            if i < n:
                resultados.append({
                    'idx': inicio_g6,
                    'tentativa': tentativa + 1,
                })

    return resultados


def contar_t1_consecutivos_antes(resultados, idx):
    """Conta quantos T1 consecutivos vieram antes do índice"""
    count = 0
    for i in range(idx - 1, -1, -1):
        if resultados[i]['tentativa'] == 1:
            count += 1
        else:
            break
    return count


def contar_t1_em_janela(resultados, idx, janela=10):
    """Conta T1s nos últimos 'janela' gatilhos"""
    inicio = max(0, idx - janela)
    return sum(1 for i in range(inicio, idx) if resultados[i]['tentativa'] == 1)


def tem_t3_em_janela(resultados, idx, janela=5):
    """Verifica se tem T3 nos últimos 'janela' gatilhos"""
    inicio = max(0, idx - janela)
    return any(resultados[i]['tentativa'] == 3 for i in range(inicio, idx))


def tem_t4_em_janela(resultados, idx, janela=10):
    """Verifica se tem T4 nos últimos 'janela' gatilhos"""
    inicio = max(0, idx - janela)
    return any(resultados[i]['tentativa'] == 4 for i in range(inicio, idx))


def main():
    print("=" * 70)
    print("ANALISE DO PADRÃO DE PERIGO")
    print("=" * 70)

    print("\nCarregando dados...")
    dados = carregar_dados()
    mults = [m for _, m in dados]
    print(f"Total: {len(mults)} rodadas")

    resultados = simular_estrategia(mults)
    print(f"Total de gatilhos: {len(resultados)}")

    # Identificar T5+
    indices_perigo = [i for i, r in enumerate(resultados) if r['tentativa'] >= 5]
    print(f"Casos T5+: {len(indices_perigo)}")

    # ===== ANÁLISE DE T1 CONSECUTIVOS =====
    print("\n" + "=" * 70)
    print("T1 CONSECUTIVOS ANTES DE T5+")
    print("=" * 70)

    t1_consec_antes_perigo = []
    for idx in indices_perigo:
        if idx > 0:
            count = contar_t1_consecutivos_antes(resultados, idx)
            t1_consec_antes_perigo.append(count)

    print("\nQuantos T1 consecutivos vieram antes de T5+?")
    dist = Counter(t1_consec_antes_perigo)
    for n in sorted(dist.keys()):
        pct = dist[n] / len(t1_consec_antes_perigo) * 100
        barra = "█" * int(pct / 2)
        print(f"  {n} T1s: {dist[n]:>3} ({pct:>5.1f}%) {barra}")

    if t1_consec_antes_perigo:
        print(f"\nMédia de T1 consecutivos antes de T5+: {statistics.mean(t1_consec_antes_perigo):.1f}")

    # ===== RISCO POR QUANTIDADE DE T1 =====
    print("\n" + "=" * 70)
    print("RISCO APÓS N T1 CONSECUTIVOS")
    print("=" * 70)

    print("\nApós quantos T1 consecutivos, qual o risco de T5+?")

    for n_t1 in range(0, 8):
        # Contar quantas vezes tivemos N T1 consecutivos
        ocorrencias = 0
        virou_perigo = 0

        for i in range(1, len(resultados)):
            t1_antes = contar_t1_consecutivos_antes(resultados, i)
            if t1_antes == n_t1:
                ocorrencias += 1
                if resultados[i]['tentativa'] >= 5:
                    virou_perigo += 1

        if ocorrencias > 0:
            risco = virou_perigo / ocorrencias * 100
            barra = "█" * int(risco * 2)
            print(f"  Após {n_t1} T1s: {virou_perigo:>3}/{ocorrencias:<4} = {risco:>5.1f}% risco {barra}")

    # ===== PADRÃO COMBINADO: T1 + T3 + sem T4 =====
    print("\n" + "=" * 70)
    print("PADRÃO COMBINADO: Muitos T1 + T3 recente + sem T4")
    print("=" * 70)

    # Definir critérios
    criterios = [
        ("5+ T1 nos últimos 7", lambda i: contar_t1_em_janela(resultados, i, 7) >= 5),
        ("6+ T1 nos últimos 8", lambda i: contar_t1_em_janela(resultados, i, 8) >= 6),
        ("T3 nos últimos 5", lambda i: tem_t3_em_janela(resultados, i, 5)),
        ("Sem T4 nos últimos 10", lambda i: not tem_t4_em_janela(resultados, i, 10)),
        ("5+ T1/7 + T3/5", lambda i: contar_t1_em_janela(resultados, i, 7) >= 5 and tem_t3_em_janela(resultados, i, 5)),
        ("5+ T1/7 + sem T4/10", lambda i: contar_t1_em_janela(resultados, i, 7) >= 5 and not tem_t4_em_janela(resultados, i, 10)),
        ("COMBO: 5+ T1/7 + T3/5 + sem T4/10", lambda i: contar_t1_em_janela(resultados, i, 7) >= 5 and tem_t3_em_janela(resultados, i, 5) and not tem_t4_em_janela(resultados, i, 10)),
    ]

    print("\nRisco de T5+ por critério:\n")
    print(f"{'Critério':<35} {'Ocorr':>6} {'T5+':>5} {'Risco':>7}")
    print("-" * 60)

    for nome, func in criterios:
        ocorrencias = 0
        perigos = 0

        for i in range(10, len(resultados)):
            if func(i):
                ocorrencias += 1
                if resultados[i]['tentativa'] >= 5:
                    perigos += 1

        if ocorrencias > 0:
            risco = perigos / ocorrencias * 100
            print(f"{nome:<35} {ocorrencias:>6} {perigos:>5} {risco:>6.1f}%")

    # ===== SCORE DE RISCO =====
    print("\n" + "=" * 70)
    print("SCORE DE RISCO")
    print("=" * 70)

    print("\nCriando um score baseado nos últimos resultados...")

    def calcular_score(resultados, idx, janela=10):
        """
        Score de risco baseado nos padrões identificados
        """
        if idx < janela:
            return 0

        score = 0
        ultimos = [resultados[i]['tentativa'] for i in range(idx - janela, idx)]

        # Muitos T1 aumenta risco
        t1_count = sum(1 for t in ultimos if t == 1)
        score += t1_count * 1.5

        # T3 recente aumenta risco
        t3_recente = sum(1 for t in ultimos[-5:] if t == 3)
        score += t3_recente * 2

        # T4 recente DIMINUI risco
        t4_recente = sum(1 for t in ultimos if t == 4)
        score -= t4_recente * 3

        # T2 em quantidade normal não afeta muito
        t2_count = sum(1 for t in ultimos if t == 2)
        if t2_count < 2:
            score += 1  # Poucos T2 = mais risco

        return max(0, score)

    # Calcular score para todos os pontos
    scores_perigo = []
    scores_normal = []

    for i in range(10, len(resultados)):
        score = calcular_score(resultados, i)
        if resultados[i]['tentativa'] >= 5:
            scores_perigo.append(score)
        else:
            scores_normal.append(score)

    print(f"\nScore médio antes de T5+: {statistics.mean(scores_perigo):.1f}")
    print(f"Score médio em casos normais: {statistics.mean(scores_normal):.1f}")

    # Distribuição de scores
    print("\nDistribuição de scores pré-T5+:")
    dist_perigo = Counter([int(s) for s in scores_perigo])
    for s in sorted(dist_perigo.keys()):
        pct = dist_perigo[s] / len(scores_perigo) * 100
        print(f"  Score {s:>2}: {dist_perigo[s]:>3} ({pct:>5.1f}%)")

    # Threshold de alerta
    print("\n" + "=" * 70)
    print("THRESHOLD DE ALERTA")
    print("=" * 70)

    print("\nSe usarmos diferentes thresholds de score:")

    for threshold in [8, 10, 12, 14]:
        alertas_total = sum(1 for s in scores_perigo + scores_normal if s >= threshold)
        alertas_corretos = sum(1 for s in scores_perigo if s >= threshold)

        if alertas_total > 0:
            precisao = alertas_corretos / alertas_total * 100
            cobertura = alertas_corretos / len(scores_perigo) * 100

            print(f"\n  Score >= {threshold}:")
            print(f"    Alertas disparados: {alertas_total}")
            print(f"    T5+ capturados: {alertas_corretos}/{len(scores_perigo)}")
            print(f"    Precisão: {precisao:.1f}%")
            print(f"    Cobertura: {cobertura:.1f}%")

    # ===== EXEMPLOS CONCRETOS =====
    print("\n" + "=" * 70)
    print("EXEMPLOS: Últimos 10 gatilhos antes de cada T5+")
    print("=" * 70)

    for idx in indices_perigo[:15]:
        if idx >= 10:
            ultimos = [resultados[i]['tentativa'] for i in range(idx - 10, idx)]
            score = calcular_score(resultados, idx)
            seq = '-'.join(f'T{t}' for t in ultimos)
            t_final = resultados[idx]['tentativa']
            print(f"  {seq} → T{t_final}  (score: {score:.0f})")

    # ===== CONCLUSÃO =====
    print("\n" + "=" * 70)
    print("CONCLUSÃO")
    print("=" * 70)

    print(f"""
PADRÃO DE PERIGO IDENTIFICADO:

1. Muitos T1 consecutivos ou na janela recente
2. Presença de T3 nos últimos 5 gatilhos
3. Ausência de T4 nos últimos 10 gatilhos

SCORE DE RISCO:
- Score >= 10: Atenção moderada
- Score >= 12: Atenção alta
- Score >= 14: Perigo iminente

FÓRMULA DO SCORE:
  score = (T1 * 1.5) + (T3_recente * 2) - (T4 * 3)
  Se poucos T2: score += 1
""")


if __name__ == "__main__":
    main()
