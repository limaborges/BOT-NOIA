#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANALISE DE SINAIS - O que denuncia uma sessão ameaçadora?

Busca: Quais padrões ANTECEDEM ou ACOMPANHAM zonas de perigo?
- O que acontece nas 30-50 rodadas ANTES de um G8+?
- Existem assinaturas que denunciam o regime?
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


def encontrar_sequencias_longas(mults, min_seq=8):
    """Encontra todas as sequências de baixos >= min_seq"""
    sequencias = []
    seq_atual = 0
    inicio_seq = 0

    for i, m in enumerate(mults):
        if m < 2.0:
            if seq_atual == 0:
                inicio_seq = i
            seq_atual += 1
        else:
            if seq_atual >= min_seq:
                sequencias.append({
                    'inicio': inicio_seq,
                    'fim': i,
                    'tamanho': seq_atual,
                })
            seq_atual = 0

    return sequencias


def classificar_mult(m):
    """Classifica multiplicador em categorias"""
    if m < 1.5:
        return 'MB'  # Muito baixo
    elif m < 2.0:
        return 'B'   # Baixo
    elif m < 3.0:
        return 'M'   # Médio
    elif m < 5.0:
        return 'A'   # Alto
    elif m < 10.0:
        return 'MA'  # Muito alto
    else:
        return 'E'   # Extremo


def extrair_assinatura(mults, janela=30):
    """Extrai assinatura de uma janela de multiplicadores"""
    if len(mults) < janela:
        return None

    # Usar últimos 'janela' multiplicadores
    ultimos = mults[-janela:]

    # Contagem de categorias
    categorias = [classificar_mult(m) for m in ultimos]
    contagem = Counter(categorias)

    # Estatísticas
    pct_baixos = (contagem.get('MB', 0) + contagem.get('B', 0)) / janela
    pct_extremos = contagem.get('E', 0) / janela

    # Padrões de sequência
    max_seq_baixo = 0
    seq_atual = 0
    for c in categorias:
        if c in ['MB', 'B']:
            seq_atual += 1
            max_seq_baixo = max(max_seq_baixo, seq_atual)
        else:
            seq_atual = 0

    # Alternância (quantas vezes muda de baixo para alto e vice-versa)
    alternancia = 0
    for i in range(1, len(categorias)):
        baixo_antes = categorias[i-1] in ['MB', 'B']
        baixo_depois = categorias[i] in ['MB', 'B']
        if baixo_antes != baixo_depois:
            alternancia += 1

    return {
        'pct_baixos': pct_baixos,
        'pct_muito_baixos': contagem.get('MB', 0) / janela,
        'pct_extremos': pct_extremos,
        'max_seq_baixo': max_seq_baixo,
        'alternancia': alternancia / janela,  # Normalizado
        'media': statistics.mean(ultimos),
        'mediana': statistics.median(ultimos),
        'desvio': statistics.stdev(ultimos) if len(ultimos) > 1 else 0,
    }


def main():
    print("=" * 70)
    print("ANALISE DE SINAIS - O que denuncia o perigo?")
    print("=" * 70)

    print("\nCarregando dados...")
    dados = carregar_dados()
    mults = [m for _, m in dados]
    print(f"Total: {len(mults)} rodadas")

    # ===== ENCONTRAR SEQUÊNCIAS G8+ =====
    print("\n" + "=" * 70)
    print("SEQUÊNCIAS LONGAS (G8+) - Eventos de risco")
    print("=" * 70)

    sequencias = encontrar_sequencias_longas(mults, min_seq=8)
    print(f"\nTotal de sequências G8+: {len(sequencias)}")

    # Agrupar por tamanho
    por_tamanho = {}
    for s in sequencias:
        t = s['tamanho']
        if t not in por_tamanho:
            por_tamanho[t] = 0
        por_tamanho[t] += 1

    print("\nDistribuição:")
    for t in sorted(por_tamanho.keys()):
        print(f"  G{t}: {por_tamanho[t]}")

    # ===== ANALISAR O QUE VEM ANTES =====
    print("\n" + "=" * 70)
    print("O QUE ACONTECE ANTES DE UM G8+?")
    print("=" * 70)

    janela_antes = 30
    assinaturas_antes = []
    assinaturas_normal = []

    for seq in sequencias:
        if seq['inicio'] >= janela_antes:
            antes = mults[seq['inicio'] - janela_antes:seq['inicio']]
            assinatura = extrair_assinatura(antes, janela_antes)
            if assinatura:
                assinatura['tamanho_seq'] = seq['tamanho']
                assinaturas_antes.append(assinatura)

    # Comparar com janelas "normais" (aleatórias sem G8 depois)
    import random
    random.seed(42)

    indices_normais = []
    for _ in range(len(assinaturas_antes) * 3):
        idx = random.randint(janela_antes, len(mults) - 50)
        # Verificar se não tem G8 nas próximas 50 rodadas
        proximas = mults[idx:idx+50]
        max_seq = 0
        seq_at = 0
        for m in proximas:
            if m < 2.0:
                seq_at += 1
                max_seq = max(max_seq, seq_at)
            else:
                seq_at = 0
        if max_seq < 8:
            indices_normais.append(idx)

    for idx in indices_normais[:len(assinaturas_antes)]:
        antes = mults[idx - janela_antes:idx]
        assinatura = extrair_assinatura(antes, janela_antes)
        if assinatura:
            assinaturas_normal.append(assinatura)

    # Comparar médias
    print(f"\nComparando {len(assinaturas_antes)} janelas pré-G8+ vs {len(assinaturas_normal)} janelas normais:\n")

    metricas = ['pct_baixos', 'pct_muito_baixos', 'max_seq_baixo', 'alternancia', 'media', 'mediana']

    print(f"{'Métrica':<18} {'Pré-G8+':>10} {'Normal':>10} {'Diff':>10}")
    print("-" * 50)

    diferencas = {}
    for m in metricas:
        media_antes = statistics.mean([a[m] for a in assinaturas_antes])
        media_normal = statistics.mean([a[m] for a in assinaturas_normal])
        diff = media_antes - media_normal
        diff_pct = (diff / media_normal * 100) if media_normal != 0 else 0
        diferencas[m] = diff_pct

        print(f"{m:<18} {media_antes:>10.3f} {media_normal:>10.3f} {diff_pct:>+9.1f}%")

    # ===== SINAIS DE ALERTA =====
    print("\n" + "=" * 70)
    print("SINAIS DE ALERTA IDENTIFICADOS")
    print("=" * 70)

    sinais = []
    if diferencas['pct_baixos'] > 5:
        sinais.append(f"% de baixos elevado (+{diferencas['pct_baixos']:.0f}%)")
    if diferencas['pct_muito_baixos'] > 5:
        sinais.append(f"% de muito baixos (<1.5x) elevado (+{diferencas['pct_muito_baixos']:.0f}%)")
    if diferencas['max_seq_baixo'] > 10:
        sinais.append(f"Já existem sequências de baixos antes (+{diferencas['max_seq_baixo']:.0f}%)")
    if diferencas['alternancia'] < -5:
        sinais.append(f"Menos alternância (fica mais tempo em baixos)")
    if diferencas['media'] < -5:
        sinais.append(f"Média mais baixa ({diferencas['media']:.0f}%)")

    if sinais:
        print("\n⚠️  Antes de um G8+, observa-se:")
        for s in sinais:
            print(f"   • {s}")
    else:
        print("\nNenhum sinal claro identificado nas últimas 30 rodadas.")

    # ===== ANÁLISE MAIS PROFUNDA: Padrões específicos =====
    print("\n" + "=" * 70)
    print("PADRÕES ESPECÍFICOS PRÉ-G8+")
    print("=" * 70)

    # Olhar os últimos 10 multiplicadores antes do G8+
    print("\nÚltimos 10 multiplicadores antes de cada G8+:")

    padroes_10 = []
    for seq in sequencias[:50]:  # Olhar primeiros 50
        if seq['inicio'] >= 10:
            ultimos_10 = mults[seq['inicio'] - 10:seq['inicio']]
            baixos_10 = sum(1 for m in ultimos_10 if m < 2.0)
            padroes_10.append({
                'baixos': baixos_10,
                'media': statistics.mean(ultimos_10),
                'min': min(ultimos_10),
                'max': max(ultimos_10),
            })

    if padroes_10:
        media_baixos = statistics.mean([p['baixos'] for p in padroes_10])
        media_media = statistics.mean([p['media'] for p in padroes_10])

        print(f"\nNas 10 rodadas antes de G8+:")
        print(f"  Média de baixos: {media_baixos:.1f} (de 10)")
        print(f"  Média dos multiplicadores: {media_media:.2f}x")

        # Distribuição de baixos
        dist_baixos = Counter([p['baixos'] for p in padroes_10])
        print("\n  Distribuição de quantos baixos aparecem:")
        for b in sorted(dist_baixos.keys()):
            pct = dist_baixos[b] / len(padroes_10) * 100
            barra = "█" * int(pct / 5)
            print(f"    {b} baixos: {dist_baixos[b]:>3} ({pct:>5.1f}%) {barra}")

    # ===== G6 QUE VIRAM G8+ =====
    print("\n" + "=" * 70)
    print("G6 QUE EVOLUEM PARA G8+")
    print("=" * 70)

    # Encontrar todos os G6
    todos_g6 = encontrar_sequencias_longas(mults, min_seq=6)
    g6_que_viram_g8 = [s for s in todos_g6 if s['tamanho'] >= 8]
    g6_que_pararam = [s for s in todos_g6 if s['tamanho'] < 8]

    print(f"\nTotal de gatilhos G6+: {len(todos_g6)}")
    print(f"  Pararam em G6/G7: {len(g6_que_pararam)} ({len(g6_que_pararam)/len(todos_g6)*100:.1f}%)")
    print(f"  Foram para G8+: {len(g6_que_viram_g8)} ({len(g6_que_viram_g8)/len(todos_g6)*100:.1f}%)")

    # O que diferencia os que param dos que continuam?
    print("\nO que diferencia os que param (G6/G7) dos que continuam (G8+)?")

    assinaturas_param = []
    assinaturas_continuam = []

    for seq in g6_que_pararam[:200]:
        if seq['inicio'] >= 20:
            antes = mults[seq['inicio'] - 20:seq['inicio']]
            assinatura = extrair_assinatura(antes, 20)
            if assinatura:
                assinaturas_param.append(assinatura)

    for seq in g6_que_viram_g8:
        if seq['inicio'] >= 20:
            antes = mults[seq['inicio'] - 20:seq['inicio']]
            assinatura = extrair_assinatura(antes, 20)
            if assinatura:
                assinaturas_continuam.append(assinatura)

    if assinaturas_param and assinaturas_continuam:
        print(f"\nComparando {len(assinaturas_continuam)} G8+ vs {len(assinaturas_param)} G6/G7:\n")

        print(f"{'Métrica':<18} {'Pré-G8+':>10} {'Pré-G6/G7':>10} {'Diff':>10}")
        print("-" * 50)

        for m in metricas:
            media_cont = statistics.mean([a[m] for a in assinaturas_continuam])
            media_param = statistics.mean([a[m] for a in assinaturas_param])
            diff_pct = ((media_cont - media_param) / media_param * 100) if media_param != 0 else 0

            print(f"{m:<18} {media_cont:>10.3f} {media_param:>10.3f} {diff_pct:>+9.1f}%")


if __name__ == "__main__":
    main()
