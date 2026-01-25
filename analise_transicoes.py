#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANALISE DE TRANSICOES - Detecção de mudanças de regime/seed

Detecta os pontos exatos onde o comportamento do jogo muda,
sem impor janelas de tamanho fixo.
"""

import re
import sqlite3
import os
from datetime import datetime
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


def carregar_todos_dados():
    """Carrega dados de todas as fontes"""
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

    # Ordenar e remover duplicatas
    dados_total.sort(key=lambda x: x[0])
    dados_unicos = []
    ultimo_ts = None
    for ts, mult in dados_total:
        if ts != ultimo_ts:
            dados_unicos.append((ts, mult))
            ultimo_ts = ts

    return dados_unicos


def segmentar_sessoes(dados, gap_minutos=5):
    """
    Divide os dados em sessões contínuas.

    Um gap > gap_minutos indica que o bot estava desligado,
    então iniciamos uma nova sessão.

    Retorna lista de sessões, cada uma sendo lista de (timestamp, mult)
    """
    if not dados:
        return []

    sessoes = []
    sessao_atual = [dados[0]]

    for i in range(1, len(dados)):
        ts_anterior = dados[i-1][0]
        ts_atual = dados[i][0]

        # Calcular gap em minutos
        gap = (ts_atual - ts_anterior).total_seconds() / 60

        if gap > gap_minutos:
            # Gap detectado - salvar sessão atual e iniciar nova
            if len(sessao_atual) >= 50:  # Só salvar se tiver dados suficientes
                sessoes.append(sessao_atual)
            sessao_atual = [dados[i]]
        else:
            sessao_atual.append(dados[i])

    # Última sessão
    if len(sessao_atual) >= 50:
        sessoes.append(sessao_atual)

    return sessoes


def calcular_cusum(valores, target=None):
    """
    CUSUM - Cumulative Sum Control Chart
    Detecta desvios da média esperada
    """
    if target is None:
        target = statistics.mean(valores)

    cusum_pos = [0]
    cusum_neg = [0]

    for v in valores:
        diff = v - target
        cusum_pos.append(max(0, cusum_pos[-1] + diff))
        cusum_neg.append(min(0, cusum_neg[-1] + diff))

    return cusum_pos[1:], cusum_neg[1:]


def detectar_transicoes_cusum(dados, janela_media=50, threshold_mult=3.0):
    """
    Detecta transições usando CUSUM adaptativo

    Usa uma janela móvel para calcular o baseline local,
    e detecta quando o CUSUM excede um threshold.
    """
    mults = [m for _, m in dados]
    n = len(mults)

    # Converter para binário: 1 = baixo (<2x), 0 = alto
    binario = [1 if m < 2.0 else 0 for m in mults]

    # Taxa esperada de baixos (global)
    taxa_global = sum(binario) / len(binario)
    print(f"\nTaxa global de baixos: {taxa_global:.1%}")

    transicoes = []

    # CUSUM para detectar mudanças na taxa de baixos
    cusum = 0
    ultimo_reset = 0

    # Threshold adaptativo baseado no desvio padrão
    std_janela = 50

    for i in range(n):
        # Valor centrado (desvio da média)
        cusum += binario[i] - taxa_global

        # Calcular threshold local
        if i >= std_janela:
            janela = binario[i-std_janela:i]
            std_local = statistics.stdev(janela) if len(set(janela)) > 1 else 0.5
            threshold = threshold_mult * std_local * (i - ultimo_reset) ** 0.5
        else:
            threshold = threshold_mult * 0.5 * (i - ultimo_reset + 1) ** 0.5

        # Detectar transição
        if abs(cusum) > threshold and (i - ultimo_reset) >= 20:
            direcao = "MAIS BAIXOS" if cusum > 0 else "MENOS BAIXOS"
            transicoes.append({
                'idx': i,
                'timestamp': dados[i][0],
                'cusum': cusum,
                'direcao': direcao,
                'duracao_anterior': i - ultimo_reset,
            })
            cusum = 0
            ultimo_reset = i

    return transicoes


def detectar_transicoes_taxa(dados, janela=30, sensibilidade=0.15):
    """
    Detecta transições baseado na taxa de baixos em janela móvel.

    Quando a taxa muda significativamente em relação à janela anterior,
    marca uma transição.
    """
    mults = [m for _, m in dados]
    binario = [1 if m < 2.0 else 0 for m in mults]
    n = len(binario)

    transicoes = []
    ultima_transicao = 0
    taxa_anterior = None

    for i in range(janela, n - janela):
        # Taxa na janela atual
        taxa_atual = sum(binario[i:i+janela]) / janela

        # Taxa na janela anterior
        taxa_antes = sum(binario[i-janela:i]) / janela

        # Detectar mudança significativa
        diff = abs(taxa_atual - taxa_antes)

        if diff > sensibilidade and (i - ultima_transicao) >= janela:
            transicoes.append({
                'idx': i,
                'timestamp': dados[i][0],
                'taxa_antes': taxa_antes,
                'taxa_depois': taxa_atual,
                'diff': diff,
                'duracao_anterior': i - ultima_transicao,
            })
            ultima_transicao = i
            taxa_anterior = taxa_atual

    return transicoes


def caracterizar_segmento(dados, inicio, fim):
    """Cria a 'impressão digital' de um segmento"""
    if fim <= inicio:
        return None

    mults = [m for _, m in dados[inicio:fim]]
    if not mults:
        return None

    n = len(mults)
    baixos = [m for m in mults if m < 2.0]

    # Contar sequências de baixos
    seq_atual = 0
    max_seq = 0
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

    return {
        'inicio_idx': inicio,
        'fim_idx': fim,
        'inicio_ts': dados[inicio][0],
        'fim_ts': dados[fim-1][0],
        'duracao': n,
        'pct_baixos': len(baixos) / n,
        'media': statistics.mean(mults),
        'mediana': statistics.median(mults),
        'desvio': statistics.stdev(mults) if n > 1 else 0,
        'max_seq': max_seq,
        'g6_count': g6_count,
        'g8_count': g8_count,
        'g6_ratio': g6_count / n * 100,
        'altos_10x': sum(1 for m in mults if m >= 10) / n,
        'altos_50x': sum(1 for m in mults if m >= 50) / n,
    }


def distancia_segmentos(seg1, seg2):
    """Calcula a distância (dissimilaridade) entre dois segmentos"""
    # Pesos para cada característica
    pesos = {
        'pct_baixos': 3.0,      # Muito importante
        'g6_ratio': 2.0,        # Importante
        'max_seq': 1.5,         # Moderado
        'media': 1.0,           # Base
        'desvio': 0.5,          # Secundário
        'altos_10x': 1.0,       # Base
    }

    distancia = 0
    for key, peso in pesos.items():
        v1 = seg1.get(key, 0)
        v2 = seg2.get(key, 0)
        # Normalizar pela média
        media = (abs(v1) + abs(v2)) / 2 if (v1 != 0 or v2 != 0) else 1
        diff = abs(v1 - v2) / media if media > 0 else 0
        distancia += peso * diff

    return distancia


def agrupar_segmentos(segmentos, threshold_dist=1.5):
    """Agrupa segmentos similares"""
    n = len(segmentos)
    grupos = [-1] * n  # -1 = não atribuído
    grupo_atual = 0

    for i in range(n):
        if grupos[i] != -1:
            continue

        # Novo grupo
        grupos[i] = grupo_atual

        # Encontrar segmentos similares
        for j in range(i + 1, n):
            if grupos[j] != -1:
                continue

            dist = distancia_segmentos(segmentos[i], segmentos[j])
            if dist < threshold_dist:
                grupos[j] = grupo_atual

        grupo_atual += 1

    return grupos


def main():
    print("=" * 70)
    print("ANALISE DE TRANSICOES - DETECÇÃO DE MUDANÇAS DE REGIME")
    print("=" * 70)

    print("\nCarregando dados...")
    dados = carregar_todos_dados()
    print(f"\nTotal: {len(dados)} rodadas")

    # ===== SEGMENTAR EM SESSÕES CONTÍNUAS =====
    print("\n" + "=" * 70)
    print("SEGMENTAÇÃO EM SESSÕES CONTÍNUAS")
    print("=" * 70)

    sessoes = segmentar_sessoes(dados, gap_minutos=5)
    print(f"\nSessões contínuas encontradas: {len(sessoes)}")

    tamanhos = [len(s) for s in sessoes]
    print(f"Tamanho médio: {statistics.mean(tamanhos):.0f} rodadas")
    print(f"Maior sessão: {max(tamanhos)} rodadas")
    print(f"Menor sessão: {min(tamanhos)} rodadas")

    # Distribuição
    pequenas = sum(1 for t in tamanhos if t < 100)
    medias = sum(1 for t in tamanhos if 100 <= t < 500)
    grandes = sum(1 for t in tamanhos if 500 <= t < 2000)
    enormes = sum(1 for t in tamanhos if t >= 2000)

    print(f"\nDistribuição de tamanhos:")
    print(f"  Pequenas (<100): {pequenas}")
    print(f"  Médias (100-500): {medias}")
    print(f"  Grandes (500-2000): {grandes}")
    print(f"  Enormes (>2000): {enormes}")

    # Só analisar sessões grandes (>= 200 rodadas)
    sessoes_grandes = [s for s in sessoes if len(s) >= 200]
    print(f"\nSessões >= 200 rodadas para análise: {len(sessoes_grandes)}")
    print(f"Total de rodadas nessas sessões: {sum(len(s) for s in sessoes_grandes)}")

    # ===== ANÁLISE POR SESSÃO CONTÍNUA =====
    print("\n" + "=" * 70)
    print("DETECÇÃO DE TRANSIÇÕES (apenas dentro de sessões contínuas)")
    print("=" * 70)

    todas_transicoes = []
    todos_segmentos = []

    for idx_sessao, sessao in enumerate(sessoes_grandes):
        # Detectar transições dentro desta sessão
        transicoes = detectar_transicoes_taxa(sessao, janela=30, sensibilidade=0.15)

        for t in transicoes:
            t['sessao'] = idx_sessao
            todas_transicoes.append(t)

        # Caracterizar segmentos dentro desta sessão
        inicio = 0
        for t in transicoes:
            seg = caracterizar_segmento(sessao, inicio, t['idx'])
            if seg:
                seg['sessao'] = idx_sessao
                todos_segmentos.append(seg)
            inicio = t['idx']

        # Último segmento da sessão
        seg = caracterizar_segmento(sessao, inicio, len(sessao))
        if seg:
            seg['sessao'] = idx_sessao
            todos_segmentos.append(seg)

    print(f"\nTransições detectadas (total): {len(todas_transicoes)}")
    print(f"Segmentos caracterizados: {len(todos_segmentos)}")

    if todas_transicoes:
        duracoes = [t['duracao_anterior'] for t in todas_transicoes if t['duracao_anterior'] > 0]
        if duracoes:
            print(f"\nDuração média dos regimes: {statistics.mean(duracoes):.0f} rodadas")
            print(f"Duração mínima: {min(duracoes)} rodadas")
            print(f"Duração máxima: {max(duracoes)} rodadas")

            # Distribuição de durações
            curtos = sum(1 for d in duracoes if d < 50)
            medios = sum(1 for d in duracoes if 50 <= d < 200)
            longos = sum(1 for d in duracoes if d >= 200)

            print(f"\nDistribuição de durações dos regimes:")
            print(f"  Curtos (<50 rodadas): {curtos} ({curtos/len(duracoes)*100:.1f}%)")
            print(f"  Médios (50-200): {medios} ({medios/len(duracoes)*100:.1f}%)")
            print(f"  Longos (>200): {longos} ({longos/len(duracoes)*100:.1f}%)")

    # ===== CARACTERIZAR E AGRUPAR SEGMENTOS =====
    print("\n" + "=" * 70)
    print("CARACTERIZAÇÃO E AGRUPAMENTO DE SEGMENTOS")
    print("=" * 70)

    if len(todos_segmentos) > 5:
        # Agrupar segmentos similares
        grupos = agrupar_segmentos(todos_segmentos, threshold_dist=1.2)
        n_grupos = max(grupos) + 1

        print(f"\nGrupos distintos encontrados: {n_grupos}")

        # Estatísticas por grupo
        print("\nCaracterísticas médias por grupo:")
        print(f"{'Grupo':<6} {'N':>4} {'%Baixos':>8} {'Media':>7} {'MaxSeq':>7} {'G6/100':>7} {'Duração':>8}")
        print("-" * 55)

        grupos_info = []
        for g in range(n_grupos):
            segs_grupo = [todos_segmentos[i] for i in range(len(todos_segmentos)) if grupos[i] == g]
            if not segs_grupo:
                continue

            pct_medio = statistics.mean([s['pct_baixos'] for s in segs_grupo]) * 100
            media_media = statistics.mean([s['media'] for s in segs_grupo])
            max_seq_medio = statistics.mean([s['max_seq'] for s in segs_grupo])
            g6_ratio_medio = statistics.mean([s['g6_ratio'] for s in segs_grupo])
            duracao_media = statistics.mean([s['duracao'] for s in segs_grupo])

            grupos_info.append({
                'grupo': g,
                'n': len(segs_grupo),
                'pct_baixos': pct_medio,
                'media': media_media,
                'max_seq': max_seq_medio,
                'g6_ratio': g6_ratio_medio,
                'duracao': duracao_media,
            })

        # Ordenar por frequência
        grupos_info.sort(key=lambda x: x['n'], reverse=True)

        for info in grupos_info[:10]:
            print(f"  {info['grupo']:<4} {info['n']:>4} {info['pct_baixos']:>7.1f}% {info['media']:>7.2f} {info['max_seq']:>7.1f} {info['g6_ratio']:>7.2f} {info['duracao']:>7.0f}")

        # Verificar se grupos se repetem ao longo do tempo
        print("\n" + "=" * 70)
        print("PADRÃO TEMPORAL DOS GRUPOS")
        print("=" * 70)

        print("\nOs mesmos grupos aparecem em sessões diferentes?")

        # Para cada grupo frequente, ver em quantas sessões aparece
        for info in grupos_info[:5]:
            g = info['grupo']
            segs_do_grupo = [todos_segmentos[i] for i in range(len(todos_segmentos)) if grupos[i] == g]
            sessoes_do_grupo = set(s['sessao'] for s in segs_do_grupo)

            print(f"\nGrupo {g}: {info['n']} ocorrências em {len(sessoes_do_grupo)} sessões diferentes")
            print(f"  Características: {info['pct_baixos']:.0f}% baixos, média {info['media']:.2f}x, MaxSeq {info['max_seq']:.0f}")

            # Mostrar algumas aparições
            print(f"  Aparições:")
            for seg in segs_do_grupo[:5]:
                print(f"    {seg['inicio_ts'].strftime('%m/%d %H:%M')} - {seg['duracao']} rodadas")
            if len(segs_do_grupo) > 5:
                print(f"    ... e mais {len(segs_do_grupo) - 5}")

    # ===== CONCLUSÃO =====
    print("\n" + "=" * 70)
    print("CONCLUSÃO")
    print("=" * 70)

    if todas_transicoes:
        duracoes = [t['duracao_anterior'] for t in todas_transicoes if t['duracao_anterior'] > 0]
        if duracoes:
            curtos = sum(1 for d in duracoes if d < 50)

            print(f"""
Sessões contínuas analisadas: {len(sessoes_grandes)}
Transições detectadas: {len(todas_transicoes)}
Segmentos caracterizados: {len(todos_segmentos)}
Duração média de regime: {statistics.mean(duracoes):.0f} rodadas
Regimes curtos (<50): {curtos} ({curtos/len(duracoes)*100:.1f}%)

Interpretação:
- Regimes curtos sugerem seeds de curta duração
- Grupos que se repetem em sessões diferentes indicam seeds recorrentes
- Quantidade de grupos distintos = quantidade de "estados" do jogo
""")


if __name__ == "__main__":
    main()
