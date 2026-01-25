#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANALISE DE RESULTADOS - O padrão de acertos denuncia o risco?

Hipótese: O padrão de T1, T2, T3 que você teve pode sinalizar
que um T6/T7 está por vir.

Exemplo: Após muitos T3 seguidos, ou após X% de T1, vem o perigo.
"""

import re
import sqlite3
import os
from datetime import datetime
import statistics
from collections import Counter, deque

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
    """
    Simula a estratégia G6 e retorna os resultados (T1, T2, T3...)

    G6 = 6 baixos consecutivos
    T1 = resolveu na 7ª rodada (primeiro após G6)
    T2 = resolveu na 8ª rodada
    ...
    """
    resultados = []
    i = 0
    n = len(mults)

    while i < n - 15:  # Margem para analisar
        # Procurar G6 (6 baixos consecutivos)
        seq_baixos = 0

        while i < n and seq_baixos < 6:
            if mults[i] < 2.0:
                seq_baixos += 1
            else:
                seq_baixos = 0
            i += 1

        if seq_baixos >= 6 and i < n - 10:
            # G6 detectado! Agora ver em qual tentativa resolve
            inicio_g6 = i - 6
            tentativa = 0

            while i < n and mults[i] < 2.0:
                tentativa += 1
                i += 1

            # Resolveu (ou acabou os dados)
            if i < n:
                resultados.append({
                    'idx': inicio_g6,
                    'tentativa': tentativa + 1,  # T1 = resolveu na 1ª após G6
                    'tamanho_total': 6 + tentativa,  # G6 + tentativas
                })

    return resultados


def analisar_sequencia_pre_perigo(resultados, janela=10, min_tentativa=5):
    """
    Analisa a sequência de Ts antes de um T perigoso
    min_tentativa=5 para NS6, min_tentativa=6 para NS7
    """
    # Encontrar índices de perigo
    indices_perigo = [i for i, r in enumerate(resultados) if r['tentativa'] >= min_tentativa]

    padroes_antes = []

    for idx in indices_perigo:
        if idx >= janela:
            # Pegar os últimos 'janela' resultados antes do T6+
            anteriores = resultados[idx - janela:idx]
            tentativas = [r['tentativa'] for r in anteriores]

            padroes_antes.append({
                'antes': tentativas,
                'perigo': resultados[idx]['tentativa'],
                't1_count': sum(1 for t in tentativas if t == 1),
                't2_count': sum(1 for t in tentativas if t == 2),
                't3_count': sum(1 for t in tentativas if t == 3),
                't4_count': sum(1 for t in tentativas if t == 4),
                't5_count': sum(1 for t in tentativas if t == 5),
                'media_t': statistics.mean(tentativas),
                'max_t': max(tentativas),
            })

    return padroes_antes


def analisar_sequencia_normal(resultados, janela=10, n_amostras=500, min_tentativa=5):
    """
    Analisa sequências normais (não seguidas de perigo) para comparação
    """
    import random
    random.seed(42)

    # Encontrar índices que NÃO são seguidos de perigo
    indices_perigo = set()
    for i, r in enumerate(resultados):
        if r['tentativa'] >= min_tentativa:
            # Marcar os 'janela' anteriores como "pré-perigo"
            for j in range(max(0, i - janela), i):
                indices_perigo.add(j)

    indices_normais = [i for i in range(janela, len(resultados) - 3)
                       if i not in indices_perigo]

    amostras = random.sample(indices_normais, min(n_amostras, len(indices_normais)))

    padroes_normal = []
    for idx in amostras:
        anteriores = resultados[idx - janela:idx]
        tentativas = [r['tentativa'] for r in anteriores]

        padroes_normal.append({
            'antes': tentativas,
            't1_count': sum(1 for t in tentativas if t == 1),
            't2_count': sum(1 for t in tentativas if t == 2),
            't3_count': sum(1 for t in tentativas if t == 3),
            't4_count': sum(1 for t in tentativas if t == 4),
            't5_count': sum(1 for t in tentativas if t == 5),
            'media_t': statistics.mean(tentativas),
            'max_t': max(tentativas),
        })

    return padroes_normal


def main():
    print("=" * 70)
    print("ANALISE DE RESULTADOS - O padrão de Ts denuncia o risco?")
    print("=" * 70)

    print("\nCarregando dados...")
    dados = carregar_dados()
    mults = [m for _, m in dados]
    print(f"Total: {len(mults)} rodadas")

    # Simular estratégia
    print("\nSimulando estratégia G6...")
    resultados = simular_estrategia(mults)
    print(f"Total de gatilhos: {len(resultados)}")

    # Distribuição de tentativas
    dist = Counter([r['tentativa'] for r in resultados])
    print("\nDistribuição de tentativas:")
    for t in sorted(dist.keys()):
        pct = dist[t] / len(resultados) * 100
        barra = "█" * int(pct / 2)
        print(f"  T{t}: {dist[t]:>4} ({pct:>5.1f}%) {barra}")

    # ===== ANÁLISE DO QUE VEM ANTES DE T5+ (perigo para NS6) =====
    print("\n" + "=" * 70)
    print("O QUE VEM ANTES DE T5+? (perda no NS6)")
    print("=" * 70)

    janela = 10
    min_t = 5  # T5+ = perda no NS6
    padroes_perigo = analisar_sequencia_pre_perigo(resultados, janela, min_t)
    padroes_normal = analisar_sequencia_normal(resultados, janela, min_tentativa=min_t)

    print(f"\nAnalisando últimos {janela} gatilhos antes de T5+")
    print(f"Casos T5+: {len(padroes_perigo)}")
    print(f"Casos normais (controle): {len(padroes_normal)}")

    # Comparar médias
    print(f"\n{'Métrica':<15} {'Pré-T5+':>10} {'Normal':>10} {'Diff':>10}")
    print("-" * 50)

    metricas = ['t1_count', 't2_count', 't3_count', 't4_count', 't5_count', 'media_t', 'max_t']
    diferencas = {}

    for m in metricas:
        media_perigo = statistics.mean([p[m] for p in padroes_perigo]) if padroes_perigo else 0
        media_normal = statistics.mean([p[m] for p in padroes_normal]) if padroes_normal else 0
        diff_pct = ((media_perigo - media_normal) / media_normal * 100) if media_normal != 0 else 0
        diferencas[m] = diff_pct

        nome = m.replace('_count', '').replace('_', ' ').upper()
        print(f"{nome:<15} {media_perigo:>10.2f} {media_normal:>10.2f} {diff_pct:>+9.1f}%")

    # ===== IDENTIFICAR SINAIS =====
    print("\n" + "=" * 70)
    print("SINAIS IDENTIFICADOS")
    print("=" * 70)

    sinais = []
    for m, diff in diferencas.items():
        if abs(diff) > 10:
            nome = m.replace('_count', '').replace('_', ' ').upper()
            direcao = "mais" if diff > 0 else "menos"
            sinais.append(f"{nome}: {direcao} ({diff:+.0f}%)")

    if sinais:
        print("\n⚠️  Antes de T5+, observa-se:")
        for s in sinais:
            print(f"   • {s}")
    else:
        print("\nNenhuma diferença significativa (>10%) encontrada.")

    # ===== PADRÕES ESPECÍFICOS =====
    print("\n" + "=" * 70)
    print("PADRÕES ESPECÍFICOS PRÉ-T5+")
    print("=" * 70)

    # Olhar sequências específicas
    print("\nÚltimos 5 resultados antes de cada T5+:")

    sequencias_5 = []
    for p in padroes_perigo:
        if len(p['antes']) >= 5:
            seq = tuple(p['antes'][-5:])
            sequencias_5.append(seq)

    # Contar sequências mais comuns
    seq_counter = Counter(sequencias_5)
    print("\nSequências mais frequentes (últimos 5):")
    for seq, count in seq_counter.most_common(10):
        seq_str = '-'.join(f'T{t}' for t in seq)
        print(f"  {seq_str}: {count} vezes")

    # ===== ANÁLISE DE ACUMULAÇÃO =====
    print("\n" + "=" * 70)
    print("ANÁLISE DE ACUMULAÇÃO")
    print("=" * 70)

    print("\nO que acontece quando acumula certos padrões?")

    # Verificar: após certos padrões, qual a chance de T5+?
    for criterio_nome, criterio_func in [
        ("3+ T1 nos últimos 5", lambda p: p['t1_count'] >= 3 and len(p['antes']) >= 5),
        ("2+ T3 nos últimos 5", lambda p: p['t3_count'] >= 2 and len(p['antes']) >= 5),
        ("3+ T3 nos últimos 10", lambda p: p['t3_count'] >= 3),
        ("T4 nos últimos 5", lambda p: p['t4_count'] >= 1 and len(p['antes']) >= 5),
        ("Média T > 2.0", lambda p: p['media_t'] > 2.0),
        ("Média T > 2.5", lambda p: p['media_t'] > 2.5),
        ("Max T >= 4 nos últimos 10", lambda p: p['max_t'] >= 4),
    ]:
        perigo_match = sum(1 for p in padroes_perigo if criterio_func(p))
        normal_match = sum(1 for p in padroes_normal if criterio_func(p))

        pct_perigo = perigo_match / len(padroes_perigo) * 100 if padroes_perigo else 0
        pct_normal = normal_match / len(padroes_normal) * 100 if padroes_normal else 0

        diff = pct_perigo - pct_normal

        print(f"\n  {criterio_nome}:")
        print(f"    Pré-T6+: {pct_perigo:.1f}%")
        print(f"    Normal:  {pct_normal:.1f}%")
        print(f"    Diff:    {diff:+.1f} pontos percentuais")

    # ===== T5+ APÓS T4 =====
    print("\n" + "=" * 70)
    print("T5+ VEIO APÓS QUAL RESULTADO?")
    print("=" * 70)

    # Quantos T5+ vieram logo após cada tipo?
    t5_apos = {1: 0, 2: 0, 3: 0, 4: 0}

    for i, r in enumerate(resultados):
        if r['tentativa'] >= 5 and i > 0:
            anterior = resultados[i-1]['tentativa']
            if anterior in t5_apos:
                t5_apos[anterior] += 1

    total_t5 = sum(t5_apos.values())
    if total_t5 > 0:
        print(f"\nT5+ veio imediatamente após:")
        for t in sorted(t5_apos.keys()):
            print(f"  T{t}: {t5_apos[t]} ({t5_apos[t]/total_t5*100:.1f}%)")

    # ===== CONCLUSÃO =====
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)

    total_perigo = sum(1 for r in resultados if r['tentativa'] >= 5)
    print(f"""
Total de gatilhos analisados: {len(resultados)}
Gatilhos T5+ (perda NS6): {total_perigo} ({total_perigo/len(resultados)*100:.1f}%)

Os padrões de acerto (T1, T2, T3, T4) denunciam T5+?
""")

    # Verificar se há sinal forte
    tem_sinal = any(abs(d) > 15 for d in diferencas.values())

    if tem_sinal:
        print("✓ SIM - Há diferenças significativas no padrão pré-T5+")
    else:
        print("✗ NÃO - Os padrões são muito similares")


if __name__ == "__main__":
    main()
