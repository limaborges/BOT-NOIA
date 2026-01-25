#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RESERVA MANAGER - Gerenciador de Reserva de Lucros + Emprestimo

Logica de Reserva:
- Meta: 10% de lucro sobre a banca base
- Ao bater meta:
  - 50% vai para RESERVA (disponivel para saque)
  - 50% fica na banca (compound)
  - Nova banca base = banca atual

Logica de Emprestimo (pos-cluster):
- Apos 25 gatilhos sem T6, pode emprestar da reserva
- Maximo 50% da reserva por emprestimo
- Pagamento: 50% de cada lucro vai para pagar divida
- Nao acumula dividas (paga antes de novo emprestimo)

Referencias:
- ESTRATEGIA_EMPRESTIMO_RESERVA.md
- ESTRATEGIA_ACELERACAO_776.md

Arquivo de estado: reserva_state.json
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime


@dataclass
class EstadoReserva:
    """Estado da reserva de lucros e emprestimo"""
    banca_base: float = 0.0           # Banca de referencia para calcular 10%
    reserva_total: float = 0.0        # Total reservado (disponivel para saque)
    total_metas_batidas: int = 0      # Quantas vezes bateu 10%
    lucro_acumulado: float = 0.0      # Lucro desde ultima meta

    # Emprestimo
    divida_reserva: float = 0.0       # Divida atual com a reserva
    total_emprestimos: int = 0        # Total de emprestimos realizados
    total_emprestado: float = 0.0     # Valor total ja emprestado (historico)

    def to_dict(self) -> Dict:
        return {
            'banca_base': self.banca_base,
            'reserva_total': self.reserva_total,
            'total_metas_batidas': self.total_metas_batidas,
            'lucro_acumulado': self.lucro_acumulado,
            'divida_reserva': self.divida_reserva,
            'total_emprestimos': self.total_emprestimos,
            'total_emprestado': self.total_emprestado,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EstadoReserva':
        return cls(
            banca_base=data.get('banca_base', 0.0),
            reserva_total=data.get('reserva_total', 0.0),
            total_metas_batidas=data.get('total_metas_batidas', 0),
            lucro_acumulado=data.get('lucro_acumulado', 0.0),
            divida_reserva=data.get('divida_reserva', 0.0),
            total_emprestimos=data.get('total_emprestimos', 0),
            total_emprestado=data.get('total_emprestado', 0.0),
        )


class ReservaManager:
    """
    Gerenciador de Reserva de Lucros + Emprestimo.

    A cada 10% de lucro:
    - 50% vai para RESERVA (pode sacar)
    - 50% fica na banca (compound)

    Emprestimo da Reserva:
    - Condicoes: >= 25 gatilhos sem T6, banca < pico, sem divida
    - Limite: 50% da reserva
    - Pagamento: 50% de cada lucro
    """

    # Parametros de Reserva
    META_LUCRO_PCT: float = 0.10      # Meta = 10% de lucro
    PCT_RESERVA: float = 0.50         # 50% do lucro vai para reserva

    # Parametros de Emprestimo
    GATILHOS_PARA_EMPRESTIMO: int = 25   # Gatilhos sem T6 para poder emprestar
    LIMITE_EMPRESTIMO_PCT: float = 0.50  # Maximo 50% da reserva
    TAXA_PAGAMENTO: float = 1.0          # 100% do lucro paga divida ate quitar
    EMPRESTIMO_MINIMO_PCT: float = 0.05  # So empresta se for > 5% da banca

    # Arquivo de estado
    STATE_FILE = 'reserva_state.json'

    def __init__(self):
        self.estado = EstadoReserva()
        self._dir = os.path.dirname(__file__)
        self._emprestimo_ativo = True  # Pode desativar emprestimo

    def inicializar(self, banca: float):
        """Inicializa com uma banca base"""
        self.estado = EstadoReserva(
            banca_base=banca,
            reserva_total=0.0,
            total_metas_batidas=0,
            lucro_acumulado=0.0,
        )
        self.salvar()

    def get_meta_valor(self) -> float:
        """Retorna o valor da meta (10% da banca base)"""
        return self.estado.banca_base * self.META_LUCRO_PCT

    def get_progresso_pct(self) -> float:
        """Retorna progresso em % para a meta"""
        meta = self.get_meta_valor()
        if meta <= 0:
            return 0.0
        return (self.estado.lucro_acumulado / meta) * 100

    def registrar_resultado(self, lucro_perda: float, saldo_atual: float) -> Optional[Dict]:
        """
        Registra resultado de um trigger.

        Args:
            lucro_perda: Lucro ou perda do trigger
            saldo_atual: Saldo atual da banca (lido da tela)

        Returns:
            Dict com info se bateu meta, None caso contrario
        """
        self.estado.lucro_acumulado += lucro_perda

        # Verificar se bateu meta de 10%
        meta_valor = self.get_meta_valor()

        # CORRECAO V3: Sincronizar com lucro REAL baseado na BANCA OPERACIONAL
        # Bug anterior: usava saldo_atual - banca_base, mas isso nao considerava
        # que banca_base representa a banca operacional, nao o saldo total.
        # Correto: lucro = banca_operacional_atual - banca_base
        #          onde banca_operacional_atual = saldo - reserva_total
        banca_operacional_atual = saldo_atual - self.estado.reserva_total
        lucro_real = banca_operacional_atual - self.estado.banca_base
        if abs(lucro_real - self.estado.lucro_acumulado) > 1.0:
            # Discrepancia detectada - sincronizar com lucro real
            print(f"[RESERVA] Sync: lucro_acum={self.estado.lucro_acumulado:.2f} -> real={lucro_real:.2f} (banca_op={banca_operacional_atual:.2f}, base={self.estado.banca_base:.2f})")
            self.estado.lucro_acumulado = lucro_real

        if self.estado.lucro_acumulado >= meta_valor:
            return self._processar_meta(saldo_atual)

        self.salvar()
        return None

    def _processar_meta(self, saldo_atual: float) -> Dict:
        """Processa quando bate 10% de lucro"""
        lucro = self.estado.lucro_acumulado

        # Calcular reserva (5% da banca = 50% do lucro de 10%)
        valor_reserva = lucro * self.PCT_RESERVA
        valor_compound = lucro - valor_reserva  # Os outros 50%

        # Atualizar reserva
        self.estado.reserva_total += valor_reserva
        self.estado.total_metas_batidas += 1

        # CORRECAO V3: Nova banca base = banca operacional atual
        # Bug anterior: usava saldo - valor_reserva (so desta meta)
        # Correto: banca_base = saldo - reserva_total (toda reserva acumulada)
        # IMPORTANTE: reserva_total ja foi atualizado na linha acima!
        self.estado.banca_base = saldo_atual - self.estado.reserva_total
        self.estado.lucro_acumulado = 0.0

        self.salvar()

        return {
            'meta_batida': True,
            'lucro_total': lucro,
            'valor_reserva': valor_reserva,
            'valor_compound': valor_compound,
            'reserva_total': self.estado.reserva_total,
            'nova_banca_base': self.estado.banca_base,
            'total_metas': self.estado.total_metas_batidas,
        }

    def registrar_saque(self, valor: float):
        """Registra saque da reserva"""
        if valor <= self.estado.reserva_total:
            self.estado.reserva_total -= valor
            self.salvar()
            return True
        return False

    def get_reserva(self) -> float:
        """Retorna o valor reservado"""
        return self.estado.reserva_total

    def get_status(self) -> Dict:
        """Retorna status atual"""
        return {
            'banca_base': self.estado.banca_base,
            'reserva_total': self.estado.reserva_total,
            'meta_valor': self.get_meta_valor(),
            'lucro_acumulado': self.estado.lucro_acumulado,
            'progresso_pct': self.get_progresso_pct(),
            'total_metas': self.estado.total_metas_batidas,
            # Emprestimo
            'divida_reserva': self.estado.divida_reserva,
            'total_emprestimos': self.estado.total_emprestimos,
            'total_emprestado': self.estado.total_emprestado,
            'emprestimo_ativo': self._emprestimo_ativo,
        }

    # ============================================================
    # SISTEMA DE EMPRESTIMO DA RESERVA
    # ============================================================

    def ativar_emprestimo(self, ativo: bool = True):
        """Ativa ou desativa o sistema de emprestimo"""
        self._emprestimo_ativo = ativo

    def tem_divida(self) -> bool:
        """Verifica se tem divida pendente"""
        return self.estado.divida_reserva > 0

    def pode_emprestar(self, gatilhos_desde_t6: int, banca_atual: float, banca_pico: float) -> bool:
        """
        Verifica se pode fazer emprestimo da reserva.

        Condicoes:
        1. Emprestimo ativo
        2. >= 25 gatilhos sem T6 (cluster acabou)
        3. Banca < 90% do pico (ha deficit)
        4. Reserva > 0 (tem de onde emprestar)
        5. Sem divida pendente

        Args:
            gatilhos_desde_t6: Quantos gatilhos desde ultimo T6
            banca_atual: Banca atual
            banca_pico: Maior banca ja atingida

        Returns:
            bool: True se pode emprestar
        """
        if not self._emprestimo_ativo:
            return False

        return (
            gatilhos_desde_t6 >= self.GATILHOS_PARA_EMPRESTIMO and
            banca_atual < banca_pico * 0.9 and
            self.estado.reserva_total > 0 and
            self.estado.divida_reserva == 0
        )

    def calcular_emprestimo(self, banca_atual: float, banca_pico: float) -> float:
        """
        Calcula valor do emprestimo.

        Args:
            banca_atual: Banca atual
            banca_pico: Maior banca ja atingida

        Returns:
            float: Valor a emprestar (0 se nao vale a pena)
        """
        if self.estado.reserva_total <= 0:
            return 0.0

        # Calcular deficit
        deficit = banca_pico - banca_atual

        # Limite: 50% da reserva
        max_emprestimo = self.estado.reserva_total * self.LIMITE_EMPRESTIMO_PCT

        # Emprestar o menor entre deficit e limite
        emprestimo = min(deficit, max_emprestimo)

        # So empresta se for significativo (> 5% da banca)
        if emprestimo < banca_atual * self.EMPRESTIMO_MINIMO_PCT:
            return 0.0

        return emprestimo

    def realizar_emprestimo(self, valor: float) -> Optional[Dict]:
        """
        Realiza emprestimo da reserva.

        Args:
            valor: Valor a emprestar

        Returns:
            Dict com detalhes do emprestimo, ou None se falhou
        """
        if valor <= 0:
            return None

        if valor > self.estado.reserva_total:
            valor = self.estado.reserva_total

        # Transferir da reserva para banca (virtualmente)
        self.estado.reserva_total -= valor
        self.estado.divida_reserva += valor
        self.estado.total_emprestimos += 1
        self.estado.total_emprestado += valor

        self.salvar()

        return {
            'valor_emprestado': valor,
            'reserva_restante': self.estado.reserva_total,
            'divida_total': self.estado.divida_reserva,
            'emprestimo_numero': self.estado.total_emprestimos,
        }

    def pagar_divida(self, lucro_gatilho: float) -> Optional[Dict]:
        """
        Paga parte da divida com o lucro do gatilho.

        Regra: 50% do lucro vai para pagar divida.
        O pagamento tem PRIORIDADE sobre a reserva normal.

        Args:
            lucro_gatilho: Lucro do gatilho (so paga se > 0)

        Returns:
            Dict com detalhes do pagamento, ou None se nao pagou
        """
        if self.estado.divida_reserva <= 0:
            return None

        if lucro_gatilho <= 0:
            return None

        # Calcular pagamento (50% do lucro)
        pagamento_desejado = lucro_gatilho * self.TAXA_PAGAMENTO

        # Nao pagar mais que a divida
        pagamento = min(pagamento_desejado, self.estado.divida_reserva)

        # Transferir para reserva
        self.estado.reserva_total += pagamento
        self.estado.divida_reserva -= pagamento

        self.salvar()

        return {
            'pagamento': pagamento,
            'divida_restante': self.estado.divida_reserva,
            'reserva_apos': self.estado.reserva_total,
            'quitado': self.estado.divida_reserva == 0,
        }

    def verificar_emprestimo(self, gatilhos_desde_t6: int, banca_atual: float,
                             banca_pico: float) -> Optional[Dict]:
        """
        Verifica e realiza emprestimo se condicoes forem atendidas.

        Metodo de conveniencia que combina pode_emprestar, calcular_emprestimo
        e realizar_emprestimo.

        Args:
            gatilhos_desde_t6: Gatilhos desde ultimo T6
            banca_atual: Banca atual
            banca_pico: Banca pico

        Returns:
            Dict com detalhes se emprestou, None caso contrario
        """
        if not self.pode_emprestar(gatilhos_desde_t6, banca_atual, banca_pico):
            return None

        valor = self.calcular_emprestimo(banca_atual, banca_pico)
        if valor <= 0:
            return None

        return self.realizar_emprestimo(valor)

    def salvar(self):
        """Salva estado em arquivo"""
        path = os.path.join(self._dir, self.STATE_FILE)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.estado.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar reserva: {e}")

    def carregar(self) -> bool:
        """Carrega estado de arquivo"""
        path = os.path.join(self._dir, self.STATE_FILE)
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.estado = EstadoReserva.from_dict(data)
                return True
        except Exception as e:
            print(f"Erro ao carregar reserva: {e}")
            return False


# Teste
if __name__ == "__main__":
    print("=" * 50)
    print("TESTE RESERVA MANAGER")
    print("=" * 50)

    rm = ReservaManager()
    rm.inicializar(10000.0)

    print(f"\nBanca inicial: R$ 10.000")
    print(f"Meta 10%: R$ {rm.get_meta_valor():.2f}")

    # Simular wins ate bater meta
    print(f"\n--- Simulando triggers ---")
    saldo = 10000.0

    for i in range(15):
        lucro = 80  # ~0.8% por win
        saldo += lucro

        resultado = rm.registrar_resultado(lucro, saldo)

        print(f"Win {i+1}: Lucro +R$ {lucro} | Progresso: {rm.get_progresso_pct():.1f}%")

        if resultado:
            print(f"\n>>> META BATIDA!")
            print(f"    Reserva: R$ {resultado['valor_reserva']:.2f}")
            print(f"    Compound: R$ {resultado['valor_compound']:.2f}")
            print(f"    Total reservado: R$ {resultado['reserva_total']:.2f}")
            print(f"    Nova banca base: R$ {resultado['nova_banca_base']:.2f}")
            break

    print(f"\n--- Status Final ---")
    status = rm.get_status()
    for k, v in status.items():
        if isinstance(v, float):
            print(f"  {k}: R$ {v:.2f}" if 'pct' not in k else f"  {k}: {v:.1f}%")
        else:
            print(f"  {k}: {v}")

    print("\n" + "=" * 50)
