#!/usr/bin/env python3
"""
Simulador NS8 COMPLETO - Fiel a Estrategia V4
- Compound real (aposta base recalculada a cada gatilho)
- Analise de cenarios A/B/C
- Defesa 1.10x
- Periodo: 08/01/2026 a 20/01/2026
- Banca: R$ 1000
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

# ==============================================================================
# CONSTANTES - ESTRATEGIA V4 COM DEFESA 1.10x
# ==============================================================================

ALVO_LUCRO = 1.99
ALVO_DEFESA = 1.10
ALVO_ULTIMA = 2.50
GATILHO_BAIXOS = 6
THRESHOLD_BAIXO = 2.0

NIVEIS = {
    7: {'nome': 'NS7', 'divisor': 127, 'tentativas': 7},
    8: {'nome': 'NS8', 'divisor': 255, 'tentativas': 8},
}

# ==============================================================================
# CENARIOS
# ==============================================================================

class Cenario(Enum):
    A = "A"      # mult >= alvo_alto (ambos slots ganham)
    B = "B"      # alvo_baixo <= mult < alvo_alto (so defesa ganha)
    C = "C"      # mult < alvo_baixo (ambos perdem)
    WIN = "WIN"  # 1 slot, ganhou
    LOSS = "LOSS"  # 1 slot, perdeu


# ==============================================================================
# CONFIGURACAO DE TENTATIVAS
# ==============================================================================

@dataclass
class SlotConfig:
    proporcao: float
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
    Configuracao V4 com defesa 1.10x

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
                SlotConfig(12/32, ALVO_ULTIMA),
                SlotConfig(20/32, ALVO_DEFESA)
            ],
            is_ultima=True
        )

    # PENULTIMA: 2 slots (6/16 @ 1.99x + 10/16 @ 1.10x) - PARAR cenario B
    if is_penultima:
        return TentativaConfig(
            slots=[
                SlotConfig(6/16, ALVO_LUCRO),
                SlotConfig(10/16, ALVO_DEFESA)
            ],
            parar_cenario_b=True
        )

    # T1 ate pen-penultima: 1 slot @ 1.99x
    return TentativaConfig(
        slots=[SlotConfig(1.0, ALVO_LUCRO)]
    )


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
# SIMULADOR COMPLETO COM COMPOUND
# ==============================================================================

class SimuladorCompleto:
    def __init__(self, banca_inicial: float, nivel: int):
        self.banca_inicial = banca_inicial
        self.banca = banca_inicial
        self.nivel = nivel
        self.divisor = NIVEIS[nivel]['divisor']
        self.max_tentativas = NIVEIS[nivel]['tentativas']

        # Estado do gatilho
        self.baixos_consecutivos = 0
        self.em_sequencia = False
        self.tentativa_atual = 0
        self.aposta_base = 0.0  # Calculado no inicio de cada gatilho (COMPOUND!)

        # Estatisticas
        self.rodadas = 0
        self.gatilhos = 0
        self.wins = 0
        self.paradas = 0
        self.busts = 0

        # Por tentativa (até 15 para segurança)
        self.wins_por_tentativa = {i: 0 for i in range(1, 16)}

        # Por cenario
        self.cenarios = {'A': 0, 'B': 0, 'C': 0, 'WIN': 0, 'LOSS': 0}

        # Tracking
        self.banca_maxima = banca_inicial
        self.banca_minima = banca_inicial
        self.drawdown_maximo = 0.0

        # Historico detalhado
        self.historico_gatilhos = []

    def _calcular_ganho(self, valor: float, alvo: float, mult: float) -> float:
        """Calcula ganho baseado no ALVO"""
        if mult >= alvo:
            return valor * (alvo - 1)
        return -valor

    def processar(self, mult: float) -> Optional[Dict]:
        self.rodadas += 1

        if not self.em_sequencia:
            return self._processar_aguardando(mult)
        else:
            return self._processar_sequencia(mult)

    def _processar_aguardando(self, mult: float) -> Optional[Dict]:
        """Aguardando gatilho de 6 baixos"""
        if mult < THRESHOLD_BAIXO:
            self.baixos_consecutivos += 1

            if self.baixos_consecutivos == GATILHO_BAIXOS:
                # GATILHO ATIVADO!
                self.gatilhos += 1
                self.em_sequencia = True
                self.tentativa_atual = 1
                self.baixos_consecutivos = 0

                # COMPOUND: Calcular aposta base com banca ATUAL
                self.aposta_base = self.banca / self.divisor

                self._atualizar_tracking()
                return {
                    'evento': 'gatilho',
                    'num': self.gatilhos,
                    'banca': self.banca,
                    'aposta_base': self.aposta_base
                }
        else:
            self.baixos_consecutivos = 0

        self._atualizar_tracking()
        return None

    def _processar_sequencia(self, mult: float) -> Dict:
        """Processar tentativa em sequencia ativa"""
        config = get_config_tentativa(self.nivel, self.tentativa_atual)
        mult_aposta = 2 ** (self.tentativa_atual - 1)
        valor_total = self.aposta_base * mult_aposta

        # Detectar cenario
        cenario = detectar_cenario(mult, config)
        self.cenarios[cenario.value] += 1

        # Calcular ganho/perda
        if config.is_2_slots:
            v1 = valor_total * config.slots[0].proporcao
            v2 = valor_total * config.slots[1].proporcao
            g1 = self._calcular_ganho(v1, config.slots[0].alvo, mult)
            g2 = self._calcular_ganho(v2, config.slots[1].alvo, mult)
            ganho = g1 + g2
        else:
            ganho = self._calcular_ganho(valor_total, config.slots[0].alvo, mult)

        resultado = {
            'tentativa': self.tentativa_atual,
            'mult': mult,
            'cenario': cenario.value,
            'valor_aposta': valor_total,
            'ganho': ganho,
            'is_2_slots': config.is_2_slots
        }

        # ===== PROCESSAR POR CENARIO =====

        # CENARIO A ou WIN: Ambos ganham / slot unico ganha
        if cenario in [Cenario.A, Cenario.WIN]:
            self.banca += ganho
            self.wins += 1
            self.wins_por_tentativa[self.tentativa_atual] += 1
            self._finalizar_gatilho('win', resultado)
            resultado['evento'] = 'win'
            resultado['banca'] = self.banca

        # CENARIO B: So slot de defesa ganha (1.10 <= mult < 1.99 ou 2.50)
        elif cenario == Cenario.B:
            self.banca += ganho  # Ganho parcial (slot1 perde, slot2 ganha)

            if config.parar_cenario_b:
                # PARAR - Aceitar perda parcial, nao ir para ultima
                self.paradas += 1
                self._finalizar_gatilho('parar', resultado)
                resultado['evento'] = 'parar'
                resultado['banca'] = self.banca
                resultado['info'] = 'Cenario B - PARAR (evita ultima)'
            elif config.is_ultima:
                # ULTIMA TENTATIVA com Cenario B = WIN parcial (defesa salvou!)
                self.wins += 1
                self.wins_por_tentativa[self.tentativa_atual] += 1
                self._finalizar_gatilho('win_parcial', resultado)
                resultado['evento'] = 'win_parcial'
                resultado['banca'] = self.banca
                resultado['info'] = 'Cenario B na ultima - defesa salvou!'
            else:
                # Continuar para proxima tentativa
                self.tentativa_atual += 1
                resultado['evento'] = 'continuar'
                resultado['banca'] = self.banca

        # CENARIO C ou LOSS: Ambos perdem / slot unico perde
        elif cenario in [Cenario.C, Cenario.LOSS]:
            self.banca += ganho  # Ganho negativo

            if config.is_ultima:
                # BUST!
                self.busts += 1
                self._finalizar_gatilho('bust', resultado)
                resultado['evento'] = 'bust'
                resultado['banca'] = self.banca
            else:
                # Proxima tentativa
                self.tentativa_atual += 1
                resultado['evento'] = 'loss'
                resultado['banca'] = self.banca

        self._atualizar_tracking()
        return resultado

    def _finalizar_gatilho(self, resultado: str, info: Dict):
        """Finaliza gatilho e registra no historico"""
        self.historico_gatilhos.append({
            'gatilho': self.gatilhos,
            'resultado': resultado,
            'tentativa_final': self.tentativa_atual,
            'banca_final': self.banca,
            'cenario': info.get('cenario'),
            'mult': info.get('mult')
        })
        self.em_sequencia = False
        self.tentativa_atual = 0

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
        lucro = self.banca - self.banca_inicial
        ganho_pct = (lucro / self.banca_inicial) * 100

        # Calcular tentativas de lucro (antes da penultima)
        tent_lucro = self.max_tentativas - 2
        wins_lucro = sum(self.wins_por_tentativa[t] for t in range(1, tent_lucro + 1))
        wins_penultima = self.wins_por_tentativa[self.max_tentativas - 1]
        wins_ultima = self.wins_por_tentativa[self.max_tentativas]

        return {
            'nivel': f"NS{self.nivel}",
            'divisor': self.divisor,
            'max_tentativas': self.max_tentativas,
            'banca_inicial': self.banca_inicial,
            'banca_final': self.banca,
            'lucro': lucro,
            'ganho_pct': ganho_pct,
            'rodadas': self.rodadas,
            'gatilhos': self.gatilhos,
            'wins': self.wins,
            'wins_lucro': wins_lucro,
            'wins_penultima': wins_penultima,
            'wins_ultima': wins_ultima,
            'paradas': self.paradas,
            'busts': self.busts,
            'cenarios': self.cenarios,
            'drawdown_max_pct': self.drawdown_maximo * 100,
            'banca_maxima': self.banca_maxima,
            'banca_minima': self.banca_minima,
            'wins_por_tentativa': dict(self.wins_por_tentativa),
        }


# ==============================================================================
# CARREGAMENTO DE DADOS
# ==============================================================================

def carregar_periodo(filepath: str, data_inicio: str, data_fim: str) -> List[float]:
    """Carrega multiplicadores de um periodo"""
    multiplicadores = []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)  # Skip header

        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()

                    dt = datetime.strptime(data, '%d/%m/%Y')
                    dt_ini = datetime.strptime(data_inicio, '%d/%m/%Y')
                    dt_fim = datetime.strptime(data_fim, '%d/%m/%Y')

                    if dt_ini <= dt <= dt_fim:
                        multiplicadores.append(mult)
            except:
                continue

    return multiplicadores


# ==============================================================================
# COMPARATIVO NS7 vs NS8
# ==============================================================================

def comparar(multiplicadores: List[float], banca: float):
    """Comparativo completo NS7 vs NS8"""

    print("\n" + "=" * 80)
    print("SIMULACAO COMPLETA - NS7 vs NS8")
    print("Estrategia V4 | Defesa 1.10x | Compound Ativo")
    print("=" * 80)

    # NS7
    sim7 = SimuladorCompleto(banca, nivel=7)
    rel7 = sim7.simular(multiplicadores)

    # NS8
    sim8 = SimuladorCompleto(banca, nivel=8)
    rel8 = sim8.simular(multiplicadores)

    # Header
    print(f"\n{'METRICA':<35} {'NS7':>18} {'NS8':>18}")
    print("-" * 75)

    # Config
    print(f"{'Divisor':<35} {rel7['divisor']:>18} {rel8['divisor']:>18}")
    print(f"{'Tentativas':<35} {rel7['max_tentativas']:>18} {rel8['max_tentativas']:>18}")
    print(f"{'Tent. lucro (@ 1.99x)':<35} {'T1-T5':>18} {'T1-T6':>18}")

    # Resultados
    print("-" * 75)
    print(f"{'Banca Inicial':<35} R$ {rel7['banca_inicial']:>14,.2f} R$ {rel8['banca_inicial']:>14,.2f}")
    print(f"{'Banca Final':<35} R$ {rel7['banca_final']:>14,.2f} R$ {rel8['banca_final']:>14,.2f}")
    print(f"{'Lucro':<35} R$ {rel7['lucro']:>14,.2f} R$ {rel8['lucro']:>14,.2f}")
    print(f"{'Ganho %':<35} {rel7['ganho_pct']:>17.2f}% {rel8['ganho_pct']:>17.2f}%")

    # Risco
    print("-" * 75)
    print(f"{'Drawdown Maximo':<35} {rel7['drawdown_max_pct']:>17.2f}% {rel8['drawdown_max_pct']:>17.2f}%")
    print(f"{'Banca Minima':<35} R$ {rel7['banca_minima']:>14,.2f} R$ {rel8['banca_minima']:>14,.2f}")
    print(f"{'Banca Maxima':<35} R$ {rel7['banca_maxima']:>14,.2f} R$ {rel8['banca_maxima']:>14,.2f}")

    # Estatisticas
    print("-" * 75)
    print(f"{'Rodadas':<35} {rel7['rodadas']:>18,} {rel8['rodadas']:>18,}")
    print(f"{'Gatilhos':<35} {rel7['gatilhos']:>18,} {rel8['gatilhos']:>18,}")
    print(f"{'Wins':<35} {rel7['wins']:>18,} {rel8['wins']:>18,}")
    print(f"{'  - Wins Lucro (T1-T5/T6)':<35} {rel7['wins_lucro']:>18,} {rel8['wins_lucro']:>18,}")
    print(f"{'  - Wins Penultima':<35} {rel7['wins_penultima']:>18,} {rel8['wins_penultima']:>18,}")
    print(f"{'  - Wins Ultima':<35} {rel7['wins_ultima']:>18,} {rel8['wins_ultima']:>18,}")
    print(f"{'Paradas (Cenario B)':<35} {rel7['paradas']:>18,} {rel8['paradas']:>18,}")
    print(f"{'Busts':<35} {rel7['busts']:>18,} {rel8['busts']:>18,}")

    # Taxas
    print("-" * 75)
    if rel7['gatilhos'] > 0 and rel8['gatilhos'] > 0:
        taxa7 = (rel7['wins'] + rel7['paradas']) / rel7['gatilhos'] * 100
        taxa8 = (rel8['wins'] + rel8['paradas']) / rel8['gatilhos'] * 100
        bust7 = rel7['busts'] / rel7['gatilhos'] * 100
        bust8 = rel8['busts'] / rel8['gatilhos'] * 100

        print(f"{'Taxa Sucesso (win+parar)':<35} {taxa7:>17.2f}% {taxa8:>17.2f}%")
        print(f"{'Taxa Bust':<35} {bust7:>17.4f}% {bust8:>17.4f}%")

    # Cenarios
    print("-" * 75)
    print("CENARIOS:")
    for cen in ['A', 'B', 'C', 'WIN', 'LOSS']:
        c7 = rel7['cenarios'].get(cen, 0)
        c8 = rel8['cenarios'].get(cen, 0)
        print(f"  Cenario {cen:<25} {c7:>18,} {c8:>18,}")

    # Distribuicao wins
    print("-" * 75)
    print("WINS POR TENTATIVA:")
    for t in range(1, 9):
        w7 = rel7['wins_por_tentativa'].get(t, 0)
        w8 = rel8['wins_por_tentativa'].get(t, 0)
        if t <= 7:
            print(f"  T{t:<30} {w7:>18,} {w8:>18,}")
        else:
            print(f"  T{t:<30} {'-':>18} {w8:>18,}")

    # Conclusao
    print("\n" + "=" * 80)
    print("CONCLUSAO:")
    print("=" * 80)

    diff_lucro = rel8['lucro'] - rel7['lucro']
    diff_pct = rel8['ganho_pct'] - rel7['ganho_pct']
    diff_busts = rel8['busts'] - rel7['busts']
    diff_dd = rel8['drawdown_max_pct'] - rel7['drawdown_max_pct']

    print(f"\nNS8 vs NS7:")
    print(f"  Diferenca Lucro: {'+'if diff_lucro>=0 else ''}R$ {diff_lucro:,.2f}")
    print(f"  Diferenca Ganho: {'+'if diff_pct>=0 else ''}{diff_pct:.2f}%")
    print(f"  Diferenca Busts: {'+'if diff_busts>=0 else ''}{diff_busts}")
    print(f"  Diferenca DD: {'+'if diff_dd>=0 else ''}{diff_dd:.2f}pp")

    if rel8['ganho_pct'] > rel7['ganho_pct'] and rel8['busts'] <= rel7['busts']:
        print("\n  >> NS8 SUPERIOR: Maior lucro com igual ou menos busts")
    elif rel8['ganho_pct'] > rel7['ganho_pct']:
        print(f"\n  >> NS8 mais lucrativo (+{diff_pct:.2f}%), porem com +{diff_busts} busts")
    elif rel8['busts'] < rel7['busts']:
        print(f"\n  >> NS8 mais seguro ({-diff_busts} busts a menos), porem -{-diff_pct:.2f}% lucro")
    else:
        print("\n  >> NS7 melhor neste periodo")

    return rel7, rel8


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'
    banca = 1000.0
    data_inicio = '08/01/2026'
    data_fim = '20/01/2026'

    print("=" * 80)
    print("SIMULADOR NS8 COMPLETO")
    print("Estrategia V4 | Compound | Analise de Cenarios")
    print("=" * 80)
    print(f"\nPeriodo: {data_inicio} a {data_fim}")
    print(f"Banca: R$ {banca:,.2f}")
    print(f"Defesa: {ALVO_DEFESA}x")

    print(f"\nCarregando dados...")
    multiplicadores = carregar_periodo(csv_path, data_inicio, data_fim)
    print(f"Multiplicadores: {len(multiplicadores):,}")

    if not multiplicadores:
        print("ERRO: Nenhum dado encontrado!")
        exit(1)

    dias = 13  # 08 a 20 janeiro
    print(f"Dias: {dias}")
    print(f"Media/dia: {len(multiplicadores)/dias:,.0f} multiplicadores")

    # Rodar comparativo
    rel7, rel8 = comparar(multiplicadores, banca)

    print("\n" + "=" * 80)
    print("Simulacao concluida!")
    print("=" * 80)
