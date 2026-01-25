#!/usr/bin/env python3
"""
Simulador MartingaleV2 - Versao 2.0
Segue a metodologia documentada em METODOLOGIA_SIMULACAO.md

Autor: Claude + Linnaldo
Data: 08/01/2026
"""

import re
import json
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum

# ==============================================================================
# CONSTANTES E CONFIGURACOES
# ==============================================================================

GAP_THRESHOLD = 600  # 10 minutos em segundos
MIN_RODADAS_SESSAO = 100

# Alvos padrao
ALVO_LUCRO = 1.99
ALVO_SEGURANCA = 1.25
ALVO_T6_NS6 = 2.50
ALVO_ALTO_MANUS = 5.00

# Divisores por nivel de seguranca
DIVISORES = {
    6: 63,
    7: 127,
    8: 255,
    9: 511,
    10: 1023
}

# Tentativas por nivel
TENTATIVAS = {
    6: 6,
    7: 7,
    8: 8,
    9: 9,
    10: 10
}


# ==============================================================================
# CONFIGURACOES DE TENTATIVA
# ==============================================================================

@dataclass
class SlotConfig:
    """Configuracao de um slot de aposta"""
    proporcao: float  # Proporcao da aposta (ex: 0.30 = 30%)
    alvo: float       # Alvo do multiplicador


@dataclass
class TentativaConfig:
    """Configuracao completa de uma tentativa"""
    slots: List[SlotConfig]
    parar_cenario_b: bool = False
    is_ultima: bool = False
    continuar_partial: bool = False  # Para refinamento Manus.ia

    @property
    def is_2_slots(self) -> bool:
        return len(self.slots) == 2

    @property
    def alvo_alto(self) -> float:
        return max(s.alvo for s in self.slots)

    @property
    def alvo_baixo(self) -> float:
        return min(s.alvo for s in self.slots)


class EstrategiaBase:
    """Classe base para estrategias"""

    def get_config_tentativa(self, nivel: int, tentativa: int) -> TentativaConfig:
        raise NotImplementedError


class EstrategiaV4Atual(EstrategiaBase):
    """
    Estrategia V4 atual no codigo:
    - T1 ate penpenultima: 1 slot @ 1.99x
    - Penultima: 2 slots (6/16 @ 1.99x + 10/16 @ 1.25x) - PARAR cenario B
    - Ultima: 2 slots (12/32 @ 2.50x + 20/32 @ 1.25x)
    """

    def get_config_tentativa(self, nivel: int, tentativa: int) -> TentativaConfig:
        max_t = TENTATIVAS[nivel]
        is_ultima = (tentativa == max_t)
        is_penultima = (tentativa == max_t - 1)

        # NS6 caso especial
        if nivel == 6:
            if tentativa <= 4:
                return TentativaConfig(
                    slots=[SlotConfig(1.0, ALVO_LUCRO)]
                )
            elif tentativa == 5:
                return TentativaConfig(
                    slots=[
                        SlotConfig(6/16, ALVO_LUCRO),
                        SlotConfig(10/16, ALVO_SEGURANCA)
                    ],
                    parar_cenario_b=True
                )
            else:  # T6 ultima
                return TentativaConfig(
                    slots=[
                        SlotConfig(12/32, ALVO_T6_NS6),
                        SlotConfig(20/32, ALVO_SEGURANCA)
                    ],
                    is_ultima=True
                )

        # NS7+
        if is_ultima:
            return TentativaConfig(
                slots=[
                    SlotConfig(12/32, ALVO_T6_NS6),
                    SlotConfig(20/32, ALVO_SEGURANCA)
                ],
                is_ultima=True
            )

        if is_penultima:
            return TentativaConfig(
                slots=[
                    SlotConfig(6/16, ALVO_LUCRO),
                    SlotConfig(10/16, ALVO_SEGURANCA)
                ],
                parar_cenario_b=True
            )

        # T1 ate penpenultima
        return TentativaConfig(
            slots=[SlotConfig(1.0, ALVO_LUCRO)]
        )


class EstrategiaManusIA(EstrategiaBase):
    """
    Estrategia refinada pelo Manus.ia:
    - T1-T4: 1 slot @ 1.99x
    - T5: 2 slots (30% @ 1.99x + 70% @ 5.00x) - CONTINUAR acerto parcial
    - T6: 2 slots (37.5% @ 1.99x + 62.5% @ 1.25x) - PARAR cenario B
    - T7: 1 slot @ 1.25x
    """

    def get_config_tentativa(self, nivel: int, tentativa: int) -> TentativaConfig:
        max_t = TENTATIVAS[nivel]
        is_ultima = (tentativa == max_t)
        is_penultima = (tentativa == max_t - 1)
        is_antepenultima = (tentativa == max_t - 2)

        # Ultima: 1 slot @ 1.25x (sobrevivencia)
        if is_ultima:
            return TentativaConfig(
                slots=[SlotConfig(1.0, ALVO_SEGURANCA)],
                is_ultima=True
            )

        # Penultima: 2 slots @ 1.99x/1.25x - PARAR cenario B
        if is_penultima:
            return TentativaConfig(
                slots=[
                    SlotConfig(6/16, ALVO_LUCRO),
                    SlotConfig(10/16, ALVO_SEGURANCA)
                ],
                parar_cenario_b=True
            )

        # Antepenultima (T5 no NS7): 2 slots @ 1.99x/5.00x - CONTINUAR partial
        if is_antepenultima:
            return TentativaConfig(
                slots=[
                    SlotConfig(0.30, ALVO_LUCRO),
                    SlotConfig(0.70, ALVO_ALTO_MANUS)
                ],
                continuar_partial=True
            )

        # T1 ate ante-antepenultima: 1 slot @ 1.99x
        return TentativaConfig(
            slots=[SlotConfig(1.0, ALVO_LUCRO)]
        )


class EstrategiaDocNS7(EstrategiaBase):
    """
    Estrategia conforme documentacao ESTRATEGIA_V4_NS7.md:
    - T1-T5: 1 slot @ 1.99x
    - T6: 2 slots (6/16 @ 1.99x + 10/16 @ 1.25x) - PARAR cenario B
    - T7: 1 slot @ 1.25x
    """

    def get_config_tentativa(self, nivel: int, tentativa: int) -> TentativaConfig:
        max_t = TENTATIVAS[nivel]
        is_ultima = (tentativa == max_t)
        is_penultima = (tentativa == max_t - 1)

        # Ultima: 1 slot @ 1.25x
        if is_ultima:
            return TentativaConfig(
                slots=[SlotConfig(1.0, ALVO_SEGURANCA)],
                is_ultima=True
            )

        # Penultima: 2 slots - PARAR cenario B
        if is_penultima:
            return TentativaConfig(
                slots=[
                    SlotConfig(6/16, ALVO_LUCRO),
                    SlotConfig(10/16, ALVO_SEGURANCA)
                ],
                parar_cenario_b=True
            )

        # T1 ate penpenultima: 1 slot @ 1.99x
        return TentativaConfig(
            slots=[SlotConfig(1.0, ALVO_LUCRO)]
        )


class Estrategia776(EstrategiaBase):
    """
    Estrategia [7,7,6] validada em 140k multiplicadores.

    IMPORTANTE: O GATILHO e SEMPRE 6 baixos consecutivos!
    O padrao [7,7,6] apenas alterna o DIVISOR:
    - Gatilho 1: NS7 (divisor 127)
    - Gatilho 2: NS7 (divisor 127)
    - Gatilho 3: NS6 (divisor 63) <- BOOST 2x
    ... repete

    A configuracao de tentativas segue EstrategiaV4Atual.
    """

    def __init__(self, padrao: List[int] = None):
        self.padrao = padrao or [7, 7, 6]
        self.indice = 0
        self._estrategia_base = EstrategiaV4Atual()

    def get_nivel_atual(self) -> int:
        """Retorna o nivel de seguranca atual no padrao"""
        return self.padrao[self.indice % len(self.padrao)]

    def avancar_padrao(self):
        """Avanca para proximo indice no padrao"""
        self.indice += 1

    def reset(self):
        """Reseta o indice do padrao"""
        self.indice = 0

    def get_config_tentativa(self, nivel: int, tentativa: int) -> TentativaConfig:
        """
        Retorna config de tentativa baseado no nivel atual do padrao.
        O parametro 'nivel' e ignorado - usamos o nivel do padrao.
        """
        nivel_atual = self.get_nivel_atual()
        return self._estrategia_base.get_config_tentativa(nivel_atual, tentativa)


# ==============================================================================
# CENARIOS E RESULTADOS
# ==============================================================================

class Cenario(Enum):
    A = "A"  # Ambos slots ganham (mult >= alvo_alto)
    B = "B"  # So slot seguranca ganha (alvo_baixo <= mult < alvo_alto)
    C = "C"  # Ambos perdem (mult < alvo_baixo)
    WIN = "WIN"  # 1 slot, ganhou
    LOSS = "LOSS"  # 1 slot, perdeu


@dataclass
class ResultadoTentativa:
    tentativa: int
    multiplicador: float
    cenario: Cenario
    ganho_bruto: float  # Ganho/perda desta tentativa
    acao: str  # "WIN", "LOSS", "PARAR", "CONTINUAR"


@dataclass
class ResultadoGatilho:
    gatilho_num: int
    tentativa_final: int
    resultado: str  # "WIN", "LOSS", "BUST", "PARAR"
    ganho_liquido: float
    tentativas: List[ResultadoTentativa] = field(default_factory=list)


# ==============================================================================
# SIMULADOR PRINCIPAL
# ==============================================================================

class SimuladorMartingale:
    """
    Simulador que segue a metodologia documentada.
    Processa rodada a rodada como no jogo real.

    Suporta:
    - Estrategia776 com nivel dinamico [7,7,6]
    - Redeposit apos bust (para continuar simulacao)
    - Sistema de reserva de lucros
    - Sistema de emprestimo da reserva (NOVO!)
    """

    # Parametros de Emprestimo (mesmos do reserva_manager.py)
    GATILHOS_PARA_EMPRESTIMO: int = 25   # Gatilhos sem T6 para poder emprestar
    LIMITE_EMPRESTIMO_PCT: float = 0.50  # Maximo 50% da reserva
    TAXA_PAGAMENTO: float = 0.50         # 50% do lucro paga divida
    EMPRESTIMO_MINIMO_PCT: float = 0.05  # So empresta se for > 5% da banca

    def __init__(
        self,
        banca_inicial: float = 1000.0,
        nivel: int = 7,
        estrategia: EstrategiaBase = None,
        reserva_ativa: bool = True,
        meta_reserva_pct: float = 0.10,
        proporcao_reserva: float = 0.50,
        redeposit_ativo: bool = False,  # Redepositar apos bust
        redeposit_valor: float = None,  # Valor do redeposit (None = banca_inicial)
        emprestimo_ativo: bool = True   # Sistema de emprestimo da reserva
    ):
        self.banca_inicial = banca_inicial
        self.banca = banca_inicial
        self.banca_referencia = banca_inicial  # Para calculo de reserva
        self.nivel = nivel
        self.estrategia = estrategia or EstrategiaV4Atual()

        # Reserva de lucros
        self.reserva_ativa = reserva_ativa
        self.meta_reserva_pct = meta_reserva_pct
        self.proporcao_reserva = proporcao_reserva
        self.reserva = 0.0

        # Sistema de Emprestimo
        self.emprestimo_ativo = emprestimo_ativo
        self.divida_reserva = 0.0        # Divida atual com a reserva
        self.total_emprestimos = 0       # Total de emprestimos realizados
        self.total_emprestado = 0.0      # Valor total ja emprestado (historico)
        self.gatilhos_desde_t6 = 0       # Gatilhos desde ultimo T6 (para emprestimo)
        self.banca_pico = banca_inicial  # Maior banca ja atingida

        # Redeposit
        self.redeposit_ativo = redeposit_ativo
        self.redeposit_valor = redeposit_valor or banca_inicial
        self.total_depositado = banca_inicial  # Tracking de depositos
        self.total_redeposits = 0

        # Estado do gatilho
        self.baixos_consecutivos = 0
        self.em_sequencia = False
        self.tentativa_atual = 0
        self.perdas_acumuladas = 0.0
        self.aposta_base_sequencia = 0.0  # Aposta base fixa do inicio da sequencia
        self.nivel_gatilho_atual = nivel  # Nivel do gatilho atual (para 776)

        # Estatisticas
        self.gatilhos_total = 0
        self.wins = 0
        self.losses = 0
        self.busts = 0
        self.paradas = 0
        self.gatilhos_ns6 = 0
        self.gatilhos_ns7 = 0

        # Por tentativa
        self.resolveu_t = {i: 0 for i in range(1, 11)}
        self.foi_t = {i: 0 for i in range(1, 11)}

        # Historico
        self.historico: List[ResultadoGatilho] = []
        self.historico_banca: List[Tuple[int, float]] = []  # (rodada, banca)

        # Tracking
        self.rodada_num = 0
        self.banca_minima = banca_inicial
        self.banca_maxima = banca_inicial
        self.drawdown_maximo = 0.0

        # Gatilho atual (para historico)
        self._tentativas_gatilho_atual: List[ResultadoTentativa] = []

    def _get_nivel_atual(self) -> int:
        """Retorna o nivel atual - dinamico para 776 ou fixo para outras"""
        if isinstance(self.estrategia, Estrategia776):
            return self.estrategia.get_nivel_atual()
        return self.nivel

    def _avancar_estrategia(self):
        """Avanca a estrategia (para 776)"""
        if isinstance(self.estrategia, Estrategia776):
            self.estrategia.avancar_padrao()

    # ============================================================
    # SISTEMA DE EMPRESTIMO DA RESERVA
    # ============================================================

    def _pode_emprestar(self) -> bool:
        """
        Verifica se pode fazer emprestimo da reserva.

        Condicoes (mesmas do reserva_manager.py):
        1. Emprestimo ativo
        2. >= 25 gatilhos sem T6 (cluster acabou)
        3. Banca < 90% do pico (ha deficit)
        4. Reserva > 0 (tem de onde emprestar)
        5. Sem divida pendente
        """
        if not self.emprestimo_ativo:
            return False

        return (
            self.gatilhos_desde_t6 >= self.GATILHOS_PARA_EMPRESTIMO and
            self.banca < self.banca_pico * 0.9 and
            self.reserva > 0 and
            self.divida_reserva == 0
        )

    def _calcular_emprestimo(self) -> float:
        """Calcula valor do emprestimo"""
        if self.reserva <= 0:
            return 0.0

        # Calcular deficit
        deficit = self.banca_pico - self.banca

        # Limite: 50% da reserva
        max_emprestimo = self.reserva * self.LIMITE_EMPRESTIMO_PCT

        # Emprestar o menor entre deficit e limite
        emprestimo = min(deficit, max_emprestimo)

        # So empresta se for significativo (> 5% da banca)
        if emprestimo < self.banca * self.EMPRESTIMO_MINIMO_PCT:
            return 0.0

        return emprestimo

    def _realizar_emprestimo(self, valor: float) -> bool:
        """
        Realiza emprestimo da reserva.

        IMPORTANTE: O emprestimo e VIRTUAL - nao adiciona dinheiro real!
        A reserva e virtual (o dinheiro ja esta na banca), entao o emprestimo
        apenas ajusta os trackings:
        - Reduz reserva (estamos usando dinheiro "protegido")
        - Aumenta divida (vamos pagar de volta quando ganharmos)
        """
        if valor <= 0:
            return False

        if valor > self.reserva:
            valor = self.reserva

        # Transferir da reserva para divida (VIRTUALMENTE - banca NAO muda!)
        self.reserva -= valor
        self.divida_reserva += valor
        self.total_emprestimos += 1
        self.total_emprestado += valor

        return True

    def _pagar_divida(self, lucro_gatilho: float) -> float:
        """
        Paga parte da divida com o lucro do gatilho.
        Retorna o valor pago.
        """
        if self.divida_reserva <= 0:
            return 0.0

        if lucro_gatilho <= 0:
            return 0.0

        # Calcular pagamento (50% do lucro)
        pagamento_desejado = lucro_gatilho * self.TAXA_PAGAMENTO

        # Nao pagar mais que a divida
        pagamento = min(pagamento_desejado, self.divida_reserva)

        # Transferir para reserva
        self.reserva += pagamento
        self.divida_reserva -= pagamento

        return pagamento

    def _verificar_emprestimo(self):
        """Verifica e realiza emprestimo se condicoes forem atendidas"""
        if not self._pode_emprestar():
            return None

        valor = self._calcular_emprestimo()
        if valor <= 0:
            return None

        if self._realizar_emprestimo(valor):
            return {
                'emprestimo': True,
                'valor': valor,
                'reserva_restante': self.reserva,
                'divida': self.divida_reserva
            }
        return None

    def _redepositar(self):
        """Executa redeposit apos bust"""
        self.banca = self.redeposit_valor
        self.banca_referencia = self.redeposit_valor
        self.banca_pico = self.redeposit_valor  # Reset pico
        self.total_depositado += self.redeposit_valor
        self.total_redeposits += 1

        # Reset estado de emprestimo
        self.divida_reserva = 0.0
        self.gatilhos_desde_t6 = 0

        # Reset estrategia 776 apos bust
        if isinstance(self.estrategia, Estrategia776):
            self.estrategia.reset()

    def _calcular_ganho_slot(self, valor: float, alvo: float, mult: float) -> float:
        """
        Calcula ganho de um slot.
        IMPORTANTE: Usa ALVO para calcular ganho, nao multiplicador!
        """
        if mult >= alvo:
            # Ganho = valor * (alvo - 1), pois aposta ja esta no valor
            return valor * (alvo - 1)
        else:
            return -valor

    def _detectar_cenario(self, mult: float, config: TentativaConfig) -> Cenario:
        """Detecta cenario baseado no multiplicador e configuracao"""
        if not config.is_2_slots:
            return Cenario.WIN if mult >= config.slots[0].alvo else Cenario.LOSS

        if mult >= config.alvo_alto:
            return Cenario.A
        elif mult >= config.alvo_baixo:
            return Cenario.B
        else:
            return Cenario.C

    def _processar_reserva(self):
        """
        Processa reserva de lucros se atingiu meta.

        IMPORTANTE: A reserva e VIRTUAL - nao sai da banca operacional!
        O saldo continua sendo usado integralmente para calcular apostas.
        A banca_referencia e usada apenas para calcular progresso da meta.
        """
        if not self.reserva_ativa:
            return

        # Verificar se banca_referencia e valida
        if self.banca_referencia <= 0:
            return

        lucro_pct = (self.banca - self.banca_referencia) / self.banca_referencia

        if lucro_pct >= self.meta_reserva_pct:
            lucro_atual = self.banca - self.banca_referencia

            # 50% vai para reserva (VIRTUAL - apenas tracking)
            valor_reserva = lucro_atual * self.proporcao_reserva
            self.reserva += valor_reserva

            # A banca NAO muda! A reserva e virtual.
            # Apenas atualiza a referencia para proxima meta
            # Nova banca_referencia = saldo_atual - valor_reserva
            self.banca_referencia = self.banca - valor_reserva

    def _registrar_historico_banca(self):
        """Registra estado da banca"""
        self.historico_banca.append((self.rodada_num, self.banca))

        if self.banca < self.banca_minima:
            self.banca_minima = self.banca
        if self.banca > self.banca_maxima:
            self.banca_maxima = self.banca

        # Drawdown desde o pico
        if self.banca_maxima > 0:
            dd = (self.banca_maxima - self.banca) / self.banca_maxima
            if dd > self.drawdown_maximo:
                self.drawdown_maximo = dd

    def processar_multiplicador(self, mult: float) -> Optional[Dict]:
        """
        Processa um multiplicador (uma rodada).
        Retorna dict com info se houve evento significativo, None caso contrario.
        """
        self.rodada_num += 1
        resultado = None

        # Se nao esta em sequencia, verificar gatilho
        if not self.em_sequencia:
            if mult < 2.0:
                self.baixos_consecutivos += 1
                if self.baixos_consecutivos == 6:
                    # Gatilho ativado!
                    self.gatilhos_total += 1
                    self.em_sequencia = True
                    self.tentativa_atual = 1
                    self.perdas_acumuladas = 0.0
                    self.baixos_consecutivos = 0
                    self._tentativas_gatilho_atual = []

                    # Obter nivel atual (dinamico para 776, fixo para outras)
                    self.nivel_gatilho_atual = self._get_nivel_atual()

                    # Registrar estatisticas por NS
                    if self.nivel_gatilho_atual == 6:
                        self.gatilhos_ns6 += 1
                    elif self.nivel_gatilho_atual == 7:
                        self.gatilhos_ns7 += 1

                    # Calcular aposta base FIXA para toda a sequencia
                    self.aposta_base_sequencia = self.banca / DIVISORES[self.nivel_gatilho_atual]
                    resultado = {'evento': 'gatilho', 'gatilho_num': self.gatilhos_total, 'nivel': self.nivel_gatilho_atual}
            else:
                self.baixos_consecutivos = 0

            self._registrar_historico_banca()
            return resultado

        # Em sequencia - processar tentativa (usa nivel do gatilho atual)
        config = self.estrategia.get_config_tentativa(self.nivel_gatilho_atual, self.tentativa_atual)
        # Usar aposta base FIXA do inicio da sequencia
        multiplicador_aposta = 2 ** (self.tentativa_atual - 1)
        valor_total = self.aposta_base_sequencia * multiplicador_aposta

        # Calcular ganho
        cenario = self._detectar_cenario(mult, config)

        if config.is_2_slots:
            valor_slot1 = valor_total * config.slots[0].proporcao
            valor_slot2 = valor_total * config.slots[1].proporcao

            ganho_slot1 = self._calcular_ganho_slot(valor_slot1, config.slots[0].alvo, mult)
            ganho_slot2 = self._calcular_ganho_slot(valor_slot2, config.slots[1].alvo, mult)
            ganho_bruto = ganho_slot1 + ganho_slot2
        else:
            ganho_bruto = self._calcular_ganho_slot(valor_total, config.slots[0].alvo, mult)

        # Determinar acao
        if cenario == Cenario.WIN or cenario == Cenario.A:
            # Ganhou completamente
            acao = "WIN"
            # ganho_bruto ja eh o ganho desta tentativa
            # perdas_acumuladas foram subtraidas da banca a cada loss
            # Entao ganho_liquido = ganho_bruto (apenas adiciona o lucro)
            ganho_liquido = ganho_bruto
            self.banca += ganho_liquido
            self.wins += 1
            self.resolveu_t[self.tentativa_atual] += 1

            self._tentativas_gatilho_atual.append(ResultadoTentativa(
                self.tentativa_atual, mult, cenario, ganho_bruto, acao
            ))

            # Ganho real da sequencia = ganho final - perdas acumuladas
            ganho_sequencia = ganho_bruto - self.perdas_acumuladas

            self.historico.append(ResultadoGatilho(
                self.gatilhos_total,
                self.tentativa_atual,
                "WIN",
                ganho_sequencia,
                self._tentativas_gatilho_atual.copy()
            ))

            # SISTEMA DE EMPRESTIMO: Pagar divida se houver lucro
            pagamento_divida = 0.0
            if ganho_sequencia > 0 and self.divida_reserva > 0:
                pagamento_divida = self._pagar_divida(ganho_sequencia)

            # SISTEMA DE EMPRESTIMO: Atualizar gatilhos_desde_t6
            # Se foi ate ultima tentativa (T6 no NS6, T7 no NS7), zera contador
            max_tentativas = TENTATIVAS[self.nivel_gatilho_atual]
            tentativa_final = self._tentativas_gatilho_atual[-1].tentativa
            if tentativa_final == max_tentativas:
                self.gatilhos_desde_t6 = 0  # T6/T7 - reseta contador
            else:
                self.gatilhos_desde_t6 += 1  # Nao foi ate o fim - incrementa

            # Atualizar banca_pico
            if self.banca > self.banca_pico:
                self.banca_pico = self.banca

            self._processar_reserva()
            self._avancar_estrategia()  # Avanca padrao [7,7,6]

            # SISTEMA DE EMPRESTIMO: Verificar se pode emprestar
            emprestimo_info = self._verificar_emprestimo()

            self.em_sequencia = False
            self.tentativa_atual = 0
            self.perdas_acumuladas = 0.0

            resultado = {
                'evento': 'win',
                'tentativa': tentativa_final,
                'ganho': ganho_liquido,
                'banca': self.banca,
                'pagamento_divida': pagamento_divida
            }
            if emprestimo_info:
                resultado['emprestimo'] = emprestimo_info

        elif cenario == Cenario.B:
            # Acerto parcial (2 slots)
            self.foi_t[self.tentativa_atual] += 1

            if config.parar_cenario_b:
                # PARAR - aceitar perda parcial
                acao = "PARAR"
                # Ganho bruto ja considera slot1 perdeu, slot2 ganhou
                self.banca += ganho_bruto
                self.perdas_acumuladas += (-ganho_bruto if ganho_bruto < 0 else 0)
                self.paradas += 1

                self._tentativas_gatilho_atual.append(ResultadoTentativa(
                    self.tentativa_atual, mult, cenario, ganho_bruto, acao
                ))

                # Calcular perda total da sequencia
                perda_total = sum(-t.ganho_bruto for t in self._tentativas_gatilho_atual if t.ganho_bruto < 0)
                ganho_total = sum(t.ganho_bruto for t in self._tentativas_gatilho_atual if t.ganho_bruto > 0)
                ganho_liquido_seq = ganho_total - perda_total

                self.historico.append(ResultadoGatilho(
                    self.gatilhos_total,
                    self.tentativa_atual,
                    "PARAR",
                    ganho_liquido_seq,
                    self._tentativas_gatilho_atual.copy()
                ))

                # SISTEMA DE EMPRESTIMO: Pagar divida se houver lucro
                pagamento_divida = 0.0
                if ganho_liquido_seq > 0 and self.divida_reserva > 0:
                    pagamento_divida = self._pagar_divida(ganho_liquido_seq)

                # SISTEMA DE EMPRESTIMO: Incrementar gatilhos_desde_t6 (nao foi ate T6)
                self.gatilhos_desde_t6 += 1

                # Atualizar banca_pico se lucro
                if self.banca > self.banca_pico:
                    self.banca_pico = self.banca

                self._avancar_estrategia()  # Avanca padrao [7,7,6]

                # SISTEMA DE EMPRESTIMO: Verificar se pode emprestar
                emprestimo_info = self._verificar_emprestimo()

                self.em_sequencia = False
                self.tentativa_atual = 0
                self.perdas_acumuladas = 0.0

                resultado = {
                    'evento': 'parar',
                    'tentativa': self._tentativas_gatilho_atual[-1].tentativa,
                    'banca': self.banca
                }
                if emprestimo_info:
                    resultado['emprestimo'] = emprestimo_info

            elif config.continuar_partial:
                # CONTINUAR para proxima tentativa (refinamento Manus.ia)
                acao = "CONTINUAR"
                # Slot1 ganhou, slot2 perdeu - banca recebe ganho do slot1
                self.banca += ganho_bruto
                self.perdas_acumuladas += (-ganho_bruto if ganho_bruto < 0 else 0)

                self._tentativas_gatilho_atual.append(ResultadoTentativa(
                    self.tentativa_atual, mult, cenario, ganho_bruto, acao
                ))

                self.tentativa_atual += 1
                resultado = {
                    'evento': 'continuar',
                    'tentativa': self.tentativa_atual,
                    'banca': self.banca
                }

            else:
                # Comportamento padrao para Cenario B sem parar_cenario_b nem continuar_partial
                # Se for ultima tentativa, encerra como WIN parcial (slot2 ganhou)
                if config.is_ultima:
                    acao = "WIN_PARCIAL"
                    # ganho_bruto ja tem slot1 perdeu + slot2 ganhou
                    self.banca += ganho_bruto
                    self.wins += 1

                    self._tentativas_gatilho_atual.append(ResultadoTentativa(
                        self.tentativa_atual, mult, cenario, ganho_bruto, acao
                    ))

                    ganho_sequencia = ganho_bruto - self.perdas_acumuladas

                    self.historico.append(ResultadoGatilho(
                        self.gatilhos_total,
                        self.tentativa_atual,
                        "WIN",
                        ganho_sequencia,
                        self._tentativas_gatilho_atual.copy()
                    ))

                    # SISTEMA DE EMPRESTIMO: Pagar divida se houver lucro
                    pagamento_divida = 0.0
                    if ganho_sequencia > 0 and self.divida_reserva > 0:
                        pagamento_divida = self._pagar_divida(ganho_sequencia)

                    # SISTEMA DE EMPRESTIMO: Foi ate T6/T7 - reseta contador
                    self.gatilhos_desde_t6 = 0

                    # Atualizar banca_pico se lucro
                    if self.banca > self.banca_pico:
                        self.banca_pico = self.banca

                    self._avancar_estrategia()  # Avanca padrao [7,7,6]

                    # SISTEMA DE EMPRESTIMO: Verificar se pode emprestar
                    emprestimo_info = self._verificar_emprestimo()

                    self.em_sequencia = False
                    self.tentativa_atual = 0
                    self.perdas_acumuladas = 0.0

                    resultado = {
                        'evento': 'win_parcial',
                        'tentativa': self._tentativas_gatilho_atual[-1].tentativa,
                        'ganho': ganho_sequencia,
                        'banca': self.banca
                    }
                    if emprestimo_info:
                        resultado['emprestimo'] = emprestimo_info
                else:
                    # Nao eh ultima, continua para proxima tentativa
                    acao = "LOSS"
                    self.banca += ganho_bruto
                    self.perdas_acumuladas += valor_total
                    self.losses += 1

                    self._tentativas_gatilho_atual.append(ResultadoTentativa(
                        self.tentativa_atual, mult, cenario, ganho_bruto, acao
                    ))

                    self.tentativa_atual += 1

        elif cenario == Cenario.C or cenario == Cenario.LOSS:
            # Perdeu
            acao = "LOSS"
            self.banca += ganho_bruto  # ganho_bruto é negativo
            self.perdas_acumuladas += valor_total
            self.losses += 1
            self.foi_t[self.tentativa_atual] += 1

            self._tentativas_gatilho_atual.append(ResultadoTentativa(
                self.tentativa_atual, mult, cenario, ganho_bruto, acao
            ))

            # Verificar se era ultima tentativa
            if config.is_ultima:
                self.busts += 1

                self.historico.append(ResultadoGatilho(
                    self.gatilhos_total,
                    self.tentativa_atual,
                    "BUST",
                    -self.perdas_acumuladas,
                    self._tentativas_gatilho_atual.copy()
                ))

                # SISTEMA DE EMPRESTIMO: Bust = reseta contador (chegou no T6/T7)
                # Divida e perdida junto com o bust (nao da para pagar de volta)
                # Reserva virtual tambem e perdida (estava contida na banca)
                self.gatilhos_desde_t6 = 0
                self.divida_reserva = 0.0  # Divida perdida no bust
                self.reserva = 0.0  # Reserva perdida (era virtual/parte da banca)

                self._avancar_estrategia()  # Avanca padrao [7,7,6]
                self.em_sequencia = False
                self.tentativa_atual = 0
                perda_bust = self.perdas_acumuladas
                self.perdas_acumuladas = 0.0

                # Redeposit se ativo e banca muito baixa
                if self.redeposit_ativo and self.banca < self.redeposit_valor * 0.1:
                    self._redepositar()

                resultado = {
                    'evento': 'bust',
                    'tentativa': self._tentativas_gatilho_atual[-1].tentativa,
                    'perda': perda_bust,
                    'banca': self.banca
                }
            else:
                self.tentativa_atual += 1
                resultado = {
                    'evento': 'loss',
                    'tentativa': self.tentativa_atual,
                    'banca': self.banca
                }

        self._registrar_historico_banca()
        return resultado

    def simular(self, multiplicadores: List[float]) -> Dict:
        """
        Simula uma lista de multiplicadores.
        Retorna relatorio completo.
        """
        for mult in multiplicadores:
            self.processar_multiplicador(mult)

        return self.gerar_relatorio()

    def gerar_relatorio(self) -> Dict:
        """Gera relatorio completo da simulacao"""
        # A reserva e VIRTUAL - ja esta contida na banca
        # Patrimonio = banca (que inclui a reserva virtual)
        patrimonio = self.banca
        lucro_total = patrimonio - self.total_depositado
        ganho_pct = (lucro_total / self.banca_inicial) * 100

        return {
            'banca_inicial': self.banca_inicial,
            'banca_final': self.banca,
            'reserva': self.reserva,  # Quanto do saldo e "protegido" virtualmente
            'divida_reserva': self.divida_reserva,  # Divida atual
            'total': patrimonio,  # = banca (reserva ja esta inclusa)
            'lucro': lucro_total,
            'ganho_pct': ganho_pct,

            'gatilhos': self.gatilhos_total,
            'wins': self.wins,
            'losses': self.losses,
            'busts': self.busts,
            'paradas': self.paradas,

            # Estatisticas por NS (para 776)
            'gatilhos_ns6': self.gatilhos_ns6,
            'gatilhos_ns7': self.gatilhos_ns7,

            # Sistema de Emprestimo
            'total_emprestimos': self.total_emprestimos,
            'total_emprestado': self.total_emprestado,

            # Redeposits
            'total_depositado': self.total_depositado,
            'total_redeposits': self.total_redeposits,

            'banca_minima': self.banca_minima,
            'banca_maxima': self.banca_maxima,
            'banca_pico': self.banca_pico,
            'drawdown_maximo_pct': self.drawdown_maximo * 100,

            'rodadas': self.rodada_num,
            'nivel': self.nivel,
            'estrategia': self.estrategia.__class__.__name__
        }


# ==============================================================================
# CARREGAMENTO DE DADOS
# ==============================================================================

def carregar_multiplicadores_txt(filepath: str) -> List[Tuple[datetime, float]]:
    """Carrega multiplicadores de arquivo TXT com timestamp"""
    rodadas = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.match(
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - .* - INFO - Rodada salva: ([\d.]+)x',
                line
            )
            if match:
                ts_str, mult = match.groups()
                ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                rodadas.append((ts, float(mult)))
    return rodadas


def carregar_multiplicadores_db(filepath: str) -> List[Tuple[datetime, float]]:
    """Carrega multiplicadores do database com timestamp"""
    conn = sqlite3.connect(filepath)
    cur = conn.cursor()
    cur.execute('SELECT timestamp, multiplier FROM rounds ORDER BY timestamp')
    rows = cur.fetchall()
    conn.close()

    rodadas = []
    for ts_str, mult in rows:
        try:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        except:
            try:
                ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            except:
                continue
        rodadas.append((ts, mult))

    return rodadas


def filtrar_sessoes_continuas(
    rodadas: List[Tuple[datetime, float]],
    gap_threshold: int = GAP_THRESHOLD,
    min_rodadas: int = MIN_RODADAS_SESSAO
) -> List[List[float]]:
    """
    Filtra rodadas em sessoes continuas.
    Retorna lista de listas de multiplicadores.
    """
    sessoes = []
    sessao_atual = []
    ultimo_ts = None

    for ts, mult in rodadas:
        if ultimo_ts:
            gap = (ts - ultimo_ts).total_seconds()
            if gap > gap_threshold:
                if len(sessao_atual) >= min_rodadas:
                    sessoes.append([r[1] for r in sessao_atual])
                sessao_atual = []

        sessao_atual.append((ts, mult))
        ultimo_ts = ts

    if len(sessao_atual) >= min_rodadas:
        sessoes.append([r[1] for r in sessao_atual])

    return sessoes


def carregar_multiplicadores_csv(filepath: str) -> List[Tuple[datetime, float]]:
    """
    Carrega multiplicadores de arquivo CSV.
    Formato esperado: timestamp,multiplier (com header)
    """
    rodadas = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        # Pular header
        next(f, None)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    ts_str = parts[0].strip()
                    mult_str = parts[1].strip()

                    # Tentar varios formatos de timestamp
                    try:
                        ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        except:
                            ts = datetime.now()  # Fallback

                    mult = float(mult_str)
                    rodadas.append((ts, mult))
            except:
                continue

    return rodadas


def carregar_apenas_multiplicadores_csv(filepath: str) -> List[float]:
    """
    Carrega apenas os multiplicadores do CSV (sem timestamp).
    Formato: Número,Cor,Data,Horário,DateTime
    O multiplicador esta na PRIMEIRA coluna.
    """
    multiplicadores = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        # Pular header
        header = next(f, None)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 1:
                    # Multiplicador na primeira coluna
                    mult = float(parts[0].strip())
                    multiplicadores.append(mult)
            except:
                continue

    return multiplicadores


# ==============================================================================
# TESTES
# ==============================================================================

def comparar_776_vs_ns7(multiplicadores: List[float], banca_inicial: float = 1000.0):
    """Compara estrategia [7,7,6] vs NS7 puro"""

    print("\n" + "=" * 80)
    print("COMPARACAO: [7,7,6] vs NS7 Puro")
    print("=" * 80)
    print(f"Multiplicadores: {len(multiplicadores):,}")
    print(f"Banca inicial: R$ {banca_inicial:,.2f}")

    # NS7 Puro (SEM redeposit para ver resultado real)
    sim_ns7 = SimuladorMartingale(
        banca_inicial=banca_inicial,
        nivel=7,
        estrategia=EstrategiaV4Atual(),
        reserva_ativa=True,
        redeposit_ativo=False
    )
    rel_ns7 = sim_ns7.simular(multiplicadores)

    # [7,7,6] (SEM redeposit para ver resultado real)
    sim_776 = SimuladorMartingale(
        banca_inicial=banca_inicial,
        nivel=7,  # Nivel base (sera sobrescrito pela estrategia)
        estrategia=Estrategia776(),
        reserva_ativa=True,
        redeposit_ativo=False
    )
    rel_776 = sim_776.simular(multiplicadores)

    # Resultados
    print("\n" + "-" * 70)
    print(f"{'Metrica':<25} {'NS7 Puro':>18} {'[7,7,6]':>18}")
    print("-" * 70)

    print(f"{'Patrimonio Final':<25} R$ {rel_ns7['total']:>14,.2f} R$ {rel_776['total']:>14,.2f}")
    print(f"{'Reserva Virtual':<25} R$ {rel_ns7['reserva']:>14,.2f} R$ {rel_776['reserva']:>14,.2f}")
    print(f"{'Banca Pico':<25} R$ {rel_ns7['banca_pico']:>14,.2f} R$ {rel_776['banca_pico']:>14,.2f}")

    ns7_ganho = rel_ns7['ganho_pct']
    p776_ganho = rel_776['ganho_pct']
    ratio = p776_ganho / max(ns7_ganho, 0.01) if ns7_ganho != 0 else 0

    print(f"{'Ganho %':<25} {ns7_ganho:>17.2f}% {p776_ganho:>17.2f}%")
    if ratio != 0 and ratio != 1:
        print(f"{'  (Comparacao)':<25} {'-':>18} {ratio:>17.1f}x")

    print(f"{'Drawdown Max':<25} {rel_ns7['drawdown_maximo_pct']:>17.2f}% {rel_776['drawdown_maximo_pct']:>17.2f}%")
    print("-" * 70)

    print(f"{'Gatilhos':<25} {rel_ns7['gatilhos']:>18,} {rel_776['gatilhos']:>18,}")
    print(f"{'Wins':<25} {rel_ns7['wins']:>18,} {rel_776['wins']:>18,}")
    print(f"{'Busts':<25} {rel_ns7['busts']:>18,} {rel_776['busts']:>18,}")
    print(f"{'Paradas (Cenario B)':<25} {rel_ns7['paradas']:>18,} {rel_776['paradas']:>18,}")

    # Sistema de emprestimo
    print("-" * 70)
    print(f"{'Emprestimos Realizados':<25} {rel_ns7['total_emprestimos']:>18,} {rel_776['total_emprestimos']:>18,}")
    print(f"{'Total Emprestado':<25} R$ {rel_ns7['total_emprestado']:>14,.2f} R$ {rel_776['total_emprestado']:>14,.2f}")

    if rel_776['gatilhos'] > 0 and rel_776['gatilhos_ns6'] > 0:
        print("-" * 70)
        print(f"[7,7,6] Detalhes:")
        print(f"  Gatilhos NS6: {rel_776['gatilhos_ns6']:,} ({rel_776['gatilhos_ns6']/rel_776['gatilhos']*100:.1f}%)")
        print(f"  Gatilhos NS7: {rel_776['gatilhos_ns7']:,} ({rel_776['gatilhos_ns7']/rel_776['gatilhos']*100:.1f}%)")

    print("-" * 70)

    return rel_ns7, rel_776


def carregar_csv_com_datas(filepath: str) -> List[Tuple[datetime, float]]:
    """
    Carrega multiplicadores do CSV com datas.
    Formato: Numero,Cor,Data,Horario,DateTime
    """
    rodadas = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        header = next(f, None)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 5:
                    mult = float(parts[0].strip())
                    # DateTime esta na quinta coluna
                    dt_str = parts[4].strip()
                    try:
                        ts = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        try:
                            ts = datetime.fromisoformat(dt_str)
                        except:
                            # Usar data e horario separados
                            data = parts[2].strip()
                            hora = parts[3].strip()
                            ts = datetime.strptime(f"{data} {hora}", '%Y-%m-%d %H:%M:%S')
                    rodadas.append((ts, mult))
            except:
                continue
    return rodadas


def simular_mes_a_mes(filepath: str, banca_inicial: float = 1000.0,
                      usar_776: bool = True, redeposit: bool = True):
    """
    Simula mes a mes com relatorio detalhado.
    Permite comparar [7,7,6] vs NS7 puro.
    """
    print(f"\n{'=' * 80}")
    estrategia_nome = "[7,7,6]" if usar_776 else "NS7 Puro"
    print(f"SIMULACAO MES A MES - {estrategia_nome}")
    print(f"{'=' * 80}")

    # Carregar dados com datas
    rodadas = carregar_csv_com_datas(filepath)
    if not rodadas:
        print("Erro: Nao foi possivel carregar dados com datas")
        return None

    print(f"Total de rodadas: {len(rodadas):,}")

    # Agrupar por mes
    meses = {}
    for ts, mult in rodadas:
        chave = ts.strftime('%Y-%m')
        if chave not in meses:
            meses[chave] = []
        meses[chave].append(mult)

    print(f"Meses encontrados: {len(meses)}")
    print(f"Banca inicial: R$ {banca_inicial:,.2f}")
    print(f"Redeposit: {'Ativo' if redeposit else 'Desativado'}")

    # Simular
    if usar_776:
        estrategia = Estrategia776()
    else:
        estrategia = EstrategiaV4Atual()

    sim = SimuladorMartingale(
        banca_inicial=banca_inicial,
        nivel=7,
        estrategia=estrategia,
        reserva_ativa=True,
        redeposit_ativo=redeposit,
        redeposit_valor=banca_inicial,
        emprestimo_ativo=True
    )

    print(f"\n{'-' * 80}")
    print(f"{'Mes':<10} {'Rodadas':>10} {'Gatilhos':>10} {'Busts':>8} {'Banca Fim':>15} {'Ganho %':>12}")
    print(f"{'-' * 80}")

    resultados_mes = []
    for mes in sorted(meses.keys()):
        multiplicadores_mes = meses[mes]

        # Estado antes do mes
        banca_inicio_mes = sim.banca
        busts_inicio = sim.busts
        gatilhos_inicio = sim.gatilhos_total

        # Processar multiplicadores do mes
        for mult in multiplicadores_mes:
            sim.processar_multiplicador(mult)

        # Estatisticas do mes
        busts_mes = sim.busts - busts_inicio
        gatilhos_mes = sim.gatilhos_total - gatilhos_inicio

        if banca_inicio_mes > 0:
            ganho_mes_pct = ((sim.banca - banca_inicio_mes) / banca_inicio_mes) * 100
        else:
            ganho_mes_pct = 0

        resultados_mes.append({
            'mes': mes,
            'rodadas': len(multiplicadores_mes),
            'gatilhos': gatilhos_mes,
            'busts': busts_mes,
            'banca_fim': sim.banca,
            'ganho_pct': ganho_mes_pct
        })

        busts_str = f"{busts_mes}" if busts_mes == 0 else f"**{busts_mes}**"
        print(f"{mes:<10} {len(multiplicadores_mes):>10,} {gatilhos_mes:>10,} {busts_str:>8} R$ {sim.banca:>11,.2f} {ganho_mes_pct:>11.1f}%")

    # Relatorio final
    rel = sim.gerar_relatorio()
    print(f"{'-' * 80}")
    print(f"\nRESUMO FINAL ({estrategia_nome}):")
    print(f"  Patrimonio Final: R$ {rel['total']:,.2f}")
    print(f"  Total Depositado: R$ {rel['total_depositado']:,.2f}")
    print(f"  Lucro Liquido: R$ {rel['lucro']:,.2f} ({rel['ganho_pct']:.1f}%)")
    print(f"  Reserva Virtual: R$ {rel['reserva']:,.2f}")
    print(f"  Banca Pico: R$ {rel['banca_pico']:,.2f}")
    print(f"  Drawdown Maximo: {rel['drawdown_maximo_pct']:.1f}%")
    print(f"  Total Gatilhos: {rel['gatilhos']:,}")
    print(f"  Total Busts: {rel['busts']}")
    print(f"  Total Redeposits: {rel['total_redeposits']}")
    print(f"  Emprestimos: {rel['total_emprestimos']} (R$ {rel['total_emprestado']:,.2f})")

    if usar_776:
        print(f"  Gatilhos NS6: {rel['gatilhos_ns6']:,} ({rel['gatilhos_ns6']/max(rel['gatilhos'],1)*100:.1f}%)")
        print(f"  Gatilhos NS7: {rel['gatilhos_ns7']:,} ({rel['gatilhos_ns7']/max(rel['gatilhos'],1)*100:.1f}%)")

    return rel, resultados_mes


if __name__ == "__main__":
    import os
    import sys

    print("=" * 80)
    print("SIMULADOR MARTINGALE V2 - Estrategia [7,7,6]")
    print("=" * 80)

    # Verificar se tem CSV grande
    csv_path = '/mnt/c/Users/linna/Desktop/MartingaleV2_Build/brabet_complete_clean_sorted.csv'

    if os.path.exists(csv_path):
        print(f"\nCarregando CSV: {csv_path}")
        multiplicadores = carregar_apenas_multiplicadores_csv(csv_path)
        print(f"Total de multiplicadores: {len(multiplicadores):,}")

        if len(multiplicadores) > 0:
            # Comparacao rapida
            comparar_776_vs_ns7(multiplicadores, banca_inicial=1000.0)

            # Simulacao mes a mes com [7,7,6]
            print("\n\n" + "=" * 80)
            print("INICIANDO SIMULACAO MES A MES")
            print("=" * 80)

            # [7,7,6] com redeposit
            simular_mes_a_mes(csv_path, banca_inicial=1000.0, usar_776=True, redeposit=True)

            # NS7 Puro com redeposit
            simular_mes_a_mes(csv_path, banca_inicial=1000.0, usar_776=False, redeposit=True)

    else:
        print(f"\nCSV nao encontrado: {csv_path}")
        print("Usando database local...")

        # Carregar dados de teste do database
        rodadas_db = carregar_multiplicadores_db(
            '/mnt/c/Users/linna/Desktop/MartingaleV2_Build/database/rounds.db'
        )
        print(f"Total de rodadas: {len(rodadas_db):,}")

        if rodadas_db:
            # Usar todos os multiplicadores
            multiplicadores = [m for _, m in rodadas_db]
            comparar_776_vs_ns7(multiplicadores, banca_inicial=1000.0)

    print("\n" + "=" * 80)
    print("Simulacao concluida!")
    print("=" * 80)
