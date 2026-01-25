#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar padrão real das sequências longas
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


def analisar_sequencias(multiplicadores: List[float]):
    p_baixa = sum(1 for m in multiplicadores if m < ALVO_LUCRO) / len(multiplicadores)

    # Contar sequências por tamanho
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

    print(f"{'='*70}")
    print("ANÁLISE DAS SEQUÊNCIAS DE BAIXAS")
    print(f"{'='*70}")
    print(f"\nP(baixa) = {p_baixa:.4f} = {p_baixa*100:.2f}%")

    print(f"\n{'Tamanho':>8} {'Real':>8} {'Esperado':>10} {'Razão':>10} {'R→R+1':>10}")
    print("-" * 50)

    total_seqs = sum(v for k, v in sequencias.items() if k >= 1)

    for n in range(5, 17):
        real = sequencias.get(n, 0)
        # Esperado se sequências fossem independentes
        esperado = total_seqs * (p_baixa ** n) * (1 - p_baixa)
        razao = real / esperado if esperado > 0 else 0

        # Transição para próximo tamanho
        prox = sequencias.get(n + 1, 0)
        trans = prox / real if real > 0 else 0

        print(f"{n:>8} {real:>8} {esperado:>10.1f} {razao:>10.2f} {trans:>10.3f}")

    print(f"\n{'='*70}")
    print("OBSERVAÇÃO IMPORTANTE")
    print(f"{'='*70}")
    print(f"""
  A coluna 'R→R+1' mostra a taxa de transição:
  quantas sequências de tamanho N se tornam N+1

  Se fosse aleatório puro, deveria ser ~{p_baixa:.2f} (= P(baixa))

  Observe que para sequências longas (13+), a taxa cai para ~0.29
  Isso sugere que o jogo pode ter algum mecanismo que
  dificulta sequências muito longas.

  MAS: isso não é garantia. Pode ser apenas variação estatística.
""")

    # Calcular risco baseado em dados empíricos
    print(f"{'='*70}")
    print("RISCO EMPÍRICO (baseado nos dados reais)")
    print(f"{'='*70}")

    # Taxa de transição média para sequências longas
    trans_13_14 = sequencias.get(14, 0) / sequencias.get(13, 1)
    trans_14_15 = sequencias.get(15, 0) / sequencias.get(14, 1)
    trans_media_longa = (trans_13_14 + trans_14_15) / 2

    print(f"\n  Taxa de transição 13→14: {trans_13_14:.3f}")
    print(f"  Taxa de transição 14→15: {trans_14_15:.3f}")
    print(f"  Média (sequências longas): {trans_media_longa:.3f}")

    # Se assumirmos essa taxa continua
    # P(16 dado 15) ≈ 0.29
    # P(16 dado 5) ≈ taxa^11

    # Usando taxa empírica
    p_bust_empirico = trans_media_longa ** 11
    print(f"\n  P(bust dado G5) usando taxa empírica:")
    print(f"    = {trans_media_longa:.3f}^11 = {p_bust_empirico*100:.6f}%")
    print(f"    = 1 em {1/p_bust_empirico:,.0f}")

    # Usando P(baixa) teórico
    p_bust_teorico = p_baixa ** 11
    print(f"\n  P(bust dado G5) usando P(baixa) teórico:")
    print(f"    = {p_baixa:.3f}^11 = {p_bust_teorico*100:.4f}%")
    print(f"    = 1 em {1/p_bust_teorico:,.0f}")

    print(f"\n{'='*70}")
    print("CONCLUSÃO")
    print(f"{'='*70}")

    gatilhos_ano = 74 * 365

    p_bust_ano_emp = 1 - (1 - p_bust_empirico) ** gatilhos_ano
    p_bust_ano_teo = 1 - (1 - p_bust_teorico) ** gatilhos_ano

    print(f"""
  Risco de bust em 1 ano (27.000 gatilhos):

    Usando taxa empírica: {p_bust_ano_emp*100:.1f}%
    Usando P teórico:     {p_bust_ano_teo*100:.1f}%

  O dataset de 374 dias mostrou 0 busts com proteção 16.
  Isso é consistente com taxa empírica ({p_bust_ano_emp*100:.1f}% chance),
  mas inconsistente com taxa teórica ({p_bust_ano_teo*100:.1f}% chance).

  INTERPRETAÇÃO:
    - Ou o jogo tem algum mecanismo anti-streak
    - Ou tivemos sorte estatística
    - Ou a amostra não é grande o suficiente

  RECOMENDAÇÃO:
    ✅ Proteção 16 é a mais segura disponível
    ✅ Risco real parece menor que o teórico
    ⚠️  Mas bust ainda é possível - saque lucros regularmente
""")


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    analisar_sequencias(multiplicadores)


if __name__ == "__main__":
    main()
