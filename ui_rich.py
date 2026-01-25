# -*- coding: utf-8 -*-
"""
MartingaleV2 - Interface Rich
UI compacta e elegante para terminal
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from datetime import datetime, timedelta
from typing import List, Optional
import math
import sys
import os

# Forcar UTF-8 no Windows
if sys.platform == "win32":
    os.system("")  # Habilita ANSI no Windows
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

console = Console(force_terminal=True, legacy_windows=False)

# Caracteres para sparkline (ASCII compativel)
SPARK_CHARS = "_.-~=+*#"


def sparkline(values: List[float], width: int = 20) -> str:
    """Gera sparkline ASCII para evolucao da banca"""
    if not values or len(values) < 2:
        return "─" * width

    # Pegar ultimos 'width' valores
    values = values[-width:]

    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return SPARK_CHARS[4] * len(values)

    result = ""
    for v in values:
        # Normalizar para 0-7 (indices do SPARK_CHARS)
        idx = int((v - min_val) / (max_val - min_val) * 7)
        idx = max(0, min(7, idx))
        result += SPARK_CHARS[idx]

    return result


def formato_tempo(segundos: float) -> str:
    """Formata segundos em tempo legivel compacto"""
    if segundos < 60:
        return f"{int(segundos)}s"
    elif segundos < 3600:
        return f"{int(segundos // 60)}m"
    elif segundos < 86400:
        horas = segundos // 3600
        mins = (segundos % 3600) // 60
        return f"{int(horas)}h{int(mins):02d}m"
    else:
        dias = segundos // 86400
        horas = (segundos % 86400) // 3600
        return f"{int(dias)}d{int(horas)}h"


def calcular_wins_para_meta(lucro_atual_pct: float, meta_pct: float = 100.0, lucro_por_win_pct: float = 1.57) -> int:
    """Calcula quantos WINs faltam para atingir a meta usando compound"""
    if lucro_atual_pct >= meta_pct:
        return 0

    # Formula compound: (1 + lucro_por_win)^n = (1 + meta) / (1 + atual)
    fator_atual = 1 + (lucro_atual_pct / 100)
    fator_meta = 1 + (meta_pct / 100)
    fator_win = 1 + (lucro_por_win_pct / 100)

    if fator_win <= 1:
        return 999

    wins = math.log(fator_meta / fator_atual) / math.log(fator_win)
    return max(0, math.ceil(wins))


def barra_progresso(atual: float, total: float, largura: int = 20) -> str:
    """Cria barra de progresso compacta (ASCII compativel)"""
    if total <= 0:
        return "." * largura

    pct = min(1.0, atual / total)
    preenchido = int(pct * largura)

    return "#" * preenchido + "." * (largura - preenchido)


def indicador_triggers(triggers_hora: float) -> str:
    """Indicador criativo de frequencia de triggers"""
    # Pulso visual baseado na frequencia (ASCII compativel)
    if triggers_hora >= 2.0:
        pulso = "[***]"  # Muito ativo
        status = "INTENSO"
    elif triggers_hora >= 1.0:
        pulso = "[**.]"   # Normal
        status = "NORMAL"
    elif triggers_hora >= 0.5:
        pulso = "[*..]"   # Lento
        status = "LENTO"
    else:
        pulso = "[...]"    # Parado
        status = "QUIETO"

    return f"{pulso} {triggers_hora:.1f}/h {status}"


def indicador_countdown(wins_faltam: int, lucro_pct: float) -> str:
    """Indicador criativo de countdown para meta"""
    if wins_faltam == 0:
        return "[META!]"

    # Barra de progresso para meta (ASCII compativel)
    pct = min(100, max(0, lucro_pct))
    blocos = int(pct / 25)

    barra = "[" + "#" * blocos + "." * (4 - blocos) + "]"

    return f"{barra} {wins_faltam}W->NS"


def painel_status(
    banca: float,
    banca_inicial: float,
    nivel: int,
    tentativa_atual: int,
    historico_banca: List[float],
    triggers_sessao: int,
    tempo_sessao_segundos: float,
    ultimo_resultado: Optional[str] = None,
    ultimo_valor: Optional[float] = None
):
    """
    Renderiza painel de status compacto e elegante

    Args:
        banca: Banca atual
        banca_inicial: Banca no inicio da sessao
        nivel: Nivel de seguranca atual (6-10)
        tentativa_atual: Tentativa atual no ciclo (1-N)
        historico_banca: Lista de valores da banca ao longo do tempo
        triggers_sessao: Numero de triggers na sessao
        tempo_sessao_segundos: Tempo de sessao em segundos
        ultimo_resultado: "WIN" ou "LOSS" ou None
        ultimo_valor: Valor ganho/perdido
    """

    # Calculos
    lucro_pct = ((banca - banca_inicial) / banca_inicial) * 100 if banca_inicial > 0 else 0
    triggers_hora = (triggers_sessao / tempo_sessao_segundos * 3600) if tempo_sessao_segundos > 60 else 0

    # Lucro por WIN baseado no nivel
    lucro_por_win = {6: 1.57, 7: 0.78, 8: 0.39, 9: 0.19, 10: 0.10}.get(nivel, 1.0)
    wins_faltam = calcular_wins_para_meta(lucro_pct, 100.0, lucro_por_win)

    # Cores
    cor_lucro = "green" if lucro_pct >= 0 else "red"
    cor_resultado = "green" if ultimo_resultado == "WIN" else "red" if ultimo_resultado == "LOSS" else "white"

    # Sparkline da evolucao
    spark = sparkline(historico_banca, 16)

    # Montar texto
    linhas = []

    # Linha 1: Banca e Nivel
    linha1 = f"[bold]R$ {banca:.2f}[/bold]  [dim]NS{nivel}[/dim]  T{tentativa_atual}"
    if ultimo_resultado:
        sinal = "+" if ultimo_resultado == "WIN" else "-"
        linha1 += f"  [{cor_resultado}]{ultimo_resultado} {sinal}R${abs(ultimo_valor or 0):.2f}[/{cor_resultado}]"
    linhas.append(linha1)

    # Linha 2: Lucro e Sparkline
    sinal_lucro = "+" if lucro_pct >= 0 else ""
    linha2 = f"[{cor_lucro}]{sinal_lucro}{lucro_pct:.1f}%[/{cor_lucro}]  [cyan]{spark}[/cyan]"
    linhas.append(linha2)

    # Linha 3: Indicadores criativos
    linha3 = f"{indicador_triggers(triggers_hora)}  {indicador_countdown(wins_faltam, lucro_pct)}"
    linhas.append(linha3)

    # Criar painel
    conteudo = "\n".join(linhas)

    painel = Panel(
        conteudo,
        title="[bold blue]MartingaleV2[/bold blue]",
        border_style="blue",
        box=box.ROUNDED,
        padding=(0, 1)
    )

    console.print(painel)


def resultado_compacto(tipo: str, tentativa: int, alvo: float, valor: float, banca: float):
    """Mostra resultado de forma compacta inline"""
    if tipo == "WIN":
        console.print(f"[green]>[/green] T{tentativa}@{alvo}x [green]+R${valor:.2f}[/green] -> R${banca:.2f}")
    else:
        console.print(f"[red]X[/red] T{tentativa}@{alvo}x [red]-R${valor:.2f}[/red] -> R${banca:.2f}")


def alerta(mensagem: str, tipo: str = "info"):
    """Mostra alerta colorido"""
    cores = {
        "info": "blue",
        "sucesso": "green",
        "aviso": "yellow",
        "erro": "red"
    }
    cor = cores.get(tipo, "white")
    console.print(f"[{cor}]> {mensagem}[/{cor}]")


def limpar():
    """Limpa o terminal"""
    console.clear()


def separador():
    """Linha separadora sutil"""
    console.print("[dim]" + "-" * 50 + "[/dim]")


# ============================================================
# Exemplo de uso / Teste
# ============================================================

if __name__ == "__main__":
    # Teste do painel
    print("\n=== Teste UI Rich ===\n")

    # Simular dados
    historico = [400, 405, 410, 408, 415, 420, 418, 425, 430, 428, 435, 440, 438, 445, 450, 455]

    painel_status(
        banca=455.00,
        banca_inicial=400.00,
        nivel=6,
        tentativa_atual=1,
        historico_banca=historico,
        triggers_sessao=28,
        tempo_sessao_segundos=86400,  # 24h
        ultimo_resultado="WIN",
        ultimo_valor=7.22
    )

    print()
    resultado_compacto("WIN", 2, 1.99, 7.22, 455.00)
    resultado_compacto("LOSS", 6, 1.30, 155.00, 300.00)

    print()
    alerta("Nivel subiu para NS7!", "sucesso")
    alerta("Aguardando proximo trigger...", "info")
