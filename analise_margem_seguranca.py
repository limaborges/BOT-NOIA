#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANÁLISE DE MARGEM DE SEGURANÇA

1. Até quantos T1/T3 é seguro antes de esperar T5?
2. T5+ vêm sozinhos ou acompanhados?
3. Análise apenas em sessões contínuas (sem gaps)
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


def segmentar_sessoes(dados, gap_minutos=5):
    """Divide em sessões contínuas"""
    if not dados:
        return []

    sessoes = []
    sessao_atual = [dados[0]]

    for i in range(1, len(dados)):
        gap = (dados[i][0] - dados[i-1][0]).total_seconds() / 60
        if gap > gap_minutos:
            if len(sessao_atual) >= 100:
                sessoes.append(sessao_atual)
            sessao_atual = [dados[i]]
        else:
            sessao_atual.append(dados[i])

    if len(sessao_atual) >= 100:
        sessoes.append(sessao_atual)

    return sessoes


def simular_estrategia_sessao(sessao):
    """Simula estratégia numa sessão contínua"""
    mults = [m for _, m in sessao]
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
                    'timestamp': sessao[inicio_g6][0],
                })

    return resultados


def main():
    print("=" * 70)
    print("ANÁLISE DE MARGEM DE SEGURANÇA")
    print("=" * 70)

    print("\nCarregando dados...")
    dados = carregar_dados()
    print(f"Total: {len(dados)} rodadas")

    # Segmentar em sessões contínuas
    sessoes = segmentar_sessoes(dados, gap_minutos=5)
    print(f"Sessões contínuas (>=100 rodadas): {len(sessoes)}")

    # Simular estratégia em cada sessão
    todas_sessoes_resultados = []
    for sessao in sessoes:
        resultados = simular_estrategia_sessao(sessao)
        if resultados:
            todas_sessoes_resultados.append(resultados)

    print(f"Sessões com gatilhos: {len(todas_sessoes_resultados)}")

    total_gatilhos = sum(len(r) for r in todas_sessoes_resultados)
    print(f"Total de gatilhos: {total_gatilhos}")

    # ===== ANÁLISE 1: MARGEM DE SEGURANÇA =====
    print("\n" + "=" * 70)
    print("1. MARGEM DE SEGURANÇA - Até quantos T1 fáceis?")
    print("=" * 70)

    # Contar T1 acumulados antes de cada T5+ (dentro da sessão)
    t1_antes_perigo = []

    for resultados in todas_sessoes_resultados:
        t1_acumulado = 0
        for i, r in enumerate(resultados):
            if r['tentativa'] == 1:
                t1_acumulado += 1
            else:
                if r['tentativa'] >= 5:
                    t1_antes_perigo.append(t1_acumulado)
                # Reset ou decremento após não-T1
                if r['tentativa'] >= 3:
                    t1_acumulado = max(0, t1_acumulado - 2)
                else:
                    t1_acumulado = max(0, t1_acumulado - 1)

    print("\nT1 acumulados antes de T5+ (com decay após não-T1):")
    dist = Counter(t1_antes_perigo)
    for n in sorted(dist.keys())[:15]:
        pct = dist[n] / len(t1_antes_perigo) * 100
        barra = "█" * int(pct)
        print(f"  {n:>2} T1s: {dist[n]:>3} ({pct:>5.1f}%) {barra}")

    # Calcular risco acumulado
    print("\n" + "-" * 50)
    print("RISCO ACUMULADO por quantidade de T1:")
    print("-" * 50)

    for limite in [3, 4, 5, 6, 7, 8, 10]:
        casos_ate = sum(1 for x in t1_antes_perigo if x <= limite)
        pct = casos_ate / len(t1_antes_perigo) * 100
        print(f"  Até {limite} T1s: {pct:.1f}% dos T5+ já teriam ocorrido")

    # ===== ANÁLISE 2: T5+ VÊM SOZINHOS OU ACOMPANHADOS? =====
    print("\n" + "=" * 70)
    print("2. T5+ VÊM SOZINHOS OU ACOMPANHADOS?")
    print("=" * 70)

    # Analisar clustering de T5+ dentro de cada sessão
    clusters_t5 = []

    for resultados in todas_sessoes_resultados:
        em_cluster = False
        cluster_atual = []

        for i, r in enumerate(resultados):
            if r['tentativa'] >= 5:
                cluster_atual.append(r)
            else:
                if len(cluster_atual) > 0:
                    clusters_t5.append(cluster_atual)
                    cluster_atual = []

        if cluster_atual:
            clusters_t5.append(cluster_atual)

    # Estatísticas de clusters
    tamanhos = [len(c) for c in clusters_t5]
    sozinhos = sum(1 for t in tamanhos if t == 1)
    duplos = sum(1 for t in tamanhos if t == 2)
    triplos_mais = sum(1 for t in tamanhos if t >= 3)

    print(f"\nTotal de 'eventos' T5+: {len(clusters_t5)}")
    print(f"  Sozinhos (1 T5+): {sozinhos} ({sozinhos/len(clusters_t5)*100:.1f}%)")
    print(f"  Duplos (2 T5+): {duplos} ({duplos/len(clusters_t5)*100:.1f}%)")
    print(f"  Triplos+ (3+ T5+): {triplos_mais} ({triplos_mais/len(clusters_t5)*100:.1f}%)")

    # Quantos T5+ vieram em cluster vs sozinhos?
    t5_em_cluster = sum(len(c) for c in clusters_t5 if len(c) >= 2)
    t5_sozinho = sum(1 for c in clusters_t5 if len(c) == 1)
    total_t5 = t5_em_cluster + t5_sozinho

    print(f"\nDos {total_t5} T5+ individuais:")
    print(f"  Vieram SOZINHOS: {t5_sozinho} ({t5_sozinho/total_t5*100:.1f}%)")
    print(f"  Vieram ACOMPANHADOS: {t5_em_cluster} ({t5_em_cluster/total_t5*100:.1f}%)")

    # Distância entre T5+ consecutivos (em gatilhos)
    print("\n" + "-" * 50)
    print("Distância entre T5+ consecutivos (em gatilhos):")
    print("-" * 50)

    distancias = []
    for resultados in todas_sessoes_resultados:
        ultimo_t5_idx = None
        for i, r in enumerate(resultados):
            if r['tentativa'] >= 5:
                if ultimo_t5_idx is not None:
                    dist = i - ultimo_t5_idx
                    distancias.append(dist)
                ultimo_t5_idx = i

    if distancias:
        dist_counter = Counter(distancias)
        print("\nDistância (gatilhos) entre T5+ consecutivos:")
        for d in sorted(dist_counter.keys())[:15]:
            count = dist_counter[d]
            pct = count / len(distancias) * 100
            barra = "█" * int(pct * 2)
            print(f"  {d:>2} gatilhos: {count:>3} ({pct:>5.1f}%) {barra}")

        print(f"\nMédia: {statistics.mean(distancias):.1f} gatilhos")
        print(f"Mediana: {statistics.median(distancias):.0f} gatilhos")

        # Quantos vieram com distância <= 3?
        proximos = sum(1 for d in distancias if d <= 3)
        print(f"\nT5+ que veio logo após outro (<=3 gatilhos): {proximos} ({proximos/len(distancias)*100:.1f}%)")

    # ===== ANÁLISE 3: PADRÃO DENTRO DA SESSÃO =====
    print("\n" + "=" * 70)
    print("3. MOMENTO DO T5+ DENTRO DA SESSÃO")
    print("=" * 70)

    # Quando na sessão o T5+ costuma aparecer?
    posicao_relativa = []

    for resultados in todas_sessoes_resultados:
        n = len(resultados)
        for i, r in enumerate(resultados):
            if r['tentativa'] >= 5:
                pos = i / n  # 0 = início, 1 = fim
                posicao_relativa.append(pos)

    # Dividir em terços
    inicio = sum(1 for p in posicao_relativa if p < 0.33)
    meio = sum(1 for p in posicao_relativa if 0.33 <= p < 0.67)
    fim = sum(1 for p in posicao_relativa if p >= 0.67)

    print(f"\nOnde na sessão o T5+ aparece?")
    print(f"  Início (0-33%): {inicio} ({inicio/len(posicao_relativa)*100:.1f}%)")
    print(f"  Meio (33-67%): {meio} ({meio/len(posicao_relativa)*100:.1f}%)")
    print(f"  Fim (67-100%): {fim} ({fim/len(posicao_relativa)*100:.1f}%)")

    # ===== ANÁLISE 4: APÓS QUANTOS GATILHOS NA SESSÃO? =====
    print("\n" + "-" * 50)
    print("Após quantos gatilhos na sessão vem o primeiro T5+?")
    print("-" * 50)

    primeiro_t5_idx = []
    for resultados in todas_sessoes_resultados:
        for i, r in enumerate(resultados):
            if r['tentativa'] >= 5:
                primeiro_t5_idx.append(i)
                break

    if primeiro_t5_idx:
        print(f"\nPrimeiro T5+ da sessão aparece após:")
        print(f"  Mínimo: {min(primeiro_t5_idx)} gatilhos")
        print(f"  Máximo: {max(primeiro_t5_idx)} gatilhos")
        print(f"  Média: {statistics.mean(primeiro_t5_idx):.1f} gatilhos")
        print(f"  Mediana: {statistics.median(primeiro_t5_idx):.0f} gatilhos")

        # Distribuição
        ranges = [(0, 5), (5, 10), (10, 20), (20, 50), (50, 100)]
        for r_min, r_max in ranges:
            count = sum(1 for x in primeiro_t5_idx if r_min <= x < r_max)
            pct = count / len(primeiro_t5_idx) * 100
            print(f"  {r_min:>3}-{r_max:<3} gatilhos: {count:>3} ({pct:>5.1f}%)")

    # ===== CONCLUSÃO =====
    print("\n" + "=" * 70)
    print("CONCLUSÃO")
    print("=" * 70)

    print(f"""
MARGEM DE SEGURANÇA:
  - Após {sorted(t1_antes_perigo)[int(len(t1_antes_perigo)*0.5)]} T1 acumulados, 50% dos T5+ já ocorreram
  - Após {sorted(t1_antes_perigo)[int(len(t1_antes_perigo)*0.75)]} T1 acumulados, 75% dos T5+ já ocorreram

T5+ VÊM ACOMPANHADOS?
  - {t5_em_cluster/total_t5*100:.0f}% vieram acompanhados de outro T5+ próximo
  - Quando vem um, é bom esperar

MOMENTO NA SESSÃO:
  - Distribuição relativamente uniforme
  - Primeiro T5+ costuma vir após ~{statistics.median(primeiro_t5_idx):.0f} gatilhos
""")


if __name__ == "__main__":
    main()
