#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cálculo do risco real de 16+ baixas consecutivas
"""

import csv
from typing import List

ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
ALVO_LUCRO = 1.99


def carregar_multiplicadores(arquivo: str) -> List[float]:
    multiplicadores = []
    with open(arquivo, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                mult = float(row.get('Número', row.get('numero', list(row.values())[0])))
                multiplicadores.append(mult)
            except:
                continue
    return multiplicadores


def analisar_probabilidades(multiplicadores: List[float]):
    """Analisa probabilidades reais do dataset"""

    total = len(multiplicadores)
    baixas = sum(1 for m in multiplicadores if m < ALVO_LUCRO)
    altas = total - baixas

    p_baixa = baixas / total
    p_alta = altas / total

    print(f"{'='*70}")
    print("PROBABILIDADES REAIS DO DATASET")
    print(f"{'='*70}")
    print(f"\n  Total de rodadas: {total:,}")
    print(f"  Baixas (< {ALVO_LUCRO}x): {baixas:,} ({p_baixa*100:.2f}%)")
    print(f"  Altas (>= {ALVO_LUCRO}x): {altas:,} ({p_alta*100:.2f}%)")

    # Probabilidade de N baixas consecutivas
    print(f"\n{'='*70}")
    print("PROBABILIDADE TEÓRICA DE SEQUÊNCIAS")
    print(f"{'='*70}")
    print(f"\n  P(baixa) = {p_baixa:.4f}")
    print(f"\n  {'N baixas':>10} {'P(sequência)':>15} {'1 em X':>12}")
    print("-" * 40)

    for n in range(10, 20):
        p_seq = p_baixa ** n
        one_in = 1 / p_seq if p_seq > 0 else float('inf')
        print(f"  {n:>10} {p_seq*100:>14.6f}% {one_in:>11,.0f}")

    # Contar sequências reais no dataset
    print(f"\n{'='*70}")
    print("SEQUÊNCIAS REAIS NO DATASET")
    print(f"{'='*70}")

    # Contar todas as sequências de baixas
    sequencias = {}
    atual = 0
    for m in multiplicadores:
        if m < ALVO_LUCRO:
            atual += 1
        else:
            if atual > 0:
                sequencias[atual] = sequencias.get(atual, 0) + 1
            atual = 0
    if atual > 0:
        sequencias[atual] = sequencias.get(atual, 0) + 1

    print(f"\n  {'Tamanho':>10} {'Ocorrências':>12} {'Esperado':>12}")
    print("-" * 40)

    total_seqs = sum(sequencias.values())
    for n in sorted(sequencias.keys()):
        if n >= 8:
            esperado = total_seqs * (p_baixa ** n) * (1 - p_baixa)
            print(f"  {n:>10} {sequencias[n]:>12} {esperado:>12.1f}")

    max_seq = max(sequencias.keys())
    print(f"\n  Máxima sequência encontrada: {max_seq} baixas")

    # Risco futuro
    print(f"\n{'='*70}")
    print("RISCO DE 16+ BAIXAS NO FUTURO")
    print(f"{'='*70}")

    # Número de "oportunidades" por ano
    # Cada vez que temos 5 baixas (G5), é uma oportunidade de continuar
    gatilhos_dia = 74  # Aproximado do dataset
    dias_ano = 365
    oportunidades_ano = gatilhos_dia * dias_ano

    print(f"\n  Gatilhos G5/dia: ~{gatilhos_dia}")
    print(f"  Oportunidades/ano: ~{oportunidades_ano:,}")

    # P(sequência de 16 | já teve 5) = P(mais 11 baixas) = p_baixa^11
    p_mais_11 = p_baixa ** 11
    p_bust_dado_g5 = p_mais_11

    print(f"\n  Dado que entrou em G5:")
    print(f"    P(chegar a 16 baixas) = P(mais 11 baixas)")
    print(f"    = {p_baixa:.4f}^11 = {p_bust_dado_g5*100:.6f}%")
    print(f"    = 1 em {1/p_bust_dado_g5:,.0f}")

    # Probabilidade de pelo menos 1 bust em N gatilhos
    print(f"\n  Probabilidade de pelo menos 1 bust:")
    for periodo, gatilhos in [("1 mês", gatilhos_dia * 30),
                               ("6 meses", gatilhos_dia * 180),
                               ("1 ano", gatilhos_dia * 365),
                               ("2 anos", gatilhos_dia * 730)]:
        p_nenhum_bust = (1 - p_bust_dado_g5) ** gatilhos
        p_algum_bust = 1 - p_nenhum_bust
        print(f"    {periodo:>10}: {p_algum_bust*100:.2f}%")

    # Conclusão
    print(f"\n{'='*70}")
    print("CONCLUSÃO")
    print(f"{'='*70}")
    print(f"""
  Com proteção 16 (G5 + D3 + D511):

  - No dataset de 1.3M rodadas (374 dias): 0 busts
  - Risco de bust em 1 ano: ~{(1 - (1 - p_bust_dado_g5) ** oportunidades_ano)*100:.1f}%
  - Risco de bust em 2 anos: ~{(1 - (1 - p_bust_dado_g5) ** (oportunidades_ano*2))*100:.1f}%

  INTERPRETAÇÃO:
  - Proteção 16 é MUITO segura, mas não é 100%
  - Em operação longa (anos), bust é provável eventualmente
  - Estratégia: sacar lucros regularmente para proteger capital
""")

    return p_baixa, max_seq


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    analisar_probabilidades(multiplicadores)


if __name__ == "__main__":
    main()
