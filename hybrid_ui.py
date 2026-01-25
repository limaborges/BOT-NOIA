#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HYBRID UI V2 - Interface Melhorada para Sistema Martingale V2
- Grafico de evolucao da banca
- Historico completo de apostas com rolagem
- Estatisticas detalhadas
"""

import os
import time
import sys
from datetime import datetime
from colorama import Fore, Style, init
from typing import List, Dict

init(autoreset=True)


class HybridUI:
    """Interface melhorada para o Hybrid System V2"""

    def __init__(self, controller):
        self.controller = controller
        self.running = False
        self.update_interval = 1.5

        # Controle de rolagem do historico
        self.scroll_offset = 0
        self.visible_bets = 5  # Mais compacto

        # Historico de saldos para grafico (adaptativo)
        self.saldo_history: List[Dict] = []  # {'valor': float, 'evento': 'normal'|'win'|'loss'}
        self.last_saldo = 0.0

        # Buffer de comando
        self.command_buffer = ""
        self.command_mode = False
        self.last_message = ""  # Mensagem para exibir temporariamente

        # Configurar terminal
        self.setup_terminal()

    def setup_terminal(self):
        """Configura tamanho do terminal - compacto"""
        try:
            if os.name == 'nt':
                os.system('mode con: cols=85 lines=35')
                os.system('title Martingale V2')
        except:
            pass

    def clear_screen(self):
        """Limpa tela"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def format_money(self, valor: float) -> str:
        """Formata valor monetario com cor"""
        if valor >= 0:
            return f"{Fore.GREEN}R$ {valor:+.2f}{Fore.WHITE}"
        else:
            return f"{Fore.RED}R$ {valor:+.2f}{Fore.WHITE}"

    def format_percent(self, valor: float) -> str:
        """Formata percentual com cor"""
        if valor >= 0:
            return f"{Fore.GREEN}{valor:+.1f}%{Fore.WHITE}"
        else:
            return f"{Fore.RED}{valor:+.1f}%{Fore.WHITE}"

    def draw_graph(self, data_points: List[Dict], width: int = 50, height: int = 8) -> List[str]:
        """
        Desenha grafico de LINHA ASCII com eixos
        Eixo Y: Banca (R$)
        Eixo X: Tempo (pontos de dados)
        """
        if not data_points or len(data_points) < 2:
            return [f"{Fore.CYAN}  EVOLUCAO DA BANCA", f"{Fore.WHITE}  Aguardando dados..."]

        # Extrair valores
        values = [p['valor'] for p in data_points]
        eventos = [p.get('evento', 'normal') for p in data_points]

        # Calcular min/max com margem
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val if max_val != min_val else 1

        # Adaptar pontos ao tamanho disponivel
        if len(values) > width:
            step = len(values) / width
            display_values = []
            display_eventos = []
            for i in range(width):
                idx = int(i * step)
                display_values.append(values[min(idx, len(values)-1)])
                display_eventos.append(eventos[min(idx, len(eventos)-1)])
        else:
            display_values = values
            display_eventos = eventos

        initial_val = values[0]
        current_val = values[-1]
        lucro = current_val - initial_val

        lines = []

        # Cabecalho
        cor_lucro = Fore.GREEN if lucro >= 0 else Fore.RED
        lines.append(f"{Fore.CYAN}  BANCA  {cor_lucro}R$ {current_val:.2f} ({lucro:+.2f}){Fore.WHITE}")

        # Calcular posicao Y de cada ponto (0 a height-1)
        def get_y(val):
            if range_val == 0:
                return height // 2
            return int((val - min_val) / range_val * (height - 1))

        # Criar matriz do grafico
        graph_matrix = [[' ' for _ in range(len(display_values))] for _ in range(height)]

        # Plotar linha conectando pontos
        for i, val in enumerate(display_values):
            y = get_y(val)
            evento = display_eventos[i]

            # Simbolo baseado no evento
            if evento == 'win':
                symbol = '▲'
                color = Fore.GREEN
            elif evento == 'loss':
                symbol = '▼'
                color = Fore.RED
            else:
                symbol = '●' if val >= initial_val else '○'
                color = Fore.GREEN if val >= initial_val else Fore.RED

            graph_matrix[y][i] = (color, symbol)

            # Conectar com ponto anterior
            if i > 0:
                prev_y = get_y(display_values[i-1])
                if prev_y != y:
                    step_y = 1 if y > prev_y else -1
                    for mid_y in range(prev_y + step_y, y, step_y):
                        if graph_matrix[mid_y][i] == ' ':
                            graph_matrix[mid_y][i] = (Fore.WHITE, '│')

        # Renderizar grafico (de cima para baixo)
        for row in range(height - 1, -1, -1):
            # Eixo Y com valor
            if row == height - 1:
                y_label = f"{max_val:>7.0f}"
            elif row == 0:
                y_label = f"{min_val:>7.0f}"
            elif row == height // 2:
                mid_val = (max_val + min_val) / 2
                y_label = f"{mid_val:>7.0f}"
            else:
                y_label = "       "

            line = f"{Fore.WHITE}{y_label}│"

            for col in range(len(display_values)):
                cell = graph_matrix[row][col]
                if cell == ' ':
                    line += ' '
                else:
                    color, symbol = cell
                    line += f"{color}{symbol}{Fore.WHITE}"

            lines.append(line)

        # Eixo X
        x_axis = "       └" + "─" * len(display_values)
        lines.append(f"{Fore.WHITE}{x_axis}")

        # Labels do eixo X (inicio e fim)
        x_labels = "        inicio" + " " * (len(display_values) - 12) + "agora"
        lines.append(f"{Fore.WHITE}{x_labels}")

        return lines

    def render(self):
        """Renderiza interface completa"""
        try:
            # Obter dados do controller
            data = self.controller.get_current_status()

            # Atualizar historico de saldos com deteccao de eventos
            saldo_atual = data.get('saldo_atual', 0.0)
            sessoes_win = data.get('sessoes_win', 0)
            sessoes_loss = data.get('sessoes_loss', 0)

            # Só adiciona ao histórico quando o saldo REALMENTE mudar
            if saldo_atual > 0 and saldo_atual != self.last_saldo:
                # Detectar evento baseado na mudanca de saldo
                evento = 'normal'
                if self.last_saldo > 0:
                    diff = saldo_atual - self.last_saldo
                    # Detectar win/loss por mudanca significativa
                    if diff > 5:  # Ganhou mais de R$5
                        evento = 'win'
                    elif diff < -5:  # Perdeu mais de R$5
                        evento = 'loss'

                self.saldo_history.append({'valor': saldo_atual, 'evento': evento})
                self.last_saldo = saldo_atual

            # Dados da sessao
            uptime = data.get('uptime', '00:00:00')
            total_rodadas = data.get('total_rodadas', 0)
            deposito_inicial = data.get('deposito_inicial', 0.0)
            resultado_bruto = data.get('resultado_bruto', 0.0)
            resultado_percent = data.get('resultado_percent', 0.0)

            # Estado do martingale
            sequencia_baixos = data.get('sequencia_baixos', 0)
            gatilho = data.get('gatilho', 7)
            em_martingale = data.get('em_martingale', False)
            tentativa_atual = data.get('tentativa_atual', 0)
            max_tentativas = data.get('max_tentativas', 7)
            alvo_atual = data.get('alvo_atual', 1.99)
            aposta_base = data.get('aposta_base', 0.0)

            # Estatisticas
            historico_apostas = data.get('historico_apostas', [])
            taxa_acerto = data.get('taxa_acerto', 0.0)
            stats = data.get('stats', {})
            multiplier_history = data.get('multiplier_history', [])

            # Dados do refresh
            time_since_explosion = data.get('time_since_explosion', 0)
            refresh_timeout = data.get('refresh_timeout', 133)
            total_refreshes = data.get('total_refreshes', 0)

            # Status do martingale
            if em_martingale:
                if tentativa_atual >= 5:
                    mart_status = f"{Fore.RED}SOBREVIVENCIA T{tentativa_atual}/{max_tentativas} @ {alvo_atual}x{Fore.WHITE}"
                elif tentativa_atual >= 4:
                    mart_status = f"{Fore.YELLOW}TRANSICAO T{tentativa_atual}/{max_tentativas} @ {alvo_atual}x{Fore.WHITE}"
                else:
                    mart_status = f"{Fore.GREEN}LUCRO T{tentativa_atual}/{max_tentativas} @ {alvo_atual}x{Fore.WHITE}"
            else:
                mart_status = f"{Fore.WHITE}Aguardando gatilho ({sequencia_baixos}/{gatilho})"

            # Barra de progresso do gatilho
            progresso_gatilho = int((sequencia_baixos / gatilho) * 20)
            barra_gatilho = f"[{'█' * progresso_gatilho}{'░' * (20 - progresso_gatilho)}]"

            # Historico de multiplicadores formatado (ultimos 14)
            mult_str = ""
            for m in multiplier_history[-14:]:
                if m < 2.0:
                    mult_str += f"{Fore.RED}{m:.2f}x{Fore.WHITE} "
                else:
                    mult_str += f"{Fore.GREEN}{m:.2f}x{Fore.WHITE} "

            # Risco atual (100% do saldo, dividido por 127)
            risco_atual = aposta_base * 127 if aposta_base > 0 else saldo_atual
            pct_risco = (risco_atual / saldo_atual * 100) if saldo_atual > 0 else 0

            # Layout compacto
            timer_cor = Fore.YELLOW if time_since_explosion > 60 else Fore.WHITE
            layout = f"""{Fore.CYAN}{'='*80}
{Fore.CYAN}  MARTINGALE V2  {datetime.now().strftime('%H:%M:%S')}  |  {uptime}  |  R: {total_rodadas}
{Fore.CYAN}{'='*80}
{Fore.WHITE}  Saldo: R$ {saldo_atual:.2f}  |  P/L: {self.format_money(resultado_bruto)} ({self.format_percent(resultado_percent)})
{Fore.WHITE}  Gatilho: {barra_gatilho} {sequencia_baixos}/{gatilho}  |  Base: R$ {aposta_base:.2f}  |  Timer: {timer_cor}{time_since_explosion:.0f}s{Fore.WHITE}
{Fore.WHITE}  Status: {mart_status}
{Fore.WHITE}  Mult: {mult_str if mult_str else 'Aguardando...'}
"""
            # Grafico mais compacto
            graph_lines = self.draw_graph(self.saldo_history, width=60, height=5)
            for line in graph_lines:
                layout += line + "\n"

            # Stats em uma linha
            win_count = stats.get('apostas_ganhas', 0)
            loss_count = stats.get('apostas_perdidas', 0)
            layout += f"""
{Fore.WHITE}  Stats: {Fore.GREEN}W:{win_count}{Fore.WHITE} | {Fore.RED}L:{loss_count}{Fore.WHITE} | Rate: {Fore.GREEN if taxa_acerto >= 50 else Fore.RED}{taxa_acerto:.0f}%{Fore.WHITE} | Max Seq: {stats.get('maior_sequencia_baixos', 0)}
{Fore.CYAN}  APOSTAS ({len(historico_apostas)}) {Fore.WHITE}{'─'*60}"""

            # Historico de apostas com scroll
            if historico_apostas:
                total_apostas = len(historico_apostas)
                # Limitar scroll
                max_scroll = max(0, total_apostas - self.visible_bets)
                self.scroll_offset = min(self.scroll_offset, max_scroll)

                start_idx = max(0, total_apostas - self.visible_bets - self.scroll_offset)
                end_idx = total_apostas - self.scroll_offset

                apostas_visiveis = historico_apostas[start_idx:end_idx]

                if self.scroll_offset > 0:
                    layout += f"\n{Fore.YELLOW}  ▲ +{self.scroll_offset} acima"

                for aposta in apostas_visiveis:
                    horario = aposta.get('horario', '--:--:--')
                    valor = aposta.get('valor_apostado', 0)
                    resultado = aposta.get('resultado', 0)
                    ganhou = aposta.get('ganhou', False)
                    tentativa = aposta.get('tentativa', 1)
                    alvo = aposta.get('alvo', 1.99)
                    mult_real = aposta.get('multiplicador_real', 0)

                    if ganhou:
                        status_cor = Fore.GREEN
                        status_txt = "WIN "
                    else:
                        status_cor = Fore.RED
                        status_txt = "LOSS"

                    layout += f"\n{Fore.WHITE}  [{horario}] T{tentativa} | R$ {valor:>7.2f} @ {alvo}x | Real: {mult_real:.2f}x | {status_cor}{status_txt}{Fore.WHITE} | {self.format_money(resultado)}"

                if start_idx > 0:
                    layout += f"\n{Fore.YELLOW}  ▼ +{start_idx} abaixo"
            else:
                layout += f"\n{Fore.WHITE}  Aguardando apostas..."

            # Mostrar nivel e modo
            nivel_nome = data.get('nome_nivel', 'NS7')
            modo = data.get('modo_operacao', 'manual').upper()

            # Footer com comandos
            if self.command_mode:
                cmd_line = f"{Fore.YELLOW}  CMD: /{self.command_buffer}_"
            else:
                cmd_line = f"{Fore.WHITE}  Pressione / para comandos"

            # Mensagem temporaria
            msg_line = ""
            if self.last_message:
                msg_line = f"\n{Fore.CYAN}  >> {self.last_message}"

            layout += f"""
{Fore.CYAN}{'='*80}
{Fore.WHITE}  {nivel_nome} | {modo}  |  Saques: R$ {data.get('total_saques', 0):.2f}
{Fore.CYAN}  COMANDOS: {Fore.WHITE}/status  /saque VALOR  /nivel 6-10  /help
{cmd_line}{msg_line}
{Fore.CYAN}{'='*80}"""

            return layout

        except Exception as e:
            import traceback
            return f"{Fore.RED}Erro na interface: {e}\n{traceback.format_exc()}"

    def update_display(self):
        """Atualiza display"""
        self.clear_screen()
        layout = self.render()
        print(layout)

    def handle_input(self):
        """Trata input do teclado (non-blocking)"""
        try:
            if os.name == 'nt':
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch()

                    if self.command_mode:
                        # Modo de digitacao de comando
                        if key == b'\r':  # Enter
                            self.execute_command(self.command_buffer)
                            self.command_buffer = ""
                            self.command_mode = False
                        elif key == b'\x08':  # Backspace
                            self.command_buffer = self.command_buffer[:-1]
                            if not self.command_buffer:
                                self.command_mode = False
                        elif key == b'\x1b':  # Escape
                            self.command_buffer = ""
                            self.command_mode = False
                        elif key.isalnum() or key in [b' ', b'.']:
                            self.command_buffer += key.decode('utf-8', errors='ignore')
                    else:
                        # Modo normal
                        if key == b'/':  # Iniciar comando
                            self.command_mode = True
                            self.command_buffer = ""
                            self.last_message = ""
                        elif key == b'\xe0':  # Tecla especial
                            key = msvcrt.getch()
                            if key == b'H':  # Seta para cima
                                self.scroll_offset += 1
                            elif key == b'P':  # Seta para baixo
                                self.scroll_offset = max(0, self.scroll_offset - 1)
        except:
            pass

    def execute_command(self, cmd: str):
        """Executa um comando"""
        cmd = cmd.strip().lower()
        self.last_message = ""

        if cmd == 'status' or cmd == 's':
            self.show_status()

        elif cmd.startswith('saque ') or cmd.startswith('s '):
            parts = cmd.split()
            if len(parts) >= 2:
                try:
                    valor = float(parts[1].replace(',', '.'))
                    if valor > 0:
                        self.controller.registrar_saque(valor)
                        self.last_message = f"Saque de R$ {valor:.2f} registrado!"
                    else:
                        self.last_message = "Valor invalido!"
                except ValueError:
                    self.last_message = "Uso: /saque VALOR"
            else:
                self.last_message = "Uso: /saque VALOR"

        elif cmd.startswith('nivel ') or cmd.startswith('n '):
            parts = cmd.split()
            if len(parts) >= 2:
                try:
                    nivel = int(parts[1])
                    if self.controller.mudar_nivel_manual(nivel):
                        self.last_message = f"Nivel alterado para NS{nivel}!"
                    else:
                        self.last_message = "Falha ao mudar nivel."
                except ValueError:
                    self.last_message = "Uso: /nivel 6|7|8|9|10"
            else:
                self.last_message = "Uso: /nivel 6|7|8|9|10"

        elif cmd == 'help' or cmd == 'h' or cmd == '?':
            self.last_message = "/status /saque VALOR /nivel 6-10 /help"

        else:
            self.last_message = f"Comando desconhecido: /{cmd}"

    def show_status(self):
        """Mostra status detalhado"""
        data = self.controller.get_current_status()
        deposito = data.get('deposito_inicial', 0)
        saldo = data.get('saldo_atual', 0)
        saques = data.get('total_saques', 0) if hasattr(self.controller, 'total_saques') else 0

        lucro_total = saldo - deposito + saques
        self.last_message = f"Dep: R${deposito:.0f} | Saldo: R${saldo:.0f} | Saques: R${saques:.0f} | Lucro: R${lucro_total:+.0f}"

    def start(self):
        """Inicia interface"""
        self.running = True

        try:
            while self.running:
                self.handle_input()
                self.update_display()
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            self.running = False

    def stop(self):
        """Para interface"""
        self.running = False


# Teste standalone
if __name__ == "__main__":
    print("Esta interface requer o HybridSystemV2 para funcionar.")
    print("Execute: python start_v2.py")
