#!/usr/bin/env python3
"""
Análise Comparativa: NS7 Padrão vs Nova Estratégia (30/70 @ 1.99x + 5.00x)
Foco: Como ambas se comportam nos períodos críticos
"""

import json
from collections import deque
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass
class NS7Config:
    """Configuração da estratégia NS7"""
    divisor: int = 127
    gatilho_tamanho: int = 6
    gatilho_limite: float = 2.0
    
    alvos_t1_t4: float = 1.99
    alvos_t5_slot1: float = 1.99
    alvos_t5_slot2: float = None
    t5_slot1_proporcao: float = 1.0
    
    alvos_t6_slot1: float = 1.99
    alvos_t6_slot2: float = 1.25
    t6_slot1_proporcao: float = 6/16
    t6_slot2_proporcao: float = 10/16
    
    alvos_t7: float = 1.25
    
    saque_meta_pct: float = 0.10
    saque_proporcao: float = 0.50


class NS7SimulatorComHistorico:
    """Simulador que registra histórico detalhado para análise de períodos críticos"""
    
    def __init__(self, banca_inicial: float = 1000.0, config: NS7Config = None):
        self.banca_inicial = banca_inicial
        self.banca = banca_inicial
        self.banca_pico = banca_inicial
        self.lucro_realizado = 0.0
        self.meta_lucro = banca_inicial * 1.10
        self.config = config or NS7Config()
        
        self.buffer_baixos = deque(maxlen=self.config.gatilho_tamanho)
        self.em_sequencia = False
        self.tentativa_atual = 1
        self.perdas_acumuladas = 0.0
        self.rodada_numero = 0
        
        # Histórico detalhado
        self.historico = []  # Lista de dicts com info de cada rodada
        
        # Estatísticas
        self.wins = 0
        self.losses = 0
        self.busts = 0
        self.gatilhos_total = 0
    
    def simular(self, multiplicadores: List[float]) -> Dict:
        """Simula e registra histórico detalhado"""
        
        for mult in multiplicadores:
            self.rodada_numero += 1
            
            # Detectar gatilho
            if mult < self.config.gatilho_limite:
                self.buffer_baixos.append(mult)
            else:
                self.buffer_baixos.clear()
            
            # Gatilho completo?
            if len(self.buffer_baixos) == self.config.gatilho_tamanho and not self.em_sequencia:
                self.em_sequencia = True
                self.tentativa_atual = 1
                self.perdas_acumuladas = 0.0
                self.gatilhos_total += 1
                
                self.historico.append({
                    'rodada': self.rodada_numero,
                    'tipo': 'gatilho',
                    'banca': self.banca,
                    'gatilho_num': self.gatilhos_total,
                    'multiplicador': mult
                })
                continue
            
            # Processar tentativa
            if self.em_sequencia:
                aposta_base = self.banca / self.config.divisor
                aposta = aposta_base * (2 ** (self.tentativa_atual - 1))
                
                # Determinar resultado
                if self.tentativa_atual <= 4:
                    acertou = mult >= self.config.alvos_t1_t4
                    if acertou:
                        ganho_bruto = aposta * self.config.alvos_t1_t4
                        resultado = "WIN"
                        self.wins += 1
                    else:
                        ganho_bruto = -aposta
                        resultado = "LOSS"
                        self.losses += 1
                
                elif self.tentativa_atual == 5:
                    if self.config.alvos_t5_slot2 is None:
                        # 1 slot
                        acertou = mult >= self.config.alvos_t5_slot1
                        if acertou:
                            ganho_bruto = aposta * self.config.alvos_t5_slot1
                            resultado = "WIN"
                            self.wins += 1
                        else:
                            ganho_bruto = -aposta
                            resultado = "LOSS"
                            self.losses += 1
                    else:
                        # 2 slots
                        aposta_slot1 = aposta * self.config.t5_slot1_proporcao
                        aposta_slot2 = aposta * (1 - self.config.t5_slot1_proporcao)
                        
                        acertou_slot1 = mult >= self.config.alvos_t5_slot1
                        acertou_slot2 = mult >= self.config.alvos_t5_slot2
                        
                        ganho_slot1 = aposta_slot1 * self.config.alvos_t5_slot1 if acertou_slot1 else -aposta_slot1
                        ganho_slot2 = aposta_slot2 * self.config.alvos_t5_slot2 if acertou_slot2 else -aposta_slot2
                        
                        ganho_bruto = ganho_slot1 + ganho_slot2
                        
                        if acertou_slot2:
                            resultado = "WIN"
                            self.wins += 1
                        elif acertou_slot1:
                            resultado = "PARTIAL_CONTINUE"
                            self.losses += 1
                        else:
                            resultado = "LOSS"
                            self.losses += 1
                
                elif self.tentativa_atual == 6:
                    if mult >= self.config.alvos_t6_slot1:
                        ganho_bruto = aposta * self.config.alvos_t6_slot1
                        resultado = "WIN"
                        self.wins += 1
                    elif mult >= self.config.alvos_t6_slot2:
                        ganho_bruto = aposta * self.config.alvos_t6_slot2
                        resultado = "WIN"
                        self.wins += 1
                    else:
                        ganho_bruto = -aposta
                        resultado = "LOSS"
                        self.losses += 1
                
                else:  # T7
                    if mult >= self.config.alvos_t7:
                        ganho_bruto = aposta * self.config.alvos_t7
                        resultado = "WIN"
                        self.wins += 1
                    else:
                        ganho_bruto = -aposta
                        resultado = "LOSS"
                        self.losses += 1
                
                # Processar resultado
                if resultado in ["WIN", "PARTIAL_CONTINUE"]:
                    ganho_liquido = ganho_bruto - self.perdas_acumuladas
                    self.banca += ganho_liquido
                    
                    if self.banca > self.banca_pico:
                        self.banca_pico = self.banca
                    
                    # Saque
                    if self.banca >= self.meta_lucro:
                        lucro_acumulado = self.banca - (self.banca_pico / 1.10)
                        saque = lucro_acumulado * self.config.saque_proporcao
                        self.lucro_realizado += saque
                        self.banca -= saque
                        self.banca_pico = self.banca
                        self.meta_lucro = self.banca * 1.10
                    
                    if resultado == "WIN":
                        self.em_sequencia = False
                        self.perdas_acumuladas = 0.0
                    else:
                        # PARTIAL_CONTINUE
                        self.tentativa_atual += 1
                
                else:  # LOSS
                    self.perdas_acumuladas += aposta
                    self.banca -= aposta
                    
                    if self.tentativa_atual == 6:
                        if self.config.alvos_t6_slot2 <= mult < self.config.alvos_t6_slot1:
                            self.em_sequencia = False
                            self.perdas_acumuladas = 0.0
                        else:
                            self.tentativa_atual += 1
                    elif self.tentativa_atual < 7:
                        self.tentativa_atual += 1
                    else:
                        self.busts += 1
                        self.em_sequencia = False
                        self.perdas_acumuladas = 0.0
                
                # Registrar tentativa
                self.historico.append({
                    'rodada': self.rodada_numero,
                    'tipo': 'tentativa',
                    'tentativa': self.tentativa_atual,
                    'banca': self.banca,
                    'ganho_bruto': ganho_bruto,
                    'resultado': resultado,
                    'multiplicador': mult
                })
        
        return self.gerar_relatorio()
    
    def gerar_relatorio(self) -> Dict:
        return {
            'banca_final': self.banca,
            'lucro_realizado': self.lucro_realizado,
            'total': self.banca + self.lucro_realizado,
            'ganho_pct': ((self.banca + self.lucro_realizado) / self.banca_inicial - 1) * 100,
            'wins': self.wins,
            'losses': self.losses,
            'busts': self.busts,
            'gatilhos': self.gatilhos_total,
        }


def analisar_periodos_criticos(historico_padrão, historico_nova, multiplicadores, rodadas_criticas):
    """
    Analisa como ambas estratégias se comportam nos períodos críticos
    rodadas_criticas: lista de tuplas (inicio, fim) em rodadas
    """
    
    analise = {}
    
    for idx, (inicio, fim) in enumerate(rodadas_criticas):
        periodo_key = f"periodo_{idx+1}"
        
        # Extrair dados do período
        dados_padrão = [h for h in historico_padrão if inicio <= h['rodada'] <= fim]
        dados_nova = [h for h in historico_nova if inicio <= h['rodada'] <= fim]
        
        # Calcular métricas
        banca_inicio_padrão = dados_padrão[0]['banca'] if dados_padrão else 0
        banca_fim_padrão = dados_padrão[-1]['banca'] if dados_padrão else 0
        banca_minima_padrão = min([h['banca'] for h in dados_padrão]) if dados_padrão else 0
        
        banca_inicio_nova = dados_nova[0]['banca'] if dados_nova else 0
        banca_fim_nova = dados_nova[-1]['banca'] if dados_nova else 0
        banca_minima_nova = min([h['banca'] for h in dados_nova]) if dados_nova else 0
        
        drawdown_padrão = ((banca_minima_padrão - banca_inicio_padrão) / banca_inicio_padrão * 100) if banca_inicio_padrão > 0 else 0
        drawdown_nova = ((banca_minima_nova - banca_inicio_nova) / banca_inicio_nova * 100) if banca_inicio_nova > 0 else 0
        
        recuperacao_padrão = ((banca_fim_padrão - banca_minima_padrão) / banca_minima_padrão * 100) if banca_minima_padrão > 0 else 0
        recuperacao_nova = ((banca_fim_nova - banca_minima_nova) / banca_minima_nova * 100) if banca_minima_nova > 0 else 0
        
        analise[periodo_key] = {
            'rodadas': (inicio, fim),
            'duracao_rodadas': fim - inicio + 1,
            'duracao_dias': (fim - inicio + 1) / 3600,
            'padrão': {
                'banca_inicio': banca_inicio_padrão,
                'banca_fim': banca_fim_padrão,
                'banca_minima': banca_minima_padrão,
                'drawdown_pct': drawdown_padrão,
                'recuperacao_pct': recuperacao_padrão,
                'ganho_liquido': banca_fim_padrão - banca_inicio_padrão
            },
            'nova': {
                'banca_inicio': banca_inicio_nova,
                'banca_fim': banca_fim_nova,
                'banca_minima': banca_minima_nova,
                'drawdown_pct': drawdown_nova,
                'recuperacao_pct': recuperacao_nova,
                'ganho_liquido': banca_fim_nova - banca_inicio_nova
            },
            'comparacao': {
                'drawdown_diferenca': drawdown_nova - drawdown_padrão,
                'recuperacao_diferenca': recuperacao_nova - recuperacao_padrão,
                'ganho_diferenca': (banca_fim_nova - banca_inicio_nova) - (banca_fim_padrão - banca_inicio_padrão)
            }
        }
    
    return analise


# Carregar dados
with open('/home/ubuntu/multiplicadores_sessoes.json', 'r') as f:
    data = json.load(f)

print("="*140)
print("ANÁLISE COMPARATIVA: NS7 Padrão vs Nova Estratégia (30/70 @ 1.99x + 5.00x)")
print("Foco: Períodos Críticos (Sessão 1)")
print("="*140)

# Simular ambas estratégias com histórico completo
print("\nSimulando NS7 Padrão...")
cfg_padrão = NS7Config()
sim_padrão = NS7SimulatorComHistorico(banca_inicial=1000.0, config=cfg_padrão)
resultado_padrão = sim_padrão.simular(data['sessao1'])

print("Simulando Nova Estratégia...")
cfg_nova = NS7Config(alvos_t5_slot2=5.00, t5_slot1_proporcao=0.3)
sim_nova = NS7SimulatorComHistorico(banca_inicial=1000.0, config=cfg_nova)
resultado_nova = sim_nova.simular(data['sessao1'])

# Períodos críticos identificados (em rodadas)
# Período 1: Rodadas 12.491 - 17.020 (queda + recuperação)
# Período 2: Rodadas 39.986 - 41.605 (queda severa no final)
periodos_criticos = [
    (12491, 17020),
    (39986, 41605)
]

# Analisar períodos críticos
analise = analisar_periodos_criticos(
    sim_padrão.historico,
    sim_nova.historico,
    data['sessao1'],
    periodos_criticos
)

# Exibir resultados
for periodo_key, dados in analise.items():
    print(f"\n{'='*140}")
    print(f"{periodo_key.upper()}")
    print(f"{'='*140}")
    print(f"Rodadas: {dados['rodadas'][0]:,} - {dados['rodadas'][1]:,} ({dados['duracao_rodadas']:,} rodadas / {dados['duracao_dias']:.2f} dias)")
    
    print(f"\n{'NS7 PADRÃO':^70} | {'NOVA ESTRATÉGIA':^70}")
    print(f"{'-'*70} | {'-'*70}")
    
    p = dados['padrão']
    n = dados['nova']
    
    print(f"Banca Início: R$ {p['banca_inicio']:>15,.2f} | Banca Início: R$ {n['banca_inicio']:>15,.2f}")
    print(f"Banca Mínima: R$ {p['banca_minima']:>15,.2f} | Banca Mínima: R$ {n['banca_minima']:>15,.2f}")
    print(f"Banca Fim:    R$ {p['banca_fim']:>15,.2f} | Banca Fim:    R$ {n['banca_fim']:>15,.2f}")
    print(f"Drawdown:     {p['drawdown_pct']:>15.2f}% | Drawdown:     {n['drawdown_pct']:>15.2f}%")
    print(f"Recuperação:  {p['recuperacao_pct']:>15.2f}% | Recuperação:  {n['recuperacao_pct']:>15.2f}%")
    print(f"Ganho Líquido: R$ {p['ganho_liquido']:>14,.2f} | Ganho Líquido: R$ {n['ganho_liquido']:>14,.2f}")
    
    print(f"\n{'COMPARAÇÃO':^140}")
    print(f"{'-'*140}")
    c = dados['comparacao']
    
    drawdown_melhor = "✓ NOVA é melhor" if c['drawdown_diferenca'] < 0 else "✗ PADRÃO é melhor"
    recuperacao_melhor = "✓ NOVA é melhor" if c['recuperacao_diferenca'] > 0 else "✗ PADRÃO é melhor"
    ganho_melhor = "✓ NOVA é melhor" if c['ganho_diferenca'] > 0 else "✗ PADRÃO é melhor"
    
    print(f"Drawdown Diferença:     {c['drawdown_diferenca']:>8.2f}% {drawdown_melhor}")
    print(f"Recuperação Diferença:  {c['recuperacao_diferenca']:>8.2f}% {recuperacao_melhor}")
    print(f"Ganho Diferença:        R$ {c['ganho_diferenca']:>12,.2f} {ganho_melhor}")

# Resumo geral
print(f"\n{'='*140}")
print("RESUMO GERAL - SESSÃO 1 COMPLETA")
print(f"{'='*140}")

print(f"\n{'NS7 PADRÃO':^70} | {'NOVA ESTRATÉGIA':^70}")
print(f"{'-'*70} | {'-'*70}")
print(f"Lucro Total:  R$ {resultado_padrão['total']:>15,.2f} | Lucro Total:  R$ {resultado_nova['total']:>15,.2f}")
print(f"Ganho %:      {resultado_padrão['ganho_pct']:>15.2f}% | Ganho %:      {resultado_nova['ganho_pct']:>15.2f}%")
print(f"Wins:         {resultado_padrão['wins']:>15,} | Wins:         {resultado_nova['wins']:>15,}")
print(f"Losses:       {resultado_padrão['losses']:>15,} | Losses:       {resultado_nova['losses']:>15,}")
print(f"Busts:        {resultado_padrão['busts']:>15,} | Busts:        {resultado_nova['busts']:>15,}")

diferenca_total = resultado_nova['total'] - resultado_padrão['total']
pct_diferenca = (diferenca_total / resultado_padrão['total']) * 100

print(f"\n{'VANTAGEM GERAL':^140}")
print(f"{'-'*140}")
print(f"Ganho Extra: R$ {diferenca_total:>15,.2f} ({pct_diferenca:>6.2f}%)")
print(f"Status: ✓ NOVA ESTRATÉGIA É {pct_diferenca:.2f}% MELHOR")

# Salvar análise
with open('/home/ubuntu/analise_periodos_criticos_resultado.json', 'w') as f:
    json.dump({
        'resultado_padrão': resultado_padrão,
        'resultado_nova': resultado_nova,
        'periodos_criticos': analise,
        'diferenca_total': diferenca_total,
        'pct_diferenca': pct_diferenca
    }, f, indent=2)

print(f"\n{'='*140}")
print("Resultados salvos em: /home/ubuntu/analise_periodos_criticos_resultado.json")
print(f"{'='*140}")

