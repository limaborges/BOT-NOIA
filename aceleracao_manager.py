#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ACELERACAO MANAGER - Estrategia [7,7,6]

Implementa a estrategia de aceleracao validada em 140k multiplicadores:
- Padrao [7,7,6]: NS7 -> NS7 -> NS6 -> NS7 -> NS7 -> NS6 -> ...
- Resultado: 7x mais ganho que NS7 puro com apenas +2.8pp de drawdown

Referencias:
- ESTRATEGIA_ACELERACAO_776.md
- ESTRATEGIA_EMPRESTIMO_RESERVA.md
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime


# ============================================================
# CONFIGURACAO DA ESTRATEGIA
# ============================================================

# Padrao de niveis de seguranca (alterna eternamente)
PADRAO_NS = [7, 7, 6]

# Divisores por nivel (para referencia)
DIVISORES = {
    6: 63,
    7: 127,
    8: 255,
    9: 511,
    10: 1023
}


# ============================================================
# ESTADO DA ACELERACAO
# ============================================================

@dataclass
class EstadoAceleracao:
    """Estado persistente da estrategia de aceleracao"""

    # Padrao [7,7,6]
    indice_padrao: int = 0           # Posicao atual no padrao (0, 1, 2, 0, 1, 2, ...)
    padrao: List[int] = field(default_factory=lambda: [7, 7, 6])

    # Controle de T6 (para emprestimo)
    gatilhos_desde_t6: int = 999     # Comeca alto (assume sem T6 recente)
    ultimo_t6_timestamp: Optional[str] = None

    # Banca pico (para emprestimo)
    banca_pico: float = 0.0

    # Estatisticas
    total_gatilhos_ns6: int = 0
    total_gatilhos_ns7: int = 0
    total_gatilhos_ns8: int = 0

    def to_dict(self) -> Dict:
        return {
            'indice_padrao': self.indice_padrao,
            'padrao': self.padrao,
            'gatilhos_desde_t6': self.gatilhos_desde_t6,
            'ultimo_t6_timestamp': self.ultimo_t6_timestamp,
            'banca_pico': self.banca_pico,
            'total_gatilhos_ns6': self.total_gatilhos_ns6,
            'total_gatilhos_ns7': self.total_gatilhos_ns7,
            'total_gatilhos_ns8': self.total_gatilhos_ns8,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EstadoAceleracao':
        return cls(
            indice_padrao=data.get('indice_padrao', 0),
            padrao=data.get('padrao', [7, 7, 6]),
            gatilhos_desde_t6=data.get('gatilhos_desde_t6', 999),
            ultimo_t6_timestamp=data.get('ultimo_t6_timestamp'),
            banca_pico=data.get('banca_pico', 0.0),
            total_gatilhos_ns6=data.get('total_gatilhos_ns6', 0),
            total_gatilhos_ns7=data.get('total_gatilhos_ns7', 0),
            total_gatilhos_ns8=data.get('total_gatilhos_ns8', 0),
        )


# ============================================================
# MANAGER DE ACELERACAO
# ============================================================

class AceleracaoManager:
    """
    Gerenciador da estrategia de aceleracao [7,7,6].

    Uso:
    1. Chamar proximo_ns() ANTES de iniciar cada gatilho
    2. Chamar registrar_gatilho_finalizado() APOS cada gatilho

    A cada 3 gatilhos:
    - Gatilho 1: NS7 (divisor 127)
    - Gatilho 2: NS7 (divisor 127)
    - Gatilho 3: NS6 (divisor 63) <- BOOST (aposta 2x maior)
    """

    STATE_FILE = 'aceleracao_state.json'

    def __init__(self):
        self.estado = EstadoAceleracao()
        self._dir = os.path.dirname(__file__)
        self._ativo = True  # Pode desativar para voltar ao NS fixo

    def inicializar(self, banca_inicial: float = 0.0, padrao: List[int] = None):
        """Inicializa o manager com estado limpo"""
        self.estado = EstadoAceleracao(
            indice_padrao=0,
            padrao=padrao or [7, 7, 6],
            gatilhos_desde_t6=999,
            banca_pico=banca_inicial,
        )
        self.salvar()

    def ativar(self, ativo: bool = True):
        """Ativa ou desativa a estrategia de aceleracao"""
        self._ativo = ativo

    def is_ativo(self) -> bool:
        """Retorna se a aceleracao esta ativa"""
        return self._ativo

    def proximo_ns(self) -> int:
        """
        Retorna o nivel de seguranca para o PROXIMO gatilho.

        NAO avanca o indice - isso e feito em registrar_gatilho_finalizado().

        Returns:
            int: Nivel de seguranca (6, 7 ou 8)
        """
        if not self._ativo:
            return 7  # Default NS7 quando desativado

        padrao = self.estado.padrao
        indice = self.estado.indice_padrao % len(padrao)
        return padrao[indice]

    def registrar_gatilho_finalizado(self, chegou_t6: bool = False, banca_atual: float = 0.0):
        """
        Registra que um gatilho foi finalizado e avanca o padrao.

        Args:
            chegou_t6: Se o gatilho chegou ate T6 (ou alem)
            banca_atual: Banca atual apos o gatilho

        Este metodo DEVE ser chamado apos cada gatilho finalizado
        para manter o padrao [7,7,6] sincronizado.
        """
        # Registrar estatistica do NS usado
        ns_usado = self.proximo_ns()
        if ns_usado == 6:
            self.estado.total_gatilhos_ns6 += 1
        elif ns_usado == 7:
            self.estado.total_gatilhos_ns7 += 1
        elif ns_usado == 8:
            self.estado.total_gatilhos_ns8 += 1

        # Avancar indice do padrao
        self.estado.indice_padrao += 1

        # Controle de T6 (para emprestimo)
        if chegou_t6:
            self.estado.gatilhos_desde_t6 = 0
            self.estado.ultimo_t6_timestamp = datetime.now().isoformat()
        else:
            self.estado.gatilhos_desde_t6 += 1

        # Atualizar banca pico
        if banca_atual > self.estado.banca_pico:
            self.estado.banca_pico = banca_atual

        self.salvar()

    def registrar_t6(self):
        """Registra que ocorreu um T6 (para controle de emprestimo)"""
        self.estado.gatilhos_desde_t6 = 0
        self.estado.ultimo_t6_timestamp = datetime.now().isoformat()
        self.salvar()

    def get_posicao_padrao(self) -> str:
        """Retorna posicao atual no padrao de forma legivel"""
        padrao = self.estado.padrao
        indice = self.estado.indice_padrao % len(padrao)

        # Mostrar padrao com marcacao da posicao atual
        partes = []
        for i, ns in enumerate(padrao):
            if i == indice:
                partes.append(f"[{ns}]")  # Posicao atual
            else:
                partes.append(str(ns))

        return "-".join(partes)

    def get_status(self) -> Dict:
        """Retorna status completo do manager"""
        ns_atual = self.proximo_ns()
        padrao_str = self.get_posicao_padrao()

        # Calcular % de tempo em cada NS
        total = (self.estado.total_gatilhos_ns6 +
                 self.estado.total_gatilhos_ns7 +
                 self.estado.total_gatilhos_ns8)

        pct_ns6 = (self.estado.total_gatilhos_ns6 / total * 100) if total > 0 else 0
        pct_ns7 = (self.estado.total_gatilhos_ns7 / total * 100) if total > 0 else 0

        return {
            'ativo': self._ativo,
            'ns_atual': ns_atual,
            'ns_nome': f'NS{ns_atual}',
            'divisor': DIVISORES.get(ns_atual, 127),
            'padrao': self.estado.padrao,
            'padrao_str': padrao_str,
            'indice': self.estado.indice_padrao,
            'posicao_no_ciclo': (self.estado.indice_padrao % len(self.estado.padrao)) + 1,
            'gatilhos_desde_t6': self.estado.gatilhos_desde_t6,
            'banca_pico': self.estado.banca_pico,
            'total_gatilhos': total,
            'pct_ns6': pct_ns6,
            'pct_ns7': pct_ns7,
        }

    def set_padrao(self, novo_padrao: List[int]):
        """
        Define um novo padrao de NS.

        Exemplos:
        - [7, 7, 6]: Aceleracao padrao (2x NS6 a cada 3 gatilhos)
        - [7, 6]: Aceleracao agressiva (1x NS6 a cada 2 gatilhos)
        - [7, 7, 7, 6]: Aceleracao conservadora
        - [7]: NS7 fixo (sem aceleracao)
        """
        if not novo_padrao or not all(ns in [6, 7, 8, 9, 10] for ns in novo_padrao):
            raise ValueError("Padrao invalido. Use niveis entre 6 e 10.")

        self.estado.padrao = novo_padrao
        self.estado.indice_padrao = 0  # Reset ao mudar padrao
        self.salvar()

    def salvar(self):
        """Salva estado em arquivo"""
        path = os.path.join(self._dir, self.STATE_FILE)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.estado.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar aceleracao: {e}")

    def carregar(self) -> bool:
        """Carrega estado de arquivo"""
        path = os.path.join(self._dir, self.STATE_FILE)
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.estado = EstadoAceleracao.from_dict(data)
                return True
        except Exception as e:
            print(f"Erro ao carregar aceleracao: {e}")
            return False


# ============================================================
# TESTE
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TESTE ACELERACAO MANAGER - Estrategia [7,7,6]")
    print("=" * 60)

    am = AceleracaoManager()
    am.inicializar(banca_inicial=10000.0)

    print(f"\nPadrao: {am.estado.padrao}")
    print(f"Divisores: NS6={DIVISORES[6]}, NS7={DIVISORES[7]}")
    print(f"NS6 aposta {DIVISORES[7]/DIVISORES[6]:.2f}x mais que NS7\n")

    print("Simulando 12 gatilhos:")
    print("-" * 40)

    for i in range(12):
        ns = am.proximo_ns()
        pos = am.get_posicao_padrao()

        # Simular: T6 a cada 10 gatilhos
        chegou_t6 = (i + 1) % 10 == 0

        print(f"Gatilho {i+1:2d}: NS{ns} | Padrao: {pos} | T6: {'SIM' if chegou_t6 else 'nao'}")

        am.registrar_gatilho_finalizado(chegou_t6=chegou_t6, banca_atual=10000 + i * 100)

    print("\n" + "-" * 40)
    print("Status final:")
    status = am.get_status()
    for k, v in status.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}")
        else:
            print(f"  {k}: {v}")

    print("\n" + "=" * 60)
