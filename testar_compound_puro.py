#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparativo: Compound puro vs Saque diário
"""

import csv
from typing import List

ARQUIVO_DADOS = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
ALVO = 1.99


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


NIVEIS = {
    9: {'divisor': 511, 'tentativas': 9},
    10: {'divisor': 1023, 'tentativas': 10},
}


def simular(multiplicadores: List[float], gatilho: int, nivel: int,
            banca_inicial: float, saque_pct: float = 0.0):
    """Simula com ou sem saque"""

    divisor = NIVEIS[nivel]['divisor']
    max_tent = NIVEIS[nivel]['tentativas']
    rodadas_por_dia = 3456

    banca = banca_inicial
    em_ciclo = False
    tentativa = 0
    apostas_perdidas = 0.0
    baixas = 0

    busts = 0
    total_sacado = 0.0
    rodada_dia = 0
    dias = 0
    historico = []

    for mult in multiplicadores:
        is_baixa = mult < ALVO

        if is_baixa:
            baixas += 1
        else:
            baixas = 0

        if not em_ciclo:
            if baixas >= gatilho:
                em_ciclo = True
                tentativa = 1
                apostas_perdidas = 0.0

        else:
            aposta = banca * (2 ** (tentativa - 1)) / divisor

            if mult >= ALVO:
                lucro = aposta * (ALVO - 1) - apostas_perdidas
                banca += lucro

                em_ciclo = False
                tentativa = 0
                apostas_perdidas = 0.0
                baixas = 0
            else:
                apostas_perdidas += aposta
                tentativa += 1

                if tentativa > max_tent:
                    busts += 1
                    banca = banca_inicial

                    em_ciclo = False
                    tentativa = 0
                    apostas_perdidas = 0.0
                    baixas = 0

        rodada_dia += 1
        if rodada_dia >= rodadas_por_dia:
            dias += 1

            # Saque diário (se configurado)
            saque = 0.0
            if saque_pct > 0 and banca > banca_inicial:
                lucro_disponivel = banca - banca_inicial
                saque = lucro_disponivel * saque_pct
                banca -= saque
                total_sacado += saque

            historico.append({
                'dia': dias,
                'banca': banca,
                'saque': saque,
                'total_sacado': total_sacado
            })

            rodada_dia = 0

    return historico, busts


def main():
    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(ARQUIVO_DADOS)
    print(f"Carregados {len(multiplicadores):,} multiplicadores\n")

    banca = 10000.0

    # Testar G6+NS9 (proteção 15) e G6+NS10 (proteção 16)
    configs = [
        (6, 9, "G6+NS9 (Prot 15)"),
        (6, 10, "G6+NS10 (Prot 16)"),
    ]

    for g, n, nome in configs:
        print(f"{'='*70}")
        print(f"{nome} - Banca R$ {banca:,.0f}")
        print(f"{'='*70}")

        # Compound puro
        hist_puro, busts_puro = simular(multiplicadores, g, n, banca, 0.0)

        # Com saque 50%
        hist_saque, busts_saque = simular(multiplicadores, g, n, banca, 0.5)

        print(f"\n{'Mês':>4} {'Compound Puro':>20} {'Saque 50%':>20} {'Sacado Acum':>18}")
        print("-" * 66)

        for mes in range(1, 13):
            dia = mes * 30
            if dia > len(hist_puro):
                break

            banca_puro = hist_puro[dia-1]['banca']
            banca_saque = hist_saque[dia-1]['banca']
            sacado = hist_saque[dia-1]['total_sacado']

            # Formatar números grandes
            if banca_puro > 1_000_000_000:
                bp_str = f"R$ {banca_puro/1_000_000_000:.1f}B"
            elif banca_puro > 1_000_000:
                bp_str = f"R$ {banca_puro/1_000_000:.1f}M"
            else:
                bp_str = f"R$ {banca_puro:,.0f}"

            print(f"{mes:>4} {bp_str:>20} R$ {banca_saque:>17,.0f} R$ {sacado:>15,.0f}")

        print(f"\n  Busts: {busts_puro}")

        # Resumo
        dias = len(hist_puro)
        print(f"\n  COMPOUND PURO ({dias} dias):")
        print(f"    Banca final: R$ {hist_puro[-1]['banca']:,.0f}")

        print(f"\n  SAQUE 50% DIÁRIO ({dias} dias):")
        print(f"    Total sacado: R$ {hist_saque[-1]['total_sacado']:,.0f}")
        print(f"    Banca final: R$ {hist_saque[-1]['banca']:,.0f}")
        print(f"    Média saque/mês: R$ {hist_saque[-1]['total_sacado']/(dias/30):,.0f}")
        print()


if __name__ == "__main__":
    main()
