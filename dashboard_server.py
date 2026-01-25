#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DASHBOARD SERVER - Servidor HTTP para dashboard visual
Roda em paralelo ao sistema principal, lendo dados do SQLite e JSON.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, List
import time


# Fuso horário Brasília (UTC-3)
# Banco de dados usa UTC, então para exibir em Brasília subtraímos 3 horas
BRASILIA_OFFSET = timedelta(hours=-3)


class DashboardDataProvider:
    """Provedor de dados para o dashboard"""

    def __init__(self, db_path: str = 'database/bets.db', state_path: str = 'session_state.json',
                 rounds_db_path: str = 'database/rounds.db'):
        self.db_path = db_path
        self.state_path = state_path
        self.rounds_db_path = rounds_db_path
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

    def now_brasilia(self) -> datetime:
        """Retorna datetime atual em Brasília"""
        from datetime import timezone
        utc_now = datetime.now(timezone.utc)
        return utc_now + BRASILIA_OFFSET

    def utc_to_brasilia(self, dt: datetime) -> datetime:
        """Converte UTC para Brasília"""
        return dt + BRASILIA_OFFSET

    def get_sessao_inicio(self) -> str:
        """Retorna timestamp de início da sessão (para queries no banco UTC)"""
        state = self.get_session_state()
        inicio = state.get('inicio_timestamp', '')

        if not inicio:
            return '1970-01-01 00:00:00'

        # inicio_timestamp está em Brasília, converter para UTC para queries
        try:
            brasilia_dt = datetime.strptime(inicio, '%Y-%m-%d %H:%M:%S')
            utc_dt = brasilia_dt - BRASILIA_OFFSET  # Brasília -> UTC
            return utc_dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return inicio

    def get_session_state(self) -> Dict:
        """Lê o estado atual da sessão"""
        try:
            path = os.path.join(self.base_dir, self.state_path)
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def get_reserva_state(self) -> Dict:
        """Lê o estado da reserva de lucros"""
        try:
            path = os.path.join(self.base_dir, 'reserva_state.json')
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def get_ultimos_multiplicadores(self, limit: int = 13) -> List[float]:
        """Retorna últimos multiplicadores observados pelo OCR (da tabela rounds)"""
        try:
            path = os.path.join(self.base_dir, self.rounds_db_path)
            sessao_inicio = self.get_sessao_inicio()
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT multiplier FROM rounds
                WHERE multiplier IS NOT NULL
                AND timestamp >= ?
                ORDER BY id DESC LIMIT ?
            ''', (sessao_inicio, limit))
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in reversed(rows)]
        except Exception as e:
            # Fallback: tentar do bets.db se rounds.db não existir
            try:
                path = os.path.join(self.base_dir, self.db_path)
                sessao_inicio = self.get_sessao_inicio()
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT actual_multiplier FROM bets_executed
                    WHERE actual_multiplier IS NOT NULL
                    AND timestamp >= ?
                    ORDER BY id DESC LIMIT ?
                ''', (sessao_inicio, limit))
                rows = cursor.fetchall()
                conn.close()
                return [r[0] for r in reversed(rows)]
            except:
                return []

    def get_max_streak_baixos(self) -> Dict:
        """Calcula a maior sequencia consecutiva de multiplicadores baixos (< 2.0x) da sessao"""
        try:
            path = os.path.join(self.base_dir, self.rounds_db_path)
            sessao_inicio = self.get_sessao_inicio()
            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            # Buscar todos os multiplicadores da sessao em ordem cronologica
            cursor.execute('''
                SELECT multiplier FROM rounds
                WHERE multiplier IS NOT NULL
                AND timestamp >= ?
                ORDER BY id ASC
            ''', (sessao_inicio,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {'atual': 0, 'max': 0}

            # Calcular streaks
            streak_atual = 0
            streak_max = 0

            for (mult,) in rows:
                if mult < 2.0:  # Multiplicador baixo
                    streak_atual += 1
                    if streak_atual > streak_max:
                        streak_max = streak_atual
                else:
                    streak_atual = 0

            return {
                'atual': streak_atual,  # Streak atual (em andamento)
                'max': streak_max       # Maior streak da sessao
            }

        except Exception as e:
            return {'atual': 0, 'max': 0}

    def get_session_info(self) -> Dict:
        """Retorna informações completas da sessão"""
        try:
            state = self.get_session_state()
            inicio_str = self.get_sessao_inicio()  # Usa a lógica corrigida (UTC para queries)

            # Calcular uptime
            # inicio_timestamp está em horário local, convertemos para Brasília
            uptime_str = '--:--:--'
            inicio_original = state.get('inicio_timestamp', '')
            if inicio_original:
                try:
                    # Parse inicio (local time) e converter para Brasília
                    inicio_local = datetime.strptime(inicio_original, '%Y-%m-%d %H:%M:%S')
                    # Ajuste: local (UTC-4) para Brasília (UTC-3) = +1 hora
                    inicio_brasilia = inicio_local + timedelta(hours=1)
                    agora_brasilia = self.now_brasilia()
                    # Remover timezone info para subtrair
                    agora_naive = agora_brasilia.replace(tzinfo=None)
                    delta = agora_naive - inicio_brasilia
                    # Evitar uptime negativo
                    if delta.total_seconds() < 0:
                        delta = timedelta(seconds=0)
                    hours, remainder = divmod(int(delta.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_str = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
                except:
                    pass

            # Contar rounds na sessão
            total_rounds = 0
            ultimo_round = ''
            try:
                path = os.path.join(self.base_dir, self.rounds_db_path)
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*), MAX(timestamp) FROM rounds
                    WHERE timestamp >= ?
                ''', (inicio_str or '1970-01-01',))
                row = cursor.fetchone()
                conn.close()
                total_rounds = row[0] or 0
                ultimo_round = row[1] or ''
            except:
                pass

            # Ajustar último round de UTC para Brasília
            ultimo_round_ajustado = ''
            if ultimo_round:
                try:
                    dt = datetime.strptime(ultimo_round, '%Y-%m-%d %H:%M:%S')
                    dt_brasilia = self.utc_to_brasilia(dt)
                    ultimo_round_ajustado = dt_brasilia.strftime('%H:%M:%S')
                except:
                    ultimo_round_ajustado = ultimo_round[11:19] if len(ultimo_round) > 11 else ''

            # Max streak de baixos
            streak_data = self.get_max_streak_baixos()

            return {
                'sessao_id': state.get('sessao_id', ''),
                'inicio': inicio_str,
                'uptime': uptime_str,
                'total_rounds': total_rounds,
                'ultimo_round': ultimo_round_ajustado,
                'perfil': state.get('perfil_ativo', ''),
                'nivel': state.get('nivel_seguranca', 6),
                'streak_baixos': streak_data.get('atual', 0),
                'max_streak_baixos': streak_data.get('max', 0),
            }
        except:
            return {
                'sessao_id': '',
                'inicio': '',
                'uptime': '--:--:--',
                'total_rounds': 0,
                'ultimo_round': '',
                'perfil': '',
                'nivel': 6,
                'streak_baixos': 0,
                'max_streak_baixos': 0,
            }

    def get_apostas_recentes(self, limit: int = 20) -> List[Dict]:
        """Retorna apostas recentes da sessão atual"""
        try:
            path = os.path.join(self.base_dir, self.db_path)
            sessao_inicio = self.get_sessao_inicio()
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, bet_amount, target_multiplier, actual_multiplier,
                       result, profit_loss, bet_slot
                FROM bets_executed
                WHERE timestamp >= ?
                ORDER BY id DESC LIMIT ?
            ''', (sessao_inicio, limit))
            rows = cursor.fetchall()
            conn.close()

            apostas = []
            for r in rows:
                apostas.append({
                    'timestamp': r[0][:19] if r[0] else '',
                    'valor': r[1] or 0,
                    'alvo': r[2] or 0,
                    'multiplicador': r[3] or 0,
                    'resultado': r[4] or '',
                    'lucro': r[5] or 0,
                    'slot': r[6] or 1
                })
            return apostas
        except:
            return []

    def get_triggers_por_hora(self, horas: int = 6) -> Dict[str, int]:
        """Retorna contagem de triggers por hora da sessão atual"""
        try:
            path = os.path.join(self.base_dir, self.db_path)
            sessao_inicio = self.get_sessao_inicio()
            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT strftime('%H', timestamp) as hora, COUNT(*) as qtd
                FROM recommendations
                WHERE pattern_detected LIKE 'MARTINGALE%'
                AND timestamp >= ?
                GROUP BY strftime('%H', timestamp)
                ORDER BY hora
            ''', (sessao_inicio,))
            rows = cursor.fetchall()
            conn.close()

            return {f"{r[0]}h": r[1] for r in rows}
        except:
            return {}

    def get_evolucao_banca(self) -> List[Dict]:
        """Retorna evolução da banca da sessão atual (TODAS as apostas)"""
        try:
            path = os.path.join(self.base_dir, self.db_path)
            sessao_inicio = self.get_sessao_inicio()
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            # Join com recommendations para pegar o reason (contém tentativa)
            # Sem LIMIT - busca TODAS as apostas da sessão
            cursor.execute('''
                SELECT b.timestamp, b.working_balance_after, b.result, b.profit_loss,
                       r.reason, b.bet_amount, b.target_multiplier, b.actual_multiplier
                FROM bets_executed b
                LEFT JOIN recommendations r ON b.recommendation_id = r.id
                WHERE b.working_balance_after IS NOT NULL
                AND b.timestamp >= ?
                ORDER BY b.id ASC
            ''', (sessao_inicio,))
            rows = cursor.fetchall()
            conn.close()

            evolucao = []
            for r in rows:  # Já está em ordem ASC, não precisa reverter
                # Extrair tentativa do reason (formato: "Sessao WIN [WIN] em T1")
                reason = r[4] or ''
                tentativa = ''
                import re
                match = re.search(r'T(\d+)', reason)
                if match:
                    tentativa = f"T{match.group(1)}"

                evolucao.append({
                    'timestamp': r[0][11:16] if r[0] else '',  # HH:MM
                    'saldo': r[1] or 0,
                    'resultado': r[2] or '',
                    'lucro': r[3] or 0,
                    'tentativa': tentativa,
                    'valor': r[5] or 0,
                    'alvo': r[6] or 0,
                    'mult_real': r[7] or 0
                })
            return evolucao
        except:
            return []

    def get_performance(self) -> Dict:
        """Retorna estatísticas de performance da sessão atual"""
        try:
            path = os.path.join(self.base_dir, self.db_path)
            sessao_inicio = self.get_sessao_inicio()
            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            # Wins e losses da sessão atual
            cursor.execute('''
                SELECT result, COUNT(*) FROM bets_executed
                WHERE timestamp >= ?
                GROUP BY result
            ''', (sessao_inicio,))
            rows = cursor.fetchall()
            conn.close()

            perf = {'wins': 0, 'losses': 0}
            for r in rows:
                if r[0] == 'WIN':
                    perf['wins'] = r[1]
                elif r[0] == 'LOSS':
                    perf['losses'] = r[1]

            return perf
        except:
            return {'wins': 0, 'losses': 0}

    def get_wins_por_tentativa(self) -> Dict[str, int]:
        """Retorna contagem de wins por tentativa (T1-T6+) da sessão atual

        Infere o número da tentativa pela sequência de apostas:
        - Uma sequência de LOSS seguida de WIN indica em qual tentativa ganhou
        - LOSS, LOSS, WIN = ganhou em T3
        """
        try:
            path = os.path.join(self.base_dir, self.db_path)
            sessao_inicio = self.get_sessao_inicio()
            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            # Buscar todas as apostas em ordem cronológica
            cursor.execute('''
                SELECT result, timestamp FROM bets_executed
                WHERE timestamp >= ?
                ORDER BY id ASC
            ''', (sessao_inicio,))
            rows = cursor.fetchall()
            conn.close()

            # Inicializar contadores
            tentativas = {'T1': 0, 'T2': 0, 'T3': 0, 'T4': 0, 'T5': 0, 'T6+': 0}

            # Contar tentativas baseado na sequência
            current_attempt = 1
            for result, _ in rows:
                if result == 'WIN':
                    # Registrar em qual tentativa ganhou
                    if current_attempt <= 5:
                        tentativas[f'T{current_attempt}'] += 1
                    else:
                        tentativas['T6+'] += 1
                    current_attempt = 1  # Reset para próxima sessão
                elif result == 'LOSS':
                    current_attempt += 1  # Incrementar tentativa

            return tentativas
        except:
            return {'T1': 0, 'T2': 0, 'T3': 0, 'T4': 0, 'T5': 0, 'T6+': 0}

    def get_estatisticas_validacao(self) -> Dict:
        """Retorna estatísticas esperadas vs reais para validação

        Usa a mesma lógica de inferir tentativas pela sequência LOSS/WIN
        """
        try:
            # Reutilizar a contagem de tentativas
            tentativas = self.get_wins_por_tentativa()

            # Total de sessões completas (wins)
            total_sessions = sum(tentativas.values())

            if total_sessions == 0:
                return {'items': [], 'total_triggers': 0}

            # Valores esperados (baseados em 99k rodadas)
            esperados = {
                'T1': 50.0,   # 50% resolve em T1
                'T2': 25.0,   # 25% resolve em T2
                'T3': 12.5,   # 12.5% resolve em T3
                'T4': 6.25,   # 6.25% resolve em T4
                'T5': 3.13,   # 3.13% resolve em T5
                'T6+': 3.12,  # 3.12% vai para T6+
            }

            items = []
            for label in ['T1', 'T2', 'T3', 'T4', 'T5', 'T6+']:
                wins = tentativas.get(label, 0)
                real_pct = (wins / total_sessions * 100) if total_sessions > 0 else 0
                esperado_pct = esperados.get(label, 0)

                items.append({
                    'label': label,
                    'esperado': esperado_pct,
                    'real': round(real_pct, 1),
                    'count': wins,
                    'status': 'ok' if abs(real_pct - esperado_pct) < 15 else ('high' if real_pct > esperado_pct else 'low')
                })

            return {
                'items': items,
                'total_triggers': total_sessions,
                'total_losses': 0  # Será calculado quando houver losses completos
            }
        except Exception as e:
            return {'items': [], 'total_triggers': 0, 'error': str(e)}

    def get_dashboard_data(self) -> Dict:
        """Retorna todos os dados para o dashboard"""
        state = self.get_session_state()
        reserva = self.get_reserva_state()
        perf = self.get_performance()
        session_info = self.get_session_info()

        # Calcular frequência de triggers
        triggers_hora = self.get_triggers_por_hora(4)
        total_triggers = sum(triggers_hora.values())
        freq_triggers = total_triggers / 4 if triggers_hora else 0

        # Lucro considera saques realizados (saque não é perda!)
        saques = state.get('total_saques', 0)
        lucro = state.get('saldo_atual', 0) - state.get('deposito_inicial', 0) + saques
        deposito = state.get('deposito_inicial', 1)
        lucro_pct = (lucro / deposito) * 100 if deposito > 0 else 0

        # Dados da reserva
        banca_base = reserva.get('banca_base', 0)
        meta_valor = banca_base * 0.10 if banca_base > 0 else 0
        lucro_acumulado = reserva.get('lucro_acumulado', 0)
        progresso_meta = (lucro_acumulado / meta_valor * 100) if meta_valor > 0 else 0

        return {
            'timestamp': self.now_brasilia().isoformat(),
            'saldo_atual': state.get('saldo_atual', 0),
            'deposito_inicial': state.get('deposito_inicial', 0),
            'total_saques': saques,
            'lucro': lucro,
            'lucro_pct': lucro_pct,
            'sessoes_win': state.get('sessoes_win', 0),
            'sessoes_loss': state.get('sessoes_loss', 0),
            'total_rodadas': state.get('total_rodadas', 0),
            'nivel': state.get('nivel_seguranca', 6),
            'perfil': state.get('perfil_ativo', ''),
            'multiplicadores': self.get_ultimos_multiplicadores(13),
            'apostas': self.get_apostas_recentes(10),
            'triggers_hora': triggers_hora,
            'freq_triggers': freq_triggers,
            'evolucao': self.get_evolucao_banca(),  # Todas as apostas da sessão
            'performance': perf,
            'wins_por_tentativa': self.get_wins_por_tentativa(),
            'validacao': self.get_estatisticas_validacao(),
            'session_info': session_info,
            # Reserva de lucros
            'reserva_total': reserva.get('reserva_total', 0),
            'reserva_metas': reserva.get('total_metas_batidas', 0),
            'reserva_meta_valor': meta_valor,
            'reserva_progresso': progresso_meta,
            'reserva_lucro_acum': lucro_acumulado,
        }


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Handler customizado para servir API e arquivos estáticos"""

    data_provider = None

    def __init__(self, *args, **kwargs):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=self.base_dir, **kwargs)

    def do_GET(self):
        if self.path == '/api/dashboard':
            self.send_api_response()
        elif self.path == '/' or self.path == '/dashboard':
            self.path = '/dashboard.html'
            self.send_file_no_cache()
        else:
            # Adicionar no-cache para arquivos estáticos (HTML, JS, CSS)
            if self.path.endswith(('.html', '.js', '.css')):
                self.send_file_no_cache()
            else:
                super().do_GET()

    def send_file_no_cache(self):
        """Envia arquivo com headers anti-cache"""
        try:
            file_path = os.path.join(self.base_dir, self.path.lstrip('/'))
            with open(file_path, 'rb') as f:
                content = f.read()

            self.send_response(200)
            # Determinar content-type
            if self.path.endswith('.html'):
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            elif self.path.endswith('.js'):
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            elif self.path.endswith('.css'):
                self.send_header('Content-Type', 'text/css; charset=utf-8')
            # Headers anti-cache
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, 'File not found')
        except Exception as e:
            self.send_error(500, str(e))

    def send_api_response(self):
        """Envia dados JSON do dashboard"""
        try:
            data = self.data_provider.get_dashboard_data()
            response = json.dumps(data, ensure_ascii=False)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, format, *args):
        """Silencia logs do servidor"""
        pass


class DashboardServer:
    """Servidor do dashboard"""

    def __init__(self, port: int = 8080):
        self.port = port
        self.server = None
        self.thread = None
        self.data_provider = DashboardDataProvider()

    def start(self):
        """Inicia o servidor em thread separada"""
        DashboardRequestHandler.data_provider = self.data_provider

        self.server = HTTPServer(('0.0.0.0', self.port), DashboardRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        print(f"\n{'='*50}")
        print(f"  DASHBOARD DISPONIVEL")
        print(f"  http://localhost:{self.port}/dashboard")
        print(f"{'='*50}\n")

    def stop(self):
        """Para o servidor"""
        if self.server:
            self.server.shutdown()


# Instância global para fácil acesso
_dashboard_server = None

def iniciar_dashboard(port: int = 8080):
    """Inicia o dashboard server"""
    global _dashboard_server
    if _dashboard_server is None:
        _dashboard_server = DashboardServer(port)
        _dashboard_server.start()
    return _dashboard_server

def parar_dashboard():
    """Para o dashboard server"""
    global _dashboard_server
    if _dashboard_server:
        _dashboard_server.stop()
        _dashboard_server = None


if __name__ == '__main__':
    print("Iniciando Dashboard Server...")
    server = iniciar_dashboard(8080)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando...")
        parar_dashboard()
