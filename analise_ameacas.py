#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANALISE DE AMEAÇAS - Identificar regimes perigosos

Foco: Quando o jogo está em estado perigoso?
- Alto % de baixos (>60%)
- MaxSeq alto (>=8, ou seja, T3+)
- Alta frequência de G6
"""

import re
import sqlite3
import os
from datetime import datetime
import statistics

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

    # Remover duplicatas
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
            if len(sessao_atual) >= 50:
                sessoes.append(sessao_atual)
            sessao_atual = [dados[i]]
        else:
            sessao_atual.append(dados[i])

    if len(sessao_atual) >= 50:
        sessoes.append(sessao_atual)

    return sessoes


def analisar_janela(mults):
    """Analisa uma janela de multiplicadores"""
    n = len(mults)
    baixos = sum(1 for m in mults if m < 2.0)
    pct_baixos = baixos / n

    # Encontrar max sequência de baixos
    max_seq = 0
    seq_atual = 0
    g6_count = 0

    for m in mults:
        if m < 2.0:
            seq_atual += 1
            max_seq = max(max_seq, seq_atual)
        else:
            if seq_atual >= 6:
                g6_count += 1
            seq_atual = 0

    return {
        'pct_baixos': pct_baixos,
        'max_seq': max_seq,
        'g6_count': g6_count,
    }


def detectar_zonas_perigo(sessao, janela=50):
    """
    Detecta zonas de perigo numa sessão.

    Perigo = janela com:
    - pct_baixos > 60% OU
    - max_seq >= 8 (chegou a T3+) OU
    - g6_count >= 2 (múltiplos gatilhos)
    """
    mults = [m for _, m in sessao]
    n = len(mults)

    zonas_perigo = []
    em_perigo = False
    inicio_perigo = None

    for i in range(0, n - janela, janela // 2):
        janela_mults = mults[i:i+janela]
        stats = analisar_janela(janela_mults)

        # Critérios de perigo
        perigo = (
            stats['pct_baixos'] > 0.60 or
            stats['max_seq'] >= 8 or
            stats['g6_count'] >= 2
        )

        if perigo and not em_perigo:
            # Entrando em zona de perigo
            em_perigo = True
            inicio_perigo = i
        elif not perigo and em_perigo:
            # Saindo da zona de perigo
            em_perigo = False
            zonas_perigo.append({
                'inicio_idx': inicio_perigo,
                'fim_idx': i,
                'inicio_ts': sessao[inicio_perigo][0],
                'fim_ts': sessao[i][0],
                'duracao': i - inicio_perigo,
            })

    # Se terminou em perigo
    if em_perigo:
        zonas_perigo.append({
            'inicio_idx': inicio_perigo,
            'fim_idx': n,
            'inicio_ts': sessao[inicio_perigo][0],
            'fim_ts': sessao[-1][0],
            'duracao': n - inicio_perigo,
        })

    return zonas_perigo


def analisar_zona_perigo(sessao, zona):
    """Analisa detalhadamente uma zona de perigo"""
    inicio = zona['inicio_idx']
    fim = zona['fim_idx']
    mults = [m for _, m in sessao[inicio:fim]]

    # Estatísticas
    pct_baixos = sum(1 for m in mults if m < 2.0) / len(mults)
    media = statistics.mean(mults)

    # Max seq e gatilhos
    max_seq = 0
    seq_atual = 0
    g6_count = 0
    g8_count = 0

    for m in mults:
        if m < 2.0:
            seq_atual += 1
            max_seq = max(max_seq, seq_atual)
        else:
            if seq_atual >= 6:
                g6_count += 1
            if seq_atual >= 8:
                g8_count += 1
            seq_atual = 0

    # Tentativa máxima (MaxSeq - 5 = tentativa)
    max_tentativa = max(0, max_seq - 5)

    return {
        'duracao': fim - inicio,
        'pct_baixos': pct_baixos * 100,
        'media': media,
        'max_seq': max_seq,
        'max_tentativa': max_tentativa,
        'g6_count': g6_count,
        'g8_count': g8_count,
    }


def main():
    print("=" * 70)
    print("ANALISE DE AMEAÇAS - ZONAS DE PERIGO")
    print("=" * 70)

    print("\nCarregando dados...")
    dados = carregar_dados()
    print(f"Total: {len(dados)} rodadas")

    sessoes = segmentar_sessoes(dados)
    print(f"Sessões contínuas: {len(sessoes)}")

    # Detectar zonas de perigo em todas as sessões
    todas_zonas = []

    for idx, sessao in enumerate(sessoes):
        if len(sessao) < 100:
            continue
        zonas = detectar_zonas_perigo(sessao, janela=50)
        for z in zonas:
            z['sessao'] = idx
            z['analise'] = analisar_zona_perigo(sessao, z)
            todas_zonas.append(z)

    print(f"\nZonas de perigo detectadas: {len(todas_zonas)}")

    # ===== ESTATÍSTICAS DAS ZONAS =====
    print("\n" + "=" * 70)
    print("ESTATÍSTICAS DAS ZONAS DE PERIGO")
    print("=" * 70)

    duracoes = [z['duracao'] for z in todas_zonas]
    print(f"\nDuração média: {statistics.mean(duracoes):.0f} rodadas")
    print(f"Duração mínima: {min(duracoes)} rodadas")
    print(f"Duração máxima: {max(duracoes)} rodadas")

    # Por max_tentativa
    por_tentativa = {}
    for z in todas_zonas:
        t = z['analise']['max_tentativa']
        if t not in por_tentativa:
            por_tentativa[t] = []
        por_tentativa[t].append(z)

    print("\nZonas por tentativa máxima alcançada:")
    for t in sorted(por_tentativa.keys()):
        zonas = por_tentativa[t]
        print(f"  T{t}: {len(zonas)} zonas")

    # ===== ZONAS MAIS PERIGOSAS =====
    print("\n" + "=" * 70)
    print("TOP 20 ZONAS MAIS PERIGOSAS (por MaxSeq)")
    print("=" * 70)

    # Ordenar por max_seq
    todas_zonas.sort(key=lambda z: z['analise']['max_seq'], reverse=True)

    print(f"\n{'Data/Hora':<16} {'Duração':>8} {'%Baixos':>8} {'MaxSeq':>7} {'T':>3} {'G6':>4} {'G8':>4}")
    print("-" * 60)

    for z in todas_zonas[:20]:
        a = z['analise']
        print(f"{z['inicio_ts'].strftime('%m/%d %H:%M'):<16} {a['duracao']:>8} {a['pct_baixos']:>7.0f}% {a['max_seq']:>7} T{a['max_tentativa']:>2} {a['g6_count']:>4} {a['g8_count']:>4}")

    # ===== PADRÃO TEMPORAL =====
    print("\n" + "=" * 70)
    print("PADRÃO TEMPORAL - Quando as ameaças aparecem?")
    print("=" * 70)

    # Por hora do dia
    por_hora = {}
    for z in todas_zonas:
        hora = z['inicio_ts'].hour
        if hora not in por_hora:
            por_hora[hora] = []
        por_hora[hora].append(z)

    print("\nZonas de perigo por hora do dia:")
    for hora in sorted(por_hora.keys()):
        n = len(por_hora[hora])
        barra = "█" * (n // 3)
        print(f"  {hora:02d}h: {n:>3} {barra}")

    # Zonas extremas (T4+)
    zonas_extremas = [z for z in todas_zonas if z['analise']['max_tentativa'] >= 4]

    if zonas_extremas:
        print(f"\n" + "=" * 70)
        print(f"ZONAS EXTREMAS (T4+): {len(zonas_extremas)}")
        print("=" * 70)

        print(f"\n{'Data/Hora':<16} {'Duração':>8} {'%Baixos':>8} {'MaxSeq':>7} {'T':>3}")
        print("-" * 50)

        for z in zonas_extremas:
            a = z['analise']
            print(f"{z['inicio_ts'].strftime('%m/%d %H:%M'):<16} {a['duracao']:>8} {a['pct_baixos']:>7.0f}% {a['max_seq']:>7} T{a['max_tentativa']:>2}")

    # ===== CONCLUSÃO =====
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)

    total_rodadas = sum(len(s) for s in sessoes)
    rodadas_perigo = sum(z['duracao'] for z in todas_zonas)
    pct_perigo = rodadas_perigo / total_rodadas * 100

    print(f"""
Total de rodadas: {total_rodadas:,}
Rodadas em zona de perigo: {rodadas_perigo:,} ({pct_perigo:.1f}%)
Zonas de perigo: {len(todas_zonas)}
Zonas extremas (T4+): {len(zonas_extremas)}
""")


if __name__ == "__main__":
    main()
