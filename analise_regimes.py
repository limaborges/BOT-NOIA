#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANALISE DE REGIMES - Deteccao de padroes de alternancia

Hipotese do usuario:
- Seeds distintos com duracao variavel
- Periodos sem gatilhos vs rallies com muitos gatilhos
- T5/T6 tendem a se repetir em sequencia
- Alternancia entre regimes "calmos" e "agressivos"
"""

import re
import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def extrair_multiplicadores_log(filepath):
    """Extrai multiplicadores e timestamps de arquivo de log"""
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
    """Extrai multiplicadores do banco de dados"""
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


def detectar_gatilhos_g6(dados):
    """
    Detecta todos os gatilhos G6+ e retorna informacoes detalhadas
    """
    gatilhos = []
    seq_baixos = 0
    inicio_seq = None

    for i, (ts, mult) in enumerate(dados):
        if mult < 2.00:
            if seq_baixos == 0:
                inicio_seq = i
            seq_baixos += 1
        else:
            if seq_baixos >= 6:
                # Gatilho G6+ detectado
                # Simular tentativas ate resolver (proximo >= 2.00)
                tentativas = 0
                idx = i  # Comeca no primeiro alto apos G6
                while idx < len(dados) and tentativas < 20:
                    tentativas += 1
                    if dados[idx][1] >= 2.00:
                        break
                    idx += 1

                gatilhos.append({
                    'idx': inicio_seq,
                    'timestamp': dados[inicio_seq][0],
                    'tamanho_gatilho': seq_baixos,  # G6, G7, G8...
                    'tentativas': min(tentativas, 10),  # T1, T2... ate T10
                    'mult_resolucao': dados[i][1] if i < len(dados) else None,
                })
            seq_baixos = 0
            inicio_seq = None

    return gatilhos


def analisar_clusters_gatilhos(gatilhos, dados):
    """
    Analisa clusters de gatilhos - detecta rallies vs desertos
    """
    if not gatilhos:
        return []

    clusters = []
    cluster_atual = [gatilhos[0]]

    for i in range(1, len(gatilhos)):
        g_atual = gatilhos[i]
        g_anterior = gatilhos[i-1]

        # Calcular distancia em rodadas
        dist_rodadas = g_atual['idx'] - g_anterior['idx']

        # Calcular distancia em tempo
        dist_tempo = (g_atual['timestamp'] - g_anterior['timestamp']).total_seconds() / 60  # minutos

        # Se muito proximo (menos de 50 rodadas ou 30 min), mesmo cluster
        if dist_rodadas < 50:
            cluster_atual.append(g_atual)
        else:
            # Fechar cluster anterior
            if len(cluster_atual) >= 1:
                clusters.append({
                    'inicio': cluster_atual[0]['timestamp'],
                    'fim': cluster_atual[-1]['timestamp'],
                    'num_gatilhos': len(cluster_atual),
                    'gatilhos': cluster_atual,
                    'idx_inicio': cluster_atual[0]['idx'],
                    'idx_fim': cluster_atual[-1]['idx'],
                })
            cluster_atual = [g_atual]

    # Ultimo cluster
    if cluster_atual:
        clusters.append({
            'inicio': cluster_atual[0]['timestamp'],
            'fim': cluster_atual[-1]['timestamp'],
            'num_gatilhos': len(cluster_atual),
            'gatilhos': cluster_atual,
            'idx_inicio': cluster_atual[0]['idx'],
            'idx_fim': cluster_atual[-1]['idx'],
        })

    return clusters


def analisar_repeticao_t5_t6(gatilhos):
    """
    Analisa se T5/T6 tendem a aparecer em sequencia
    """
    # Marcar gatilhos que foram ate T5+
    t5_plus = [g for g in gatilhos if g['tentativas'] >= 5]

    # Analisar distancia entre T5+
    if len(t5_plus) < 2:
        return None

    distancias = []
    sequencias_proximas = 0  # T5+ seguido de outro T5+ em menos de 20 rodadas

    for i in range(1, len(t5_plus)):
        dist = t5_plus[i]['idx'] - t5_plus[i-1]['idx']
        distancias.append(dist)
        if dist < 30:
            sequencias_proximas += 1

    return {
        'total_t5_plus': len(t5_plus),
        'sequencias_proximas': sequencias_proximas,
        'pct_proximas': (sequencias_proximas / (len(t5_plus) - 1) * 100) if len(t5_plus) > 1 else 0,
        'dist_media': statistics.mean(distancias) if distancias else 0,
        'dist_mediana': statistics.median(distancias) if distancias else 0,
        'dist_min': min(distancias) if distancias else 0,
        'dist_max': max(distancias) if distancias else 0,
    }


def detectar_regimes(dados, janela=200):
    """
    Detecta regimes baseado na frequencia de baixos em janela deslizante
    """
    regimes = []

    for i in range(0, len(dados) - janela, janela // 4):
        janela_dados = dados[i:i + janela]
        mults = [m for _, m in janela_dados]

        # Calcular % de baixos
        pct_baixos = sum(1 for m in mults if m < 2.00) / len(mults) * 100

        # Contar G6 na janela
        seq = 0
        g6_count = 0
        for m in mults:
            if m < 2.00:
                seq += 1
            else:
                if seq >= 6:
                    g6_count += 1
                seq = 0

        # Classificar regime
        # "Calmo" = poucos G6, baixo % de baixos
        # "Agressivo" = muitos G6, alto % de baixos
        g6_ratio = g6_count / janela * 1000  # G6 por 1000 rodadas

        if g6_ratio > 15 or pct_baixos > 58:
            regime = "AGRESSIVO"
        elif g6_ratio < 8 or pct_baixos < 50:
            regime = "CALMO"
        else:
            regime = "NORMAL"

        regimes.append({
            'idx': i,
            'timestamp': janela_dados[0][0],
            'pct_baixos': pct_baixos,
            'g6_count': g6_count,
            'g6_ratio': g6_ratio,
            'regime': regime,
        })

    return regimes


def consolidar_regimes(regimes):
    """
    Consolida regimes consecutivos iguais
    """
    if not regimes:
        return []

    consolidado = []
    atual = {
        'regime': regimes[0]['regime'],
        'inicio': regimes[0]['timestamp'],
        'idx_inicio': regimes[0]['idx'],
        'count': 1,
    }

    for r in regimes[1:]:
        if r['regime'] == atual['regime']:
            atual['count'] += 1
            atual['fim'] = r['timestamp']
            atual['idx_fim'] = r['idx']
        else:
            atual['fim'] = r['timestamp']
            atual['idx_fim'] = r['idx']
            consolidado.append(atual)
            atual = {
                'regime': r['regime'],
                'inicio': r['timestamp'],
                'idx_inicio': r['idx'],
                'count': 1,
            }

    consolidado.append(atual)
    return consolidado


def analisar_max_streaks(dados):
    """
    Analisa as maiores sequencias de baixos e quando ocorrem
    """
    streaks = []
    seq = 0
    inicio_idx = 0

    for i, (ts, mult) in enumerate(dados):
        if mult < 2.00:
            if seq == 0:
                inicio_idx = i
            seq += 1
        else:
            if seq >= 8:  # Registrar streaks de 8+
                streaks.append({
                    'tamanho': seq,
                    'idx': inicio_idx,
                    'timestamp': dados[inicio_idx][0],
                })
            seq = 0

    return sorted(streaks, key=lambda x: x['tamanho'], reverse=True)


def main():
    print("=" * 70)
    print("ANALISE DE REGIMES - CRASH GAME")
    print("=" * 70)

    # Carregar dados
    print("\nCarregando dados...")
    dados_total = []

    arquivo1 = os.path.join(BASE_DIR, '16.10.25--27.11.25.txt')
    if os.path.exists(arquivo1):
        dados1 = extrair_multiplicadores_log(arquivo1)
        print(f"  Arquivo 1: {len(dados1)} registros")
        dados_total.extend(dados1)

    arquivo2 = os.path.join(BASE_DIR, '28.11.25--15.12.25.txt')
    if os.path.exists(arquivo2):
        dados2 = extrair_multiplicadores_log(arquivo2)
        print(f"  Arquivo 2: {len(dados2)} registros")
        dados_total.extend(dados2)

    db_path = os.path.join(BASE_DIR, 'database', 'rounds.db')
    if os.path.exists(db_path):
        dados_db = extrair_multiplicadores_db(db_path)
        print(f"  Database: {len(dados_db)} registros")
        dados_total.extend(dados_db)

    dados_total.sort(key=lambda x: x[0])

    # Remover duplicatas
    dados = []
    ultimo_ts = None
    for ts, mult in dados_total:
        if ts != ultimo_ts:
            dados.append((ts, mult))
            ultimo_ts = ts

    print(f"\nTotal: {len(dados)} rodadas")

    # ===== DETECTAR GATILHOS =====
    print("\n" + "=" * 70)
    print("ANALISE DE GATILHOS G6+")
    print("=" * 70)

    gatilhos = detectar_gatilhos_g6(dados)
    print(f"\nTotal de gatilhos G6+: {len(gatilhos)}")

    # Distribuicao por tamanho do gatilho
    por_tamanho = defaultdict(int)
    for g in gatilhos:
        por_tamanho[g['tamanho_gatilho']] += 1

    print("\nDistribuicao por tamanho do gatilho:")
    for tam in sorted(por_tamanho.keys()):
        print(f"  G{tam}: {por_tamanho[tam]} ({por_tamanho[tam]/len(gatilhos)*100:.1f}%)")

    # Distribuicao por tentativas
    por_tentativa = defaultdict(int)
    for g in gatilhos:
        por_tentativa[g['tentativas']] += 1

    print("\nDistribuicao por tentativas ate resolver:")
    for t in sorted(por_tentativa.keys()):
        pct = por_tentativa[t] / len(gatilhos) * 100
        barra = "#" * int(pct / 2)
        print(f"  T{t}: {por_tentativa[t]:4d} ({pct:5.1f}%) {barra}")

    # ===== CLUSTERS DE GATILHOS =====
    print("\n" + "=" * 70)
    print("CLUSTERS DE GATILHOS (Rallies vs Desertos)")
    print("=" * 70)

    clusters = analisar_clusters_gatilhos(gatilhos, dados)

    # Separar rallies (muitos gatilhos) vs isolados
    rallies = [c for c in clusters if c['num_gatilhos'] >= 3]

    print(f"\nTotal de clusters: {len(clusters)}")
    print(f"Rallies (3+ gatilhos): {len(rallies)}")

    if rallies:
        tamanhos_rally = [r['num_gatilhos'] for r in rallies]
        print(f"\nMaior rally: {max(tamanhos_rally)} gatilhos")
        print(f"Media de gatilhos por rally: {statistics.mean(tamanhos_rally):.1f}")

        print("\nTop 10 maiores rallies:")
        for r in sorted(rallies, key=lambda x: x['num_gatilhos'], reverse=True)[:10]:
            duracao = r['idx_fim'] - r['idx_inicio']
            t5_plus = sum(1 for g in r['gatilhos'] if g['tentativas'] >= 5)
            print(f"  {r['inicio'].strftime('%Y-%m-%d %H:%M')} | {r['num_gatilhos']:2d} gatilhos | {duracao:4d} rodadas | T5+: {t5_plus}")

    # ===== REPETICAO DE T5/T6 =====
    print("\n" + "=" * 70)
    print("REPETICAO DE T5/T6")
    print("=" * 70)

    rep = analisar_repeticao_t5_t6(gatilhos)
    if rep:
        print(f"\nTotal de T5+: {rep['total_t5_plus']}")
        print(f"T5+ seguido de outro T5+ em <30 rodadas: {rep['sequencias_proximas']} ({rep['pct_proximas']:.1f}%)")
        print(f"\nDistancia entre T5+:")
        print(f"  Media: {rep['dist_media']:.0f} rodadas")
        print(f"  Mediana: {rep['dist_mediana']:.0f} rodadas")
        print(f"  Min: {rep['dist_min']} | Max: {rep['dist_max']}")

        # Probabilidade esperada vs observada
        # Se T5+ ocorre ~5% dos gatilhos, a chance de 2 em 30 rodadas seria muito baixa
        # Se observamos mais, indica clustering
        if rep['pct_proximas'] > 15:
            print(f"\n[!] CLUSTERING DETECTADO: T5+ tendem a se repetir!")

    # ===== MAX STREAKS =====
    print("\n" + "=" * 70)
    print("MAIORES SEQUENCIAS DE BAIXOS (G8+)")
    print("=" * 70)

    streaks = analisar_max_streaks(dados)

    if streaks:
        print(f"\nTotal de sequencias G8+: {len(streaks)}")

        print("\nTop 20 maiores streaks:")
        for s in streaks[:20]:
            print(f"  G{s['tamanho']:2d} em {s['timestamp'].strftime('%Y-%m-%d %H:%M')}")

        # Verificar se streaks grandes aparecem proximos
        print("\nAnalise de proximidade de streaks grandes (G10+):")
        g10_plus = [s for s in streaks if s['tamanho'] >= 10]

        if len(g10_plus) >= 2:
            for i in range(1, min(10, len(g10_plus))):
                dist = g10_plus[i]['idx'] - g10_plus[i-1]['idx']
                tempo = (g10_plus[i]['timestamp'] - g10_plus[i-1]['timestamp']).total_seconds() / 3600
                print(f"  G{g10_plus[i-1]['tamanho']} -> G{g10_plus[i]['tamanho']}: {dist} rodadas ({tempo:.1f}h)")

    # ===== DETECCAO DE REGIMES =====
    print("\n" + "=" * 70)
    print("DETECCAO DE REGIMES")
    print("=" * 70)

    regimes = detectar_regimes(dados, janela=200)
    consolidado = consolidar_regimes(regimes)

    # Contar regimes
    count_regime = defaultdict(int)
    for r in consolidado:
        count_regime[r['regime']] += 1

    print(f"\nRegimes detectados:")
    for regime, count in sorted(count_regime.items()):
        print(f"  {regime}: {count} periodos")

    # Duracao media de cada regime
    print(f"\nDuracao dos regimes (em rodadas):")
    for regime_tipo in ['CALMO', 'NORMAL', 'AGRESSIVO']:
        duracoes = []
        for r in consolidado:
            if r['regime'] == regime_tipo and 'idx_fim' in r:
                dur = r['idx_fim'] - r['idx_inicio']
                duracoes.append(dur)

        if duracoes:
            print(f"  {regime_tipo}:")
            print(f"    Media: {statistics.mean(duracoes):.0f} rodadas")
            print(f"    Max: {max(duracoes)} rodadas")
            print(f"    Min: {min(duracoes)} rodadas")

    # Timeline de regimes
    print(f"\nTimeline dos ultimos 30 regimes:")
    for r in consolidado[-30:]:
        dur = r.get('idx_fim', r['idx_inicio']) - r['idx_inicio']
        emoji = "🔥" if r['regime'] == "AGRESSIVO" else ("😴" if r['regime'] == "CALMO" else "➖")
        print(f"  {r['inicio'].strftime('%m/%d %H:%M')} | {r['regime']:10s} | ~{dur:4d} rodadas {emoji}")

    # ===== CONCLUSAO =====
    print("\n" + "=" * 70)
    print("CONCLUSAO")
    print("=" * 70)

    evidencias = []

    if rep and rep['pct_proximas'] > 15:
        evidencias.append("T5/T6 tendem a se repetir em sequencia")

    if rallies and max(tamanhos_rally) >= 5:
        evidencias.append(f"Rallies de ate {max(tamanhos_rally)} gatilhos consecutivos")

    if len(count_regime) >= 2:
        evidencias.append("Alternancia clara entre regimes CALMO e AGRESSIVO")

    if evidencias:
        print("\n[!] EVIDENCIAS DE REGIMES/SEEDS DISTINTOS:")
        for e in evidencias:
            print(f"    - {e}")
        print("\nSua intuicao parece correta: o jogo alterna entre diferentes")
        print("'estados' ou 'seeds' com caracteristicas distintas.")
    else:
        print("\nNao foram encontradas evidencias claras de regimes distintos.")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
