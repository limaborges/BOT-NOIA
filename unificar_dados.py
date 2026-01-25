#!/usr/bin/env python3
"""
Script para unificar os arquivos de multiplicadores (sem pandas)
"""
import csv
from datetime import datetime

def carregar_arquivo_principal(caminho):
    """Carrega o arquivo 1.3m que já está no formato correto"""
    print(f"Carregando {caminho}...")
    dados = []
    with open(caminho, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dados.append(row)
    print(f"  Linhas: {len(dados)}")
    print(f"  Período: {dados[0]['Data']} - {dados[-1]['Data']}")
    return dados

def carregar_arquivo_novo(caminho):
    """Carrega arquivos novos (formato tipminer com ; e decimal com vírgula)"""
    print(f"Carregando {caminho}...")
    dados = []

    with open(caminho, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            # Pular linhas de propaganda tipminer
            if row['Número'] == 'tipminer.com':
                continue

            # Converter decimal de vírgula para ponto
            numero = row['Número'].replace(',', '.')

            # Criar DateTime
            dt_str = f"{row['Data']} {row['Horário']}"
            dt = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
            datetime_fmt = dt.strftime('%Y-%m-%d %H:%M:%S')

            # Determinar cor baseado no número
            valor = float(numero)
            cor = row['Cor']

            dados.append({
                'Número': numero,
                'Cor': cor,
                'Data': row['Data'],
                'Horário': row['Horário'],
                'DateTime': datetime_fmt
            })

    # Ordenar por DateTime (crescente)
    dados.sort(key=lambda x: x['DateTime'])

    print(f"  Linhas: {len(dados)}")
    if dados:
        print(f"  Período: {dados[0]['Data']} - {dados[-1]['Data']}")

    return dados

def main():
    # Caminhos dos arquivos
    arquivo_1m = '/home/linnaldonitro/MartingaleV2_Build/brabet_complete_clean_sorted1.3m.csv'
    arquivo_8a15 = '/home/linnaldonitro/MartingaleV2_Build/8a15jan.csv'
    arquivo_16a20 = '/home/linnaldonitro/MartingaleV2_Build/16a20jan26.csv'
    arquivo_saida = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    # Carregar arquivos
    dados_principal = carregar_arquivo_principal(arquivo_1m)
    dados_8a15 = carregar_arquivo_novo(arquivo_8a15)
    dados_16a20 = carregar_arquivo_novo(arquivo_16a20)

    # Verificar última data do arquivo principal
    ultima_datetime_principal = dados_principal[-1]['DateTime']
    print(f"\nÚltima data do arquivo principal: {ultima_datetime_principal}")

    # Filtrar dados novos para não duplicar
    dados_8a15_filtrado = [d for d in dados_8a15 if d['DateTime'] > ultima_datetime_principal]
    print(f"Dados 8a15jan após filtro: {len(dados_8a15_filtrado)} linhas")

    # 16a20jan são todos novos
    print(f"Dados 16a20jan: {len(dados_16a20)} linhas")

    # Unificar
    print("\nUnificando...")
    dados_unificado = dados_principal + dados_8a15_filtrado + dados_16a20

    # Ordenar por DateTime
    dados_unificado.sort(key=lambda x: x['DateTime'])

    # Remover duplicatas (mesmo DateTime)
    vistos = set()
    dados_sem_duplicatas = []
    duplicatas = 0
    for d in dados_unificado:
        if d['DateTime'] not in vistos:
            vistos.add(d['DateTime'])
            dados_sem_duplicatas.append(d)
        else:
            duplicatas += 1

    if duplicatas > 0:
        print(f"Removidas {duplicatas} duplicatas")

    dados_unificado = dados_sem_duplicatas

    # Estatísticas finais
    print(f"\n=== RESULTADO FINAL ===")
    print(f"Total de linhas: {len(dados_unificado)}")
    print(f"Período: {dados_unificado[0]['Data']} até {dados_unificado[-1]['Data']}")
    print(f"DateTime: {dados_unificado[0]['DateTime']} até {dados_unificado[-1]['DateTime']}")

    # Salvar
    with open(arquivo_saida, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['Número', 'Cor', 'Data', 'Horário', 'DateTime']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dados_unificado)

    print(f"\nArquivo salvo: {arquivo_saida}")

    # Verificar integridade
    print("\n=== VERIFICAÇÃO ===")
    print("Primeiras 5 linhas:")
    for d in dados_unificado[:5]:
        print(f"  {d['Número']}, {d['Cor']}, {d['Data']}, {d['Horário']}")

    print("\nÚltimas 5 linhas:")
    for d in dados_unificado[-5:]:
        print(f"  {d['Número']}, {d['Cor']}, {d['Data']}, {d['Horário']}")

if __name__ == '__main__':
    main()
