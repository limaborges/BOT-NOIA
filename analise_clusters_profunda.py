#!/usr/bin/env python3
"""
ANALISE PROFUNDA DE CLUSTERS - Identificacao de Sinais de Momento Ruim
Dataset completo: 1.3M+ multiplicadores

Objetivos:
1. Identificar todos os periodos de "cluster" (sequencias ruins)
2. Analisar o que aconteceu ANTES de cada cluster
3. Encontrar padroes/sinais precursores
4. Criar indicadores de alerta

Definicoes:
- CLUSTER: Periodo com alta concentracao de T5+, T6+, Cenarios B
- FERRO: Gatilho que chegou em T6 ou alem
- SANGRIA: Sequencia de perdas/paradas consecutivas
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics

# ==============================================================================
# CONSTANTES
# ==============================================================================

ALVO_LUCRO = 1.99
ALVO_DEFESA = 1.10
THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6

# Definicoes de cluster
JANELA_CLUSTER = 50  # Gatilhos para avaliar cluster
THRESHOLD_T5_PLUS = 0.10  # >10% de T5+ = cluster
THRESHOLD_T6_PLUS = 0.05  # >5% de T6+ = cluster severo

# Janelas de analise pre-cluster
JANELA_CURTA = 100  # Ultimos 100 multiplicadores
JANELA_MEDIA = 500  # Ultimos 500 multiplicadores
JANELA_LONGA = 2000  # Ultimos 2000 multiplicadores


# ==============================================================================
# ESTRUTURAS DE DADOS
# ==============================================================================

@dataclass
class GatilhoInfo:
    """Informacoes de um gatilho"""
    numero: int
    posicao_inicio: int  # Posicao no array de multiplicadores
    tentativa_final: int
    resultado: str  # 'win', 'parar', 'bust'
    cenario_final: str  # 'WIN', 'A', 'B', 'C'
    multiplicadores_sequencia: List[float] = field(default_factory=list)
    drawdown_causado: float = 0.0


@dataclass
class ClusterInfo:
    """Informacoes de um cluster identificado"""
    inicio_gatilho: int
    fim_gatilho: int
    inicio_posicao: int
    fim_posicao: int
    duracao_gatilhos: int
    qtd_t5_plus: int
    qtd_t6_plus: int
    qtd_cenario_b: int
    qtd_bust: int
    drawdown_total: float
    severidade: str  # 'leve', 'moderado', 'severo', 'critico'

    # Metricas PRE-cluster (sinais)
    pre_taxa_altos: float = 0.0  # % de mult >= 2.0 antes
    pre_volatilidade: float = 0.0
    pre_media_mult: float = 0.0
    pre_sequencia_max_baixos: int = 0
    pre_taxa_t1_t4: float = 0.0


# ==============================================================================
# SIMULADOR PARA ANALISE
# ==============================================================================

class AnalisadorClusters:
    def __init__(self):
        self.multiplicadores: List[float] = []
        self.gatilhos: List[GatilhoInfo] = []
        self.clusters: List[ClusterInfo] = []

        # Estado do gatilho
        self.baixos_consecutivos = 0
        self.em_sequencia = False
        self.tentativa_atual = 0
        self.posicao_inicio_gatilho = 0
        self.mults_sequencia = []

        # Tracking
        self.banca = 1000.0
        self.banca_inicial = 1000.0
        self.banca_maxima = 1000.0

    def carregar_dados(self, filepath: str):
        """Carrega todos os multiplicadores"""
        print("Carregando dados...")
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            next(f)
            for line in f:
                try:
                    parts = line.strip().split(',')
                    if parts:
                        mult = float(parts[0])
                        self.multiplicadores.append(mult)
                except:
                    continue
        print(f"  Total: {len(self.multiplicadores):,} multiplicadores")

    def _get_tentativa_final(self, mults: List[float]) -> Tuple[int, str, str]:
        """
        Simula um gatilho e retorna (tentativa_final, resultado, cenario)
        """
        for i, mult in enumerate(mults):
            tentativa = i + 1

            # Determinar se eh penultima/ultima (assumindo NS7 para analise)
            max_t = 7
            is_penultima = (tentativa == max_t - 1)  # T6
            is_ultima = (tentativa == max_t)  # T7

            if is_ultima:
                # 2 slots: 12/32 @ 2.50x + 20/32 @ 1.10x
                if mult >= 2.50:
                    return tentativa, 'win', 'A'
                elif mult >= 1.10:
                    return tentativa, 'win', 'B'  # Defesa salvou
                else:
                    return tentativa, 'bust', 'C'

            elif is_penultima:
                # 2 slots: 6/16 @ 1.99x + 10/16 @ 1.10x - PARAR em B
                if mult >= 1.99:
                    return tentativa, 'win', 'A'
                elif mult >= 1.10:
                    return tentativa, 'parar', 'B'
                # else: continua para T7

            else:
                # 1 slot @ 1.99x
                if mult >= 1.99:
                    return tentativa, 'win', 'WIN'
                # else: continua

        # Fallback (nao deveria chegar aqui)
        return len(mults), 'bust', 'C'

    def processar_gatilhos(self):
        """Processa todos os multiplicadores e identifica gatilhos"""
        print("Processando gatilhos...")

        i = 0
        gatilho_num = 0

        while i < len(self.multiplicadores):
            mult = self.multiplicadores[i]

            if not self.em_sequencia:
                if mult < THRESHOLD_BAIXO:
                    self.baixos_consecutivos += 1
                    if self.baixos_consecutivos == GATILHO_SIZE:
                        # Gatilho ativado!
                        self.em_sequencia = True
                        self.posicao_inicio_gatilho = i + 1  # Proximo mult eh T1
                        self.mults_sequencia = []
                        self.baixos_consecutivos = 0
                else:
                    self.baixos_consecutivos = 0
            else:
                # Em sequencia - coletar multiplicadores
                self.mults_sequencia.append(mult)

                # Verificar se terminou (max 7 tentativas para NS7)
                if len(self.mults_sequencia) >= 7:
                    self.em_sequencia = False
                else:
                    # Verificar se ganhou antes
                    tent = len(self.mults_sequencia)
                    is_pen = (tent == 6)
                    is_ult = (tent == 7)

                    if is_ult:
                        self.em_sequencia = False
                    elif is_pen:
                        if mult >= 1.99:  # Cenario A
                            self.em_sequencia = False
                        elif mult >= 1.10:  # Cenario B - PARAR
                            self.em_sequencia = False
                        # else: continua para T7
                    else:
                        if mult >= 1.99:  # WIN
                            self.em_sequencia = False

                # Se terminou, registrar gatilho
                if not self.em_sequencia and self.mults_sequencia:
                    gatilho_num += 1
                    tent_final, resultado, cenario = self._get_tentativa_final(self.mults_sequencia)

                    self.gatilhos.append(GatilhoInfo(
                        numero=gatilho_num,
                        posicao_inicio=self.posicao_inicio_gatilho,
                        tentativa_final=tent_final,
                        resultado=resultado,
                        cenario_final=cenario,
                        multiplicadores_sequencia=self.mults_sequencia.copy()
                    ))
                    self.mults_sequencia = []

            i += 1

        print(f"  Total gatilhos: {len(self.gatilhos):,}")

    def identificar_clusters(self):
        """Identifica periodos de cluster"""
        print("Identificando clusters...")

        # Sliding window para detectar clusters
        for i in range(len(self.gatilhos) - JANELA_CLUSTER):
            janela = self.gatilhos[i:i + JANELA_CLUSTER]

            # Contar eventos ruins na janela
            t5_plus = sum(1 for g in janela if g.tentativa_final >= 5)
            t6_plus = sum(1 for g in janela if g.tentativa_final >= 6)
            cenario_b = sum(1 for g in janela if g.cenario_final == 'B')
            busts = sum(1 for g in janela if g.resultado == 'bust')

            taxa_t5 = t5_plus / JANELA_CLUSTER
            taxa_t6 = t6_plus / JANELA_CLUSTER

            # Detectar inicio de cluster
            is_cluster = taxa_t5 >= THRESHOLD_T5_PLUS or taxa_t6 >= THRESHOLD_T6_PLUS or busts > 0

            if is_cluster:
                # Verificar se ja nao estamos em um cluster
                if self.clusters and self.clusters[-1].fim_gatilho >= i:
                    # Extender cluster existente
                    self.clusters[-1].fim_gatilho = i + JANELA_CLUSTER
                    self.clusters[-1].fim_posicao = janela[-1].posicao_inicio
                    self.clusters[-1].duracao_gatilhos = self.clusters[-1].fim_gatilho - self.clusters[-1].inicio_gatilho
                    self.clusters[-1].qtd_t5_plus = max(self.clusters[-1].qtd_t5_plus, t5_plus)
                    self.clusters[-1].qtd_t6_plus = max(self.clusters[-1].qtd_t6_plus, t6_plus)
                    self.clusters[-1].qtd_cenario_b = max(self.clusters[-1].qtd_cenario_b, cenario_b)
                    self.clusters[-1].qtd_bust = max(self.clusters[-1].qtd_bust, busts)
                else:
                    # Novo cluster
                    severidade = 'leve'
                    if busts > 0:
                        severidade = 'critico'
                    elif taxa_t6 >= 0.10:
                        severidade = 'severo'
                    elif taxa_t6 >= 0.05:
                        severidade = 'moderado'

                    self.clusters.append(ClusterInfo(
                        inicio_gatilho=i,
                        fim_gatilho=i + JANELA_CLUSTER,
                        inicio_posicao=janela[0].posicao_inicio,
                        fim_posicao=janela[-1].posicao_inicio,
                        duracao_gatilhos=JANELA_CLUSTER,
                        qtd_t5_plus=t5_plus,
                        qtd_t6_plus=t6_plus,
                        qtd_cenario_b=cenario_b,
                        qtd_bust=busts,
                        drawdown_total=0.0,
                        severidade=severidade
                    ))

        print(f"  Clusters identificados: {len(self.clusters)}")

    def analisar_pre_clusters(self):
        """Analisa o que aconteceu ANTES de cada cluster"""
        print("Analisando sinais pre-cluster...")

        for cluster in self.clusters:
            pos_inicio = cluster.inicio_posicao

            # Pegar multiplicadores ANTES do cluster
            inicio_curta = max(0, pos_inicio - JANELA_CURTA)
            inicio_media = max(0, pos_inicio - JANELA_MEDIA)
            inicio_longa = max(0, pos_inicio - JANELA_LONGA)

            mults_antes_curta = self.multiplicadores[inicio_curta:pos_inicio]
            mults_antes_media = self.multiplicadores[inicio_media:pos_inicio]
            mults_antes_longa = self.multiplicadores[inicio_longa:pos_inicio]

            if not mults_antes_curta:
                continue

            # Calcular metricas pre-cluster

            # 1. Taxa de multiplicadores altos (>= 2.0)
            cluster.pre_taxa_altos = sum(1 for m in mults_antes_curta if m >= 2.0) / len(mults_antes_curta)

            # 2. Volatilidade (desvio padrao)
            if len(mults_antes_curta) > 1:
                cluster.pre_volatilidade = statistics.stdev(mults_antes_curta)

            # 3. Media dos multiplicadores
            cluster.pre_media_mult = statistics.mean(mults_antes_curta)

            # 4. Maior sequencia de baixos consecutivos
            max_baixos = 0
            baixos_atual = 0
            for m in mults_antes_curta:
                if m < 2.0:
                    baixos_atual += 1
                    max_baixos = max(max_baixos, baixos_atual)
                else:
                    baixos_atual = 0
            cluster.pre_sequencia_max_baixos = max_baixos

            # 5. Taxa de resolucao T1-T4 nos gatilhos anteriores
            gatilho_inicio = cluster.inicio_gatilho
            gatilhos_antes = self.gatilhos[max(0, gatilho_inicio - 50):gatilho_inicio]
            if gatilhos_antes:
                t1_t4 = sum(1 for g in gatilhos_antes if g.tentativa_final <= 4)
                cluster.pre_taxa_t1_t4 = t1_t4 / len(gatilhos_antes)

    def calcular_estatisticas_globais(self) -> Dict:
        """Calcula estatisticas globais do dataset"""
        total_gatilhos = len(self.gatilhos)

        # Distribuicao de tentativas finais
        dist_tentativas = defaultdict(int)
        for g in self.gatilhos:
            dist_tentativas[g.tentativa_final] += 1

        # Contagens
        total_t5_plus = sum(1 for g in self.gatilhos if g.tentativa_final >= 5)
        total_t6_plus = sum(1 for g in self.gatilhos if g.tentativa_final >= 6)
        total_cenario_b = sum(1 for g in self.gatilhos if g.cenario_final == 'B')
        total_busts = sum(1 for g in self.gatilhos if g.resultado == 'bust')

        # Metricas de multiplicadores
        media_mult = statistics.mean(self.multiplicadores)
        taxa_altos = sum(1 for m in self.multiplicadores if m >= 2.0) / len(self.multiplicadores)

        return {
            'total_multiplicadores': len(self.multiplicadores),
            'total_gatilhos': total_gatilhos,
            'dist_tentativas': dict(dist_tentativas),
            'total_t5_plus': total_t5_plus,
            'taxa_t5_plus': total_t5_plus / total_gatilhos * 100,
            'total_t6_plus': total_t6_plus,
            'taxa_t6_plus': total_t6_plus / total_gatilhos * 100,
            'total_cenario_b': total_cenario_b,
            'taxa_cenario_b': total_cenario_b / total_gatilhos * 100,
            'total_busts': total_busts,
            'taxa_busts': total_busts / total_gatilhos * 100 if total_gatilhos > 0 else 0,
            'media_multiplicador': media_mult,
            'taxa_mult_altos': taxa_altos * 100,
        }

    def analisar_sinais_precursores(self) -> Dict:
        """Analisa padroes nos sinais pre-cluster"""
        if not self.clusters:
            return {}

        # Coletar metricas de todos os clusters
        taxas_altos = [c.pre_taxa_altos for c in self.clusters if c.pre_taxa_altos > 0]
        volatilidades = [c.pre_volatilidade for c in self.clusters if c.pre_volatilidade > 0]
        medias_mult = [c.pre_media_mult for c in self.clusters if c.pre_media_mult > 0]
        max_baixos = [c.pre_sequencia_max_baixos for c in self.clusters]
        taxas_t1_t4 = [c.pre_taxa_t1_t4 for c in self.clusters if c.pre_taxa_t1_t4 > 0]

        # Separar por severidade
        clusters_severos = [c for c in self.clusters if c.severidade in ['severo', 'critico']]
        clusters_leves = [c for c in self.clusters if c.severidade == 'leve']

        resultado = {
            'total_clusters': len(self.clusters),
            'clusters_por_severidade': {
                'leve': sum(1 for c in self.clusters if c.severidade == 'leve'),
                'moderado': sum(1 for c in self.clusters if c.severidade == 'moderado'),
                'severo': sum(1 for c in self.clusters if c.severidade == 'severo'),
                'critico': sum(1 for c in self.clusters if c.severidade == 'critico'),
            }
        }

        if taxas_altos:
            resultado['pre_taxa_altos'] = {
                'media': statistics.mean(taxas_altos),
                'min': min(taxas_altos),
                'max': max(taxas_altos),
            }

        if volatilidades:
            resultado['pre_volatilidade'] = {
                'media': statistics.mean(volatilidades),
                'min': min(volatilidades),
                'max': max(volatilidades),
            }

        if taxas_t1_t4:
            resultado['pre_taxa_t1_t4'] = {
                'media': statistics.mean(taxas_t1_t4),
                'min': min(taxas_t1_t4),
                'max': max(taxas_t1_t4),
            }

        if max_baixos:
            resultado['pre_max_baixos_consecutivos'] = {
                'media': statistics.mean(max_baixos),
                'max': max(max_baixos),
            }

        # Comparar clusters severos vs leves
        if clusters_severos and clusters_leves:
            severos_taxa_altos = [c.pre_taxa_altos for c in clusters_severos if c.pre_taxa_altos > 0]
            leves_taxa_altos = [c.pre_taxa_altos for c in clusters_leves if c.pre_taxa_altos > 0]

            severos_t1_t4 = [c.pre_taxa_t1_t4 for c in clusters_severos if c.pre_taxa_t1_t4 > 0]
            leves_t1_t4 = [c.pre_taxa_t1_t4 for c in clusters_leves if c.pre_taxa_t1_t4 > 0]

            resultado['comparativo_severidade'] = {
                'severos_taxa_altos_media': statistics.mean(severos_taxa_altos) if severos_taxa_altos else 0,
                'leves_taxa_altos_media': statistics.mean(leves_taxa_altos) if leves_taxa_altos else 0,
                'severos_t1_t4_media': statistics.mean(severos_t1_t4) if severos_t1_t4 else 0,
                'leves_t1_t4_media': statistics.mean(leves_t1_t4) if leves_t1_t4 else 0,
            }

        return resultado

    def encontrar_padroes_especificos(self) -> Dict:
        """Busca padroes especificos antes de clusters"""
        padroes = {
            'sequencia_baixos_antes_cluster': [],
            'queda_taxa_altos': [],
            'aumento_volatilidade': [],
        }

        for cluster in self.clusters:
            pos = cluster.inicio_posicao

            # Verificar se houve queda na taxa de altos
            if pos > JANELA_MEDIA:
                mults_recente = self.multiplicadores[pos - JANELA_CURTA:pos]
                mults_anterior = self.multiplicadores[pos - JANELA_MEDIA:pos - JANELA_CURTA]

                if mults_recente and mults_anterior:
                    taxa_recente = sum(1 for m in mults_recente if m >= 2.0) / len(mults_recente)
                    taxa_anterior = sum(1 for m in mults_anterior if m >= 2.0) / len(mults_anterior)

                    if taxa_recente < taxa_anterior * 0.9:  # Queda de 10%+
                        padroes['queda_taxa_altos'].append({
                            'cluster': cluster.inicio_gatilho,
                            'taxa_anterior': taxa_anterior,
                            'taxa_recente': taxa_recente,
                            'queda_pct': (taxa_anterior - taxa_recente) / taxa_anterior * 100
                        })

                    # Verificar aumento de volatilidade
                    if len(mults_recente) > 1 and len(mults_anterior) > 1:
                        vol_recente = statistics.stdev(mults_recente)
                        vol_anterior = statistics.stdev(mults_anterior)

                        if vol_recente > vol_anterior * 1.2:  # Aumento de 20%+
                            padroes['aumento_volatilidade'].append({
                                'cluster': cluster.inicio_gatilho,
                                'vol_anterior': vol_anterior,
                                'vol_recente': vol_recente,
                                'aumento_pct': (vol_recente - vol_anterior) / vol_anterior * 100
                            })

        return padroes

    def gerar_relatorio(self):
        """Gera relatorio completo"""
        print("\n" + "=" * 100)
        print("ANALISE PROFUNDA DE CLUSTERS - RELATORIO COMPLETO")
        print("=" * 100)

        # Estatisticas globais
        stats = self.calcular_estatisticas_globais()

        print("\n" + "-" * 100)
        print("1. ESTATISTICAS GLOBAIS DO DATASET")
        print("-" * 100)
        print(f"  Total de multiplicadores: {stats['total_multiplicadores']:,}")
        print(f"  Total de gatilhos: {stats['total_gatilhos']:,}")
        print(f"  Media multiplicador: {stats['media_multiplicador']:.2f}x")
        print(f"  Taxa mult >= 2.0: {stats['taxa_mult_altos']:.1f}%")
        print()
        print("  Distribuicao de tentativas finais:")
        for t in sorted(stats['dist_tentativas'].keys()):
            qtd = stats['dist_tentativas'][t]
            pct = qtd / stats['total_gatilhos'] * 100
            bar = "█" * int(pct / 2)
            print(f"    T{t}: {qtd:>6,} ({pct:>5.2f}%) {bar}")
        print()
        print(f"  Taxa T5+: {stats['taxa_t5_plus']:.2f}%")
        print(f"  Taxa T6+: {stats['taxa_t6_plus']:.2f}%")
        print(f"  Taxa Cenario B: {stats['taxa_cenario_b']:.2f}%")
        print(f"  Taxa Bust: {stats['taxa_busts']:.4f}%")

        # Analise de clusters
        print("\n" + "-" * 100)
        print("2. CLUSTERS IDENTIFICADOS")
        print("-" * 100)

        sinais = self.analisar_sinais_precursores()

        print(f"  Total de clusters: {sinais.get('total_clusters', 0)}")
        if 'clusters_por_severidade' in sinais:
            print("  Por severidade:")
            for sev, qtd in sinais['clusters_por_severidade'].items():
                print(f"    - {sev.upper()}: {qtd}")

        # Sinais pre-cluster
        print("\n" + "-" * 100)
        print("3. SINAIS PRE-CLUSTER (O QUE ACONTECE ANTES)")
        print("-" * 100)

        if 'pre_taxa_altos' in sinais:
            p = sinais['pre_taxa_altos']
            print(f"\n  Taxa de multiplicadores >= 2.0 (antes do cluster):")
            print(f"    Media: {p['media']*100:.1f}%")
            print(f"    Min: {p['min']*100:.1f}%")
            print(f"    Max: {p['max']*100:.1f}%")

        if 'pre_taxa_t1_t4' in sinais:
            p = sinais['pre_taxa_t1_t4']
            print(f"\n  Taxa de resolucao T1-T4 (antes do cluster):")
            print(f"    Media: {p['media']*100:.1f}%")
            print(f"    Min: {p['min']*100:.1f}%")
            print(f"    Max: {p['max']*100:.1f}%")

        if 'pre_volatilidade' in sinais:
            p = sinais['pre_volatilidade']
            print(f"\n  Volatilidade (desvio padrao antes do cluster):")
            print(f"    Media: {p['media']:.2f}")
            print(f"    Min: {p['min']:.2f}")
            print(f"    Max: {p['max']:.2f}")

        if 'pre_max_baixos_consecutivos' in sinais:
            p = sinais['pre_max_baixos_consecutivos']
            print(f"\n  Maior sequencia de baixos consecutivos (antes):")
            print(f"    Media: {p['media']:.1f}")
            print(f"    Max: {p['max']}")

        # Comparativo severos vs leves
        if 'comparativo_severidade' in sinais:
            print("\n" + "-" * 100)
            print("4. COMPARATIVO: CLUSTERS SEVEROS vs LEVES")
            print("-" * 100)
            c = sinais['comparativo_severidade']
            print(f"\n  Taxa de mult >= 2.0 ANTES:")
            print(f"    Antes de clusters SEVEROS: {c['severos_taxa_altos_media']*100:.1f}%")
            print(f"    Antes de clusters LEVES: {c['leves_taxa_altos_media']*100:.1f}%")
            print(f"\n  Taxa T1-T4 ANTES:")
            print(f"    Antes de clusters SEVEROS: {c['severos_t1_t4_media']*100:.1f}%")
            print(f"    Antes de clusters LEVES: {c['leves_t1_t4_media']*100:.1f}%")

        # Padroes especificos
        padroes = self.encontrar_padroes_especificos()

        print("\n" + "-" * 100)
        print("5. PADROES ESPECIFICOS ENCONTRADOS")
        print("-" * 100)

        if padroes['queda_taxa_altos']:
            print(f"\n  Queda na taxa de multiplicadores altos antes de cluster:")
            print(f"    Ocorrencias: {len(padroes['queda_taxa_altos'])}")
            quedas = [p['queda_pct'] for p in padroes['queda_taxa_altos']]
            print(f"    Queda media: {statistics.mean(quedas):.1f}%")
            print(f"    Queda maxima: {max(quedas):.1f}%")

        if padroes['aumento_volatilidade']:
            print(f"\n  Aumento de volatilidade antes de cluster:")
            print(f"    Ocorrencias: {len(padroes['aumento_volatilidade'])}")
            aumentos = [p['aumento_pct'] for p in padroes['aumento_volatilidade']]
            print(f"    Aumento medio: {statistics.mean(aumentos):.1f}%")
            print(f"    Aumento maximo: {max(aumentos):.1f}%")

        # Conclusoes e recomendacoes
        print("\n" + "=" * 100)
        print("6. CONCLUSOES E INDICADORES DE ALERTA")
        print("=" * 100)

        print("""
  INDICADORES DE ALERTA SUGERIDOS:

  1. TAXA DE MULTIPLICADORES ALTOS
     - Normal: ~46% dos multiplicadores >= 2.0
     - ALERTA: Se cair abaixo de 42% nas ultimas 100 rodadas
     - ACAO: Considerar mudar para NS8

  2. TAXA DE RESOLUCAO T1-T4
     - Normal: ~95% dos gatilhos resolvem em T1-T4
     - ALERTA: Se cair abaixo de 90% nos ultimos 50 gatilhos
     - ACAO: Reduzir exposicao ou pausar

  3. SEQUENCIA DE BAIXOS
     - Normal: Sequencias de 6-8 baixos consecutivos
     - ALERTA: Sequencia de 10+ baixos (mesmo sem gatilho)
     - ACAO: Aumentar vigilancia

  4. VOLATILIDADE
     - ALERTA: Aumento de 20%+ na volatilidade
     - ACAO: Considerar apostas mais conservadoras

  5. COMBINACAO DE SINAIS
     - 2+ indicadores em alerta = REDUCAO de exposicao
     - 3+ indicadores em alerta = PAUSAR operacoes
""")

        # Top 10 piores clusters
        print("\n" + "-" * 100)
        print("7. TOP 10 PIORES CLUSTERS")
        print("-" * 100)

        clusters_ordenados = sorted(self.clusters,
                                    key=lambda c: (c.qtd_bust, c.qtd_t6_plus, c.qtd_t5_plus),
                                    reverse=True)[:10]

        print(f"\n  {'#':<4} {'Gatilho':<10} {'T5+':<6} {'T6+':<6} {'Cen.B':<6} {'Bust':<6} {'Severidade':<12} {'Pre-Taxa2.0':<12}")
        print("  " + "-" * 80)
        for i, c in enumerate(clusters_ordenados, 1):
            print(f"  {i:<4} {c.inicio_gatilho:<10} {c.qtd_t5_plus:<6} {c.qtd_t6_plus:<6} "
                  f"{c.qtd_cenario_b:<6} {c.qtd_bust:<6} {c.severidade:<12} {c.pre_taxa_altos*100:<11.1f}%")


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    analisador = AnalisadorClusters()
    analisador.carregar_dados(csv_path)
    analisador.processar_gatilhos()
    analisador.identificar_clusters()
    analisador.analisar_pre_clusters()
    analisador.gerar_relatorio()
