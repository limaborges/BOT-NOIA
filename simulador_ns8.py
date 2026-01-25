#!/usr/bin/env python3
"""
Simulador NS8 - Estrategia V4 Atualizada
Configuracao: Defesa 1.10x, Divisor 255

NS8:
- T1-T6: 1 slot @ 1.99x (6 tentativas de lucro)
- T7:    2 slots (6/16 @ 1.99x + 10/16 @ 1.10x) -> PARAR cenario B
- T8:    2 slots (12/32 @ 2.50x + 20/32 @ 1.10x) -> ULTIMA

Comparativo com NS7:
- T1-T5: 1 slot @ 1.99x (5 tentativas de lucro)
- T6:    2 slots (6/16 @ 1.99x + 10/16 @ 1.10x) -> PARAR cenario B
- T7:    2 slots (12/32 @ 2.50x + 20/32 @ 1.10x) -> ULTIMA
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
from datetime import datetime

# ==============================================================================
# CONSTANTES
# ==============================================================================

# Alvos
ALVO_LUCRO = 1.99
ALVO_DEFESA = 1.10      # Defesa agressiva (NS7_PURO style)
ALVO_ULTIMA = 2.50

# Niveis
NIVEIS = {
    7: {'nome': 'NS7', 'divisor': 127, 'tentativas': 7},
    8: {'nome': 'NS8', 'divisor': 255, 'tentativas': 8},
}

# ==============================================================================
# CONFIGURACAO DE TENTATIVAS - ESTRATEGIA V4 ATUALIZADA
# ==============================================================================

@dataclass
class SlotConfig:
    proporcao: float  # Ex: 6/16 = 0.375
    alvo: float

@dataclass
class TentativaConfig:
    slots: List[SlotConfig]
    parar_cenario_b: bool = False
    is_ultima: bool = False

    @property
    def is_2_slots(self) -> bool:
        return len(self.slots) == 2

    @property
    def alvo_alto(self) -> float:
        return max(s.alvo for s in self.slots)

    @property
    def alvo_baixo(self) -> float:
        return min(s.alvo for s in self.slots)


def get_config_tentativa(nivel: int, tentativa: int) -> TentativaConfig:
    """
    Retorna configuracao da tentativa para estrategia V4 com defesa 1.10x.

    NS7: T1-T5 @ 1.99x, T6 = 2 slots PARAR, T7 = 2 slots ultima
    NS8: T1-T6 @ 1.99x, T7 = 2 slots PARAR, T8 = 2 slots ultima
    """
    max_t = NIVEIS[nivel]['tentativas']
    is_ultima = (tentativa == max_t)
    is_penultima = (tentativa == max_t - 1)

    # ULTIMA: 2 slots (12/32 @ 2.50x + 20/32 @ 1.10x)
    if is_ultima:
        return TentativaConfig(
            slots=[
                SlotConfig(12/32, ALVO_ULTIMA),   # 37.5% @ 2.50x
                SlotConfig(20/32, ALVO_DEFESA)    # 62.5% @ 1.10x
            ],
            is_ultima=True
        )

    # PENULTIMA: 2 slots (6/16 @ 1.99x + 10/16 @ 1.10x) - PARAR cenario B
    if is_penultima:
        return TentativaConfig(
            slots=[
                SlotConfig(6/16, ALVO_LUCRO),     # 37.5% @ 1.99x
                SlotConfig(10/16, ALVO_DEFESA)    # 62.5% @ 1.10x
            ],
            parar_cenario_b=True
        )

    # T1 ate pen-penultima: 1 slot @ 1.99x
    return TentativaConfig(
        slots=[SlotConfig(1.0, ALVO_LUCRO)]
    )


# ==============================================================================
# CENARIOS
# ==============================================================================

class Cenario(Enum):
    A = "A"      # Ambos ganham (mult >= alvo_alto)
    B = "B"      # So defesa ganha (alvo_baixo <= mult < alvo_alto)
    C = "C"      # Ambos perdem (mult < alvo_baixo)
    WIN = "WIN"  # 1 slot ganhou
    LOSS = "LOSS"  # 1 slot perdeu


def detectar_cenario(mult: float, config: TentativaConfig) -> Cenario:
    if not config.is_2_slots:
        return Cenario.WIN if mult >= config.slots[0].alvo else Cenario.LOSS

    if mult >= config.alvo_alto:
        return Cenario.A
    elif mult >= config.alvo_baixo:
        return Cenario.B
    else:
        return Cenario.C


# ==============================================================================
# SIMULADOR
# ==============================================================================

class Simulador:
    def __init__(
        self,
        banca_inicial: float = 1000.0,
        nivel: int = 8,
        redeposit_ativo: bool = False,
        redeposit_valor: float = None
    ):
        self.banca_inicial = banca_inicial
        self.banca = banca_inicial
        self.nivel = nivel
        self.divisor = NIVEIS[nivel]['divisor']
        self.max_tentativas = NIVEIS[nivel]['tentativas']

        # Redeposit
        self.redeposit_ativo = redeposit_ativo
        self.redeposit_valor = redeposit_valor or banca_inicial
        self.total_depositado = banca_inicial
        self.total_redeposits = 0

        # Estado
        self.baixos_consecutivos = 0
        self.em_sequencia = False
        self.tentativa_atual = 0
        self.perdas_acumuladas = 0.0
        self.aposta_base = 0.0

        # Estatisticas
        self.gatilhos = 0
        self.wins = 0
        self.wins_t1_t4 = 0  # NS7: T1-T5, NS8: T1-T6
        self.wins_penultima = 0
        self.wins_ultima = 0
        self.paradas = 0  # Cenario B na penultima
        self.busts = 0

        # Tracking
        self.rodadas = 0
        self.banca_maxima = banca_inicial
        self.banca_minima = banca_inicial
        self.drawdown_maximo = 0.0

        # Distribuicao de wins por tentativa
        self.wins_por_tentativa = {i: 0 for i in range(1, 11)}

    def _calcular_ganho_slot(self, valor: float, alvo: float, mult: float) -> float:
        """Ganho baseado no ALVO, nao no multiplicador"""
        if mult >= alvo:
            return valor * (alvo - 1)
        return -valor

    def processar(self, mult: float) -> Optional[Dict]:
        self.rodadas += 1
        resultado = None

        if not self.em_sequencia:
            # Aguardando gatilho
            if mult < 2.0:
                self.baixos_consecutivos += 1
                if self.baixos_consecutivos == 6:
                    # GATILHO!
                    self.gatilhos += 1
                    self.em_sequencia = True
                    self.tentativa_atual = 1
                    self.perdas_acumuladas = 0.0
                    self.baixos_consecutivos = 0
                    self.aposta_base = self.banca / self.divisor
                    resultado = {'evento': 'gatilho', 'num': self.gatilhos}
            else:
                self.baixos_consecutivos = 0

            self._atualizar_tracking()
            return resultado

        # EM SEQUENCIA - processar tentativa
        config = get_config_tentativa(self.nivel, self.tentativa_atual)
        mult_aposta = 2 ** (self.tentativa_atual - 1)
        valor_total = self.aposta_base * mult_aposta

        cenario = detectar_cenario(mult, config)

        # Calcular ganho
        if config.is_2_slots:
            v1 = valor_total * config.slots[0].proporcao
            v2 = valor_total * config.slots[1].proporcao
            g1 = self._calcular_ganho_slot(v1, config.slots[0].alvo, mult)
            g2 = self._calcular_ganho_slot(v2, config.slots[1].alvo, mult)
            ganho = g1 + g2
        else:
            ganho = self._calcular_ganho_slot(valor_total, config.slots[0].alvo, mult)

        # Processar cenario
        if cenario in [Cenario.WIN, Cenario.A]:
            # WIN!
            self.banca += ganho
            self.wins += 1
            self.wins_por_tentativa[self.tentativa_atual] += 1

            # Categorizar
            if self.tentativa_atual <= self.max_tentativas - 2:
                self.wins_t1_t4 += 1
            elif self.tentativa_atual == self.max_tentativas - 1:
                self.wins_penultima += 1
            else:
                self.wins_ultima += 1

            self._finalizar_sequencia()
            resultado = {'evento': 'win', 'tentativa': self.tentativa_atual, 'ganho': ganho}

        elif cenario == Cenario.B:
            if config.parar_cenario_b:
                # PARAR - aceitar perda parcial
                self.banca += ganho
                self.paradas += 1
                self._finalizar_sequencia()
                resultado = {'evento': 'parar', 'tentativa': self.tentativa_atual, 'ganho': ganho}
            else:
                # Continuar (nao deveria acontecer com config atual)
                self.banca += ganho
                self.perdas_acumuladas += (-ganho if ganho < 0 else 0)
                self.tentativa_atual += 1

        elif cenario in [Cenario.C, Cenario.LOSS]:
            if config.is_ultima:
                # BUST
                self.banca += ganho
                self.busts += 1
                self._finalizar_sequencia()

                # Redeposit se necessario
                if self.redeposit_ativo and self.banca < self.redeposit_valor * 0.1:
                    self.banca = self.redeposit_valor
                    self.total_depositado += self.redeposit_valor
                    self.total_redeposits += 1

                resultado = {'evento': 'bust', 'tentativa': self.tentativa_atual}
            else:
                # Proxima tentativa
                self.banca += ganho
                self.perdas_acumuladas += valor_total
                self.tentativa_atual += 1

        self._atualizar_tracking()
        return resultado

    def _finalizar_sequencia(self):
        self.em_sequencia = False
        self.tentativa_atual = 0
        self.perdas_acumuladas = 0.0

    def _atualizar_tracking(self):
        if self.banca > self.banca_maxima:
            self.banca_maxima = self.banca
        if self.banca < self.banca_minima:
            self.banca_minima = self.banca
        if self.banca_maxima > 0:
            dd = (self.banca_maxima - self.banca) / self.banca_maxima
            if dd > self.drawdown_maximo:
                self.drawdown_maximo = dd

    def simular(self, multiplicadores: List[float]) -> Dict:
        for mult in multiplicadores:
            self.processar(mult)
        return self.relatorio()

    def relatorio(self) -> Dict:
        lucro = self.banca - self.total_depositado
        ganho_pct = (lucro / self.banca_inicial) * 100

        return {
            'nivel': f"NS{self.nivel}",
            'divisor': self.divisor,
            'defesa': ALVO_DEFESA,
            'banca_inicial': self.banca_inicial,
            'banca_final': self.banca,
            'lucro': lucro,
            'ganho_pct': ganho_pct,
            'gatilhos': self.gatilhos,
            'wins': self.wins,
            'wins_lucro': self.wins_t1_t4,  # T1-T6 para NS8
            'wins_penultima': self.wins_penultima,
            'wins_ultima': self.wins_ultima,
            'paradas': self.paradas,
            'busts': self.busts,
            'drawdown_max_pct': self.drawdown_maximo * 100,
            'rodadas': self.rodadas,
            'total_depositado': self.total_depositado,
            'redeposits': self.total_redeposits,
            'wins_por_tentativa': self.wins_por_tentativa
        }


# ==============================================================================
# CARREGAMENTO DE DADOS
# ==============================================================================

def carregar_multiplicadores(filepath: str) -> List[float]:
    """Carrega multiplicadores do CSV unificado"""
    multiplicadores = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)  # Skip header
        for line in f:
            try:
                parts = line.strip().split(',')
                if parts:
                    mult = float(parts[0])
                    multiplicadores.append(mult)
            except:
                continue
    return multiplicadores


# ==============================================================================
# COMPARATIVO NS7 vs NS8
# ==============================================================================

def comparar_ns7_ns8(multiplicadores: List[float], banca: float = 1000.0):
    """Compara NS7 vs NS8 com mesma configuracao de defesa 1.10x"""

    print("\n" + "=" * 80)
    print("COMPARATIVO NS7 vs NS8 - Defesa 1.10x")
    print("=" * 80)
    print(f"Multiplicadores: {len(multiplicadores):,}")
    print(f"Banca inicial: R$ {banca:,.2f}")
    print(f"Defesa: {ALVO_DEFESA}x")

    # NS7
    sim7 = Simulador(banca_inicial=banca, nivel=7, redeposit_ativo=False)
    rel7 = sim7.simular(multiplicadores)

    # NS8
    sim8 = Simulador(banca_inicial=banca, nivel=8, redeposit_ativo=False)
    rel8 = sim8.simular(multiplicadores)

    # Resultados
    print("\n" + "-" * 80)
    print(f"{'Metrica':<30} {'NS7':>20} {'NS8':>20}")
    print("-" * 80)

    print(f"{'Divisor':<30} {rel7['divisor']:>20} {rel8['divisor']:>20}")
    print(f"{'Tentativas':<30} {7:>20} {8:>20}")
    print(f"{'Tent. lucro (@ 1.99x)':<30} {'T1-T5':>20} {'T1-T6':>20}")

    print("-" * 80)
    print(f"{'Banca Final':<30} R$ {rel7['banca_final']:>16,.2f} R$ {rel8['banca_final']:>16,.2f}")
    print(f"{'Lucro':<30} R$ {rel7['lucro']:>16,.2f} R$ {rel8['lucro']:>16,.2f}")
    print(f"{'Ganho %':<30} {rel7['ganho_pct']:>19.2f}% {rel8['ganho_pct']:>19.2f}%")
    print(f"{'Drawdown Max':<30} {rel7['drawdown_max_pct']:>19.2f}% {rel8['drawdown_max_pct']:>19.2f}%")

    print("-" * 80)
    print(f"{'Gatilhos':<30} {rel7['gatilhos']:>20,} {rel8['gatilhos']:>20,}")
    print(f"{'Wins Total':<30} {rel7['wins']:>20,} {rel8['wins']:>20,}")
    print(f"{'Wins T1-T5/T6 (lucro)':<30} {rel7['wins_lucro']:>20,} {rel8['wins_lucro']:>20,}")
    print(f"{'Wins Penultima':<30} {rel7['wins_penultima']:>20,} {rel8['wins_penultima']:>20,}")
    print(f"{'Wins Ultima':<30} {rel7['wins_ultima']:>20,} {rel8['wins_ultima']:>20,}")
    print(f"{'Paradas (Cen.B)':<30} {rel7['paradas']:>20,} {rel8['paradas']:>20,}")
    print(f"{'Busts':<30} {rel7['busts']:>20,} {rel8['busts']:>20,}")

    print("-" * 80)

    # Taxa de sucesso
    if rel7['gatilhos'] > 0 and rel8['gatilhos'] > 0:
        taxa7 = (rel7['wins'] + rel7['paradas']) / rel7['gatilhos'] * 100
        taxa8 = (rel8['wins'] + rel8['paradas']) / rel8['gatilhos'] * 100
        bust7 = rel7['busts'] / rel7['gatilhos'] * 100
        bust8 = rel8['busts'] / rel8['gatilhos'] * 100

        print(f"{'Taxa Sucesso':<30} {taxa7:>19.2f}% {taxa8:>19.2f}%")
        print(f"{'Taxa Bust':<30} {bust7:>19.2f}% {bust8:>19.2f}%")

    print("-" * 80)

    # Distribuicao de wins
    print("\nDistribuicao de Wins por Tentativa:")
    print("-" * 50)
    for t in range(1, 9):
        w7 = rel7['wins_por_tentativa'].get(t, 0)
        w8 = rel8['wins_por_tentativa'].get(t, 0)
        if t <= 7:
            print(f"  T{t}: NS7={w7:>6,}  NS8={w8:>6,}")
        else:
            print(f"  T{t}: NS7={'-':>6}  NS8={w8:>6,}")

    return rel7, rel8


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    import sys

    # Arquivo de dados
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("=" * 80)
    print("SIMULADOR NS8 - Estrategia V4 com Defesa 1.10x")
    print("=" * 80)

    print(f"\nCarregando: {csv_path}")
    multiplicadores = carregar_multiplicadores(csv_path)
    print(f"Total: {len(multiplicadores):,} multiplicadores")

    if len(multiplicadores) == 0:
        print("ERRO: Nenhum multiplicador carregado!")
        sys.exit(1)

    # Comparativo
    comparar_ns7_ns8(multiplicadores, banca=1000.0)

    print("\n" + "=" * 80)
    print("Simulacao concluida!")
    print("=" * 80)
