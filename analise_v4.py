#!/usr/bin/env python3
"""
Análise V4 - Estratégia com 2 Slots de Aposta
Objetivo: Minimizar perdas T5+ e maximizar sobrevivência
"""

import re
from collections import defaultdict

def extrair_multiplicadores(arquivo):
    """Extrai todos os multiplicadores do arquivo de log"""
    multiplicadores = []
    pattern = r'Rodada salva: ([\d.]+)x'

    with open(arquivo, 'r', encoding='utf-8') as f:
        for linha in f:
            match = re.search(pattern, linha)
            if match:
                mult = float(match.group(1))
                multiplicadores.append(mult)

    return multiplicadores

def encontrar_gatilhos_g6(multiplicadores, alvo=1.99):
    """
    Encontra gatilhos G6: 6 rodadas consecutivas abaixo do alvo
    Retorna lista de índices onde o gatilho foi ativado
    """
    gatilhos = []
    consecutivos = 0

    for i, mult in enumerate(multiplicadores):
        if mult < alvo:
            consecutivos += 1
            if consecutivos == 6:
                gatilhos.append(i)  # Índice da 6ª rodada (T1 começa aqui)
        else:
            consecutivos = 0

    return gatilhos

def analisar_pos_gatilho(multiplicadores, gatilhos, max_tentativas=10):
    """
    Analisa o que acontece após cada gatilho
    T1 = rodada imediatamente após o gatilho
    """
    resultados = []

    for idx_gatilho in gatilhos:
        idx_t1 = idx_gatilho + 1  # T1 começa na próxima rodada

        if idx_t1 + max_tentativas > len(multiplicadores):
            continue

        tentativas = []
        for t in range(max_tentativas):
            if idx_t1 + t < len(multiplicadores):
                tentativas.append(multiplicadores[idx_t1 + t])

        resultados.append({
            'idx_gatilho': idx_gatilho,
            'tentativas': tentativas
        })

    return resultados

def analise_1_multiplicador_seguro_t5_t6(resultados, candidatos=None):
    """
    Ponto 2: Qual multiplicador nunca falhou em T5 e T6?
    Ou seja, sempre foi atingido em pelo menos uma das duas rodadas.
    """
    if candidatos is None:
        # Testar multiplicadores de 1.01 a 2.00 em incrementos de 0.01
        candidatos = [round(1.01 + i*0.01, 2) for i in range(100)]

    # Filtrar resultados que chegaram até T5 (perderam T1-T4)
    resultados_t5 = []
    for r in resultados:
        t = r['tentativas']
        # Verificar se perdeu T1-T4 (todos abaixo de 1.99)
        if len(t) >= 6 and all(x < 1.99 for x in t[:4]):
            resultados_t5.append(r)

    print(f"\n=== ANÁLISE 1: Multiplicador Seguro T5-T6 ===")
    print(f"Total de gatilhos que chegaram em T5: {len(resultados_t5)}")

    seguros = {}
    for alvo in candidatos:
        falhas = 0
        for r in resultados_t5:
            t = r['tentativas']
            # Verifica se T5 OU T6 atingiu o alvo
            t5_ok = t[4] >= alvo if len(t) > 4 else False
            t6_ok = t[5] >= alvo if len(t) > 5 else False

            if not (t5_ok or t6_ok):
                falhas += 1

        if falhas == 0:
            seguros[alvo] = len(resultados_t5)

    if seguros:
        max_alvo = max(seguros.keys())
        print(f"\nMultiplicadores que NUNCA falharam em T5 ou T6:")
        for alvo in sorted(seguros.keys(), reverse=True)[:10]:
            print(f"  {alvo:.2f}x - 100% de sucesso em {seguros[alvo]} casos")
        print(f"\n>>> MAIOR ALVO SEGURO: {max_alvo:.2f}x <<<")
        return max_alvo
    else:
        print("\nNenhum multiplicador teve 100% de sucesso em T5-T6")
        # Mostrar os melhores
        for alvo in [1.50, 1.40, 1.30, 1.20, 1.10, 1.05, 1.02]:
            falhas = 0
            for r in resultados_t5:
                t = r['tentativas']
                t5_ok = t[4] >= alvo if len(t) > 4 else False
                t6_ok = t[5] >= alvo if len(t) > 5 else False
                if not (t5_ok or t6_ok):
                    falhas += 1
            taxa = (len(resultados_t5) - falhas) / len(resultados_t5) * 100
            print(f"  {alvo:.2f}x - {taxa:.2f}% sucesso ({falhas} falhas)")
        return None

def analise_2_multiplicador_frequente_t5_t10(resultados):
    """
    Ponto 3: Qual multiplicador >1.99x mais se repete entre T5-T10?
    """
    print(f"\n=== ANÁLISE 2: Multiplicador >1.99x Mais Frequente T5-T10 ===")

    # Filtrar resultados que chegaram em T5
    resultados_t5 = []
    for r in resultados:
        t = r['tentativas']
        if len(t) >= 6 and all(x < 1.99 for x in t[:4]):
            resultados_t5.append(r)

    # Contar ocorrências de multiplicadores >1.99 em T5-T10
    contagem = defaultdict(int)
    contagem_por_tentativa = {f'T{i}': defaultdict(int) for i in range(5, 11)}

    for r in resultados_t5:
        t = r['tentativas']
        for i in range(4, min(10, len(t))):  # T5 até T10 (índices 4-9)
            mult = t[i]
            if mult >= 2.00:
                # Arredondar para facilitar agrupamento
                mult_arred = round(mult, 1)
                contagem[mult_arred] += 1
                contagem_por_tentativa[f'T{i+1}'][mult_arred] += 1

    # Top 10 multiplicadores
    top10 = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\nTop 10 multiplicadores >1.99x em T5-T10:")
    for mult, count in top10:
        print(f"  {mult:.1f}x - {count} ocorrências")

    # Análise por faixa
    faixas = {
        '2.00-2.50x': 0,
        '2.50-3.00x': 0,
        '3.00-5.00x': 0,
        '5.00-10.00x': 0,
        '10.00+x': 0
    }

    for mult, count in contagem.items():
        if mult < 2.5:
            faixas['2.00-2.50x'] += count
        elif mult < 3.0:
            faixas['2.50-3.00x'] += count
        elif mult < 5.0:
            faixas['3.00-5.00x'] += count
        elif mult < 10.0:
            faixas['5.00-10.00x'] += count
        else:
            faixas['10.00+x'] += count

    print(f"\nDistribuição por faixa:")
    for faixa, count in faixas.items():
        print(f"  {faixa}: {count} ocorrências")

    return top10

def analise_3_setup_2_slots(resultados):
    """
    Ponto 4: Setup com 2 slots para limitar perdas
    Objetivo: -14% T5, -24% T6, -34% T7, -44% T9, -55% T10

    Com divisor 63:
    T5: aposta 16/63 = 25.4%
    T6: aposta 32/63 = 50.8%

    Precisamos calcular como dividir os 2 slots
    """
    print(f"\n=== ANÁLISE 3: Setup com 2 Slots de Aposta ===")
    print(f"\nObjetivo de sangramento máximo:")
    print(f"  T5: -14%  |  T6: -24%  |  T7: -34%  |  T9: -44%  |  T10: -55%")

    print(f"\n--- Análise Matemática ---")

    # NS6 padrão: divisor 63
    # Apostas: 1, 2, 4, 8, 16, 32 (soma = 63)

    print(f"\nNS6 Padrão (divisor 63):")
    print(f"  T1: 1/63 = 1.59%")
    print(f"  T2: 2/63 = 3.17%")
    print(f"  T3: 4/63 = 6.35%")
    print(f"  T4: 8/63 = 12.70%")
    print(f"  T5: 16/63 = 25.40%")
    print(f"  T6: 32/63 = 50.79%")
    print(f"  Acumulado T1-T4: 15/63 = 23.81%")
    print(f"  Acumulado T1-T5: 31/63 = 49.21%")
    print(f"  Acumulado T1-T6: 63/63 = 100%")

    print(f"\n--- Estratégia 2 Slots ---")
    print(f"\nIdeia: Usar 2 apostas simultâneas com alvos diferentes")
    print(f"  Slot A: Aposta menor, alvo alto (recuperação)")
    print(f"  Slot B: Aposta maior, alvo baixo (sobrevivência)")

    # Para limitar perda em T5 a 14%:
    # Perda T1-T4 já é 23.81%, então não é possível com NS6 padrão
    # Precisamos de divisor diferente

    print(f"\n--- Problema Identificado ---")
    print(f"Com NS6 (divisor 63), perda em T1-T4 já é 23.81%")
    print(f"É IMPOSSÍVEL limitar T5 a 14% se T1-T4 já perdeu 23.81%")

    print(f"\n--- Alternativa: Novos Divisores ---")

    # Para perda máxima de 14% em T5:
    # Se T5 ganha com lucro zero, perda = T1+T2+T3+T4 = 15 unidades
    # 15/divisor = 0.14 => divisor = 15/0.14 = 107

    divisor_14 = 15 / 0.14
    print(f"\nPara -14% máximo em T5: divisor = {divisor_14:.0f}")
    print(f"  Apostas: 1, 2, 4, 8, 16, 32, ... / {divisor_14:.0f}")
    print(f"  Lucro por WIN em T1: 0.93%")

    # Para -24% em T6:
    # Perda T1-T5 = 31 unidades, divisor = 31/0.24 = 129
    divisor_24 = 31 / 0.24
    print(f"\nPara -24% máximo em T6: divisor = {divisor_24:.0f}")

    print(f"\n--- Estratégia Híbrida com 2 Slots ---")
    print(f"\nSe podemos apostar em 2 slots simultaneamente:")
    print(f"")
    print(f"OPÇÃO A: Slot dividido por alvo")
    print(f"  T5 Slot 1: 8/63 (12.7%) @ 1.99x (recupera tudo se ganhar)")
    print(f"  T5 Slot 2: 8/63 (12.7%) @ 1.30x (sobrevivência)")
    print(f"  Total T5: 16/63 (25.4%)")
    print(f"  Se Slot2 ganha: retorno 8*1.30 = 10.4 unidades")
    print(f"  Prejuízo: 15 + 8 - 10.4 = 12.6 unidades = 20%")
    print(f"")
    print(f"OPÇÃO B: Ajuste de proporção")
    print(f"  T5 Slot 1: 6/63 (9.5%) @ 1.99x")
    print(f"  T5 Slot 2: 10/63 (15.9%) @ 1.20x")
    print(f"  Se Slot2 ganha: retorno 10*1.20 = 12 unidades")
    print(f"  Prejuízo: 15 + 6 - 12 = 9 unidades = 14.3%")

    return None

def analise_4_taxa_sucesso_por_alvo(resultados):
    """
    Análise adicional: taxa de sucesso por alvo em cada tentativa
    """
    print(f"\n=== ANÁLISE 4: Taxa de Sucesso por Alvo em T5-T10 ===")

    # Filtrar resultados que chegaram em T5
    resultados_t5 = []
    for r in resultados:
        t = r['tentativas']
        if len(t) >= 6 and all(x < 1.99 for x in t[:4]):
            resultados_t5.append(r)

    alvos = [1.05, 1.10, 1.20, 1.30, 1.50, 1.70, 1.99, 2.50, 3.00]

    print(f"\nTotal de triggers que chegaram em T5: {len(resultados_t5)}")
    print(f"\nTaxa de sucesso por tentativa e alvo:")
    print(f"{'Alvo':<8}", end="")
    for t in range(5, 11):
        print(f"{'T'+str(t):<10}", end="")
    print()
    print("-" * 68)

    for alvo in alvos:
        print(f"{alvo:.2f}x   ", end="")
        for t_idx in range(4, 10):  # T5 a T10
            sucessos = 0
            total = 0
            for r in resultados_t5:
                tentativas = r['tentativas']
                if len(tentativas) > t_idx:
                    total += 1
                    if tentativas[t_idx] >= alvo:
                        sucessos += 1

            if total > 0:
                taxa = sucessos / total * 100
                print(f"{taxa:>6.1f}%   ", end="")
            else:
                print(f"{'N/A':<10}", end="")
        print()

def main():
    print("=" * 70)
    print("ANÁLISE V4 - ESTRATÉGIA COM 2 SLOTS DE APOSTA")
    print("=" * 70)

    # Carregar dados
    arquivos = [
        '/mnt/c/Users/linna/Desktop/MartingaleV2_Build/28.11.25--15.12.25.txt',
        '/mnt/c/Users/linna/Desktop/MartingaleV2_Build/16.10.25--27.11.25.txt'
    ]

    todos_multiplicadores = []
    for arq in arquivos:
        try:
            mults = extrair_multiplicadores(arq)
            todos_multiplicadores.extend(mults)
            print(f"Carregado: {arq.split('/')[-1]} - {len(mults)} multiplicadores")
        except Exception as e:
            print(f"Erro ao carregar {arq}: {e}")

    print(f"\nTotal de multiplicadores: {len(todos_multiplicadores)}")

    # Encontrar gatilhos
    gatilhos = encontrar_gatilhos_g6(todos_multiplicadores, alvo=1.99)
    print(f"Total de gatilhos G6 encontrados: {len(gatilhos)}")

    # Analisar pós-gatilho
    resultados = analisar_pos_gatilho(todos_multiplicadores, gatilhos)
    print(f"Gatilhos com dados completos: {len(resultados)}")

    # Rodar análises
    analise_1_multiplicador_seguro_t5_t6(resultados)
    analise_2_multiplicador_frequente_t5_t10(resultados)
    analise_3_setup_2_slots(resultados)
    analise_4_taxa_sucesso_por_alvo(resultados)

    print("\n" + "=" * 70)
    print("FIM DA ANÁLISE")
    print("=" * 70)

if __name__ == "__main__":
    main()
