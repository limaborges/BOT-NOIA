#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
REGIME DETECTOR - Detector de regime para estrategia GAGO

Parametros:
- JANELA_REGIME: 100 rodadas
- METRICA: % de multiplicadores >= 1.99x
- LIMITE_FAVORAVEL: >= 51%

Uso:
- NAO usa durante operacao normal
- USA apenas para decidir quando RETOMAR apos pausa

Estatisticas historicas (99k multiplicadores):
- Media: 46.2%
- Desvio: 4.9%
- Min: 29.0%
- Max: 61.0%
- Janelas favoraveis (>=51%): 13.8%
"""

from collections import deque
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class RegimeStats:
    """Estatisticas do regime atual"""
    percentual_altos: float  # % de >= 1.99x na janela
    total_rodadas: int       # Rodadas na janela
    is_favoravel: bool       # Se percentual >= LIMITE_FAVORAVEL
    media_multiplicadores: float  # Media dos multiplicadores na janela


class RegimeDetector:
    """
    Detector de regime baseado em frequencia de multiplicadores altos.

    Um regime e considerado favoravel quando a porcentagem de multiplicadores
    >= 1.99x nos ultimos 100 multiplicadores e >= 51%.
    """

    # Configuracao
    JANELA_REGIME: int = 100           # Ultimas 100 rodadas
    THRESHOLD_ALTO: float = 1.99       # Multiplicador considerado "alto"
    LIMITE_FAVORAVEL: float = 51.0     # % para considerar regime favoravel

    def __init__(self, janela: int = None, limite: float = None):
        """
        Inicializa o detector de regime.

        Args:
            janela: Tamanho da janela de analise (default: 100)
            limite: Limite para regime favoravel em % (default: 51)
        """
        if janela is not None:
            self.JANELA_REGIME = janela
        if limite is not None:
            self.LIMITE_FAVORAVEL = limite

        self.buffer: deque = deque(maxlen=self.JANELA_REGIME)

    def adicionar_multiplicador(self, multiplicador: float):
        """Adiciona um multiplicador ao buffer"""
        self.buffer.append(multiplicador)

    def adicionar_varios(self, multiplicadores: List[float]):
        """Adiciona varios multiplicadores ao buffer"""
        for m in multiplicadores:
            self.buffer.append(m)

    def get_percentual_altos(self) -> float:
        """
        Retorna a porcentagem de multiplicadores >= THRESHOLD_ALTO na janela.

        Returns:
            Porcentagem (0-100) de multiplicadores altos
        """
        if len(self.buffer) == 0:
            return 0.0

        altos = sum(1 for m in self.buffer if m >= self.THRESHOLD_ALTO)
        return (altos / len(self.buffer)) * 100

    def is_favoravel(self) -> bool:
        """
        Verifica se o regime atual e favoravel.

        Returns:
            True se percentual de altos >= LIMITE_FAVORAVEL
        """
        return self.get_percentual_altos() >= self.LIMITE_FAVORAVEL

    def get_stats(self) -> RegimeStats:
        """
        Retorna estatisticas completas do regime atual.

        Returns:
            RegimeStats com todas as metricas
        """
        pct = self.get_percentual_altos()
        media = sum(self.buffer) / len(self.buffer) if self.buffer else 0.0

        return RegimeStats(
            percentual_altos=pct,
            total_rodadas=len(self.buffer),
            is_favoravel=pct >= self.LIMITE_FAVORAVEL,
            media_multiplicadores=media
        )

    def get_status_str(self) -> str:
        """
        Retorna string de status do regime.

        Returns:
            String formatada com status do regime
        """
        stats = self.get_stats()

        if stats.total_rodadas < self.JANELA_REGIME:
            return f"[AGUARDANDO] {stats.total_rodadas}/{self.JANELA_REGIME} rodadas"

        if stats.is_favoravel:
            return f"[FAVORAVEL] {stats.percentual_altos:.1f}% >= {self.LIMITE_FAVORAVEL}%"
        else:
            return f"[DESFAVORAVEL] {stats.percentual_altos:.1f}% < {self.LIMITE_FAVORAVEL}%"

    def to_dict(self) -> Dict:
        """Exporta para dicionario"""
        stats = self.get_stats()
        return {
            'percentual_altos': stats.percentual_altos,
            'total_rodadas': stats.total_rodadas,
            'is_favoravel': stats.is_favoravel,
            'media_multiplicadores': stats.media_multiplicadores,
            'janela': self.JANELA_REGIME,
            'limite_favoravel': self.LIMITE_FAVORAVEL,
            'threshold_alto': self.THRESHOLD_ALTO,
            'buffer_cheio': len(self.buffer) >= self.JANELA_REGIME,
        }

    def reset(self):
        """Limpa o buffer"""
        self.buffer.clear()


# Teste
if __name__ == "__main__":
    import random

    print("=" * 60)
    print("TESTE REGIME DETECTOR")
    print("=" * 60)

    detector = RegimeDetector()

    # Simular 150 multiplicadores
    print("\nSimulando 150 multiplicadores...")
    for i in range(150):
        # 46% de chance de ser >= 1.99x (media historica)
        if random.random() < 0.46:
            mult = random.uniform(1.99, 10.0)
        else:
            mult = random.uniform(1.01, 1.98)

        detector.adicionar_multiplicador(mult)

        if (i + 1) % 25 == 0:
            print(f"  Rodada {i+1}: {detector.get_status_str()}")

    print(f"\n--- Status Final ---")
    stats = detector.get_stats()
    print(f"Rodadas: {stats.total_rodadas}")
    print(f"% Altos (>=1.99x): {stats.percentual_altos:.1f}%")
    print(f"Media mult: {stats.media_multiplicadores:.2f}x")
    print(f"Favoravel: {stats.is_favoravel}")

    print("\n" + "=" * 60)
    print("TESTE CONCLUIDO")
    print("=" * 60)
