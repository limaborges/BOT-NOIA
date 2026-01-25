#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI TEXTUAL - Interface moderna integrada com dados reais do bot
Usa Textual para renderizar dashboard no terminal

MODO STANDALONE: Roda DASHBOARD.bat - le dados do banco
MODO INTEGRADO: bot chama run_dashboard(bot_ref=self) - dados em tempo real
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
from textual_plotext import PlotextPlot
from rich.panel import Panel
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sqlite3
import json
from pathlib import Path


class DadosBot:
    """Classe para acessar dados do banco de dados"""

    def __init__(self, db_folder: str = "database"):
        self.db_folder = Path(db_folder)
        self.bets_db = self.db_folder / "bets.db"
        self.rounds_db = self.db_folder / "rounds.db"
        self._session_start_utc = None  # Timestamp de início da sessão (UTC)

    def _get_connection(self, db_path: Path):
        """Retorna conexao com o banco"""
        if db_path.exists():
            return sqlite3.connect(db_path)
        return None

    def get_session_start_utc(self) -> str:
        """Retorna timestamp de início da sessão baseado no deposito_inicial e inicio_timestamp"""
        if self._session_start_utc:
            return self._session_start_utc

        try:
            import json
            state_path = Path("session_state.json")
            if state_path.exists():
                with open(state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)

                deposito_inicial = state.get('deposito_inicial', 0)
                inicio = state.get('inicio_timestamp', '')

                if deposito_inicial > 0 and inicio:
                    # Converter inicio_timestamp para UTC (adicionar 3 horas)
                    brasilia_dt = datetime.strptime(inicio, '%Y-%m-%d %H:%M:%S')
                    utc_dt = brasilia_dt + timedelta(hours=3)
                    inicio_utc = utc_dt.strftime('%Y-%m-%d %H:%M:%S')

                    # Encontrar a primeira aposta com saldo ~deposito_inicial APÓS o inicio_timestamp
                    conn = self._get_connection(self.bets_db)
                    if conn:
                        margem = deposito_inicial * 0.02  # 2% de margem
                        cursor = conn.execute("""
                            SELECT MIN(timestamp)
                            FROM bets_executed
                            WHERE working_balance_before >= ? AND working_balance_before <= ?
                            AND timestamp >= ?
                        """, (deposito_inicial - margem, deposito_inicial + margem, inicio_utc))
                        row = cursor.fetchone()
                        conn.close()

                        if row and row[0]:
                            self._session_start_utc = row[0]
                            return self._session_start_utc

                    # Fallback: usar inicio_timestamp convertido
                    self._session_start_utc = inicio_utc
                    return self._session_start_utc
        except:
            pass
        return '1970-01-01 00:00:00'  # Fallback: pegar tudo

    def get_saldo_e_lucro(self) -> Dict:
        """Retorna saldo atual, inicial e lucro calculado (desde inicio da sessao)"""
        try:
            conn = self._get_connection(self.bets_db)
            if not conn:
                return self._default_saldo()

            # Usar timestamp de início da sessão
            session_start = self.get_session_start_utc()

            # Primeira aposta da sessao (saldo inicial) e soma de profit_loss
            cursor = conn.execute("""
                SELECT timestamp, working_balance_before
                FROM bets_executed
                WHERE working_balance_before IS NOT NULL
                AND timestamp >= ?
                ORDER BY timestamp ASC
                LIMIT 1
            """, (session_start,))
            first = cursor.fetchone()

            # Soma de todos os profit_loss da sessao (metodo mais preciso)
            cursor = conn.execute("""
                SELECT SUM(profit_loss), MAX(timestamp)
                FROM bets_executed
                WHERE timestamp >= ?
            """, (session_start,))
            totals = cursor.fetchone()
            total_pl = totals[0] or 0
            last_timestamp = totals[1]

            # Contar ciclos WIN na sessao
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT recommendation_id)
                FROM bets_executed
                WHERE result = 'WIN' AND timestamp >= ?
            """, (session_start,))
            wins = cursor.fetchone()[0] or 0

            # Contar ciclos que so tiveram LOSS (nenhum WIN)
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT b1.recommendation_id)
                FROM bets_executed b1
                WHERE b1.timestamp >= ?
                AND b1.result = 'LOSS'
                AND NOT EXISTS (
                    SELECT 1 FROM bets_executed b2
                    WHERE b2.recommendation_id = b1.recommendation_id
                    AND b2.result = 'WIN'
                )
            """, (session_start,))
            losses = cursor.fetchone()[0] or 0

            conn.close()

            if first and first[1]:
                saldo_inicial = first[1]
                # Calcular saldo atual como: inicial + soma(profit_loss)
                # Isso é mais preciso que working_balance_after
                saldo_atual = saldo_inicial + total_pl
                lucro = total_pl
                lucro_pct = (lucro / saldo_inicial * 100) if saldo_inicial > 0 else 0

                # Parse timestamp
                try:
                    inicio = datetime.strptime(first[0], '%Y-%m-%d %H:%M:%S')
                except:
                    inicio = None

                return {
                    'saldo_inicial': saldo_inicial,
                    'saldo_atual': saldo_atual,
                    'lucro': lucro,
                    'lucro_pct': lucro_pct,
                    'wins': wins,
                    'losses': losses,
                    'inicio': inicio
                }

            return self._default_saldo()
        except:
            return self._default_saldo()

    def _default_saldo(self) -> Dict:
        return {
            'saldo_inicial': 0,
            'saldo_atual': 0,
            'lucro': 0,
            'lucro_pct': 0,
            'wins': 0,
            'losses': 0,
            'inicio': None
        }

    def get_refresh_stats(self) -> Dict:
        """Retorna estatisticas de auto-refresh"""
        try:
            debug_db = self.db_folder / "debug.db"
            conn = self._get_connection(debug_db)
            if not conn:
                return {'total': 0, 'ultimo': None, 'ultimo_motivo': None}

            # Total de refreshes
            cursor = conn.execute("SELECT COUNT(*) FROM refresh_events")
            total = cursor.fetchone()[0] or 0

            # Ultimo refresh (converter UTC para Brasilia)
            cursor = conn.execute("""
                SELECT timestamp, reason FROM refresh_events
                ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()

            if row:
                ts_str, motivo = row
                try:
                    dt_utc = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    dt_brasilia = dt_utc - timedelta(hours=3)
                    ultimo = dt_brasilia.strftime("%d/%m %H:%M")
                except:
                    ultimo = ts_str[5:16] if ts_str else None
            else:
                ultimo = None
                motivo = None

            return {
                'total': total,
                'ultimo': ultimo,
                'ultimo_motivo': motivo
            }
        except:
            return {'total': 0, 'ultimo': None, 'ultimo_motivo': None}

    def get_banca_pico(self) -> Dict:
        """Retorna pico da banca e drawdown"""
        try:
            aceleracao_file = self.db_folder.parent / "aceleracao_state.json"
            if aceleracao_file.exists():
                with open(aceleracao_file, 'r') as f:
                    data = json.load(f)
                    return {
                        'pico': data.get('banca_pico', 0),
                        'existe': True
                    }
            return {'pico': 0, 'existe': False}
        except:
            return {'pico': 0, 'existe': False}

    def get_ganhos_periodo(self, horas: int) -> Dict:
        """Retorna ganhos de um periodo especifico (filtrado por sessao)"""
        try:
            conn = self._get_connection(self.bets_db)
            if not conn:
                return {'lucro': 0, 'wins': 0}

            session_start = self.get_session_start_utc()
            since = datetime.now() - timedelta(hours=horas)

            # Usar o maior entre session_start e since
            filter_time = max(session_start, since.strftime('%Y-%m-%d %H:%M:%S'))

            cursor = conn.execute("""
                SELECT
                    SUM(profit_loss) as lucro,
                    COUNT(DISTINCT CASE WHEN result = 'WIN' THEN recommendation_id END) as wins
                FROM bets_executed
                WHERE timestamp >= ?
            """, (filter_time,))

            row = cursor.fetchone()
            conn.close()

            return {
                'lucro': row[0] or 0,
                'wins': row[1] or 0
            }
        except:
            return {'lucro': 0, 'wins': 0}

    def get_ultimas_perdas(self, limit: int = 5) -> List[Dict]:
        """Retorna sessoes de martingale com resultado liquido negativo

        Agrupa apostas em sessoes por proximidade de tempo (<60s entre apostas)
        e progressao de valores (martingale dobra a cada tentativa).
        """
        try:
            conn = self._get_connection(self.bets_db)
            if not conn:
                return []

            session_start = self.get_session_start_utc()

            # Buscar apostas da sessao atual ordenadas por timestamp
            cursor = conn.execute("""
                SELECT timestamp, bet_amount, profit_loss, result
                FROM bets_executed
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (session_start,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return []

            # Agrupar em sessoes por proximidade de tempo
            from datetime import datetime, timedelta
            sessoes = []
            sessao_atual = []

            for row in rows:
                ts_str, bet_amount, profit_loss, result = row
                if profit_loss is None:
                    profit_loss = 0
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except:
                    continue

                if not sessao_atual:
                    sessao_atual = [(ts, bet_amount, profit_loss, result)]
                else:
                    # Verificar se esta aposta é proxima da anterior (< 60s)
                    diff = abs((ts - sessao_atual[-1][0]).total_seconds())
                    if diff < 60:
                        sessao_atual.append((ts, bet_amount, profit_loss, result))
                    else:
                        # Nova sessao - salvar anterior se tiver algo
                        if sessao_atual:
                            sessoes.append(sessao_atual)
                        sessao_atual = [(ts, bet_amount, profit_loss, result)]

            # Adicionar ultima sessao
            if sessao_atual:
                sessoes.append(sessao_atual)

            # Calcular resultado de cada sessao e filtrar perdas
            perdas = []
            for sessao in reversed(sessoes):  # mais recentes primeiro
                total_pl = sum(b[2] for b in sessao)  # soma profit_loss
                if total_pl < 0:
                    # Converter numero de apostas para tentativa real
                    # T1-T5: 1 aposta cada, T6: 2 apostas, T7: 2 apostas
                    num_bets = len(sessao)
                    if num_bets <= 5:
                        tentativa = num_bets
                    elif num_bets <= 7:
                        tentativa = 6  # T6 tem 2 slots
                    else:
                        tentativa = 7  # T7 tem 2 slots

                    # Data e horario da ultima aposta (converter UTC para Brasilia)
                    ultima_ts = max(b[0] for b in sessao)
                    ultima_ts_brasilia = ultima_ts - timedelta(hours=3)
                    data_hora = ultima_ts_brasilia.strftime("%d/%m %H:%M")

                    perdas.append({
                        'data_hora': data_hora,
                        'valor': total_pl,
                        'tentativa': tentativa
                    })

                    if len(perdas) >= limit:
                        break

            return perdas
        except:
            return []

    def get_acertos_por_tentativa(self) -> Dict[str, int]:
        """Retorna contagem de wins por tentativa (T1-T7)

        Agrupa apostas em sessoes por proximidade de tempo e identifica
        em qual tentativa (posicao na sessao) ocorreu o WIN.
        """
        try:
            conn = self._get_connection(self.bets_db)
            if not conn:
                return {f"T{i}": 0 for i in range(1, 8)}

            session_start = self.get_session_start_utc()

            cursor = conn.execute("""
                SELECT timestamp, bet_amount, profit_loss, result
                FROM bets_executed
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (session_start,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {f"T{i}": 0 for i in range(1, 8)}

            # Agrupar em sessoes por proximidade de tempo
            from datetime import datetime, timedelta
            sessoes = []
            sessao_atual = []

            for row in rows:
                ts_str, bet_amount, profit_loss, result = row
                if profit_loss is None:
                    profit_loss = 0
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except:
                    continue

                if not sessao_atual:
                    sessao_atual = [(ts, bet_amount, profit_loss, result)]
                else:
                    diff = abs((ts - sessao_atual[-1][0]).total_seconds())
                    if diff < 60:
                        sessao_atual.append((ts, bet_amount, profit_loss, result))
                    else:
                        if sessao_atual:
                            sessoes.append(sessao_atual)
                        sessao_atual = [(ts, bet_amount, profit_loss, result)]

            if sessao_atual:
                sessoes.append(sessao_atual)

            # Contar WINs por tentativa (baseado no tamanho da sessao)
            # T1-T5: 1 aposta cada, T6: 2 apostas, T7: 2 apostas
            result = {f"T{i}": 0 for i in range(1, 8)}
            for sessao in sessoes:
                # Verificar se a sessao terminou em WIN
                ultimo_resultado = sessao[-1][3]  # result da ultima aposta
                if ultimo_resultado == "WIN":
                    num_bets = len(sessao)
                    if num_bets <= 5:
                        tentativa = num_bets
                    elif num_bets <= 7:
                        tentativa = 6
                    else:
                        tentativa = 7

                    if 1 <= tentativa <= 7:
                        result[f"T{tentativa}"] += 1

            return result
        except:
            return {f"T{i}": 0 for i in range(1, 8)}

    def get_historico_banca(self) -> List[float]:
        """Retorna historico de evolucao da banca (saldo final de cada CICLO de martingale)"""
        try:
            conn = self._get_connection(self.bets_db)
            if not conn:
                return []

            session_start = self.get_session_start_utc()

            # Buscar todas as apostas ordenadas
            cursor = conn.execute("""
                SELECT timestamp, working_balance_after, result
                FROM bets_executed
                WHERE working_balance_after IS NOT NULL
                AND timestamp >= ?
                ORDER BY timestamp ASC
            """, (session_start,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return []

            # Adicionar saldo inicial (deposito) como primeiro ponto
            try:
                import json
                state_path = Path("session_state.json")
                if state_path.exists():
                    with open(state_path, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                    deposito_inicial = state.get('deposito_inicial', 0)
                else:
                    deposito_inicial = 0
            except:
                deposito_inicial = 0

            # Agrupar em ciclos: apostas com menos de 60s entre elas são do mesmo ciclo
            # Pegar apenas o saldo final de cada ciclo (quando WIN ou última do ciclo)
            valores = [deposito_inicial] if deposito_inicial > 0 else []
            ciclo_saldos = []

            for i, row in enumerate(rows):
                ts_str, saldo, result = row
                ciclo_saldos.append(saldo)

                # Verificar se é fim de ciclo
                is_win = result == 'WIN'
                is_last = (i == len(rows) - 1)

                # Verificar gap de tempo para próxima aposta
                if not is_last:
                    next_ts_str = rows[i + 1][0]
                    try:
                        ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                        next_ts = datetime.strptime(next_ts_str, '%Y-%m-%d %H:%M:%S')
                        gap = (next_ts - ts).total_seconds()
                        is_new_cycle = gap > 60  # Mais de 60s = novo ciclo
                    except:
                        is_new_cycle = False
                else:
                    is_new_cycle = True

                # Se WIN ou novo ciclo, registrar saldo final
                if is_win or is_new_cycle:
                    valores.append(ciclo_saldos[-1])
                    ciclo_saldos = []

            return valores
        except:
            return []

    def get_aposta_base(self) -> Dict:
        """Calcula aposta base a partir do saldo (NS7 = /127)"""
        try:
            # Pegar saldo inicial e atual
            dados = self.get_saldo_e_lucro()
            saldo_inicial = dados['saldo_inicial']
            saldo_atual = dados['saldo_atual']

            # NS7 = divisor 127
            divisor = 127

            base_inicial = saldo_inicial / divisor if saldo_inicial > 0 else 0
            base_atual = saldo_atual / divisor if saldo_atual > 0 else 0

            return {
                'base_inicial': base_inicial,
                'base_atual': base_atual
            }
        except:
            return {'base_inicial': 0, 'base_atual': 0}


# ========== PAINEIS ==========

class PainelResumo(Static):
    """Painel com resumo principal"""

    def __init__(self, bot_ref=None, **kwargs):
        super().__init__(**kwargs)
        self.bot_ref = bot_ref
        self.dados = DadosBot()

    def compose(self) -> ComposeResult:
        yield Static(id="resumo-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(3, self.atualizar)

    def atualizar(self):
        try:
            if self.bot_ref:
                # Modo integrado: dados do bot
                saldo = getattr(self.bot_ref, 'saldo_atual', 0)
                deposito = getattr(self.bot_ref, 'deposito_inicial', saldo)
                stats = getattr(self.bot_ref, 'stats', {})
                inicio = getattr(self.bot_ref, 'session_start', None)
                wins = stats.get('sessoes_win', 0)
                losses = stats.get('sessoes_loss', 0)
                lucro = saldo - deposito if deposito else 0
                lucro_pct = (lucro / deposito * 100) if deposito and deposito > 0 else 0
            else:
                # Modo standalone: dados do banco
                d = self.dados.get_saldo_e_lucro()
                saldo = d['saldo_atual']
                deposito = d['saldo_inicial']
                lucro = d['lucro']
                lucro_pct = d['lucro_pct']
                wins = d['wins']
                losses = d['losses']
                inicio = d['inicio']

            # Uptime
            if inicio:
                uptime = datetime.now() - inicio
                dias = uptime.days
                horas = uptime.seconds // 3600
                minutos = (uptime.seconds % 3600) // 60
                uptime_str = f"{dias}d {horas}h {minutos}m" if dias > 0 else f"{horas}h {minutos}m"
            else:
                uptime_str = "--"

            lucro_cor = "green" if lucro >= 0 else "red"
            lucro_sinal = "+" if lucro >= 0 else ""

            # Dados de refresh
            refresh = self.dados.get_refresh_stats()
            refresh_str = f"F5:{refresh['total']}"
            if refresh['ultimo']:
                refresh_str += f" ({refresh['ultimo']})"

            # Pico da banca e drawdown
            pico_data = self.dados.get_banca_pico()
            pico = pico_data['pico']
            if pico > 0 and saldo < pico:
                drawdown = pico - saldo
                dd_pct = (drawdown / pico * 100)
                pico_str = f"[green]PICO:R${pico:,.0f}[/] [red]DD:{dd_pct:.0f}%[/]"
            elif pico > 0:
                pico_str = f"[green]PICO:R${pico:,.0f}[/] [green]NO PICO[/]"
            else:
                pico_str = ""

            content = f"""[cyan]R${saldo:,.0f}[/] [{lucro_cor}]{lucro_sinal}R${lucro:,.0f}[/]
[white]{wins}W/{losses}L[/] [dim]{uptime_str}[/] [yellow]{refresh_str}[/]
{pico_str}"""

            self.query_one("#resumo-content").update(Panel(content, title="RESUMO", border_style="green"))
        except Exception as e:
            self.query_one("#resumo-content").update(Panel(f"Erro: {e}", title="RESUMO", border_style="red"))


class PainelGanhosPeriodo(Static):
    """Painel com ganhos por periodo"""

    periodo_idx = reactive(0)
    periodos_horas = [24, 12, 6, 1]
    periodos_labels = ["24h", "12h", "6h", "1h"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dados = DadosBot()

    def compose(self) -> ComposeResult:
        yield Static(id="ganhos-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(5, self.proximo_periodo)

    def proximo_periodo(self):
        self.periodo_idx = (self.periodo_idx + 1) % len(self.periodos_horas)
        self.atualizar()

    def atualizar(self):
        try:
            horas = self.periodos_horas[self.periodo_idx]
            label = self.periodos_labels[self.periodo_idx]
            d = self.dados.get_ganhos_periodo(horas)

            lucro = d['lucro']
            wins = d['wins']
            cor = "green" if lucro >= 0 else "red"
            sinal = "+" if lucro >= 0 else ""

            content = f"""[bold cyan]Ultimas {label}[/]
[{cor}]{sinal}R$ {lucro:,.2f}[/]
{wins} ciclos ganhos"""

            self.query_one("#ganhos-content").update(Panel(content, title=f"GANHOS {label}", border_style="cyan"))
        except:
            self.query_one("#ganhos-content").update(Panel("--", title="GANHOS", border_style="cyan"))


class PainelCountdown(Static):
    """Countdown para metas"""

    def __init__(self, bot_ref=None, **kwargs):
        super().__init__(**kwargs)
        self.bot_ref = bot_ref
        self.dados = DadosBot()

    def compose(self) -> ComposeResult:
        yield Static(id="countdown-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(10, self.atualizar)

    def atualizar(self):
        try:
            if self.bot_ref:
                saldo = getattr(self.bot_ref, 'saldo_atual', 0)
                inicial = getattr(self.bot_ref, 'deposito_inicial', saldo)
            else:
                d = self.dados.get_saldo_e_lucro()
                saldo = d['saldo_atual']
                inicial = d['saldo_inicial']

            if inicial <= 0:
                inicial = saldo if saldo > 0 else 100

            # Calcular nivel atual (quantas vezes dobrou)
            # nivel 0: inicial, nivel 1: 2x, nivel 2: 4x, nivel 3: 8x, etc
            nivel = 0
            meta_atual = inicial
            while saldo >= meta_atual * 2:
                meta_atual *= 2
                nivel += 1

            # Proxima meta
            proxima_meta = meta_atual * 2
            progresso = (saldo / proxima_meta * 100) if proxima_meta > 0 else 0
            bar_len = min(10, int(progresso / 10))

            # Multiplicador atual e proximo
            mult_atual = 2 ** nivel  # 1, 2, 4, 8, 16...
            mult_prox = 2 ** (nivel + 1)

            # Metas atingidas
            metas_atingidas = f"[green]✓[/] " + " → ".join([f"{2**i}x" for i in range(1, nivel + 1)]) if nivel > 0 else ""

            content = f"""[green]{metas_atingidas}[/]
[yellow]→ {mult_prox}x[/] {'█'*bar_len}{'░'*(10-bar_len)} {progresso:.0f}%
[dim]R${saldo:,.0f} / R${proxima_meta:,.0f}[/]"""

            self.query_one("#countdown-content").update(Panel(content, title="METAS", border_style="yellow"))
        except:
            self.query_one("#countdown-content").update(Panel("--", title="METAS", border_style="yellow"))


class PainelCompound(Static):
    """Info do compound"""

    def __init__(self, bot_ref=None, **kwargs):
        super().__init__(**kwargs)
        self.bot_ref = bot_ref
        self.dados = DadosBot()

    def compose(self) -> ComposeResult:
        yield Static(id="compound-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(10, self.atualizar)

    def atualizar(self):
        try:
            if self.bot_ref and hasattr(self.bot_ref, 'martingale'):
                m = self.bot_ref.martingale
                base_inicial = getattr(m, 'aposta_base_inicial', 0) or 15
                base_atual = getattr(m, 'aposta_base', 0) or base_inicial
                ns = getattr(m, 'nivel_seguranca', 7)
            else:
                d = self.dados.get_aposta_base()
                base_inicial = d['base_inicial'] or 15
                base_atual = d['base_atual'] or base_inicial
                ns = 7  # Default

            crescimento = ((base_atual / base_inicial) - 1) * 100 if base_inicial > 0 else 0

            content = f"""[dim]Inicial[/] R${base_inicial:.0f}
[white]Atual[/] R${base_atual:.0f}
[green]+{crescimento:.0f}%[/] | NS{ns}"""

            self.query_one("#compound-content").update(Panel(content, title="COMPOUND", border_style="magenta"))
        except:
            self.query_one("#compound-content").update(Panel("--", title="COMPOUND", border_style="magenta"))


class PainelUltimaAposta(Static):
    """Info da ultima aposta"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dados = DadosBot()

    def compose(self) -> ComposeResult:
        yield Static(id="ultima-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(5, self.atualizar)

    def atualizar(self):
        try:
            conn = self.dados._get_connection(self.dados.bets_db)
            if not conn:
                self.query_one("#ultima-content").update(Panel("--", title="ULTIMA", border_style="blue"))
                return

            cursor = conn.execute("""
                SELECT timestamp, result, profit_loss, bet_amount
                FROM bets_executed
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()

            if row:
                ts, result, pl, amount = row
                # Converter UTC para Brasilia (UTC-3)
                if ts:
                    try:
                        dt_utc = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        dt_brasilia = dt_utc - timedelta(hours=3)
                        hora = dt_brasilia.strftime("%H:%M")
                    except:
                        hora = ts[11:16] if ts else "--"
                else:
                    hora = "--"
                cor = "green" if result == "WIN" else "red"
                pl_str = f"{pl:+.0f}" if pl else "0"
                content = f"""[white]{hora}[/] [{cor}]{result}[/]
R${amount:.0f} → {pl_str}"""
            else:
                content = "[dim]Sem apostas[/]"

            self.query_one("#ultima-content").update(Panel(content, title="ULTIMA", border_style="blue"))
        except:
            self.query_one("#ultima-content").update(Panel("--", title="ULTIMA", border_style="blue"))


class PainelStreaks(Static):
    """Maiores streaks de baixos nas ultimas 24h"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dados = DadosBot()

    def compose(self) -> ComposeResult:
        yield Static(id="streaks-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(60, self.atualizar)

    def atualizar(self):
        try:
            conn = self.dados._get_connection(self.dados.rounds_db)
            if not conn:
                self.query_one("#streaks-content").update(Panel("[dim]Sem dados[/]", title="STREAKS", border_style="red"))
                return

            since = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

            cursor = conn.execute("""
                SELECT timestamp, multiplier
                FROM rounds
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (since,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                self.query_one("#streaks-content").update(Panel("[dim]Sem dados[/]", title="STREAKS", border_style="red"))
                return

            # Encontrar streaks de baixos (< 2.0)
            streaks = []
            current_streak = 0
            streak_start = None

            for ts, mult in rows:
                if mult < 2.0:
                    if current_streak == 0:
                        streak_start = ts[11:16] if ts else "--"
                    current_streak += 1
                else:
                    if current_streak >= 5:  # Só streaks >= 5
                        streaks.append((current_streak, streak_start))
                    current_streak = 0

            # Último streak se ainda ativo
            if current_streak >= 5:
                streaks.append((current_streak, streak_start))

            # Ordenar por tamanho (maior primeiro)
            streaks.sort(key=lambda x: x[0], reverse=True)

            if streaks:
                lines = []
                for size, hora in streaks[:3]:  # Top 3
                    lines.append(f"[red]{size}[/]@{hora}")
                content = "\n".join(lines)
            else:
                content = "[green]Nenhum >= 5[/]"

            self.query_one("#streaks-content").update(Panel(content, title="STREAKS", border_style="red"))
        except:
            self.query_one("#streaks-content").update(Panel("--", title="STREAKS", border_style="red"))


class PainelPerdas(Static):
    """Historico de perdas"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dados = DadosBot()

    def compose(self) -> ComposeResult:
        yield Static(id="perdas-content")

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(10, self.atualizar)

    def atualizar(self):
        try:
            perdas = self.dados.get_ultimas_perdas(5)

            lines = []
            for p in perdas:
                tent = f"T{p['tentativa']}" if p['tentativa'] else "T?"
                lines.append(f"[red]{p['data_hora']}[/] {tent} R${abs(p['valor']):.0f}")

            content = "\n".join(lines) if lines else "[green]Nenhuma perda![/]"
            self.query_one("#perdas-content").update(Panel(content, title="PERDAS", border_style="red"))
        except Exception as e:
            self.query_one("#perdas-content").update(Panel(f"Erro: {e}", title="PERDAS", border_style="red"))


class PainelGrafico(PlotextPlot):
    """Grafico de evolucao da banca"""

    def __init__(self, bot_ref=None, **kwargs):
        super().__init__(**kwargs)
        self.bot_ref = bot_ref
        self.dados = DadosBot()

    def on_mount(self) -> None:
        self.atualizar()
        self.set_interval(30, self.atualizar)

    def atualizar(self):
        try:
            valores = self.dados.get_historico_banca()

            if not valores or len(valores) < 2:
                if self.bot_ref:
                    saldo = getattr(self.bot_ref, 'saldo_atual', 100)
                    deposito = getattr(self.bot_ref, 'deposito_inicial', saldo)
                    valores = [deposito, saldo]
                else:
                    valores = [100, 100]

            x_values = list(range(len(valores)))

            self.plt.clear_figure()
            self.plt.plot(x_values, valores, marker="braille", color="green")
            if valores:
                self.plt.hline(valores[0], color="red")
            self.plt.xlabel("Apostas")
            self.plt.ylabel("Banca (R$)")
            self.plt.title("EVOLUCAO DA BANCA")
            self.refresh()
        except:
            pass


class BotDashboard(App):
    """Dashboard principal"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 4 4;
        grid-gutter: 0;
        padding: 0;
    }
    .painel {
        height: 100%;
        border: solid green;
        padding: 0;
        margin: 0;
    }
    #painel-grafico { column-span: 3; row-span: 2; border: solid cyan; padding: 0; }
    #painel-resumo { column-span: 1; row-span: 1; }
    #painel-ganhos { column-span: 1; row-span: 1; }
    #painel-perdas { column-span: 2; row-span: 2; }
    #painel-countdown { column-span: 1; }
    #painel-compound { column-span: 1; }
    #painel-ultima { column-span: 1; }
    #painel-streaks { column-span: 1; }
    Static { padding: 0 1; }
    """

    BINDINGS = [("q", "quit", "Sair"), ("r", "refresh", "Atualizar")]

    def __init__(self, bot_ref=None, **kwargs):
        super().__init__(**kwargs)
        self.bot_ref = bot_ref

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield PainelGrafico(bot_ref=self.bot_ref, id="painel-grafico")
        yield PainelResumo(bot_ref=self.bot_ref, id="painel-resumo", classes="painel")
        yield PainelGanhosPeriodo(id="painel-ganhos", classes="painel")
        yield PainelPerdas(id="painel-perdas", classes="painel")
        yield PainelCountdown(bot_ref=self.bot_ref, id="painel-countdown", classes="painel")
        yield PainelCompound(bot_ref=self.bot_ref, id="painel-compound", classes="painel")
        yield PainelUltimaAposta(id="painel-ultima", classes="painel")
        yield PainelStreaks(id="painel-streaks", classes="painel")
        yield Footer()

    def action_refresh(self):
        for widget in self.query(".painel"):
            if hasattr(widget, 'atualizar'):
                widget.atualizar()


def run_dashboard(bot_ref=None):
    """Roda dashboard standalone ou integrado"""
    app = BotDashboard(bot_ref=bot_ref)
    app.run()


if __name__ == "__main__":
    run_dashboard()
