#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
COMPOUND MANAGER - Gerenciador de Compound + Reserva de Lucros

CORRIGIDO 05/01/2026 - Nova logica de reserva:

Parametros:
- META_LUCRO_PCT: 10% da banca_operacional
- PCT_RESERVA: 50% do lucro vai para reserva (INTOCAVEL)
- PCT_COMPOUND: 50% do lucro fica na banca

Fluxo:
1. Opera normalmente ate lucrar 10% da banca
2. Ao bater 10%:
   - Reserva 5% (intocavel, mesmo em BUST)
   - Compound 5% na banca operacional
   - Continua operando
3. Em caso de BUST:
   - Bot PARA imediatamente
   - Reserva e preservada
   - Usuario pode reiniciar com nova banca

IMPORTANTE:
- A reserva NUNCA e usada para apostas
- Mesmo em BUST, a reserva esta protegida
- Bot opera de forma autonoma e ininterrupta
"""

import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, List
import json
import os


@dataclass
class EstadoCompound:
    """Estado do compound manager para persistencia"""
    # Financeiro
    banca_inicial: float = 0.0        # Banca no inicio da sessao
    banca_operacional: float = 0.0    # Disponivel para apostas (compound cresce aqui)
    reserva_lucros: float = 0.0       # INTOCAVEL - reservado mesmo em BUST

    # Controle de lucro
    lucro_desde_ultima_meta: float = 0.0   # Lucro acumulado desde ultima reserva
    banca_na_ultima_meta: float = 0.0      # Banca quando bateu ultima meta (para calcular %)

    # Estatisticas
    total_metas_batidas: int = 0      # Quantas vezes bateu 10%
    total_reservado: float = 0.0      # Soma de tudo que foi para reserva
    total_compounded: float = 0.0     # Soma de tudo que foi reinvestido
    total_triggers: int = 0
    total_wins: int = 0
    total_losses: int = 0
    cenarios_b: int = 0

    # Controle de BUST
    bust_detectado: bool = False
    motivo_bust: str = ""
    timestamp_bust: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            'banca_inicial': self.banca_inicial,
            'banca_operacional': self.banca_operacional,
            'reserva_lucros': self.reserva_lucros,
            'lucro_desde_ultima_meta': self.lucro_desde_ultima_meta,
            'banca_na_ultima_meta': self.banca_na_ultima_meta,
            'total_metas_batidas': self.total_metas_batidas,
            'total_reservado': self.total_reservado,
            'total_compounded': self.total_compounded,
            'total_triggers': self.total_triggers,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'cenarios_b': self.cenarios_b,
            'bust_detectado': self.bust_detectado,
            'motivo_bust': self.motivo_bust,
            'timestamp_bust': self.timestamp_bust.isoformat() if self.timestamp_bust else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EstadoCompound':
        timestamp_bust = None
        if data.get('timestamp_bust'):
            try:
                timestamp_bust = datetime.fromisoformat(data['timestamp_bust'])
            except:
                pass

        return cls(
            banca_inicial=data.get('banca_inicial', 0.0),
            banca_operacional=data.get('banca_operacional', 0.0),
            reserva_lucros=data.get('reserva_lucros', 0.0),
            lucro_desde_ultima_meta=data.get('lucro_desde_ultima_meta', 0.0),
            banca_na_ultima_meta=data.get('banca_na_ultima_meta', 0.0),
            total_metas_batidas=data.get('total_metas_batidas', 0),
            total_reservado=data.get('total_reservado', 0.0),
            total_compounded=data.get('total_compounded', 0.0),
            total_triggers=data.get('total_triggers', 0),
            total_wins=data.get('total_wins', 0),
            total_losses=data.get('total_losses', 0),
            cenarios_b=data.get('cenarios_b', 0),
            bust_detectado=data.get('bust_detectado', False),
            motivo_bust=data.get('motivo_bust', ''),
            timestamp_bust=timestamp_bust,
        )


class CompoundManager:
    """
    Gerenciador de Compound + Reserva de Lucros.

    A cada 10% de lucro:
    - 5% vai para RESERVA (intocavel, mesmo em BUST)
    - 5% fica na banca (compound)

    Em caso de BUST:
    - Bot PARA
    - Reserva e preservada
    """

    # Parametros de Reserva
    META_LUCRO_PCT: float = 0.10       # Meta = 10% de lucro sobre a banca
    PCT_RESERVA: float = 0.50          # 50% do lucro vai para reserva (5% da banca)
    PCT_COMPOUND: float = 0.50         # 50% do lucro fica na banca (5% da banca)

    # Arquivo de estado
    STATE_FILE = 'compound_state.json'

    def __init__(self, banca_inicial: float = 0.0):
        """
        Inicializa o compound manager.

        Args:
            banca_inicial: Banca inicial para operacao
        """
        self.estado = EstadoCompound()

        if banca_inicial > 0:
            self.inicializar(banca_inicial)

    def inicializar(self, banca: float):
        """Inicializa com uma banca"""
        self.estado.banca_inicial = banca
        self.estado.banca_operacional = banca
        self.estado.banca_na_ultima_meta = banca
        self.estado.lucro_desde_ultima_meta = 0.0
        self.estado.reserva_lucros = 0.0
        self.estado.bust_detectado = False

    def get_banca_para_apostas(self) -> float:
        """
        Retorna a banca disponivel para apostas.
        NUNCA inclui a reserva!
        """
        if self.estado.bust_detectado:
            return 0.0  # BUST - nao pode apostar
        return self.estado.banca_operacional

    def registrar_resultado(self, lucro_perda: float, is_win: bool = True,
                           is_cenario_b: bool = False, is_bust: bool = False):
        """
        Registra resultado de um trigger.

        Args:
            lucro_perda: Lucro ou perda do trigger
            is_win: Se foi win
            is_cenario_b: Se foi cenario B (parada estrategica)
            is_bust: Se foi BUST (perda total)
        """
        # Verificar BUST
        if is_bust:
            self._processar_bust(f"BUST detectado. Perda: R$ {abs(lucro_perda):.2f}")
            return

        self.estado.total_triggers += 1
        self.estado.lucro_desde_ultima_meta += lucro_perda
        self.estado.banca_operacional += lucro_perda

        if is_win:
            self.estado.total_wins += 1
        else:
            self.estado.total_losses += 1

        if is_cenario_b:
            self.estado.cenarios_b += 1

        # Verificar se bateu meta de 10%
        meta_valor = self.estado.banca_na_ultima_meta * self.META_LUCRO_PCT
        if self.estado.lucro_desde_ultima_meta >= meta_valor:
            self._processar_meta_batida()

    def _processar_meta_batida(self):
        """Processa quando bate 10% de lucro"""
        lucro = self.estado.lucro_desde_ultima_meta

        # Calcular reserva (5%) e compound (5%)
        valor_reserva = lucro * self.PCT_RESERVA
        valor_compound = lucro * self.PCT_COMPOUND

        # Atualizar reserva (INTOCAVEL)
        self.estado.reserva_lucros += valor_reserva
        self.estado.total_reservado += valor_reserva
        self.estado.total_compounded += valor_compound

        # Atualizar banca operacional
        # A banca ja foi atualizada com o lucro total, entao precisa remover a parte da reserva
        self.estado.banca_operacional -= valor_reserva

        # Atualizar controles
        self.estado.total_metas_batidas += 1
        self.estado.banca_na_ultima_meta = self.estado.banca_operacional
        self.estado.lucro_desde_ultima_meta = 0.0

        # Salvar estado apos cada meta
        self.salvar_estado()

    def _processar_bust(self, motivo: str):
        """Processa BUST - para o bot e preserva reserva"""
        self.estado.bust_detectado = True
        self.estado.motivo_bust = motivo
        self.estado.timestamp_bust = datetime.now()
        self.estado.banca_operacional = 0.0  # Perdeu tudo que estava em jogo
        # MAS a reserva_lucros permanece intacta!
        self.salvar_estado()

    def pode_operar(self) -> bool:
        """Verifica se pode continuar operando"""
        if self.estado.bust_detectado:
            return False
        if self.estado.banca_operacional <= 0:
            return False
        return True

    def get_reserva(self) -> float:
        """Retorna o valor reservado (intocavel)"""
        return self.estado.reserva_lucros

    def get_patrimonio_total(self) -> float:
        """Retorna patrimonio total (banca + reserva)"""
        return self.estado.banca_operacional + self.estado.reserva_lucros

    def get_status(self) -> Dict:
        """Retorna status atual"""
        s = self.estado
        meta_valor = s.banca_na_ultima_meta * self.META_LUCRO_PCT if s.banca_na_ultima_meta > 0 else 0

        return {
            'banca_inicial': s.banca_inicial,
            'banca_operacional': s.banca_operacional,
            'reserva_lucros': s.reserva_lucros,
            'patrimonio_total': s.banca_operacional + s.reserva_lucros,
            'meta_valor': meta_valor,
            'lucro_desde_meta': s.lucro_desde_ultima_meta,
            'progresso_meta': (s.lucro_desde_ultima_meta / meta_valor * 100) if meta_valor > 0 else 0,
            'total_metas_batidas': s.total_metas_batidas,
            'total_reservado': s.total_reservado,
            'total_compounded': s.total_compounded,
            'total_triggers': s.total_triggers,
            'total_wins': s.total_wins,
            'total_losses': s.total_losses,
            'cenarios_b': s.cenarios_b,
            'bust_detectado': s.bust_detectado,
            'motivo_bust': s.motivo_bust,
            'pode_operar': self.pode_operar(),
        }

    def get_relatorio(self) -> str:
        """Retorna relatorio formatado"""
        s = self.estado
        meta_valor = s.banca_na_ultima_meta * self.META_LUCRO_PCT if s.banca_na_ultima_meta > 0 else 0
        progresso = (s.lucro_desde_ultima_meta / meta_valor * 100) if meta_valor > 0 else 0

        lines = [
            "=" * 55,
            "       COMPOUND + RESERVA DE LUCROS",
            "=" * 55,
            "",
            "FINANCEIRO",
            f"  Banca inicial:     R$ {s.banca_inicial:,.2f}",
            f"  Banca operacional: R$ {s.banca_operacional:,.2f}",
            f"  RESERVA (intocavel): R$ {s.reserva_lucros:,.2f}",
            f"  Patrimonio total:  R$ {s.banca_operacional + s.reserva_lucros:,.2f}",
            "",
            "META 10%",
            f"  Meta atual:        R$ {meta_valor:,.2f}",
            f"  Lucro acumulado:   R$ {s.lucro_desde_ultima_meta:,.2f}",
            f"  Progresso:         {progresso:.1f}%",
            "",
            "ESTATISTICAS",
            f"  Metas batidas:     {s.total_metas_batidas}x",
            f"  Total reservado:   R$ {s.total_reservado:,.2f}",
            f"  Total compounded:  R$ {s.total_compounded:,.2f}",
            f"  Triggers:          {s.total_triggers} (W:{s.total_wins} L:{s.total_losses})",
            f"  Cenarios B:        {s.cenarios_b}",
            "",
        ]

        if s.bust_detectado:
            lines.append("STATUS")
            lines.append(f"  [BUST] {s.motivo_bust}")
            lines.append(f"  Reserva preservada: R$ {s.reserva_lucros:,.2f}")
        else:
            lines.append("STATUS")
            lines.append("  [OPERANDO]")

        lines.append("=" * 55)
        return "\n".join(lines)

    def get_status_telegram(self) -> str:
        """Retorna status formatado para Telegram"""
        s = self.estado
        meta_valor = s.banca_na_ultima_meta * self.META_LUCRO_PCT if s.banca_na_ultima_meta > 0 else 0
        progresso = (s.lucro_desde_ultima_meta / meta_valor * 100) if meta_valor > 0 else 0

        if s.bust_detectado:
            return (
                f"[BUST] Bot parado\n"
                f"Reserva preservada: R$ {s.reserva_lucros:,.2f}"
            )

        return (
            f"Banca: R$ {s.banca_operacional:,.2f}\n"
            f"RESERVA: R$ {s.reserva_lucros:,.2f}\n"
            f"Meta 10%: {progresso:.1f}%\n"
            f"Metas: {s.total_metas_batidas}x"
        )

    def salvar_estado(self, filepath: str = None):
        """Salva estado em arquivo"""
        path = filepath or os.path.join(os.path.dirname(__file__), self.STATE_FILE)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.estado.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar estado compound: {e}")

    def carregar_estado(self, filepath: str = None) -> bool:
        """Carrega estado de arquivo"""
        path = filepath or os.path.join(os.path.dirname(__file__), self.STATE_FILE)
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.estado = EstadoCompound.from_dict(data)
                return True
        except Exception as e:
            print(f"Erro ao carregar estado compound: {e}")
            return False


# Teste
if __name__ == "__main__":
    print("=" * 60)
    print("TESTE COMPOUND + RESERVA DE LUCROS")
    print("=" * 60)

    # Simular operacao com banca inicial de R$ 10.000
    manager = CompoundManager(banca_inicial=10000.0)

    print(f"\n--- Estado Inicial ---")
    print(f"Banca: R$ {manager.estado.banca_operacional:,.2f}")
    print(f"Meta 10%: R$ {manager.estado.banca_na_ultima_meta * manager.META_LUCRO_PCT:,.2f}")

    # Simular wins ate bater meta (10%)
    print(f"\n--- Simulando triggers (NS7 ~0.78%/win) ---")
    lucro_por_win = 10000 * 0.0078  # ~R$ 78

    for i in range(15):
        manager.registrar_resultado(lucro_por_win, is_win=True)
        status = manager.get_status()

        print(f"Win {i+1}: Progresso {status['progresso_meta']:.1f}% | "
              f"Banca: R$ {status['banca_operacional']:,.2f} | "
              f"Reserva: R$ {status['reserva_lucros']:,.2f}")

        if status['total_metas_batidas'] >= 2:
            print(f"\n>>> 2 METAS BATIDAS!")
            break

    print(f"\n--- Relatorio Final ---")
    print(manager.get_relatorio())

    print(f"\n--- Status Telegram ---")
    print(manager.get_status_telegram())

    # Simular BUST
    print(f"\n--- Simulando BUST ---")
    manager.registrar_resultado(-5000, is_win=False, is_bust=True)
    print(f"Apos BUST:")
    print(f"  Pode operar: {manager.pode_operar()}")
    print(f"  Banca: R$ {manager.estado.banca_operacional:,.2f}")
    print(f"  RESERVA PRESERVADA: R$ {manager.estado.reserva_lucros:,.2f}")

    print("\n" + "=" * 60)
    print("TESTE CONCLUIDO")
    print("=" * 60)
