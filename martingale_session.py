#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MARTINGALE SESSION - Gerenciador de sessao de martingale
Versao 4.0 - Estrategia V4 com 2 Slots

Fluxo:
- Ler saldo ANTES de iniciar
- Executar apostas (1 ou 2 slots) sem ler saldo no meio
- WIN/LOSS baseado em multiplicador vs alvos dos slots
- Ler saldo e calcular P/L so no FINAL

Estrategia V4 - 2 Slots:
- T1-T4: 1 slot @ 1.99x (geracao de lucro)
- T5: 2 slots (6/16 @ 1.99x + 10/16 @ 1.25x)
  - Cenario A (>=1.99x): ambos ganham -> FIM
  - Cenario B (1.25-1.98x): so slot2 ganha -> PARAR
  - Cenario C (<1.25x): ambos perdem -> T6
- T6 ate penultima: 1 slot @ 1.99x (tentar zerar)
- Ultima tentativa: 1 slot @ 1.25x (sobrevivencia)

Niveis de Seguranca (NS):
- NS6:  6 tentativas, divisor 63
- NS7:  7 tentativas, divisor 127
- NS8:  8 tentativas, divisor 255
- NS9:  9 tentativas, divisor 511
- NS10: 10 tentativas, divisor 1023
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from enum import Enum
import json
import os


# ============================================================
# CENARIOS DE RESULTADO (V4)
# ============================================================

class Cenario(Enum):
    """Cenarios possiveis apos uma tentativa"""
    A = "A"      # Ambos slots ganham (mult >= alvo alto)
    B = "B"      # So slot de seguranca ganha (alvo baixo <= mult < alvo alto)
    C = "C"      # Ambos slots perdem (mult < alvo baixo)
    WIN = "WIN"  # Slot unico ganha
    LOSS = "LOSS"  # Slot unico perde


@dataclass
class SlotConfig:
    """Configuracao de um slot de aposta"""
    proporcao: int  # Numerador (ex: 6 de 16)
    alvo: float     # Multiplicador alvo


@dataclass
class TentativaConfig:
    """Configuracao completa de uma tentativa"""
    slots: List[SlotConfig]      # Lista de slots (1 ou 2)
    divisor_proporcao: int       # Denominador total (ex: 16)
    parar_cenario_b: bool = False  # Se True, para no cenario B
    is_ultima: bool = False      # Se e a ultima tentativa do nivel

    @property
    def num_slots(self) -> int:
        return len(self.slots)

    @property
    def is_2_slots(self) -> bool:
        return len(self.slots) == 2


# ============================================================
# MODOS DE OPERACAO
# ============================================================

class ModoOperacao(Enum):
    """Modos de operacao do sistema"""
    AUTOMATICO = "automatico"  # Sobe nivel ao atingir % de lucro
    MANUAL = "manual"          # Usuario controla mudanca de nivel
    GAGO = "gago"              # Estrategia Gago: divisor 7, compound controlado, pausa autonoma
    NS7_PURO = "ns7_puro"      # NS7 puro: defesa 1.10x, sem reserva, banca integral
    G6_NS9 = "g6_ns9"          # G6+NS9: Agressivo, protecao 15, 2 busts/ano, ~25k/mes por 10k
    G6_NS10 = "g6_ns10"        # G6+NS10: Conservador, protecao 16, 0 busts, ~12k/mes por 10k


@dataclass
class ConfiguracaoModo:
    """Configuracao do modo de operacao"""
    modo: ModoOperacao = ModoOperacao.MANUAL
    nivel_inicial: int = 6  # Inicia em NS6 (velocidade 2x)
    lucro_para_subir: float = 100.0  # % de lucro para subir de nivel (modo auto)
    alvo_defesa: float = 1.25  # Alvo de defesa (1.25 padrao, 1.10 para NS7_PURO)

    def to_dict(self) -> Dict:
        return {
            'modo': self.modo.value,
            'nivel_inicial': self.nivel_inicial,
            'lucro_para_subir': self.lucro_para_subir,
            'alvo_defesa': self.alvo_defesa,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ConfiguracaoModo':
        return cls(
            modo=ModoOperacao(data.get('modo', 'manual')),
            nivel_inicial=data.get('nivel_inicial', 7),
            lucro_para_subir=data.get('lucro_para_subir', 50.0),
            alvo_defesa=data.get('alvo_defesa', 1.25),
        )


# ============================================================
# CONFIGURACAO ESTRATEGIAS G6+NS9 e G6+NS10
# ============================================================

CONFIG_G6_NS9 = {
    'nome': 'G6+NS9 AGRESSIVO',
    'gatilho': 6,           # G6: 6 baixas consecutivas para entrar
    'nivel': 9,             # NS9
    'divisor': 511,         # Divisor 511 = 9 tentativas
    'tentativas': 9,
    'alvo': 1.99,           # Alvo de lucro
    'protecao': 15,         # 6 + 9 = 15 baixas para bust
    'busts_esperados': '2 por ano',
    'retorno_10k': '~R$ 25k/mes',
}

CONFIG_G6_NS10 = {
    'nome': 'G6+NS10 CONSERVADOR',
    'gatilho': 6,           # G6: 6 baixas consecutivas para entrar
    'nivel': 10,            # NS10
    'divisor': 1023,        # Divisor 1023 = 10 tentativas
    'tentativas': 10,
    'alvo': 1.99,           # Alvo de lucro
    'protecao': 16,         # 6 + 10 = 16 baixas para bust
    'busts_esperados': '0 (dataset 1.3M)',
    'retorno_10k': '~R$ 12k/mes',
}


# ============================================================
# PERSISTENCIA DE SESSAO
# ============================================================

SESSION_STATE_FILE = 'session_state.json'


@dataclass
class EstadoSessao:
    """Estado persistente da sessao"""
    # Identificacao
    sessao_id: str = ""
    inicio_timestamp: str = ""

    # Financeiro
    deposito_inicial: float = 0.0
    saldo_atual: float = 0.0
    total_saques: float = 0.0
    total_depositos: float = 0.0

    # Nivel e modo
    nivel_seguranca: int = 6
    config_modo: Dict = field(default_factory=dict)

    # Estatisticas
    sessoes_win: int = 0
    sessoes_loss: int = 0
    total_rodadas: int = 0

    # Perfil
    perfil_ativo: str = ""

    # Historico de apostas (para restaurar grafico)
    historico_apostas: List = field(default_factory=list)

    # Timestamp da ultima atualizacao (para Telegram verificar dados frescos)
    ultima_atualizacao: str = ""

    def to_dict(self) -> Dict:
        return {
            'sessao_id': self.sessao_id,
            'inicio_timestamp': self.inicio_timestamp,
            'deposito_inicial': self.deposito_inicial,
            'saldo_atual': self.saldo_atual,
            'total_saques': self.total_saques,
            'total_depositos': self.total_depositos,
            'nivel_seguranca': self.nivel_seguranca,
            'config_modo': self.config_modo,
            'sessoes_win': self.sessoes_win,
            'sessoes_loss': self.sessoes_loss,
            'total_rodadas': self.total_rodadas,
            'perfil_ativo': self.perfil_ativo,
            'historico_apostas': self.historico_apostas,
            'ultima_atualizacao': self.ultima_atualizacao,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EstadoSessao':
        return cls(
            sessao_id=data.get('sessao_id', ''),
            inicio_timestamp=data.get('inicio_timestamp', ''),
            deposito_inicial=data.get('deposito_inicial', 0.0),
            saldo_atual=data.get('saldo_atual', 0.0),
            total_saques=data.get('total_saques', 0.0),
            total_depositos=data.get('total_depositos', 0.0),
            nivel_seguranca=data.get('nivel_seguranca', 6),
            config_modo=data.get('config_modo', {}),
            sessoes_win=data.get('sessoes_win', 0),
            sessoes_loss=data.get('sessoes_loss', 0),
            total_rodadas=data.get('total_rodadas', 0),
            perfil_ativo=data.get('perfil_ativo', ''),
            historico_apostas=data.get('historico_apostas', []),
            ultima_atualizacao=data.get('ultima_atualizacao', ''),
        )


def get_session_state_path() -> str:
    """Retorna o caminho do arquivo de estado da sessao"""
    return os.path.join(os.path.dirname(__file__), SESSION_STATE_FILE)


def salvar_estado_sessao(estado: EstadoSessao):
    """Salva o estado da sessao em arquivo"""
    try:
        with open(get_session_state_path(), 'w', encoding='utf-8') as f:
            json.dump(estado.to_dict(), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"ERRO ao salvar estado: {e}")


def carregar_estado_sessao() -> Optional[EstadoSessao]:
    """Carrega o estado da sessao do arquivo"""
    path = get_session_state_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return EstadoSessao.from_dict(data)
    except Exception as e:
        print(f"ERRO ao carregar estado: {e}")
        return None


def existe_sessao_ativa() -> bool:
    """Verifica se existe uma sessao ativa salva"""
    return os.path.exists(get_session_state_path())


# ============================================================
# CONFIGURACAO DOS NIVEIS DE SEGURANCA
# ============================================================

NIVEIS_SEGURANCA = {
    6: {
        'nome': 'NS6',
        'tentativas': 6,
        'divisor': 63,
        'multiplicadores': [1, 2, 4, 8, 16, 32],
        'threshold': 95,
        'risco_por_trigger': 1.56,
        'lucro_por_win': 1.57,
    },
    7: {
        'nome': 'NS7',
        'tentativas': 7,
        'divisor': 127,
        'multiplicadores': [1, 2, 4, 8, 16, 32, 64],
        'threshold': 191,
        'risco_por_trigger': 0.78,
        'lucro_por_win': 0.78,
    },
    8: {
        'nome': 'NS8',
        'tentativas': 8,
        'divisor': 255,
        'multiplicadores': [1, 2, 4, 8, 16, 32, 64, 128],
        'threshold': 383,
        'risco_por_trigger': 0.39,
        'lucro_por_win': 0.39,
    },
    9: {
        'nome': 'NS9',
        'tentativas': 9,
        'divisor': 511,
        'multiplicadores': [1, 2, 4, 8, 16, 32, 64, 128, 256],
        'threshold': 767,
        'risco_por_trigger': 0.19,
        'lucro_por_win': 0.19,
    },
    10: {
        'nome': 'NS10',
        'tentativas': 10,
        'divisor': 1023,
        'multiplicadores': [1, 2, 4, 8, 16, 32, 64, 128, 256, 512],
        'threshold': 1535,
        'risco_por_trigger': 0.10,
        'lucro_por_win': 0.10,
    },
}

# ============================================================
# ALVOS PARA TODAS AS ESTRATEGIAS
# ============================================================

ALVO_LUCRO = 2.00       # T1-T4: geracao de lucro
ALVO_SEGURANCA = 1.25   # Slot de seguranca
ALVO_ZERAR = 2.00       # T6+ (exceto ultima): tentar zerar
ALVO_T6_NS6 = 2.50      # T6 NS6: slot principal @ 2.50x

# ============================================================
# CONFIGURACAO ESTRATEGIA GAGO - Divisor 7, Progressao 1-2-4-1-2-4
# ============================================================

NIVEL_GAGO = {
    'nome': 'GAGO',
    'tentativas': 6,
    'divisor': 7,
    'multiplicadores': [1, 2, 4, 1, 2, 4],  # Ciclo 1 (1-2-4) + Ciclo 2 (1-2-4)
    'threshold': 0,  # Sem threshold minimo (multi-banca)
    'risco_por_trigger': 200.0,  # 200% da banca por trigger (14x base)
    'lucro_por_win': 14.14,  # ~14% por win (base * 0.99)
}

def get_config_tentativa_gago(tentativa: int) -> TentativaConfig:
    """
    Retorna configuracao da tentativa para estrategia GAGO.

    Estrategia GAGO (divisor 7, progressao 1-2-4-1-2-4):
    - T1-T3: Ciclo 1 - 1 slot @ 1.99x (geracao de lucro)
    - T4-T5: Ciclo 2 - 2 slots (37.5% @ 1.99x + 62.5% @ 1.25x) - PARAR no cenario B
    - T6: Ciclo 2 - 2 slots (37.5% @ 2.50x + 62.5% @ 1.25x) - ultima tentativa
    """
    # Ciclo 1: T1-T3 - 1 slot @ 1.99x
    if tentativa <= 3:
        return TentativaConfig(
            slots=[SlotConfig(proporcao=1, alvo=ALVO_LUCRO)],
            divisor_proporcao=1,
            parar_cenario_b=False,
            is_ultima=False
        )

    # Ciclo 2: T4-T5 - 2 slots (37.5% @ 1.99x + 62.5% @ 1.25x) - PARAR no cenario B
    if tentativa in [4, 5]:
        return TentativaConfig(
            slots=[
                SlotConfig(proporcao=3, alvo=ALVO_LUCRO),      # Slot 1: 3/8 (37.5%) @ 1.99x
                SlotConfig(proporcao=5, alvo=ALVO_SEGURANCA)   # Slot 2: 5/8 (62.5%) @ 1.25x
            ],
            divisor_proporcao=8,
            parar_cenario_b=True,  # PARAR no cenario B para evitar perda maior
            is_ultima=False
        )

    # T6: ultima - 2 slots (37.5% @ 2.50x + 62.5% @ 1.25x)
    if tentativa == 6:
        return TentativaConfig(
            slots=[
                SlotConfig(proporcao=3, alvo=ALVO_T6_NS6),     # Slot 1: 3/8 (37.5%) @ 2.50x
                SlotConfig(proporcao=5, alvo=ALVO_SEGURANCA)   # Slot 2: 5/8 (62.5%) @ 1.25x
            ],
            divisor_proporcao=8,
            parar_cenario_b=False,  # Ultima tentativa, nao para
            is_ultima=True
        )

    # Fallback (nao deveria acontecer)
    return TentativaConfig(
        slots=[SlotConfig(proporcao=1, alvo=ALVO_LUCRO)],
        divisor_proporcao=1,
        parar_cenario_b=False,
        is_ultima=False
    )


def get_alvos_gago() -> List[float]:
    """
    Retorna lista de alvos para estrategia GAGO.
    Retorna o alvo principal de cada tentativa.
    """
    alvos = []
    for t in range(1, 7):  # T1 a T6
        config = get_config_tentativa_gago(t)
        alvos.append(config.slots[0].alvo)
    return alvos


# ============================================================
# CONFIGURACAO ESTRATEGIA V4 - 2 SLOTS
# ============================================================

def get_config_tentativa_v4(nivel: int, tentativa: int, alvo_defesa: float = None) -> TentativaConfig:
    """
    Retorna configuracao da tentativa para estrategia V4.

    Estrategia V4 CORRIGIDA v2 (05/01/2026):

    NS6:
    - T1-T4: 1 slot @ 1.99x
    - T5: 2 slots (6/16 @ 1.99x + 10/16 @ defesa) - PARAR no cenario B
    - T6 (ultima): 2 slots (12/32 @ 2.50x + 20/32 @ defesa)

    NS7+:
    - T1 ate penpenultima: 1 slot @ 1.99x (lucrar)
    - Penultima: 2 slots (6/16 @ 1.99x + 10/16 @ defesa) - PARAR no cenario B
    - Ultima: 2 slots (12/32 @ 2.50x + 20/32 @ defesa) - igual NS6!

    Args:
        nivel: Nivel de seguranca (6-10)
        tentativa: Numero da tentativa atual
        alvo_defesa: Alvo de defesa (default 1.25, usar 1.10 para NS7_PURO)

    Exemplos:
    - NS7: T1-T5 @ 1.99x, T6 = 2 slots PARAR, T7 = 2 slots 2.5x/defesa
    - NS8: T1-T6 @ 1.99x, T7 = 2 slots PARAR, T8 = 2 slots 2.5x/defesa

    Justificativa da ultima @ 2.5x/defesa:
    - Em 133K mults, 60% dos T7 tiveram mult >= 2.50x
    - Com 2 slots, sangra -12% em vez de -37% quando >= 2.50x
    - Resultado: +R$170K a mais na simulacao
    """
    # Usar ALVO_SEGURANCA como default se nao especificado
    if alvo_defesa is None:
        alvo_defesa = ALVO_SEGURANCA
    max_tentativas = NIVEIS_SEGURANCA[nivel]['tentativas']
    is_ultima = (tentativa == max_tentativas)
    is_penultima = (tentativa == max_tentativas - 1)

    # ========== NS6 (caso especial) ==========
    if nivel == 6:
        # T1-T4: 1 slot @ 1.99x
        if tentativa <= 4:
            return TentativaConfig(
                slots=[SlotConfig(proporcao=1, alvo=ALVO_LUCRO)],
                divisor_proporcao=1,
                parar_cenario_b=False,
                is_ultima=False
            )

        # T5 NS6: 2 slots (6/16 @ 1.99x + 10/16 @ defesa) - PARAR no cenario B
        if tentativa == 5:
            return TentativaConfig(
                slots=[
                    SlotConfig(proporcao=6, alvo=ALVO_LUCRO),    # Slot 1: 6/16 @ 1.99x
                    SlotConfig(proporcao=10, alvo=alvo_defesa)   # Slot 2: 10/16 @ defesa
                ],
                divisor_proporcao=16,
                parar_cenario_b=True,
                is_ultima=False
            )

        # T6 NS6 (ultima): 2 slots (12/32 @ 2.50x + 20/32 @ defesa)
        if tentativa == 6:
            return TentativaConfig(
                slots=[
                    SlotConfig(proporcao=12, alvo=ALVO_T6_NS6),   # Slot 1: 12/32 @ 2.50x
                    SlotConfig(proporcao=20, alvo=alvo_defesa)    # Slot 2: 20/32 @ defesa
                ],
                divisor_proporcao=32,
                parar_cenario_b=False,
                is_ultima=True
            )

    # ========== NS7+ ==========

    # Ultima tentativa (NS7+): 2 slots (12/32 @ 2.50x + 20/32 @ defesa)
    # Igual ao T6 do NS6 - recupera mais quando mult >= 2.50x
    if is_ultima:
        return TentativaConfig(
            slots=[
                SlotConfig(proporcao=12, alvo=ALVO_T6_NS6),   # Slot 1: 12/32 @ 2.50x
                SlotConfig(proporcao=20, alvo=alvo_defesa)    # Slot 2: 20/32 @ defesa
            ],
            divisor_proporcao=32,
            parar_cenario_b=False,
            is_ultima=True
        )

    # Penultima tentativa (NS7+): 2 slots - PARAR no cenario B
    # Esta e a tentativa CRITICA que evita o BUST!
    if is_penultima:
        return TentativaConfig(
            slots=[
                SlotConfig(proporcao=6, alvo=ALVO_LUCRO),    # Slot 1: 6/16 @ 1.99x
                SlotConfig(proporcao=10, alvo=alvo_defesa)   # Slot 2: 10/16 @ defesa
            ],
            divisor_proporcao=16,
            parar_cenario_b=True,  # CRITICO: Parar no cenario B evita ir pra ultima!
            is_ultima=False
        )

    # T1 ate penpenultima (NS7+): 1 slot @ 1.99x (lucrar/zerar)
    return TentativaConfig(
        slots=[SlotConfig(proporcao=1, alvo=ALVO_LUCRO)],
        divisor_proporcao=1,
        parar_cenario_b=False,
        is_ultima=False
    )


def get_alvos(nivel: int) -> List[float]:
    """
    Retorna lista de alvos para compatibilidade.
    Para V4, retorna o alvo principal de cada tentativa.
    """
    tentativas = NIVEIS_SEGURANCA[nivel]['tentativas']
    alvos = []

    for t in range(1, tentativas + 1):
        config = get_config_tentativa_v4(nivel, t)
        # Retorna o alvo do primeiro slot (principal)
        alvos.append(config.slots[0].alvo)

    return alvos


def detectar_cenario(multiplicador: float, config: TentativaConfig, slot2_executado: bool = True) -> Cenario:
    """
    Detecta o cenario baseado no multiplicador e configuracao.

    Para 2 slots:
    - Cenario A: mult >= alvo alto (ambos ganham)
    - Cenario B: alvo baixo <= mult < alvo alto (so slot seguranca ganha)
    - Cenario C: mult < alvo baixo (ambos perdem)

    IMPORTANTE: Se slot2_executado=False, Cenario B vira Cenario C!
    (pois o slot2 nao entrou, entao nao pode ter ganho)

    Para 1 slot:
    - WIN: mult >= alvo
    - LOSS: mult < alvo
    """
    if config.is_2_slots:
        alvo_alto = max(s.alvo for s in config.slots)
        alvo_baixo = min(s.alvo for s in config.slots)

        if multiplicador >= alvo_alto:
            return Cenario.A
        elif multiplicador >= alvo_baixo:
            # Se slot 2 NAO entrou, nao pode ser Cenario B!
            # Tratar como Cenario C para ir para T6
            if not slot2_executado:
                return Cenario.C
            return Cenario.B
        else:
            return Cenario.C
    else:
        alvo = config.slots[0].alvo
        if multiplicador >= alvo:
            return Cenario.WIN
        else:
            return Cenario.LOSS

def get_nivel_para_banca(banca: float) -> int:
    """Retorna o maior nivel de seguranca permitido para a banca"""
    for nivel in [10, 9, 8, 7, 6]:
        if banca >= NIVEIS_SEGURANCA[nivel]['threshold']:
            return nivel
    return 6  # Minimo

def get_nivel_maximo_permitido(banca: float) -> int:
    """Alias para get_nivel_para_banca"""
    return get_nivel_para_banca(banca)


class SessionState(Enum):
    """Estados possiveis da sessao"""
    AGUARDANDO_GATILHO = "aguardando_gatilho"
    EM_MARTINGALE = "em_martingale"
    FINALIZADA_WIN = "finalizada_win"
    FINALIZADA_LOSS = "finalizada_loss"


@dataclass
class TentativaInfo:
    """Informacoes de uma tentativa individual (suporta 2 slots)"""
    numero: int
    multiplicador_resultado: Optional[float] = None
    cenario: Optional[Cenario] = None
    timestamp: Optional[datetime] = None

    # Slot 1
    valor_slot1: float = 0.0
    alvo_slot1: float = 0.0
    resultado_slot1: Optional[str] = None  # "WIN" ou "LOSS"

    # Slot 2 (opcional)
    valor_slot2: float = 0.0
    alvo_slot2: float = 0.0
    resultado_slot2: Optional[str] = None

    @property
    def is_2_slots(self) -> bool:
        return self.valor_slot2 > 0

    @property
    def valor_total(self) -> float:
        return self.valor_slot1 + self.valor_slot2

    # Compatibilidade com codigo antigo
    @property
    def valor_aposta(self) -> float:
        return self.valor_total

    @property
    def alvo(self) -> float:
        return self.alvo_slot1

    @property
    def resultado(self) -> Optional[str]:
        if self.cenario in [Cenario.A, Cenario.WIN]:
            return "WIN"
        elif self.cenario in [Cenario.B, Cenario.C, Cenario.LOSS]:
            return "LOSS"
        return None


@dataclass
class MartingaleSession:
    """
    Gerencia uma sessao completa de martingale.

    Estrategia V4 - 2 Slots:
    - T1-T4: 1 slot @ 1.99x (lucro)
    - T5: 2 slots (6/16 @ 1.99x + 10/16 @ 1.25x)
      - Cenario A (>=1.99x): FIM
      - Cenario B (1.25-1.98x): PARAR
      - Cenario C (<1.25x): continuar
    - T6+: 1 slot @ 1.99x (zerar)
    - Ultima: 1 slot @ 1.25x (sobrevivencia)

    Estrategia GAGO - Divisor 7, Progressao 1-2-4-1-2-4:
    - T1-T3: Ciclo 1 - 1 slot @ 1.99x
    - T4-T5: Ciclo 2 - 2 slots (37.5% @ 1.99x + 62.5% @ 1.25x) - PARAR cenario B
    - T6: Ciclo 2 - 2 slots (37.5% @ 2.50x + 62.5% @ 1.25x)

    Niveis de Seguranca: NS6 a NS10, ou GAGO
    """

    # Configuracao (definida uma vez)
    GATILHO: int = 6  # Gatilho de 6 baixos consecutivos
    THRESHOLD_BAIXO: float = 2.0
    PCT_RISCO: float = 1.0  # 100% do saldo

    # Nivel de seguranca (configuravel)
    nivel_seguranca: int = 6

    # Modo GAGO (estrategia alternativa com divisor 7)
    modo_gago: bool = False

    # Alvo de defesa configuravel (1.25 padrao, 1.10 para NS7_PURO)
    alvo_defesa: float = 1.25

    # Propriedades derivadas do nivel (ou GAGO)
    @property
    def MAX_TENTATIVAS(self) -> int:
        if self.modo_gago:
            return NIVEL_GAGO['tentativas']
        return NIVEIS_SEGURANCA[self.nivel_seguranca]['tentativas']

    @property
    def DIVISOR(self) -> int:
        if self.modo_gago:
            return NIVEL_GAGO['divisor']
        return NIVEIS_SEGURANCA[self.nivel_seguranca]['divisor']

    @property
    def ALVOS(self) -> List[float]:
        if self.modo_gago:
            return get_alvos_gago()
        return get_alvos(self.nivel_seguranca)

    @property
    def MULTIPLICADORES_APOSTA(self) -> List[int]:
        if self.modo_gago:
            return NIVEL_GAGO['multiplicadores']
        return NIVEIS_SEGURANCA[self.nivel_seguranca]['multiplicadores']

    @property
    def NOME_NIVEL(self) -> str:
        if self.modo_gago:
            return NIVEL_GAGO['nome']
        return NIVEIS_SEGURANCA[self.nivel_seguranca]['nome']

    # Estado da sessao
    state: SessionState = SessionState.AGUARDANDO_GATILHO
    sequencia_baixos: int = 0
    tentativa_atual: int = 0

    # Valores calculados no inicio do martingale
    saldo_inicio: float = 0.0
    aposta_base: float = 0.0

    # Valores capturados no fim
    saldo_fim: float = 0.0
    lucro_perda: float = 0.0

    # Historico
    tentativas: List[TentativaInfo] = field(default_factory=list)
    multiplicadores_gatilho: List[float] = field(default_factory=list)

    # Timestamps
    timestamp_inicio: Optional[datetime] = None
    timestamp_fim: Optional[datetime] = None

    def reset(self):
        """Reseta para nova sessao"""
        self.state = SessionState.AGUARDANDO_GATILHO
        self.sequencia_baixos = 0
        self.tentativa_atual = 0
        self.saldo_inicio = 0.0
        self.aposta_base = 0.0
        self.saldo_fim = 0.0
        self.lucro_perda = 0.0
        self.tentativas = []
        self.multiplicadores_gatilho = []
        self.timestamp_inicio = None
        self.timestamp_fim = None

    def processar_multiplicador(self, multiplicador: float, slot2_executado: bool = True) -> Dict:
        """
        Processa um multiplicador e retorna acao a tomar.

        Args:
            multiplicador: O multiplicador da rodada
            slot2_executado: Se o slot 2 foi executado com sucesso (para T5 com 2 slots)

        Retorna:
        {
            'acao': 'aguardar' | 'apostar' | 'finalizar',
            'valor_aposta': float (se acao == 'apostar'),
            'alvo': float (se acao == 'apostar'),
            'tentativa': int (se acao == 'apostar'),
            'resultado_sessao': 'win' | 'loss' (se acao == 'finalizar'),
            'precisa_ler_saldo_inicio': bool,
            'precisa_ler_saldo_fim': bool,
        }
        """

        if self.state == SessionState.AGUARDANDO_GATILHO:
            return self._processar_aguardando_gatilho(multiplicador)

        elif self.state == SessionState.EM_MARTINGALE:
            return self._processar_em_martingale(multiplicador, slot2_executado)

        else:
            # Sessao ja finalizada, resetar para proxima
            self.reset()
            return self._processar_aguardando_gatilho(multiplicador)

    def _processar_aguardando_gatilho(self, multiplicador: float) -> Dict:
        """Processa multiplicador enquanto aguarda gatilho"""

        if multiplicador < self.THRESHOLD_BAIXO:
            seq_antes = self.sequencia_baixos
            self.sequencia_baixos += 1
            self.multiplicadores_gatilho.append(multiplicador)

            # VALIDACAO: sequencia_baixos DEVE ser igual ao len(multiplicadores_gatilho)
            qtd_mults = len(self.multiplicadores_gatilho)
            if self.sequencia_baixos != qtd_mults:
                print(f"[BUG CRITICO] sequencia_baixos={self.sequencia_baixos} != len(mults)={qtd_mults}")
                print(f"[BUG CRITICO] Mults: {self.multiplicadores_gatilho}")
                # Corrigir sincronizacao
                self.sequencia_baixos = qtd_mults

            # DEBUG: Ver valores reais - ANTES e DEPOIS do incremento
            trigger_status = ""
            if self.sequencia_baixos == self.GATILHO:
                trigger_status = "-> TRIGGER!"
            elif self.sequencia_baixos > self.GATILHO:
                trigger_status = f"-> ANOMALIA! (>{self.GATILHO})"
            print(f"[DEBUG] mult={multiplicador:.2f} | seq: {seq_antes}->{self.sequencia_baixos} | mults={qtd_mults} | GATILHO={self.GATILHO} {trigger_status}")

            # Atingiu gatilho? USAR == ao inves de >= para evitar anomalias
            if self.sequencia_baixos == self.GATILHO:
                # Hora de iniciar martingale!
                self.state = SessionState.EM_MARTINGALE
                self.tentativa_atual = 1
                self.timestamp_inicio = datetime.now()

                return {
                    'acao': 'apostar',
                    'tentativa': 1,
                    'precisa_ler_saldo_inicio': True,  # IMPORTANTE: Ler saldo agora!
                    'precisa_ler_saldo_fim': False,
                    'info': f'Gatilho! {self.sequencia_baixos} baixos consecutivos'
                }
            else:
                return {
                    'acao': 'aguardar',
                    'sequencia_atual': self.sequencia_baixos,
                    'faltam': self.GATILHO - self.sequencia_baixos,
                    'precisa_ler_saldo_inicio': False,
                    'precisa_ler_saldo_fim': False,
                }
        else:
            # Multiplicador alto, resetar contagem
            seq_antes = self.sequencia_baixos
            self.sequencia_baixos = 0
            self.multiplicadores_gatilho = []

            # DEBUG: Mostrar reset
            if seq_antes > 0:
                print(f"[DEBUG] mult={multiplicador:.2f} | seq: {seq_antes}->0 | RESET (mult >= 2.00)")

            return {
                'acao': 'aguardar',
                'sequencia_atual': 0,
                'faltam': self.GATILHO,
                'precisa_ler_saldo_inicio': False,
                'precisa_ler_saldo_fim': False,
                'info': f'Reset - multiplicador {multiplicador:.2f}x >= {self.THRESHOLD_BAIXO}x'
            }

    def _processar_em_martingale(self, multiplicador: float, slot2_executado: bool = True) -> Dict:
        """
        Processa resultado de uma tentativa do martingale (V4 com cenarios).

        Args:
            multiplicador: O multiplicador da rodada
            slot2_executado: Se o slot 2 foi executado com sucesso

        Retorna dict com:
        - acao: 'finalizar' | 'apostar' | 'parar'
        - cenario: Cenario detectado (A, B, C, WIN, LOSS)
        - info: Mensagem descritiva
        """
        # Obter configuracao da tentativa atual (V4 ou GAGO)
        if self.modo_gago:
            config = get_config_tentativa_gago(self.tentativa_atual)
        else:
            config = get_config_tentativa_v4(self.nivel_seguranca, self.tentativa_atual, self.alvo_defesa)
        mult_aposta = self.MULTIPLICADORES_APOSTA[self.tentativa_atual - 1]

        # Calcular valores dos slots
        valor_total = self.aposta_base * mult_aposta

        if config.is_2_slots:
            valor_slot1 = valor_total * config.slots[0].proporcao / config.divisor_proporcao
            valor_slot2 = valor_total * config.slots[1].proporcao / config.divisor_proporcao
            alvo_slot1 = config.slots[0].alvo
            alvo_slot2 = config.slots[1].alvo
        else:
            valor_slot1 = valor_total
            valor_slot2 = 0.0
            alvo_slot1 = config.slots[0].alvo
            alvo_slot2 = 0.0

        # Detectar cenario (passando info se slot2 foi executado)
        cenario = detectar_cenario(multiplicador, config, slot2_executado)

        # Registrar tentativa
        tentativa = TentativaInfo(
            numero=self.tentativa_atual,
            multiplicador_resultado=multiplicador,
            cenario=cenario,
            timestamp=datetime.now(),
            valor_slot1=valor_slot1,
            alvo_slot1=alvo_slot1,
            resultado_slot1="WIN" if multiplicador >= alvo_slot1 else "LOSS",
            valor_slot2=valor_slot2,
            alvo_slot2=alvo_slot2,
            resultado_slot2="WIN" if valor_slot2 > 0 and multiplicador >= alvo_slot2 else ("LOSS" if valor_slot2 > 0 else None)
        )
        self.tentativas.append(tentativa)

        # ============================================================
        # LOGICA V4: Processar por cenario
        # ============================================================

        # Cenario A ou WIN: Sessao finalizada com sucesso
        if cenario in [Cenario.A, Cenario.WIN]:
            self.state = SessionState.FINALIZADA_WIN
            self.timestamp_fim = datetime.now()

            if config.is_2_slots:
                info = f'CENARIO A! T{self.tentativa_atual} - {multiplicador:.2f}x >= {alvo_slot1}x (ambos ganham)'
            else:
                info = f'WIN! T{self.tentativa_atual} - {multiplicador:.2f}x >= {alvo_slot1}x'

            return {
                'acao': 'finalizar',
                'resultado_sessao': 'win',
                'cenario': cenario,
                'tentativa_vitoria': self.tentativa_atual,
                'multiplicador': multiplicador,
                'config': config,
                'precisa_ler_saldo_inicio': False,
                'precisa_ler_saldo_fim': True,
                'info': info
            }

        # Cenario B: Slot de seguranca ganhou, slot principal perdeu
        if cenario == Cenario.B:
            # Se parar_cenario_b == True (T5), aceitar perda parcial e PARAR
            if config.parar_cenario_b:
                self.state = SessionState.FINALIZADA_LOSS  # Perda parcial
                self.timestamp_fim = datetime.now()

                return {
                    'acao': 'parar',  # ACAO ESPECIAL: Parar voluntariamente
                    'resultado_sessao': 'parar_cenario_b',
                    'cenario': cenario,
                    'tentativa_final': self.tentativa_atual,
                    'multiplicador': multiplicador,
                    'config': config,
                    'precisa_ler_saldo_inicio': False,
                    'precisa_ler_saldo_fim': True,
                    'info': f'CENARIO B! T{self.tentativa_atual} - {multiplicador:.2f}x (PARAR - so slot2 ganhou)'
                }
            else:
                # Cenario B mas nao precisa parar (nao deveria acontecer em V4)
                pass

        # Cenario C ou LOSS: Ambos slots perderam ou slot unico perdeu
        if cenario in [Cenario.C, Cenario.LOSS]:
            # Verificar se e ultima tentativa
            if config.is_ultima:
                self.state = SessionState.FINALIZADA_LOSS
                self.timestamp_fim = datetime.now()

                if cenario == Cenario.C:
                    info = f'CENARIO C! T{self.tentativa_atual} - {multiplicador:.2f}x < {alvo_slot2}x (BUST - ambos perderam)'
                else:
                    info = f'BUST! T{self.tentativa_atual} - {multiplicador:.2f}x < {alvo_slot1}x (ultima tentativa)'

                return {
                    'acao': 'finalizar',
                    'resultado_sessao': 'loss',
                    'cenario': cenario,
                    'tentativa_final': self.tentativa_atual,
                    'multiplicador': multiplicador,
                    'config': config,
                    'precisa_ler_saldo_inicio': False,
                    'precisa_ler_saldo_fim': True,
                    'info': info
                }
            else:
                # Proxima tentativa
                self.tentativa_atual += 1

                if cenario == Cenario.C:
                    info = f'CENARIO C! T{self.tentativa_atual - 1} - {multiplicador:.2f}x < {alvo_slot2}x -> T{self.tentativa_atual}'
                else:
                    info = f'LOSS T{self.tentativa_atual - 1} - {multiplicador:.2f}x < {alvo_slot1}x -> T{self.tentativa_atual}'

                return {
                    'acao': 'apostar',
                    'cenario': cenario,
                    'tentativa': self.tentativa_atual,
                    'precisa_ler_saldo_inicio': False,
                    'precisa_ler_saldo_fim': False,
                    'info': info
                }

        # Fallback (nao deveria chegar aqui)
        return {
            'acao': 'aguardar',
            'cenario': cenario,
            'info': f'Estado inesperado: cenario={cenario}'
        }

    def definir_saldo_inicio(self, saldo: float):
        """Define o saldo no inicio do martingale e calcula aposta base"""
        self.saldo_inicio = saldo
        self.aposta_base = (saldo * self.PCT_RISCO) / self.DIVISOR

    def set_nivel_seguranca(self, nivel: int):
        """Define o nivel de seguranca (NS6-NS10)"""
        if nivel in NIVEIS_SEGURANCA:
            self.nivel_seguranca = nivel
            self.modo_gago = False  # Desativa GAGO ao mudar nivel
        else:
            raise ValueError(f"Nivel invalido: {nivel}. Use 6, 7, 8, 9 ou 10.")

    def set_modo_gago(self, ativo: bool = True):
        """Ativa ou desativa o modo GAGO"""
        self.modo_gago = ativo
        if ativo:
            # No modo GAGO, nivel nao importa (usa config propria)
            pass

    def get_info_nivel(self) -> Dict:
        """Retorna informacoes do nivel atual (ou GAGO)"""
        if self.modo_gago:
            cfg = NIVEL_GAGO
            return {
                'nivel': 'GAGO',
                'nome': cfg['nome'],
                'tentativas': cfg['tentativas'],
                'divisor': cfg['divisor'],
                'threshold': cfg['threshold'],
                'risco_por_trigger': cfg['risco_por_trigger'],
                'lucro_por_win': cfg['lucro_por_win'],
                'alvos': self.ALVOS,
            }
        cfg = NIVEIS_SEGURANCA[self.nivel_seguranca]
        return {
            'nivel': self.nivel_seguranca,
            'nome': cfg['nome'],
            'tentativas': cfg['tentativas'],
            'divisor': cfg['divisor'],
            'threshold': cfg['threshold'],
            'risco_por_trigger': cfg['risco_por_trigger'],
            'lucro_por_win': cfg['lucro_por_win'],
            'alvos': self.ALVOS,
        }

    def definir_saldo_fim(self, saldo: float):
        """Define o saldo no fim do martingale e calcula P/L"""
        self.saldo_fim = saldo
        self.lucro_perda = saldo - self.saldo_inicio

    def get_valor_aposta_atual(self) -> float:
        """Retorna o valor TOTAL da aposta para a tentativa atual"""
        if self.tentativa_atual < 1 or self.tentativa_atual > self.MAX_TENTATIVAS:
            return 0.0
        return self.aposta_base * self.MULTIPLICADORES_APOSTA[self.tentativa_atual - 1]

    def get_alvo_atual(self) -> float:
        """Retorna o alvo PRINCIPAL para a tentativa atual (compatibilidade)"""
        if self.tentativa_atual < 1 or self.tentativa_atual > self.MAX_TENTATIVAS:
            return 0.0
        return self.ALVOS[self.tentativa_atual - 1]

    def get_config_aposta_atual(self) -> Dict:
        """
        Retorna configuracao completa da aposta atual (V4).

        Retorna dict com:
        - num_slots: 1 ou 2
        - slots: lista de {valor, alvo, slot_id}
        - valor_total: soma dos valores
        - is_2_slots: bool
        - parar_cenario_b: bool (se deve parar no cenario B)
        - is_ultima: bool
        """
        if self.tentativa_atual < 1 or self.tentativa_atual > self.MAX_TENTATIVAS:
            return {'num_slots': 0, 'slots': [], 'valor_total': 0}

        # Obter configuracao (V4 ou GAGO)
        if self.modo_gago:
            config = get_config_tentativa_gago(self.tentativa_atual)
        else:
            config = get_config_tentativa_v4(self.nivel_seguranca, self.tentativa_atual, self.alvo_defesa)
        mult_aposta = self.MULTIPLICADORES_APOSTA[self.tentativa_atual - 1]
        valor_total = self.aposta_base * mult_aposta

        slots = []
        for i, slot_config in enumerate(config.slots):
            valor_slot = valor_total * slot_config.proporcao / config.divisor_proporcao
            slots.append({
                'slot_id': i + 1,
                'valor': valor_slot,
                'alvo': slot_config.alvo,
                'proporcao': f"{slot_config.proporcao}/{config.divisor_proporcao}"
            })

        return {
            'tentativa': self.tentativa_atual,
            'num_slots': config.num_slots,
            'slots': slots,
            'valor_total': valor_total,
            'is_2_slots': config.is_2_slots,
            'parar_cenario_b': config.parar_cenario_b,
            'is_ultima': config.is_ultima
        }

    def get_total_apostado(self) -> float:
        """Retorna o total apostado ate agora"""
        return sum(t.valor_total for t in self.tentativas)

    def get_resumo(self) -> Dict:
        """Retorna resumo da sessao"""
        return {
            'state': self.state.value,
            'nivel_seguranca': self.nivel_seguranca,
            'nome_nivel': NIVEIS_SEGURANCA[self.nivel_seguranca]['nome'],
            'sequencia_baixos': self.sequencia_baixos,
            'tentativa_atual': self.tentativa_atual,
            'max_tentativas': self.MAX_TENTATIVAS,
            'saldo_inicio': self.saldo_inicio,
            'saldo_fim': self.saldo_fim,
            'lucro_perda': self.lucro_perda,
            'aposta_base': self.aposta_base,
            'total_apostado': self.get_total_apostado(),
            'tentativas': len(self.tentativas),
            'resultado': self.state.value if 'finalizada' in self.state.value else 'em_andamento'
        }


# Teste V4
if __name__ == "__main__":
    print("=" * 70)
    print("TESTE MARTINGALE SESSION V4 - ESTRATEGIA 2 SLOTS")
    print("=" * 70)

    # Mostrar configuracao V4 para cada nivel
    print("\nCONFIGURACAO V4 POR NIVEL:")
    print("-" * 70)
    for nivel in [6, 7, 8, 9, 10]:
        cfg = NIVEIS_SEGURANCA[nivel]
        print(f"\n{cfg['nome']} ({cfg['tentativas']} tentativas):")
        for t in range(1, cfg['tentativas'] + 1):
            config = get_config_tentativa_v4(nivel, t)
            if config.is_2_slots:
                s1 = config.slots[0]
                s2 = config.slots[1]
                marca = " <- PARAR cen.B" if config.parar_cenario_b else ""
                marca = " <- ULTIMA" if config.is_ultima else marca
                print(f"  T{t}: 2 slots ({s1.proporcao}/{config.divisor_proporcao} @ {s1.alvo}x + "
                      f"{s2.proporcao}/{config.divisor_proporcao} @ {s2.alvo}x){marca}")
            else:
                s = config.slots[0]
                marca = " <- ULTIMA" if config.is_ultima else ""
                print(f"  T{t}: 1 slot @ {s.alvo}x{marca}")

    # Testar cenarios com NS7
    print("\n" + "=" * 70)
    print("TESTE CENARIOS V4 COM NS7")
    print("=" * 70)

    def testar_cenario(nome: str, multiplicadores: list, nivel: int = 7):
        print(f"\n--- {nome} ---")
        session = MartingaleSession()
        session.set_nivel_seguranca(nivel)
        saldo = 1270.0  # Banca de exemplo

        for i, mult in enumerate(multiplicadores):
            resultado = session.processar_multiplicador(mult)

            if resultado.get('precisa_ler_saldo_inicio'):
                session.definir_saldo_inicio(saldo)

            if resultado['acao'] == 'apostar':
                config = session.get_config_aposta_atual()
                if config['is_2_slots']:
                    s1 = config['slots'][0]
                    s2 = config['slots'][1]
                    print(f"  T{config['tentativa']}: R${s1['valor']:.2f}@{s1['alvo']}x + R${s2['valor']:.2f}@{s2['alvo']}x")
                else:
                    s = config['slots'][0]
                    print(f"  T{config['tentativa']}: R${s['valor']:.2f}@{s['alvo']}x")

            elif resultado['acao'] in ['finalizar', 'parar']:
                cenario = resultado.get('cenario', '')
                cenario_str = f" [{cenario.value}]" if cenario else ""
                print(f"  >> {resultado['info']}{cenario_str}")
                break

            elif resultado['acao'] == 'aguardar' and 'sequencia_atual' in resultado:
                if resultado['sequencia_atual'] > 0:
                    print(f"  Gatilho: {resultado['sequencia_atual']}/6")

    # Cenario 1: WIN em T1
    testar_cenario(
        "Cenario: WIN em T1",
        [1.5, 1.8, 1.3, 1.9, 1.2, 1.7, 2.50]  # 6 baixos + T1 ganha
    )

    # Cenario 2: T5 Cenario A (ambos ganham)
    testar_cenario(
        "Cenario: T5 Cenario A (mult >= 1.99x)",
        [1.5, 1.8, 1.3, 1.9, 1.2, 1.7,  # gatilho
         1.1, 1.3, 1.5, 1.8,             # T1-T4 perdem
         2.50]                            # T5: >= 1.99x = Cenario A
    )

    # Cenario 3: T5 Cenario B (PARAR - so slot2 ganha)
    testar_cenario(
        "Cenario: T5 Cenario B (1.25 <= mult < 1.99) -> PARAR",
        [1.5, 1.8, 1.3, 1.9, 1.2, 1.7,  # gatilho
         1.1, 1.3, 1.5, 1.8,             # T1-T4 perdem
         1.50]                            # T5: 1.25-1.98 = Cenario B -> PARAR!
    )

    # Cenario 4: T5 Cenario C -> T6 WIN
    testar_cenario(
        "Cenario: T5 Cenario C -> T6 WIN",
        [1.5, 1.8, 1.3, 1.9, 1.2, 1.7,  # gatilho
         1.1, 1.3, 1.5, 1.8,             # T1-T4 perdem
         1.10,                            # T5: < 1.25 = Cenario C -> T6
         2.50]                            # T6: >= 1.99x = WIN (zera!)
    )

    # Cenario 5: T5 Cenario C -> T6 LOSS -> T7 (ultima)
    testar_cenario(
        "Cenario: T5C -> T6 LOSS -> T7 (ultima @ 1.25x)",
        [1.5, 1.8, 1.3, 1.9, 1.2, 1.7,  # gatilho
         1.1, 1.3, 1.5, 1.8,             # T1-T4 perdem
         1.10,                            # T5: Cenario C -> T6
         1.50,                            # T6: < 1.99x -> T7
         1.30]                            # T7: >= 1.25x = WIN (sobrevive!)
    )

    # Cenario 6: BUST em T7
    testar_cenario(
        "Cenario: BUST em T7 (mult < 1.25x)",
        [1.5, 1.8, 1.3, 1.9, 1.2, 1.7,  # gatilho
         1.1, 1.3, 1.5, 1.8,             # T1-T4 perdem
         1.10,                            # T5: Cenario C -> T6
         1.50,                            # T6: < 1.99x -> T7
         1.10]                            # T7: < 1.25x = BUST!
    )

    print("\n" + "=" * 70)
    print("TESTE CONCLUIDO")
    print("=" * 70)
