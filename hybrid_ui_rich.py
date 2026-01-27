# -*- coding: utf-8 -*-
"""
HYBRID UI RICH - Interface elegante com Rich
Versao compacta com grafico de evolucao da banca
"""

import os
import time
import sys
import math
import io
from datetime import datetime
from typing import List, Dict

# Forcar UTF-8 no Windows
if sys.platform == "win32":
    os.system("")
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# Keyboard input (Windows)
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# Plotext para graficos no terminal - DESABILITADO
HAS_PLOTEXT = False  # Grafico desabilitado para interface mais limpa
# try:
#     import plotext as plt
#     HAS_PLOTEXT = True
# except ImportError:
#     HAS_PLOTEXT = False
#     print("⚠️ plotext nao instalado - grafico desabilitado")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich import box

console = Console(force_terminal=True, legacy_windows=False)

# Caracteres ASCII compativeis
SPARK_CHARS = "_.-~=+*#"


class HybridUIRich:
    """Interface Rich compacta para Martingale V2"""

    def __init__(self, controller, compact_mode: bool = False):
        self.controller = controller
        self.running = False
        self.update_interval = 1.5
        self.compact_mode = compact_mode  # Modo ultra-compacto

        # Historico para sparkline
        self.saldo_history: List[float] = []
        self.last_saldo = 0.0

        # Controle de tempo para frequencia
        self.trigger_times: List[float] = []
        self.session_start = time.time()

        # Contagem inicial de triggers (para calcular apenas novos desde que UI iniciou)
        self.initial_triggers = None  # Sera capturado no primeiro render

        # Configurar terminal
        self.setup_terminal()

    def setup_terminal(self):
        """Configura terminal"""
        try:
            if os.name == 'nt':
                if self.compact_mode:
                    os.system('mode con: cols=35 lines=12')
                else:
                    os.system('mode con: cols=80 lines=50')
                os.system('title MartingaleV2')
        except:
            pass

    def toggle_compact(self):
        """Alterna entre modo compacto e normal"""
        self.compact_mode = not self.compact_mode
        self.setup_terminal()

    def contar_tentativas(self, historico: List[Dict]) -> Dict[str, int]:
        """Conta wins por tentativa"""
        contagem = {'T1': 0, 'T2': 0, 'T3': 0, 'T4': 0, 'T5': 0, 'T6+': 0}
        for aposta in historico:
            if aposta.get('ganhou'):
                tent = aposta.get('tentativa', 0)
                if tent == 1:
                    contagem['T1'] += 1
                elif tent == 2:
                    contagem['T2'] += 1
                elif tent == 3:
                    contagem['T3'] += 1
                elif tent == 4:
                    contagem['T4'] += 1
                elif tent == 5:
                    contagem['T5'] += 1
                elif tent >= 6:
                    contagem['T6+'] += 1
        return contagem

    def gerar_grafico_banca(self, historico: List[Dict], deposito: float, saldo_atual: float) -> str:
        """Gera grafico de linha da evolucao da banca com plotext"""
        if not HAS_PLOTEXT or not historico:
            return ""

        try:
            # Construir dados do grafico
            # Agrupar apostas por sessao (gatilho) - pegar apenas a ultima de cada sessao
            sessoes_finalizadas = []
            saldo_acumulado = deposito

            # Agrupar por sessao de gatilho (apostas consecutivas ate WIN ou LOSS final)
            sessao_atual = []
            for ap in historico:
                sessao_atual.append(ap)
                # Sessao termina quando ganha ou quando é T6+ loss
                ganhou = ap.get('ganhou', False)
                tent = ap.get('tentativa', 0)
                cenario = ap.get('cenario', '')

                # Fim da sessao: WIN ou LOSS final (T6 ou cenario C)
                if ganhou or tent >= 6 or cenario in ['C', 'LOSS']:
                    # Calcular resultado da sessao
                    resultado_sessao = sum(a.get('resultado', 0) for a in sessao_atual)
                    saldo_acumulado += resultado_sessao

                    # Pegar info da ultima aposta (que finalizou)
                    ultima = sessao_atual[-1]
                    sessoes_finalizadas.append({
                        'horario': ultima.get('horario', '--:--'),
                        'tentativa': ultima.get('tentativa', 0),
                        'ganhou': ganhou,
                        'resultado': resultado_sessao,
                        'saldo_apos': saldo_acumulado
                    })
                    sessao_atual = []

            if not sessoes_finalizadas:
                return ""

            # Preparar dados para plotext
            x_vals = list(range(len(sessoes_finalizadas) + 1))  # +1 para deposito inicial
            y_vals = [deposito] + [s['saldo_apos'] for s in sessoes_finalizadas]

            # Pontos de WIN e LOSS
            win_x = [i+1 for i, s in enumerate(sessoes_finalizadas) if s['ganhou']]
            win_y = [s['saldo_apos'] for s in sessoes_finalizadas if s['ganhou']]
            loss_x = [i+1 for i, s in enumerate(sessoes_finalizadas) if not s['ganhou']]
            loss_y = [s['saldo_apos'] for s in sessoes_finalizadas if not s['ganhou']]

            # Configurar plotext
            plt.clear_figure()
            plt.plotsize(60, 10)  # Largura x Altura
            plt.theme('dark')

            # Linha principal da banca
            plt.plot(x_vals, y_vals, marker='braille', color='white')

            # Marcar WINs em verde
            if win_x:
                plt.scatter(win_x, win_y, marker='dot', color='green')

            # Marcar LOSSes em vermelho
            if loss_x:
                plt.scatter(loss_x, loss_y, marker='dot', color='red')

            # Labels dos eixos
            plt.xlabel("Gatilhos")
            plt.ylabel("R$")
            plt.title("Banca")

            # Capturar output como string
            grafico_str = plt.build()

            # Adicionar legenda com ultimas operacoes
            legenda_lines = []
            ultimas = sessoes_finalizadas[-5:]  # Ultimas 5 sessoes
            for s in reversed(ultimas):
                cor = "green" if s['ganhou'] else "red"
                sinal = "+" if s['resultado'] >= 0 else ""
                status = "W" if s['ganhou'] else "L"
                legenda_lines.append(
                    f"[{cor}]{s['horario']} T{s['tentativa']} {status} {sinal}R${s['resultado']:.0f}[/{cor}]"
                )

            legenda = " | ".join(legenda_lines) if legenda_lines else ""

            return grafico_str + "\n" + legenda

        except Exception as e:
            return f"[dim]Erro grafico: {e}[/dim]"

    def sparkline(self, values: List[float], width: int = 24) -> str:
        """Gera sparkline ASCII"""
        if not values or len(values) < 2:
            return "-" * width

        values = values[-width:]
        min_val = min(values)
        max_val = max(values)

        if max_val == min_val:
            return SPARK_CHARS[4] * len(values)

        result = ""
        for v in values:
            idx = int((v - min_val) / (max_val - min_val) * 7)
            idx = max(0, min(7, idx))
            result += SPARK_CHARS[idx]

        return result

    def calcular_wins_para_meta(self, lucro_pct: float, lucro_por_win: float) -> int:
        """Calcula WINs restantes para 100%"""
        if lucro_pct >= 100:
            return 0

        fator_atual = 1 + (lucro_pct / 100)
        fator_meta = 2.0  # 100% = dobrar
        fator_win = 1 + (lucro_por_win / 100)

        if fator_win <= 1:
            return 999

        wins = math.log(fator_meta / fator_atual) / math.log(fator_win)
        return max(0, math.ceil(wins))

    def indicador_frequencia(self, triggers_hora: float) -> str:
        """Indicador de frequencia de triggers"""
        if triggers_hora >= 2.0:
            return f"[bold green][***][/bold green] {triggers_hora:.1f}/h INTENSO"
        elif triggers_hora >= 1.0:
            return f"[green][**.][/green] {triggers_hora:.1f}/h NORMAL"
        elif triggers_hora >= 0.5:
            return f"[yellow][*..][/yellow] {triggers_hora:.1f}/h LENTO"
        else:
            return f"[dim][...][/dim] {triggers_hora:.1f}/h QUIETO"

    def indicador_countdown(self, wins_faltam: int, lucro_pct: float) -> str:
        """Indicador de countdown para meta"""
        if wins_faltam == 0:
            return "[bold green][META!][/bold green]"

        pct = min(100, max(0, lucro_pct))
        blocos = int(pct / 25)
        barra = "[" + "#" * blocos + "." * (4 - blocos) + "]"

        return f"[cyan]{barra}[/cyan] {wins_faltam}W->NS"

    def render_compact(self) -> str:
        """Renderiza interface ULTRA-COMPACTA (cabe em janela pequena)"""
        try:
            data = self.controller.get_current_status()

            # Dados basicos
            saldo = data.get('saldo_atual', 0.0)
            deposito = data.get('deposito_inicial', 0.0)
            nome_nivel = data.get('nome_nivel', 'NS6')
            modo = data.get('modo_operacao', 'manual').upper()[:3]

            # Calculos
            lucro_bruto = saldo - deposito if deposito > 0 else 0
            lucro_pct = (lucro_bruto / deposito * 100) if deposito > 0 else 0

            # Estado martingale
            em_mart = data.get('em_martingale', False)
            tent_atual = data.get('tentativa_atual', 0)
            seq_baixos = data.get('sequencia_baixos', 0)
            gatilho = data.get('gatilho', 6)
            aposta_base = data.get('aposta_base', 0.0)

            # Stats
            wins = data.get('sessoes_win', 0)
            losses = data.get('sessoes_loss', 0)
            total = wins + losses
            taxa = (wins / total * 100) if total > 0 else 0

            # Timer
            timer = data.get('time_since_explosion', 0)

            # Multiplicadores (ultimos 5)
            mults = data.get('multiplier_history', [])[-5:]
            mult_str = " ".join([
                f"[red]{m:.1f}[/red]" if m < 2.0 else f"[green]{m:.1f}[/green]"
                for m in mults
            ]) if mults else "-"

            # Cor do lucro
            cor_lucro = "green" if lucro_pct >= 0 else "red"
            sinal = "+" if lucro_pct >= 0 else ""

            # Status compacto
            if em_mart:
                status = f"[bold yellow]T{tent_atual}[/bold yellow]"
            else:
                prog = int((seq_baixos / gatilho) * 6)
                barra = "#" * prog + "." * (6 - prog)
                status = f"[{barra}]"

            # Montar linhas compactas
            lines = []

            # Linha 1: Saldo + Lucro
            lines.append(f"[bold]R${saldo:.2f}[/bold] [{cor_lucro}]{sinal}{lucro_pct:.1f}%[/{cor_lucro}]")

            # Linha 2: Status + Base
            lines.append(f"{status} {nome_nivel} B:R${aposta_base:.2f}")

            # Linha 3: Stats
            lines.append(f"[green]W{wins}[/green]/[red]L{losses}[/red] {taxa:.0f}% {timer:.0f}s")

            # Linha 4: Mults
            lines.append(f"{mult_str}")

            # Ultima aposta (se houver)
            historico = data.get('historico_apostas', [])
            if historico:
                ap = historico[-1]
                hora = ap.get('horario', '--:--')[-5:]
                tent = ap.get('tentativa', 0)
                ganhou = ap.get('ganhou', False)
                resultado = ap.get('resultado', 0)
                cor = "green" if ganhou else "red"
                lines.append(f"[{cor}]{hora} T{tent} R${resultado:+.0f}[/{cor}]")

            # Reserva (se ativa)
            reserva = data.get('reserva')
            if reserva:
                reserva_total = reserva.get('reserva_total', 0)
                if reserva_total > 0:
                    lines.append(f"[cyan]RSV:R${reserva_total:.0f}[/cyan]")

            return "\n".join(lines)

        except Exception as e:
            return f"[red]Err:{e}[/red]"

    def render(self) -> str:
        """Renderiza interface compacta"""
        # Se modo compacto, usar render simplificado
        if self.compact_mode:
            return self.render_compact()

        try:
            data = self.controller.get_current_status()

            # Dados basicos
            saldo = data.get('saldo_atual', 0.0)
            deposito = data.get('deposito_inicial', 0.0)
            nivel = data.get('nivel_seguranca', 6)
            nome_nivel = data.get('nome_nivel', 'NS6')
            modo = data.get('modo_operacao', 'manual').upper()

            # Calculos
            lucro_bruto = saldo - deposito if deposito > 0 else 0
            lucro_pct = (lucro_bruto / deposito * 100) if deposito > 0 else 0

            # Lucro por WIN baseado no nivel
            lucro_por_win = {6: 1.57, 7: 0.78, 8: 0.39, 9: 0.19, 10: 0.10}.get(nivel, 1.0)
            wins_faltam = self.calcular_wins_para_meta(lucro_pct, lucro_por_win)

            # Atualizar historico
            if saldo > 0 and saldo != self.last_saldo:
                self.saldo_history.append(saldo)
                self.last_saldo = saldo

            # Frequencia de triggers (somente desde que UI iniciou)
            sessoes_total = data.get('sessoes_win', 0) + data.get('sessoes_loss', 0)

            # Capturar contagem inicial no primeiro render
            if self.initial_triggers is None:
                self.initial_triggers = sessoes_total

            # Calcular apenas triggers NOVOS desde que UI iniciou
            triggers_novos = sessoes_total - self.initial_triggers
            tempo_sessao = time.time() - self.session_start
            triggers_hora = (triggers_novos / tempo_sessao * 3600) if tempo_sessao > 60 else 0

            # Estado martingale
            em_mart = data.get('em_martingale', False)
            tent_atual = data.get('tentativa_atual', 0)
            max_tent = data.get('max_tentativas', 6)
            seq_baixos = data.get('sequencia_baixos', 0)
            gatilho = data.get('gatilho', 6)
            alvo = data.get('alvo_atual', 1.99)
            aposta_base = data.get('aposta_base', 0.0)

            # Stats
            wins = data.get('sessoes_win', 0)
            losses = data.get('sessoes_loss', 0)
            total = wins + losses
            taxa = (wins / total * 100) if total > 0 else 0

            # Timer
            timer = data.get('time_since_explosion', 0)
            timer_cor = "yellow" if timer > 60 else "white"

            # Multiplicadores
            mults = data.get('multiplier_history', [])[-12:]
            mult_str = " ".join([
                f"[red]{m:.2f}[/red]" if m < 2.0 else f"[green]{m:.2f}[/green]"
                for m in mults
            ]) if mults else "[dim]aguardando...[/dim]"

            # Sparkline
            spark = self.sparkline(self.saldo_history)

            # Cor do lucro
            cor_lucro = "green" if lucro_pct >= 0 else "red"
            sinal = "+" if lucro_pct >= 0 else ""

            # Status do martingale
            if em_mart:
                if tent_atual >= 5:
                    status = f"[bold red]T{tent_atual}/{max_tent} @{alvo}x SOBREVIVENCIA[/bold red]"
                else:
                    status = f"[bold green]T{tent_atual}/{max_tent} @{alvo}x LUCRO[/bold green]"
            else:
                prog = int((seq_baixos / gatilho) * 10)
                barra = "#" * prog + "." * (10 - prog)
                status = f"({barra}) {seq_baixos}/{gatilho}"

            # Montar conteudo
            lines = []

            # Formatar modo com cor
            if modo == 'AUTOMATICO':
                modo_str = f"[bold green]{modo}[/bold green]"
            elif modo == 'GAGO':
                modo_str = f"[bold magenta]{modo}[/bold magenta]"
            elif modo == 'AUTONOMO':
                modo_str = f"[bold cyan]{modo}[/bold cyan]"
            else:
                modo_str = f"[yellow]{modo}[/yellow]"

            # Linha 1: Banca e Nivel e Modo
            lines.append(f"[bold]R$ {saldo:.2f}[/bold]  [dim]{nome_nivel}[/dim]  [{timer_cor}]{timer:.0f}s[/{timer_cor}]  {modo_str}")

            # Linha 2: Lucro
            lines.append(f"[{cor_lucro}]{sinal}{lucro_pct:.1f}%[/{cor_lucro}] ({sinal}R${lucro_bruto:.2f})")

            # Detectar modos sem reserva (NS7_PURO, G6_NS9, G6_NS10)
            modo_sem_reserva = modo in ['NS7_PURO', 'G6_NS9', 'G6_NS10']

            # Linha 3: Status (barra de gatilho e aposta base)
            lines.append(f"{status}  Base: R$ {aposta_base:.2f}")

            # Linha 4: Stats simplificados
            lines.append(f"[bold]Triggers:{total}[/bold] [green]W:{wins}[/green] [red]L:{losses}[/red] Rate:[{'green' if taxa >= 50 else 'red'}]{taxa:.0f}%[/{'green' if taxa >= 50 else 'red'}]")

            # Linha 5: Multiplicadores
            lines.append(f"[dim]Mult:[/dim] {mult_str}")

            # Historico de apostas
            historico = data.get('historico_apostas', [])

            # Grafico de evolucao da banca
            if historico and HAS_PLOTEXT:
                grafico = self.gerar_grafico_banca(historico, deposito, saldo)
                if grafico:
                    lines.append("")
                    lines.append(grafico)

            # Linha 7: Contagem por tentativa
            if historico:
                contagem = self.contar_tentativas(historico)
                tent_str = " ".join([
                    f"[green]{k}:{v}[/green]" if v > 0 else f"[dim]{k}:0[/dim]"
                    for k, v in contagem.items()
                ])
                lines.append(f"[dim]Wins:[/dim] {tent_str}")

            # Linha 8-12: Ultimas apostas
            if historico:
                lines.append("")
                lines.append("[dim]--- Ultimas Apostas ---[/dim]")
                ultimas = historico[-5:]  # Ultimas 5
                for ap in reversed(ultimas):
                    hora = ap.get('horario', '--:--')
                    tent = ap.get('tentativa', 0)
                    valor = ap.get('valor_apostado', 0)
                    alvo = ap.get('alvo', 0)
                    mult_real = ap.get('multiplicador_real', 0)
                    ganhou = ap.get('ganhou', False)
                    resultado = ap.get('resultado', 0)
                    cenario = ap.get('cenario', '')

                    # Formatar alvo (pode ser string "1.99/1.25" para 2 slots)
                    if isinstance(alvo, str):
                        alvo_str = alvo
                    else:
                        alvo_str = f"{alvo:.2f}"

                    if ganhou:
                        cor = "green"
                        status = "WIN"
                    else:
                        cor = "red"
                        status = "LOSS"

                    cenario_str = f"[{cenario}]" if cenario else ""
                    lines.append(f"[{cor}]{hora} T{tent} R${valor:.2f}@{alvo_str}x {mult_real:.2f}x {status}{cenario_str} R${resultado:+.2f}[/{cor}]")

                    # Mostrar sequência do gatilho quando há perda (para auditoria)
                    gatilho_mults = ap.get('gatilho_mults', [])
                    if not ganhou and gatilho_mults:
                        mults_str = ",".join([f"{m:.2f}" for m in gatilho_mults])
                        lines.append(f"[dim]  Gatilho: [{mults_str}][/dim]")

            # ===== PAINEL DE VALIDACAO ESTATISTICA =====
            stats_val = data.get('estatisticas_validacao', {})
            if stats_val.get('gatilhos_total', 0) > 0:
                lines.append("")
                lines.append("[dim]--- Validacao Estatistica ---[/dim]")

                # Gatilhos
                n = stats_val.get('gatilhos_total', 0)
                pct_t1t4 = stats_val.get('pct_resolveu_t1_t4', 0)
                pct_t5 = stats_val.get('pct_foi_t5', 0)
                esp = stats_val.get('esperado', {})

                # Status indicators
                def status_icon(status):
                    if status == 'ok':
                        return '[green]ok[/green]'
                    elif status == 'X':
                        return '[red]X[/red]'
                    else:
                        return '[yellow]?[/yellow]'

                st_t1t4 = status_icon(stats_val.get('status_t1_t4', '?'))
                st_t5 = status_icon(stats_val.get('status_t5', '?'))

                lines.append(f"[dim]Gatilhos:[/dim] {n} | T1-T4: {pct_t1t4:.0f}% (esp:{esp.get('resolveu_t1_t4', 0):.0f}%) {st_t1t4} | T5: {pct_t5:.0f}% (esp:{esp.get('foi_t5', 0):.0f}%) {st_t5}")

                # T5 cenarios (se houve)
                if stats_val.get('foi_t5', 0) > 0:
                    t5_a = stats_val.get('t5_cenario_a', 0)
                    t5_b = stats_val.get('t5_cenario_b', 0)
                    t5_c = stats_val.get('t5_cenario_c', 0)
                    pct_a = stats_val.get('pct_t5_a', 0)
                    pct_b = stats_val.get('pct_t5_b', 0)
                    pct_c = stats_val.get('pct_t5_c', 0)
                    lines.append(f"[dim]T5:[/dim] [green]A:{t5_a}({pct_a:.0f}%)[/green] [yellow]B:{t5_b}({pct_b:.0f}%)[/yellow] [red]C:{t5_c}({pct_c:.0f}%)[/red]")

                # T6+ (se houve)
                if stats_val.get('t6_total', 0) > 0:
                    t6_w = stats_val.get('t6_win', 0)
                    t6_l = stats_val.get('t6_loss', 0)
                    pct_w = stats_val.get('pct_t6_win', 0)
                    lines.append(f"[dim]T6+:[/dim] [green]W:{t6_w}({pct_w:.0f}%)[/green] [red]L:{t6_l}[/red]")

                # Piores cenarios
                sangrou = stats_val.get('sangrou_60', 0)
                zerou = stats_val.get('zerou_banca', 0)
                if sangrou > 0 or zerou > 0:
                    lines.append(f"[red]ALERTA: Sangrou:{sangrou} Zerou:{zerou}[/red]")

            # ===== PAINEL RESERVA DE LUCROS (oculto em modos sem reserva) =====
            reserva = data.get('reserva')
            if reserva and not modo_sem_reserva:
                lines.append("")
                lines.append("[bold magenta]--- Reserva de Lucros ---[/bold magenta]")

                # Meta e progresso
                meta = reserva.get('meta_valor', 0)
                lucro_acum = reserva.get('lucro_acumulado', 0)
                progresso = reserva.get('progresso_pct', 0)
                barra_prog = min(int(progresso / 10), 10)
                barra = "[" + "#" * barra_prog + "." * (10 - barra_prog) + "]"

                lines.append(f"Meta 10%: R${meta:.0f} | Progresso: {barra} {progresso:.0f}%")

                # Reserva e metas
                reserva_total = reserva.get('reserva_total', 0)
                total_metas = reserva.get('total_metas', 0)
                lines.append(f"[bold cyan]RESERVA: R${reserva_total:.0f}[/bold cyan] | Metas: {total_metas}x")

            conteudo = "\n".join(lines)

            return conteudo

        except Exception as e:
            return f"[red]Erro: {e}[/red]"

    def update_display(self):
        """Atualiza display"""
        console.clear()

        conteudo = self.render()

        if self.compact_mode:
            # Modo compacto: painel minimo
            painel = Panel(
                conteudo,
                title="[blue]MV2[/blue]",
                border_style="blue",
                box=box.MINIMAL,
                padding=(0, 0)
            )
            console.print(painel)
            console.print("[dim]C=Expandir R=Redefinir Q=Sair[/dim]")
        else:
            # Modo normal
            painel = Panel(
                conteudo,
                title="[bold blue]MartingaleV2[/bold blue]",
                border_style="blue",
                box=box.ROUNDED,
                padding=(0, 1)
            )
            console.print(painel)
            console.print("[dim]T=Testar | C=Compacto | R=Redefinir | Q=Sair[/dim]")

    def check_keyboard(self):
        """Verifica se uma tecla foi pressionada"""
        if not HAS_MSVCRT:
            return None

        if msvcrt.kbhit():
            key = msvcrt.getch()
            try:
                return key.decode('utf-8').upper()
            except:
                return None
        return None

    def testar_slots(self):
        """Testa apostas nos dois slots com R$1,00 @ 1,01x"""
        console.clear()
        console.print("\n[bold yellow]═══════════════════════════════════════════════[/bold yellow]")
        console.print("[bold yellow]       TESTE DE APOSTAS - SLOTS 1 e 2[/bold yellow]")
        console.print("[bold yellow]═══════════════════════════════════════════════[/bold yellow]")
        console.print("\n[cyan]Este teste aposta R$1,00 @ 1,01x em cada slot.[/cyan]")
        console.print("[cyan]Certifique-se que está em fase de APOSTAS![/cyan]")

        # Pausar sistema
        if hasattr(self.controller, 'pausar_para_teste'):
            self.controller.pausar_para_teste()

        try:
            # Obter bet_executor do controller
            bet_executor = getattr(self.controller, 'bet_executor', None)
            if not bet_executor:
                console.print("\n[red]ERRO: bet_executor não disponível![/red]")
                input("\nPressione ENTER para voltar...")
                return

            valor = 1.00
            alvo = 1.01

            # SLOT 1
            console.print(f"\n[bold cyan]{'─'*40}[/bold cyan]")
            console.print("[bold cyan]TESTANDO SLOT 1[/bold cyan]")
            console.print(f"[white]Valor: R${valor:.2f} | Alvo: {alvo:.2f}x[/white]")
            input("\n[Pressione ENTER para apostar no SLOT 1]")

            result1 = bet_executor.execute_bet(valor, alvo, bet_slot=1)

            if result1.success:
                console.print("[green]✓ Slot 1: Aposta enviada![/green]")
                if result1.confirmed:
                    console.print("[green]✓ Slot 1: CONFIRMADA[/green]")
                else:
                    console.print("[yellow]? Slot 1: Verificar manualmente[/yellow]")
            else:
                console.print(f"[red]✗ Slot 1: FALHOU - {result1.error}[/red]")

            time.sleep(1)

            # SLOT 2
            console.print(f"\n[bold cyan]{'─'*40}[/bold cyan]")
            console.print("[bold cyan]TESTANDO SLOT 2[/bold cyan]")
            console.print(f"[white]Valor: R${valor:.2f} | Alvo: {alvo:.2f}x[/white]")
            input("\n[Pressione ENTER para apostar no SLOT 2]")

            result2 = bet_executor.execute_bet(valor, alvo, bet_slot=2)

            if result2.success:
                console.print("[green]✓ Slot 2: Aposta enviada![/green]")
                if result2.confirmed:
                    console.print("[green]✓ Slot 2: CONFIRMADA[/green]")
                else:
                    console.print("[yellow]? Slot 2: Verificar manualmente[/yellow]")
            else:
                console.print(f"[red]✗ Slot 2: FALHOU - {result2.error}[/red]")

            # Resumo
            console.print(f"\n[bold white]{'═'*40}[/bold white]")
            console.print("[bold white]RESUMO DO TESTE[/bold white]")
            console.print(f"[white]Slot 1: {'OK' if result1.success else 'FALHOU'}[/white]")
            console.print(f"[white]Slot 2: {'OK' if result2.success else 'FALHOU'}[/white]")

        except Exception as e:
            console.print(f"\n[red]ERRO: {e}[/red]")

        input("\n[Pressione ENTER para voltar ao sistema]")

        # Retomar sistema
        if hasattr(self.controller, 'retomar_apos_teste'):
            self.controller.retomar_apos_teste()

    def menu_redefinir(self):
        """Menu para redefinir sessão (reset parcial)"""
        console.clear()
        console.print(f"\n[bold cyan]{'═'*50}[/bold cyan]")
        console.print("[bold cyan]  REDEFINIR SESSÃO (Reset Parcial)[/bold cyan]")
        console.print(f"[bold cyan]{'═'*50}[/bold cyan]")

        # Mostrar estado atual
        try:
            data = self.controller.get_current_status()
            saldo = data.get('saldo_atual', 0)
            deposito = data.get('deposito_inicial', 0)
            lucro = saldo - deposito
            modo = data.get('modo_operacao', 'N/A')

            console.print(f"\n[white]Estado atual:[/white]")
            console.print(f"  Saldo: [cyan]R$ {saldo:.2f}[/cyan]")
            console.print(f"  Depósito inicial: [white]R$ {deposito:.2f}[/white]")
            console.print(f"  Lucro sessão: [green]R$ {lucro:.2f}[/green]" if lucro >= 0 else f"  Lucro sessão: [red]R$ {lucro:.2f}[/red]")
            console.print(f"  Modo: [yellow]{modo}[/yellow]")
        except:
            pass

        console.print(f"\n[white]Isso irá:[/white]")
        console.print("  • Salvar lucro atual no acumulado")
        console.print("  • Resetar depósito inicial = saldo atual")
        console.print("  • Zerar contadores de sessão")

        console.print(f"\n[bold white]Escolha o novo modo:[/bold white]")
        console.print("  [cyan]1[/cyan] - NS9 (Agressivo)")
        console.print("  [cyan]2[/cyan] - NS10 (Conservador)")
        console.print("  [cyan]3[/cyan] - Manter modo atual")
        console.print("  [cyan]0[/cyan] - Cancelar")

        try:
            escolha = input("\nOpção: ").strip()

            if escolha == '0':
                console.print("[yellow]Cancelado.[/yellow]")
                time.sleep(1)
                return

            novo_modo = None
            if escolha == '1':
                novo_modo = 'ns9'
            elif escolha == '2':
                novo_modo = 'ns10'
            elif escolha == '3':
                novo_modo = None
            else:
                console.print("[red]Opção inválida![/red]")
                time.sleep(1)
                return

            # Confirmar
            console.print(f"\n[yellow]Confirma redefinição? (s/n)[/yellow]")
            confirma = input().strip().lower()

            if confirma == 's':
                if hasattr(self.controller, 'redefinir_sessao'):
                    sucesso = self.controller.redefinir_sessao(novo_modo)
                    if sucesso:
                        console.print(f"\n[bold green]✓ Sessão redefinida com sucesso![/bold green]")
                    else:
                        console.print(f"\n[bold red]✗ Erro ao redefinir sessão[/bold red]")
                else:
                    console.print(f"\n[red]Função não disponível neste controller[/red]")
            else:
                console.print("[yellow]Cancelado.[/yellow]")

        except Exception as e:
            console.print(f"\n[red]Erro: {e}[/red]")

        input("\n[Pressione ENTER para voltar]")

    def start(self):
        """Inicia interface"""
        self.running = True
        self.session_start = time.time()

        # Inicializar saldo_history se sessao restaurada
        # Isso evita grafico vazio quando retoma sessao anterior
        try:
            data = self.controller.get_current_status()
            deposito = data.get('deposito_inicial', 0.0)
            saldo = data.get('saldo_atual', 0.0)

            # Se temos dados de sessao restaurada e historico vazio
            if deposito > 0 and saldo > 0 and not self.saldo_history:
                # Reconstruir historico a partir do historico_apostas
                historico_apostas = data.get('historico_apostas', [])
                if historico_apostas:
                    # Iniciar com deposito e calcular saldo apos cada aposta
                    saldo_acumulado = deposito
                    self.saldo_history.append(saldo_acumulado)
                    for ap in historico_apostas:
                        resultado = ap.get('resultado', 0)
                        saldo_acumulado += resultado
                        self.saldo_history.append(saldo_acumulado)
                    self.last_saldo = saldo_acumulado
                else:
                    # Nao tem historico, iniciar com deposito e saldo atual
                    if deposito != saldo:
                        self.saldo_history = [deposito, saldo]
                    else:
                        self.saldo_history = [saldo]
                    self.last_saldo = saldo
        except:
            pass  # Silencioso em caso de erro

        try:
            while self.running:
                self.update_display()

                # Verificar teclas de atalho
                key = self.check_keyboard()
                if key == 'T' and not self.compact_mode:
                    self.testar_slots()
                elif key == 'C':
                    self.toggle_compact()
                elif key == 'R':
                    self.menu_redefinir()
                elif key == 'Q':
                    self.running = False
                    break

                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            self.running = False

    def stop(self):
        """Para interface"""
        self.running = False


# Teste standalone
if __name__ == "__main__":
    # Mock controller para teste
    class MockController:
        def get_current_status(self):
            return {
                'saldo_atual': 485.22,
                'deposito_inicial': 422.47,
                'nivel_seguranca': 6,
                'nome_nivel': 'NS6',
                'modo_operacao': 'automatico',
                'em_martingale': False,
                'tentativa_atual': 0,
                'max_tentativas': 6,
                'sequencia_baixos': 4,
                'gatilho': 6,
                'alvo_atual': 1.99,
                'aposta_base': 7.58,
                'sessoes_win': 9,
                'sessoes_loss': 0,
                'time_since_explosion': 45,
                'multiplier_history': [1.50, 1.82, 2.60, 17.35, 2.55, 1.24, 3.99, 3.55, 2.72, 1.57, 1.03, 1.30],
                'rally': {
                    'estado': 'quente',
                    'estado_icon': 'QUENTE',
                    'ultimo_intervalo': 15.5,
                    'media_3_intervalos': 22.3,
                    'total_triggers': 9,
                    'baseline': 51.0,
                    'limite_rally': 25.5,
                    'limite_quente': 38.25,
                },
                'estatisticas_validacao': {
                    'gatilhos_total': 9,
                    'resolveu_t1_t4': 9,
                    'foi_t5': 0,
                    't5_cenario_a': 0,
                    't5_cenario_b': 0,
                    't5_cenario_c': 0,
                    't6_total': 0,
                    't6_win': 0,
                    't6_loss': 0,
                    'sangrou_60': 0,
                    'zerou_banca': 0,
                    'pct_resolveu_t1_t4': 100.0,
                    'pct_foi_t5': 0.0,
                    'pct_t5_a': 0.0,
                    'pct_t5_b': 0.0,
                    'pct_t5_c': 0.0,
                    'pct_t6_win': 0.0,
                    'pct_t6_loss': 0.0,
                    'status_t1_t4': '?',
                    'status_t5': '?',
                    'status_t5_a': '?',
                    'status_t5_b': '?',
                    'status_t5_c': '?',
                    'status_t6_win': '?',
                    'esperado': {
                        'resolveu_t1_t4': 95.6,
                        'foi_t5': 4.4,
                        't5_cenario_a': 64.0,
                        't5_cenario_b': 16.0,
                        't5_cenario_c': 20.0,
                        't6_win': 80.0,
                        't6_loss': 20.0,
                    },
                },
                'historico_apostas': [
                    {'horario': '04:43:02', 'tentativa': 1, 'valor_apostado': 6.71, 'alvo': 1.99, 'multiplicador_real': 1.50, 'ganhou': False, 'resultado': -6.71, 'cenario': None},
                    {'horario': '04:43:18', 'tentativa': 2, 'valor_apostado': 13.41, 'alvo': 1.99, 'multiplicador_real': 1.82, 'ganhou': False, 'resultado': -13.41, 'cenario': None},
                    {'horario': '04:43:41', 'tentativa': 3, 'valor_apostado': 26.82, 'alvo': 1.99, 'multiplicador_real': 2.60, 'ganhou': True, 'resultado': 26.56, 'cenario': 'WIN'},
                    {'horario': '05:16:55', 'tentativa': 1, 'valor_apostado': 6.81, 'alvo': 1.99, 'multiplicador_real': 17.35, 'ganhou': True, 'resultado': 6.74, 'cenario': 'WIN'},
                    {'horario': '05:29:43', 'tentativa': 1, 'valor_apostado': 6.91, 'alvo': 1.99, 'multiplicador_real': 2.55, 'ganhou': True, 'resultado': 6.85, 'cenario': 'WIN'},
                    {'horario': '05:37:18', 'tentativa': 1, 'valor_apostado': 7.02, 'alvo': 1.99, 'multiplicador_real': 1.24, 'ganhou': False, 'resultado': -7.02, 'cenario': None},
                    {'horario': '05:37:36', 'tentativa': 2, 'valor_apostado': 14.05, 'alvo': 1.99, 'multiplicador_real': 3.99, 'ganhou': True, 'resultado': 13.91, 'cenario': 'WIN'},
                    {'horario': '08:51:43', 'tentativa': 4, 'valor_apostado': 58.87, 'alvo': 1.99, 'multiplicador_real': 30.29, 'ganhou': True, 'resultado': 58.28, 'cenario': 'WIN'},
                    {'horario': '10:20:55', 'tentativa': 2, 'valor_apostado': 15.17, 'alvo': 1.99, 'multiplicador_real': 2.82, 'ganhou': True, 'resultado': 15.02, 'cenario': 'WIN'},
                ],
            }

    print("=== Teste UI Rich ===\n")
    mock = MockController()
    ui = HybridUIRich(mock)

    # Simular historico de saldo
    ui.saldo_history = [422.47, 415.76, 402.35, 428.91, 435.65, 442.50, 435.48, 449.39, 456.45, 463.62, 485.22]
    ui.last_saldo = 485.22

    ui.update_display()
