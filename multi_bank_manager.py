#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MULTI BANK MANAGER - Gerenciador de Multiplos Bancos para GAGO

Parametros:
- NUM_BANCOS: 5 bancos virtuais
- MAX_ESGOTADOS_DIA: 2 (para operacao, encerra o dia)

Fluxo:
1. Capital total e dividido em 5 bancos iguais
2. Opera com 1 banco por vez
3. Se banco esgota (perda total), muda para proximo
4. Se 2 bancos esgotam no mesmo dia, encerra operacao
5. Bancos que batem meta entram em "sucesso" ate proximo dia
6. Reset diario: bancos esgotados sao reabastecidos da reserva

Integracao com CompoundManager:
- Cada banco tem seu proprio compound_manager
- Meta, reserva e compound sao por banco
- Estatisticas globais agregam todos os bancos
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, date
from enum import Enum
import json
import os

from compound_manager import CompoundManager, EstadoCompound


class StatusBanco(Enum):
    """Status de um banco virtual"""
    DISPONIVEL = "disponivel"      # Pronto para operar
    OPERANDO = "operando"          # Banco ativo atual
    ESGOTADO = "esgotado"          # Perdeu todo o capital
    META_BATIDA = "meta_batida"    # Bateu meta, em pausa
    PAUSADO = "pausado"            # Pausado por regime desfavoravel


@dataclass
class BancoVirtual:
    """Representa um banco virtual"""
    id: int
    capital_inicial: float
    compound_manager: CompoundManager = field(default_factory=CompoundManager)
    status: StatusBanco = StatusBanco.DISPONIVEL
    data_esgotamento: Optional[date] = None

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'capital_inicial': self.capital_inicial,
            'compound_state': self.compound_manager.estado.to_dict(),
            'status': self.status.value,
            'data_esgotamento': self.data_esgotamento.isoformat() if self.data_esgotamento else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'BancoVirtual':
        banco = cls(
            id=data['id'],
            capital_inicial=data['capital_inicial'],
        )
        banco.compound_manager.estado = EstadoCompound.from_dict(data.get('compound_state', {}))
        banco.status = StatusBanco(data.get('status', 'disponivel'))
        if data.get('data_esgotamento'):
            try:
                banco.data_esgotamento = date.fromisoformat(data['data_esgotamento'])
            except:
                pass
        return banco


class MultiBankManager:
    """
    Gerenciador de multiplos bancos virtuais para estrategia GAGO.
    """

    # Configuracao
    NUM_BANCOS: int = 5
    MAX_ESGOTADOS_DIA: int = 2

    # Arquivo de estado
    STATE_FILE = 'multi_bank_state.json'

    def __init__(self, capital_total: float = 0.0):
        """
        Inicializa o gerenciador multi-banco.

        Args:
            capital_total: Capital total a ser dividido entre os bancos
        """
        self.bancos: List[BancoVirtual] = []
        self.banco_atual_idx: int = 0
        self.capital_total_inicial: float = capital_total
        self.reserva_global: float = 0.0  # Reserva de saques de todos os bancos
        self.esgotados_hoje: int = 0
        self.data_operacao: date = date.today()

        if capital_total > 0:
            self.inicializar(capital_total)

    def inicializar(self, capital_total: float):
        """
        Inicializa os bancos com o capital total.

        Args:
            capital_total: Capital total a ser dividido
        """
        self.capital_total_inicial = capital_total
        capital_por_banco = capital_total / self.NUM_BANCOS

        self.bancos = []
        for i in range(self.NUM_BANCOS):
            banco = BancoVirtual(
                id=i + 1,
                capital_inicial=capital_por_banco,
            )
            banco.compound_manager.inicializar(capital_por_banco)
            self.bancos.append(banco)

        # Primeiro banco comeca operando
        self.banco_atual_idx = 0
        self.bancos[0].status = StatusBanco.OPERANDO
        self.esgotados_hoje = 0
        self.data_operacao = date.today()

    def get_banco_atual(self) -> Optional[BancoVirtual]:
        """Retorna o banco atualmente em operacao"""
        if 0 <= self.banco_atual_idx < len(self.bancos):
            return self.bancos[self.banco_atual_idx]
        return None

    def get_compound_manager(self) -> Optional[CompoundManager]:
        """Retorna o compound manager do banco atual"""
        banco = self.get_banco_atual()
        return banco.compound_manager if banco else None

    def get_banca_operacional(self) -> float:
        """Retorna a banca operacional do banco atual"""
        banco = self.get_banco_atual()
        if banco and banco.compound_manager:
            return banco.compound_manager.estado.banca_operacional
        return 0.0

    def get_meta_atual(self) -> float:
        """Retorna a meta do banco atual (10% da banca)"""
        banco = self.get_banco_atual()
        if banco and banco.compound_manager:
            cm = banco.compound_manager
            return cm.estado.banca_na_ultima_meta * cm.META_LUCRO_PCT
        return 0.0

    def get_lucro_dia(self) -> float:
        """Retorna o lucro desde ultima meta do banco atual"""
        banco = self.get_banco_atual()
        if banco and banco.compound_manager:
            return banco.compound_manager.estado.lucro_desde_ultima_meta
        return 0.0

    def get_reserva_lucros(self) -> float:
        """Retorna a reserva de lucros do banco atual (INTOCAVEL)"""
        banco = self.get_banco_atual()
        if banco and banco.compound_manager:
            return banco.compound_manager.estado.reserva_lucros
        return 0.0

    def _verificar_novo_dia(self):
        """Verifica se e um novo dia e reseta contadores"""
        hoje = date.today()
        if hoje > self.data_operacao:
            self.data_operacao = hoje
            self.esgotados_hoje = 0

            # Reativar bancos esgotados (com capital da reserva se disponivel)
            for banco in self.bancos:
                if banco.status == StatusBanco.ESGOTADO:
                    # Tentar reativar com reserva global
                    if self.reserva_global >= banco.capital_inicial:
                        self.reserva_global -= banco.capital_inicial
                        banco.compound_manager.inicializar(banco.capital_inicial)
                        banco.status = StatusBanco.DISPONIVEL
                        banco.data_esgotamento = None

    def registrar_resultado(self, lucro_perda: float, is_win: bool = True,
                           is_cenario_b: bool = False, is_bust: bool = False) -> Dict:
        """
        Registra resultado de um trigger no banco atual.

        Args:
            lucro_perda: Lucro ou perda do trigger
            is_win: Se foi win
            is_cenario_b: Se foi cenario B
            is_bust: Se foi BUST (perda total)

        Returns:
            Dict com status da operacao
        """
        self._verificar_novo_dia()

        banco = self.get_banco_atual()
        if not banco:
            return {'erro': 'Nenhum banco disponivel'}

        # Registrar no compound manager do banco
        banco.compound_manager.registrar_resultado(
            lucro_perda,
            is_win=is_win,
            is_cenario_b=is_cenario_b,
            is_bust=is_bust
        )

        resultado = {
            'banco_id': banco.id,
            'lucro_perda': lucro_perda,
            'banca_apos': banco.compound_manager.estado.banca_operacional,
            'reserva_lucros': banco.compound_manager.estado.reserva_lucros,
            'acao': None,
        }

        # Verificar se foi BUST
        if banco.compound_manager.estado.bust_detectado:
            banco.status = StatusBanco.ESGOTADO
            banco.data_esgotamento = date.today()
            self.esgotados_hoje += 1
            resultado['acao'] = 'bust'
            resultado['reserva_preservada'] = banco.compound_manager.estado.reserva_lucros
            # Transferir reserva para reserva global
            self.reserva_global += banco.compound_manager.estado.reserva_lucros
            # NAO zerar a reserva local (para historico)

            # Tentar mudar para proximo banco
            self._mudar_proximo_banco()

        # Verificar se banco esgotou (sem ser BUST)
        elif banco.compound_manager.estado.banca_operacional <= 0:
            banco.status = StatusBanco.ESGOTADO
            banco.data_esgotamento = date.today()
            self.esgotados_hoje += 1
            resultado['acao'] = 'banco_esgotado'
            resultado['esgotados_hoje'] = self.esgotados_hoje

            # Verificar se deve parar
            if self.esgotados_hoje >= self.MAX_ESGOTADOS_DIA:
                resultado['acao'] = 'dia_encerrado'
            else:
                self._mudar_proximo_banco()

        return resultado

    def _mudar_proximo_banco(self) -> bool:
        """
        Muda para o proximo banco disponivel.

        Returns:
            True se conseguiu mudar, False se nao ha bancos disponiveis
        """
        # Procurar proximo banco disponivel
        for i in range(self.NUM_BANCOS):
            idx = (self.banco_atual_idx + 1 + i) % self.NUM_BANCOS
            if self.bancos[idx].status == StatusBanco.DISPONIVEL:
                self.bancos[self.banco_atual_idx].status = StatusBanco.PAUSADO
                self.banco_atual_idx = idx
                self.bancos[idx].status = StatusBanco.OPERANDO
                return True

        return False

    def pode_operar(self, regime_favoravel: bool = True) -> bool:
        """
        Verifica se pode continuar operando.

        Args:
            regime_favoravel: Se o regime atual e favoravel

        Returns:
            True se pode operar
        """
        self._verificar_novo_dia()

        # Verificar limite de esgotados
        if self.esgotados_hoje >= self.MAX_ESGOTADOS_DIA:
            return False

        banco = self.get_banco_atual()
        if not banco:
            return False

        # Se banco atual esta em pausa, verificar se pode retomar
        if banco.status == StatusBanco.META_BATIDA:
            if banco.compound_manager.pode_retomar(regime_favoravel):
                banco.compound_manager.retomar_operacao()
                banco.status = StatusBanco.OPERANDO
                return True
            return False

        return banco.status == StatusBanco.OPERANDO

    def get_status(self) -> Dict:
        """Retorna status geral do multi-banco"""
        banco = self.get_banco_atual()

        # Calcular totais
        total_operacional = sum(
            b.compound_manager.estado.banca_operacional
            for b in self.bancos
            if b.status not in [StatusBanco.ESGOTADO]
        )

        total_metas = sum(
            b.compound_manager.estado.total_metas_batidas
            for b in self.bancos
        )

        bancos_disponiveis = sum(
            1 for b in self.bancos
            if b.status in [StatusBanco.DISPONIVEL, StatusBanco.OPERANDO]
        )

        bancos_esgotados = sum(
            1 for b in self.bancos
            if b.status == StatusBanco.ESGOTADO
        )

        bancos_meta = sum(
            1 for b in self.bancos
            if b.status == StatusBanco.META_BATIDA
        )

        # Calcular meta atual
        meta_atual = 0
        lucro_desde_meta = 0
        reserva_lucros = 0
        if banco and banco.compound_manager:
            cm = banco.compound_manager
            meta_atual = cm.estado.banca_na_ultima_meta * cm.META_LUCRO_PCT
            lucro_desde_meta = cm.estado.lucro_desde_ultima_meta
            reserva_lucros = cm.estado.reserva_lucros

        return {
            'banco_atual': banco.id if banco else None,
            'status_banco': banco.status.value if banco else None,
            'banca_operacional': banco.compound_manager.estado.banca_operacional if banco else 0,
            'meta_atual': meta_atual,
            'lucro_desde_meta': lucro_desde_meta,
            'reserva_lucros': reserva_lucros,
            'progresso_meta': (lucro_desde_meta / meta_atual * 100) if meta_atual > 0 else 0,
            'total_operacional': total_operacional,
            'reserva_global': self.reserva_global,
            'capital_total': total_operacional + self.reserva_global,
            'bancos_disponiveis': bancos_disponiveis,
            'bancos_esgotados': bancos_esgotados,
            'bancos_meta': bancos_meta,
            'esgotados_hoje': self.esgotados_hoje,
            'max_esgotados': self.MAX_ESGOTADOS_DIA,
            'total_metas': total_metas,
            'pode_operar': self.pode_operar(),
        }

    def get_status_bancos(self) -> List[Dict]:
        """Retorna status de cada banco"""
        result = []
        for b in self.bancos:
            cm = b.compound_manager
            meta = cm.estado.banca_na_ultima_meta * cm.META_LUCRO_PCT if cm else 0
            result.append({
                'id': b.id,
                'status': b.status.value,
                'capital_inicial': b.capital_inicial,
                'banca_operacional': cm.estado.banca_operacional if cm else 0,
                'meta': meta,
                'lucro_desde_meta': cm.estado.lucro_desde_ultima_meta if cm else 0,
                'metas_batidas': cm.estado.total_metas_batidas if cm else 0,
                'reserva_lucros': cm.estado.reserva_lucros if cm else 0,
            })
        return result

    def get_relatorio(self) -> str:
        """Retorna relatorio formatado"""
        status = self.get_status()
        lines = [
            "=" * 60,
            "           RELATORIO MULTI-BANCO",
            "=" * 60,
            "",
            "CAPITAL",
            f"  Capital inicial:    R$ {self.capital_total_inicial:,.2f}",
            f"  Total operacional:  R$ {status['total_operacional']:,.2f}",
            f"  Reserva global:     R$ {self.reserva_global:,.2f}  <-- PODE SACAR",
            f"  Capital atual:      R$ {status['capital_total']:,.2f}",
            "",
            "BANCOS",
            f"  Total:              {self.NUM_BANCOS}",
            f"  Disponiveis:        {status['bancos_disponiveis']}",
            f"  Esgotados:          {status['bancos_esgotados']} (hoje: {self.esgotados_hoje}/{self.MAX_ESGOTADOS_DIA})",
            f"  Meta batida:        {status['bancos_meta']}",
            "",
            "BANCO ATUAL",
        ]

        banco = self.get_banco_atual()
        if banco:
            cm = banco.compound_manager
            est = cm.estado
            meta = est.banca_na_ultima_meta * cm.META_LUCRO_PCT
            lines.extend([
                f"  Banco #{banco.id} [{banco.status.value.upper()}]",
                f"  Banca:              R$ {est.banca_operacional:,.2f}",
                f"  RESERVA:            R$ {est.reserva_lucros:,.2f}  <-- INTOCAVEL",
                f"  Meta 10%:           R$ {meta:,.2f}",
                f"  Lucro acumulado:    R$ {est.lucro_desde_ultima_meta:,.2f} ({status['progresso_meta']:.1f}%)",
                f"  Metas batidas:      {est.total_metas_batidas}x",
            ])
        else:
            lines.append("  Nenhum banco ativo")

        lines.extend([
            "",
            "ESTATISTICAS",
            f"  Metas batidas:      {status['total_metas']}",
            f"  Pode operar:        {'SIM' if status['pode_operar'] else 'NAO'}",
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    def salvar_estado(self, filepath: str = None):
        """Salva estado em arquivo"""
        path = filepath or os.path.join(os.path.dirname(__file__), self.STATE_FILE)
        try:
            data = {
                'capital_total_inicial': self.capital_total_inicial,
                'banco_atual_idx': self.banco_atual_idx,
                'reserva_global': self.reserva_global,
                'esgotados_hoje': self.esgotados_hoje,
                'data_operacao': self.data_operacao.isoformat(),
                'bancos': [b.to_dict() for b in self.bancos],
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar estado multi-banco: {e}")

    def carregar_estado(self, filepath: str = None) -> bool:
        """Carrega estado de arquivo"""
        path = filepath or os.path.join(os.path.dirname(__file__), self.STATE_FILE)
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.capital_total_inicial = data.get('capital_total_inicial', 0)
            self.banco_atual_idx = data.get('banco_atual_idx', 0)
            self.reserva_global = data.get('reserva_global', 0)
            self.esgotados_hoje = data.get('esgotados_hoje', 0)

            if data.get('data_operacao'):
                try:
                    self.data_operacao = date.fromisoformat(data['data_operacao'])
                except:
                    self.data_operacao = date.today()

            self.bancos = [BancoVirtual.from_dict(b) for b in data.get('bancos', [])]

            return True
        except Exception as e:
            print(f"Erro ao carregar estado multi-banco: {e}")
            return False


# Teste
if __name__ == "__main__":
    print("=" * 60)
    print("TESTE MULTI BANK MANAGER")
    print("=" * 60)

    # Simular com R$500 divididos em 5 bancos de R$100
    manager = MultiBankManager(capital_total=500.0)

    print(f"\n--- Estado Inicial ---")
    print(f"Capital total: R$ {manager.capital_total_inicial:,.2f}")
    print(f"Capital por banco: R$ {manager.capital_total_inicial / manager.NUM_BANCOS:,.2f}")
    print(f"Meta por banco: R$ {manager.get_meta_atual():,.2f}")

    print(f"\n--- Status dos Bancos ---")
    for b in manager.get_status_bancos():
        print(f"  Banco #{b['id']}: {b['status']} - R$ {b['banca_operacional']:,.2f}")

    # Simular alguns resultados
    print(f"\n--- Simulando Triggers ---")

    # Win de R$14 (lucro tipico GAGO)
    for i in range(5):
        resultado = manager.registrar_resultado(14.0)
        print(f"Win {i+1}: Lucro dia = R$ {manager.get_lucro_dia():,.2f} / R$ {manager.get_meta_atual():,.2f}")

        if resultado.get('acao') == 'meta_batida':
            print(f"\n>>> META BATIDA! Reserva transferida: R$ {resultado.get('reserva_transferida', 0):,.2f}")
            break

    print(f"\n--- Status Final ---")
    print(manager.get_relatorio())

    print("\n" + "=" * 60)
    print("TESTE CONCLUIDO")
    print("=" * 60)
