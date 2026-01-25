#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI TEXTUAL - Interface moderna para o bot
Prototipo para demonstracao
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, DataTable, Label, ProgressBar
from textual.reactive import reactive
from textual_plotext import PlotextPlot
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from datetime import datetime, timedelta
import random

# Dados simulados para demonstracao
DADOS_SIMULADOS = {
    "saldo_inicial": 2195.38,
    "saldo_atual": 3129.62,
    "sessoes_win": 59,
    "sessoes_loss": 0,
    "base_inicial": 17.29,
    "base_atual": 24.64,
    "nivel_seguranca": 7,
    "inicio": datetime(2026, 1, 13, 7, 15, 56),
    "historico_banca": [
        2195, 2210, 2250, 2230, 2280, 2350, 2400, 2380, 2450, 2520,
        2480, 2550, 2600, 2580, 2650, 2700, 2680, 2750, 2800, 2780,
        2850, 2900, 2870, 2920, 2980, 3000, 2970, 3020, 3080, 3050, 3129
    ],
    "perdas": [
        {"horario": "14:32:15", "tentativa": 6, "valor": -45.20, "gatilho": [1.23, 1.45, 1.67, 1.89, 1.12, 1.34], "resultado": 1.00},
        {"horario": "09:15:42", "tentativa": 7, "valor": -89.50, "gatilho": [1.11, 1.22, 1.33, 1.44, 1.55, 1.66], "resultado": 1.05},
        {"horario": "06:17:33", "tentativa": 6, "valor": -52.30, "gatilho": [1.98, 1.87, 1.76, 1.65, 1.54, 1.43], "resultado": 1.00},
    ],
    "acertos_por_tentativa": {"T1": 42, "T2": 8, "T3": 5, "T4": 2, "T5": 1, "T6": 1, "T7": 0},
    "streaks": [
        {"tamanho": 12, "horario": "06:17", "resultado": "T7 SALVO +R$160"},
        {"tamanho": 9, "horario": "11:45", "resultado": "T6 SALVO +R$85"},
        {"tamanho": 8, "horario": "15:22", "resultado": "T5 WIN +R$42"},
        {"tamanho": 8, "horario": "20:10", "resultado": "T5 WIN +R$38"},
    ],
}


class PainelResumo(Static):
    """Painel com resumo principal"""

    def compose(self) -> ComposeResult:
        yield Static(id="resumo-content")

    def on_mount(self) -> None:
        self.atualizar()

    def atualizar(self):
        dados = DADOS_SIMULADOS
        lucro = dados["saldo_atual"] - dados["saldo_inicial"]
        lucro_pct = (lucro / dados["saldo_inicial"]) * 100

        # Calcular uptime
        uptime = datetime.now() - dados["inicio"]
        dias = uptime.days
        horas = uptime.seconds // 3600
        minutos = (uptime.seconds % 3600) // 60

        if dias > 0:
            uptime_str = f"{dias}d {horas}h {minutos}m"
        else:
            uptime_str = f"{horas}h {minutos}m"

        content = f"""[bold cyan]SALDO[/] R$ {dados['saldo_atual']:,.2f}
[bold green]LUCRO[/] R$ {lucro:,.2f} ([green]+{lucro_pct:.1f}%[/])
[bold]SESSOES[/] {dados['sessoes_win']}W / {dados['sessoes_loss']}L
[bold]NS[/] {dados['nivel_seguranca']} | [bold]BASE[/] R$ {dados['base_atual']:.2f}
[bold yellow]UPTIME[/] {uptime_str}"""

        self.query_one("#resumo-content").update(Panel(content, title="RESUMO", border_style="green"))


class PainelGanhosPeriodo(Static):
    """Painel com ganhos por periodo"""

    periodo_idx = reactive(0)
    periodos = ["24h", "12h", "6h", "1h"]

    def compose(self) -> ComposeResult:
        yield Static(id="ganhos-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(5, self.proximo_periodo)

    def proximo_periodo(self):
        self.periodo_idx = (self.periodo_idx + 1) % len(self.periodos)
        self.atualizar()

    def atualizar(self):
        periodo = self.periodos[self.periodo_idx]
        # Valores simulados
        ganhos = {"24h": 485.30, "12h": 312.15, "6h": 156.80, "1h": 42.50}
        wins = {"24h": 28, "12h": 18, "6h": 9, "1h": 3}

        content = f"""[bold cyan]Ultimas {periodo}[/]
[green]+R$ {ganhos[periodo]:,.2f}[/]
{wins[periodo]} wins"""

        self.query_one("#ganhos-content").update(Panel(content, title=f"GANHOS {periodo}", border_style="cyan"))


class PainelCountdown(Static):
    """Countdown para metas"""

    def compose(self) -> ComposeResult:
        yield Static(id="countdown-content")

    def on_mount(self) -> None:
        self.atualizar()

    def atualizar(self):
        dados = DADOS_SIMULADOS
        saldo = dados["saldo_atual"]
        inicial = dados["saldo_inicial"]

        # Calcular metas
        dobro = inicial * 2
        quadruplo = inicial * 4

        falta_dobro = max(0, dobro - saldo)
        falta_quad = max(0, quadruplo - saldo)

        # Estimar wins (media de R$15 por win)
        wins_dobro = int(falta_dobro / 15) if falta_dobro > 0 else 0
        wins_quad = int(falta_quad / 15) if falta_quad > 0 else 0

        pct_dobro = min(100, (saldo / dobro) * 100)
        pct_quad = min(100, (saldo / quadruplo) * 100)

        content = f"""[bold]2x BANCA[/] ({pct_dobro:.0f}%)
{'█' * int(pct_dobro/5)}{'░' * (20-int(pct_dobro/5))}
~{wins_dobro} wins restantes

[bold]4x BANCA[/] ({pct_quad:.0f}%)
{'█' * int(pct_quad/5)}{'░' * (20-int(pct_quad/5))}
~{wins_quad} wins restantes"""

        self.query_one("#countdown-content").update(Panel(content, title="METAS", border_style="yellow"))


class PainelCompound(Static):
    """Info do compound"""

    def compose(self) -> ComposeResult:
        yield Static(id="compound-content")

    def on_mount(self) -> None:
        self.atualizar()

    def atualizar(self):
        dados = DADOS_SIMULADOS
        crescimento = ((dados["base_atual"] / dados["base_inicial"]) - 1) * 100

        content = f"""[dim]Base inicial:[/] R$ {dados['base_inicial']:.2f}
[bold]Base atual:[/]  R$ {dados['base_atual']:.2f}
[green]Crescimento:[/] +{crescimento:.1f}%"""

        self.query_one("#compound-content").update(Panel(content, title="COMPOUND", border_style="magenta"))


class PainelAcertos(Static):
    """Acertos por tentativa"""

    def compose(self) -> ComposeResult:
        yield Static(id="acertos-content")

    def on_mount(self) -> None:
        self.atualizar()

    def atualizar(self):
        dados = DADOS_SIMULADOS["acertos_por_tentativa"]
        total = sum(dados.values())

        lines = []
        for t, qtd in dados.items():
            pct = (qtd / total * 100) if total > 0 else 0
            bar = '█' * int(pct / 5)
            lines.append(f"{t}: {qtd:2d} ({pct:4.1f}%) {bar}")

        content = "\n".join(lines)
        self.query_one("#acertos-content").update(Panel(content, title="ACERTOS/TENTATIVA", border_style="blue"))


class PainelStreaks(Static):
    """Max streaks"""

    def compose(self) -> ComposeResult:
        yield Static(id="streaks-content")

    def on_mount(self) -> None:
        self.atualizar()

    def atualizar(self):
        streaks = DADOS_SIMULADOS["streaks"]

        lines = []
        for s in streaks[:4]:
            lines.append(f"[bold]{s['tamanho']}[/] baixos @ {s['horario']} → {s['resultado']}")

        content = "\n".join(lines)
        self.query_one("#streaks-content").update(Panel(content, title="STREAKS 24h", border_style="red"))


class PainelPerdas(Static):
    """Historico de perdas"""

    def compose(self) -> ComposeResult:
        yield Static(id="perdas-content")

    def on_mount(self) -> None:
        self.atualizar()

    def atualizar(self):
        perdas = DADOS_SIMULADOS["perdas"]

        lines = []
        for p in perdas[:5]:
            gatilho_str = ",".join([f"{g:.2f}" for g in p["gatilho"]])
            lines.append(f"[red]T{p['tentativa']}[/] {p['horario']} | [red]R$ {p['valor']:.2f}[/]")
            lines.append(f"[dim]  Gatilho: [{gatilho_str}][/]")
            lines.append(f"[dim]  Explodiu: {p['resultado']:.2f}x[/]")
            lines.append("")

        content = "\n".join(lines) if lines else "[green]Nenhuma perda![/]"
        self.query_one("#perdas-content").update(Panel(content, title="ULTIMAS PERDAS", border_style="red"))


class PainelGrafico(PlotextPlot):
    """Grafico de evolucao da banca com eixos"""

    def on_mount(self) -> None:
        self.atualizar()

    def atualizar(self):
        dados = DADOS_SIMULADOS["historico_banca"]
        inicio = DADOS_SIMULADOS["inicio"]

        # Calcular eixo X adaptativo
        total_horas = len(dados)  # Simular 1 ponto por hora

        if total_horas <= 24:
            # Menos de 24h: mostrar em horas
            x_label = "Horas"
            x_values = list(range(len(dados)))
        elif total_horas <= 168:  # 7 dias
            # Até 7 dias: mostrar em horas
            x_label = "Horas"
            x_values = list(range(len(dados)))
        else:
            # Mais de 7 dias: mostrar em dias
            x_label = "Dias"
            x_values = [i / 24 for i in range(len(dados))]

        # Limpar e plotar
        self.plt.clear_figure()
        self.plt.plot(x_values, dados, marker="braille", color="green")

        # Linha do saldo inicial
        self.plt.hline(DADOS_SIMULADOS["saldo_inicial"], color="red")

        # Labels
        self.plt.xlabel(x_label)
        self.plt.ylabel("Banca (R$)")
        self.plt.title("EVOLUCAO DA BANCA")

        # Refresh
        self.refresh()


class BotDashboard(App):
    """Dashboard principal"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 4 4;
        grid-gutter: 1;
    }

    .painel {
        height: 100%;
        border: solid green;
    }

    #painel-grafico {
        column-span: 3;
        row-span: 2;
        border: solid cyan;
    }

    #painel-resumo {
        column-span: 1;
        row-span: 1;
    }

    #painel-ganhos {
        column-span: 1;
        row-span: 1;
    }

    #painel-perdas {
        column-span: 2;
        row-span: 2;
    }

    #painel-countdown {
        column-span: 1;
    }

    #painel-compound {
        column-span: 1;
    }

    #painel-acertos {
        column-span: 1;
    }

    #painel-streaks {
        column-span: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Sair"),
        ("r", "refresh", "Atualizar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield PainelGrafico(id="painel-grafico")
        yield PainelResumo(id="painel-resumo", classes="painel")
        yield PainelGanhosPeriodo(id="painel-ganhos", classes="painel")
        yield PainelPerdas(id="painel-perdas", classes="painel")
        yield PainelCountdown(id="painel-countdown", classes="painel")
        yield PainelCompound(id="painel-compound", classes="painel")
        yield PainelAcertos(id="painel-acertos", classes="painel")
        yield PainelStreaks(id="painel-streaks", classes="painel")
        yield Footer()

    def action_refresh(self):
        """Atualiza todos os paineis"""
        for widget in self.query(".painel"):
            if hasattr(widget, 'atualizar'):
                widget.atualizar()


if __name__ == "__main__":
    app = BotDashboard()
    app.run()
