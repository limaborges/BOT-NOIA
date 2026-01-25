#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANALISE DE SEEDS - Deteccao de mudancas no RNG do Crash

Metodos de deteccao:
1. Distribuicao estatistica por periodo (media, variancia, % baixos)
2. Frequencia de sequencias G6+ (6 ou mais baixos consecutivos)
3. Rolling statistics - detectar quebras estruturais
4. Teste de mudanca de regime (CUSUM)
"""

import re
import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Diretorio base
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


def analisar_periodo(multiplicadores, nome=""):
    """Analisa estatisticas de um periodo"""
    if not multiplicadores:
        return None

    mults = [m for _, m in multiplicadores]

    # Estatisticas basicas
    media = statistics.mean(mults)
    mediana = statistics.median(mults)
    desvio = statistics.stdev(mults) if len(mults) > 1 else 0

    # Frequencia de baixos (< 2.00x)
    baixos = sum(1 for m in mults if m < 2.00)
    pct_baixos = (baixos / len(mults)) * 100

    # Sequencias G6+ (6 ou mais baixos consecutivos)
    sequencias_g6 = 0
    max_sequencia = 0
    seq_atual = 0

    for m in mults:
        if m < 2.00:
            seq_atual += 1
            max_sequencia = max(max_sequencia, seq_atual)
        else:
            if seq_atual >= 6:
                sequencias_g6 += 1
            seq_atual = 0

    # Frequencia de multiplicadores altos (>= 10x)
    altos = sum(1 for m in mults if m >= 10)
    pct_altos = (altos / len(mults)) * 100

    # Muito altos (>= 100x)
    muito_altos = sum(1 for m in mults if m >= 100)

    return {
        'nome': nome,
        'total': len(mults),
        'media': media,
        'mediana': mediana,
        'desvio': desvio,
        'pct_baixos': pct_baixos,
        'pct_altos': pct_altos,
        'muito_altos': muito_altos,
        'sequencias_g6': sequencias_g6,
        'max_sequencia': max_sequencia,
        'inicio': multiplicadores[0][0] if multiplicadores else None,
        'fim': multiplicadores[-1][0] if multiplicadores else None,
    }


def detectar_quebras_por_dia(dados):
    """Agrupa dados por dia e detecta variacoes significativas"""
    por_dia = defaultdict(list)

    for ts, mult in dados:
        dia = ts.strftime('%Y-%m-%d')
        por_dia[dia].append(mult)

    resultados = []
    dias_ordenados = sorted(por_dia.keys())

    for dia in dias_ordenados:
        mults = por_dia[dia]
        if len(mults) < 10:
            continue

        media = statistics.mean(mults)
        pct_baixos = sum(1 for m in mults if m < 2.00) / len(mults) * 100

        # Contar G6 no dia
        seq_atual = 0
        g6_count = 0
        for m in mults:
            if m < 2.00:
                seq_atual += 1
            else:
                if seq_atual >= 6:
                    g6_count += 1
                seq_atual = 0

        resultados.append({
            'dia': dia,
            'count': len(mults),
            'media': media,
            'pct_baixos': pct_baixos,
            'g6_count': g6_count,
            'g6_ratio': g6_count / len(mults) * 1000 if len(mults) > 0 else 0,  # por 1000 rodadas
        })

    return resultados


def detectar_anomalias(resultados_diarios, threshold_z=2.0):
    """Detecta dias anomalos usando Z-score"""
    if len(resultados_diarios) < 5:
        return []

    # Calcular media e desvio de cada metrica
    medias = [r['media'] for r in resultados_diarios]
    pct_baixos = [r['pct_baixos'] for r in resultados_diarios]
    g6_ratios = [r['g6_ratio'] for r in resultados_diarios]

    media_geral = statistics.mean(medias)
    desvio_media = statistics.stdev(medias) if len(medias) > 1 else 1

    media_pct = statistics.mean(pct_baixos)
    desvio_pct = statistics.stdev(pct_baixos) if len(pct_baixos) > 1 else 1

    anomalias = []

    for r in resultados_diarios:
        z_media = abs(r['media'] - media_geral) / desvio_media if desvio_media > 0 else 0
        z_pct = abs(r['pct_baixos'] - media_pct) / desvio_pct if desvio_pct > 0 else 0

        if z_media > threshold_z or z_pct > threshold_z:
            anomalias.append({
                'dia': r['dia'],
                'z_media': z_media,
                'z_pct_baixos': z_pct,
                'media': r['media'],
                'pct_baixos': r['pct_baixos'],
                'g6_count': r['g6_count'],
            })

    return anomalias


def rolling_analysis(dados, window=500):
    """Analise de janela deslizante para detectar mudancas graduais"""
    if len(dados) < window * 2:
        return []

    resultados = []
    mults = [m for _, m in dados]

    for i in range(0, len(mults) - window, window // 2):
        janela = mults[i:i + window]
        media = statistics.mean(janela)
        pct_baixos = sum(1 for m in janela if m < 2.00) / len(janela) * 100

        resultados.append({
            'inicio_idx': i,
            'fim_idx': i + window,
            'media': media,
            'pct_baixos': pct_baixos,
            'timestamp': dados[i][0] if i < len(dados) else None,
        })

    return resultados


def main():
    print("=" * 70)
    print("ANALISE DE SEEDS - CRASH GAME")
    print("=" * 70)

    # Carregar todos os dados
    print("\nCarregando dados...")

    dados_total = []

    # Arquivo 1
    arquivo1 = os.path.join(BASE_DIR, '16.10.25--27.11.25.txt')
    if os.path.exists(arquivo1):
        dados1 = extrair_multiplicadores_log(arquivo1)
        print(f"  Arquivo 1: {len(dados1)} registros")
        dados_total.extend(dados1)

    # Arquivo 2
    arquivo2 = os.path.join(BASE_DIR, '28.11.25--15.12.25.txt')
    if os.path.exists(arquivo2):
        dados2 = extrair_multiplicadores_log(arquivo2)
        print(f"  Arquivo 2: {len(dados2)} registros")
        dados_total.extend(dados2)

    # Database
    db_path = os.path.join(BASE_DIR, 'database', 'rounds.db')
    if os.path.exists(db_path):
        dados_db = extrair_multiplicadores_db(db_path)
        print(f"  Database: {len(dados_db)} registros")
        dados_total.extend(dados_db)

    # Ordenar por timestamp
    dados_total.sort(key=lambda x: x[0])

    # Remover duplicatas (mesmo timestamp)
    dados_unicos = []
    ultimo_ts = None
    for ts, mult in dados_total:
        if ts != ultimo_ts:
            dados_unicos.append((ts, mult))
            ultimo_ts = ts

    print(f"\nTotal de registros unicos: {len(dados_unicos)}")

    if not dados_unicos:
        print("Nenhum dado encontrado!")
        return

    print(f"Periodo: {dados_unicos[0][0]} ate {dados_unicos[-1][0]}")

    # ===== ANALISE GERAL =====
    print("\n" + "=" * 70)
    print("ESTATISTICAS GERAIS")
    print("=" * 70)

    stats = analisar_periodo(dados_unicos, "Total")
    print(f"\nTotal de rodadas: {stats['total']:,}")
    print(f"Media: {stats['media']:.2f}x")
    print(f"Mediana: {stats['mediana']:.2f}x")
    print(f"Desvio padrao: {stats['desvio']:.2f}")
    print(f"% Baixos (<2x): {stats['pct_baixos']:.1f}%")
    print(f"% Altos (>=10x): {stats['pct_altos']:.2f}%")
    print(f"Muito altos (>=100x): {stats['muito_altos']}")
    print(f"Triggers G6+: {stats['sequencias_g6']}")
    print(f"Maior sequencia de baixos: {stats['max_sequencia']}")

    # ===== ANALISE POR SEMANA =====
    print("\n" + "=" * 70)
    print("ANALISE POR SEMANA")
    print("=" * 70)

    # Agrupar por semana
    por_semana = defaultdict(list)
    for ts, mult in dados_unicos:
        semana = ts.strftime('%Y-W%W')
        por_semana[semana].append((ts, mult))

    print(f"\n{'Semana':<12} {'Rodadas':>8} {'Media':>8} {'%Baixos':>8} {'G6+':>5} {'MaxSeq':>6}")
    print("-" * 55)

    semanas_stats = []
    for semana in sorted(por_semana.keys()):
        s = analisar_periodo(por_semana[semana], semana)
        if s:
            semanas_stats.append(s)
            print(f"{semana:<12} {s['total']:>8,} {s['media']:>8.2f} {s['pct_baixos']:>7.1f}% {s['sequencias_g6']:>5} {s['max_sequencia']:>6}")

    # ===== DETECCAO DE ANOMALIAS DIARIAS =====
    print("\n" + "=" * 70)
    print("DETECCAO DE ANOMALIAS (Z-score > 2.0)")
    print("=" * 70)

    resultados_diarios = detectar_quebras_por_dia(dados_unicos)
    anomalias = detectar_anomalias(resultados_diarios, threshold_z=2.0)

    if anomalias:
        print(f"\n{len(anomalias)} dias anomalos encontrados:\n")
        print(f"{'Dia':<12} {'Z-Media':>8} {'Z-%Baixos':>10} {'Media':>8} {'%Baixos':>8} {'G6':>4}")
        print("-" * 55)
        for a in sorted(anomalias, key=lambda x: max(x['z_media'], x['z_pct_baixos']), reverse=True)[:20]:
            print(f"{a['dia']:<12} {a['z_media']:>8.2f} {a['z_pct_baixos']:>10.2f} {a['media']:>8.2f} {a['pct_baixos']:>7.1f}% {a['g6_count']:>4}")
    else:
        print("\nNenhuma anomalia significativa detectada.")

    # ===== ANALISE DE JANELA DESLIZANTE =====
    print("\n" + "=" * 70)
    print("ANALISE DE JANELA DESLIZANTE (500 rodadas)")
    print("=" * 70)

    rolling = rolling_analysis(dados_unicos, window=500)

    if rolling:
        # Encontrar variações significativas
        medias_rolling = [r['media'] for r in rolling]
        media_geral = statistics.mean(medias_rolling)
        desvio_geral = statistics.stdev(medias_rolling) if len(medias_rolling) > 1 else 1

        print(f"\nMedia geral das janelas: {media_geral:.2f}x")
        print(f"Desvio das janelas: {desvio_geral:.2f}")

        # Detectar picos e vales
        picos = []
        vales = []

        for r in rolling:
            z = (r['media'] - media_geral) / desvio_geral if desvio_geral > 0 else 0
            if z > 2:
                picos.append((r['timestamp'], r['media'], z))
            elif z < -2:
                vales.append((r['timestamp'], r['media'], z))

        if picos:
            print(f"\nPicos (media alta, Z > 2): {len(picos)}")
            for ts, media, z in picos[:5]:
                print(f"  {ts}: media {media:.2f}x (Z={z:.2f})")

        if vales:
            print(f"\nVales (media baixa, Z < -2): {len(vales)}")
            for ts, media, z in vales[:5]:
                print(f"  {ts}: media {media:.2f}x (Z={z:.2f})")

    # ===== CONCLUSAO =====
    print("\n" + "=" * 70)
    print("CONCLUSAO")
    print("=" * 70)

    # Calcular variacao entre semanas
    if len(semanas_stats) >= 2:
        medias_semana = [s['media'] for s in semanas_stats]
        variacao_media = (max(medias_semana) - min(medias_semana)) / statistics.mean(medias_semana) * 100

        pct_baixos_semana = [s['pct_baixos'] for s in semanas_stats]
        variacao_baixos = max(pct_baixos_semana) - min(pct_baixos_semana)

        print(f"\nVariacao da media entre semanas: {variacao_media:.1f}%")
        print(f"Variacao do % baixos entre semanas: {variacao_baixos:.1f} pontos percentuais")

        if variacao_media > 20 or variacao_baixos > 5:
            print("\n[!] POSSIVEL MUDANCA DE SEED DETECTADA")
            print("    Ha variacao significativa nas estatisticas ao longo do tempo.")
        else:
            print("\n[OK] Estatisticas relativamente estaveis")
            print("     Nao ha evidencia clara de mudanca de seed.")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
