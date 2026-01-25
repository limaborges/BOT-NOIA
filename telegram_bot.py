#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TELEGRAM BOT - Controle remoto do MartingaleV2

Roda em PARALELO ao bot principal.
Comunica via arquivos compartilhados:
- session_state.json (leitura de status)
- telegram_commands.json (fila de comandos)
- reserva_state.json (reserva e emprestimo)
- aceleracao_state.json (estrategia [7,7,6])
- database/*.db (leitura de dados)

Funcionalidades:
- Status completo com estrategia [7,7,6]
- Notificacao automatica a cada 10% de lucro
- Info de reserva, emprestimo e divida
"""

import os
import sys
import json
import time
import sqlite3
import requests
from datetime import datetime
from threading import Thread

# Importar Dual Account Manager
try:
    from dual_account_manager import DualAccountManager, existe_sessao_dual_account, STOP_WIN_PCT
    DUAL_ACCOUNT_AVAILABLE = True
except ImportError:
    DUAL_ACCOUNT_AVAILABLE = False
    DualAccountManager = None

# Importar utilitario de timezone (Brasilia)
try:
    from timezone_util import horario, agora_str, converter_str_utc_para_brasilia
    TZ_UTIL = True
except ImportError:
    TZ_UTIL = False
    def horario(): return datetime.now().strftime('%H:%M:%S')
    def agora_str(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    def converter_str_utc_para_brasilia(s, f='%Y-%m-%d %H:%M:%S'): return s

# Caminho base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'telegram_config.json')
STATE_FILE = os.path.join(BASE_DIR, 'session_state.json')
COMMANDS_FILE = os.path.join(BASE_DIR, 'telegram_commands.json')
ACELERACAO_FILE = os.path.join(BASE_DIR, 'aceleracao_state.json')
RESERVA_FILE = os.path.join(BASE_DIR, 'reserva_state.json')


class TelegramBot:
    def __init__(self):
        self.config = self.load_config()
        self.token = self.config.get('token')
        self.chat_id = self.config.get('chat_id')
        self.authorized_users = self.config.get('authorized_users', [])
        self.running = False
        self.last_update_id = 0

        # Status automatico a cada 2 horas (7200 segundos)
        self.status_interval = 2 * 60 * 60  # 2 horas em segundos
        self.last_status_time = 0

        # Monitoramento de lucro para notificacao a cada 10%
        self.last_lucro_notificado = 0  # Ultimo % de lucro notificado (10, 20, 30...)
        self.lucro_check_interval = 30  # Verificar a cada 30 segundos
        self.last_lucro_check = 0

        # Monitoramento de migracao dual account
        self.last_migracao_check = 0
        self.migracao_notificada = False  # Para nao notificar mais de uma vez por dia

        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def send_message(self, text, chat_id=None):
        """Envia mensagem para o Telegram"""
        chat_id = chat_id or self.chat_id
        if not chat_id:
            return False

        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            return response.json().get('ok', False)
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")
            return False

    def get_updates(self):
        """Busca atualizacoes (mensagens) do Telegram"""
        url = f"{self.base_url}/getUpdates"
        params = {
            'offset': self.last_update_id + 1,
            'timeout': 30
        }

        try:
            response = requests.get(url, params=params, timeout=35)
            data = response.json()

            if data.get('ok'):
                return data.get('result', [])
        except Exception as e:
            print(f"Erro ao buscar updates: {e}")

        return []

    def get_session_state(self):
        """Le o estado da sessao do arquivo"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return None

    def get_database_stats(self):
        """Le estatisticas do banco de dados"""
        stats = {}

        try:
            # Rounds
            db_path = os.path.join(BASE_DIR, 'database', 'rounds.db')
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM rounds")
                stats['total_rounds'] = cursor.fetchone()[0]

                cursor.execute("SELECT * FROM rounds ORDER BY id DESC LIMIT 1")
                last = cursor.fetchone()
                if last:
                    stats['last_mult'] = last[2]
                    # Converter timestamp UTC para Brasilia
                    ts_utc = last[1]
                    if ts_utc and TZ_UTIL:
                        try:
                            stats['last_time'] = converter_str_utc_para_brasilia(ts_utc)
                        except:
                            stats['last_time'] = ts_utc
                    else:
                        stats['last_time'] = ts_utc
                conn.close()
        except:
            pass

        return stats

    def get_session_bets(self, limit=10):
        """Busca apostas da sessao atual"""
        bets = []
        state = self.get_session_state()

        if not state:
            return bets

        sessao_inicio = state.get('inicio_timestamp', '')

        try:
            db_path = os.path.join(BASE_DIR, 'database', 'bets.db')
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Buscar apostas com info de tentativa
                cursor.execute('''
                    SELECT b.timestamp, b.result, b.bet_amount, b.target_multiplier,
                           b.actual_multiplier, b.profit_loss, r.reason
                    FROM bets_executed b
                    LEFT JOIN recommendations r ON b.recommendation_id = r.id
                    WHERE b.timestamp >= ?
                    ORDER BY b.id DESC LIMIT ?
                ''', (sessao_inicio, limit))

                rows = cursor.fetchall()
                for row in rows:
                    # Extrair tentativa do reason (ex: "T1 - Slot1" -> "T1")
                    reason = row[6] or ''
                    tentativa = reason.split(' ')[0] if reason else '?'

                    # Converter timestamp UTC para Brasilia
                    ts_utc = row[0]
                    if ts_utc and TZ_UTIL:
                        try:
                            ts_brasilia = converter_str_utc_para_brasilia(ts_utc)
                        except:
                            ts_brasilia = ts_utc
                    else:
                        ts_brasilia = ts_utc

                    bets.append({
                        'timestamp': ts_brasilia,
                        'result': row[1],
                        'valor': row[2],
                        'alvo': row[3],
                        'mult_real': row[4],
                        'pl': row[5],
                        'tentativa': tentativa
                    })

                conn.close()
        except Exception as e:
            print(f"Erro ao buscar apostas: {e}")

        return bets

    def get_reserva_state(self):
        """Le estado da reserva de lucros"""
        try:
            if os.path.exists(RESERVA_FILE):
                with open(RESERVA_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def get_aceleracao_state(self):
        """Le estado da estrategia [7,7,6]"""
        try:
            if os.path.exists(ACELERACAO_FILE):
                with open(ACELERACAO_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def format_status(self):
        """Formata mensagem de status"""
        state = self.get_session_state()
        db_stats = self.get_database_stats()
        reserva = self.get_reserva_state()
        aceleracao = self.get_aceleracao_state()

        if not state:
            return "Bot nao esta rodando ou sem dados de sessao."

        deposito = state.get('deposito_inicial', 0)
        saldo = state.get('saldo_atual', 0)
        saques = state.get('total_saques', 0)
        nivel = state.get('nivel_seguranca', 7)
        modo = state.get('config_modo', {}).get('modo', 'manual')
        wins = state.get('sessoes_win', 0)
        losses = state.get('sessoes_loss', 0)
        rodadas = state.get('total_rodadas', 0)
        inicio = state.get('inicio_timestamp', '?')

        # Analisar historico de apostas para detalhes de loss
        historico = state.get('historico_apostas', [])
        loss_por_tentativa = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        total_perdas = 0.0
        busts = []  # Lista de busts (T6 que perdeu)

        for aposta in historico:
            if not aposta.get('ganhou', True):
                tentativa = aposta.get('tentativa', 1)
                if tentativa in loss_por_tentativa:
                    loss_por_tentativa[tentativa] += 1
                total_perdas += abs(aposta.get('resultado', 0))

                # Detectar bust (T6 loss ou cenario C em T5)
                if tentativa == 6 or (tentativa == 5 and aposta.get('cenario') == 'C'):
                    busts.append({
                        'horario': aposta.get('horario', '?'),
                        'tentativa': tentativa,
                        'valor': abs(aposta.get('resultado', 0)),
                        'cenario': aposta.get('cenario', 'LOSS'),
                        'gatilho_mults': aposta.get('gatilho_mults', [])
                    })

        # Dados da reserva
        reserva_total = reserva.get('reserva_total', 0)
        total_metas = reserva.get('total_metas_batidas', 0)
        divida = reserva.get('divida_reserva', 0)
        total_emprestimos = reserva.get('total_emprestimos', 0)

        # Dados da aceleracao [7,7,6]
        padrao = aceleracao.get('padrao', [7, 7, 6])
        indice = aceleracao.get('indice_padrao', 0)
        gatilhos_desde_t6 = aceleracao.get('gatilhos_desde_t6', 0)
        total_ns6 = aceleracao.get('total_gatilhos_ns6', 0)
        total_ns7 = aceleracao.get('total_gatilhos_ns7', 0)
        total_gatilhos = total_ns6 + total_ns7
        banca_pico = aceleracao.get('banca_pico', 0)

        # Calcular posicao no padrao
        posicao = indice % len(padrao) if padrao else 0
        ns_atual = padrao[posicao] if padrao else 7
        padrao_str = "-".join(f"[{p}]" if i == posicao else str(p) for i, p in enumerate(padrao))

        lucro = saldo - deposito + saques
        lucro_pct = (lucro / deposito * 100) if deposito > 0 else 0

        # Emoji baseado no lucro
        emoji = "🟢" if lucro >= 0 else "🔴"

        # Verificar se e modo NS7_PURO
        is_ns7_puro = modo == 'ns7_puro'

        # Calcular drawdown do pico
        drawdown = banca_pico - saldo if banca_pico > saldo else 0
        drawdown_pct = (drawdown / banca_pico * 100) if banca_pico > 0 else 0

        msg = f"""
<b>📊 STATUS MARTINGALE V2</b>

<b>💰 Financeiro:</b>
  Deposito: R$ {deposito:.2f}
  Saldo: R$ {saldo:.2f}
  📈 Pico: R$ {banca_pico:.2f}"""

        # Mostrar drawdown se houver
        if drawdown > 0:
            msg += f"""
  📉 Drawdown: R$ {drawdown:.2f} ({drawdown_pct:.1f}%)"""

        msg += f"""
  {emoji} Lucro: R$ {lucro:+.2f} ({lucro_pct:+.1f}%)"""

        # NS7_PURO: sem reserva
        if is_ns7_puro:
            msg += f"""

<b>🎯 Modo NS7 PURO:</b>
  Banca: R$ {saldo:.2f} (100%)
  Aposta base: R$ {saldo / 127:.2f}
  Defesa: 1.10x"""
        else:
            msg += f"""

<b>💎 Reserva:</b>
  Total: R$ {reserva_total:.2f}
  Metas 10%: {total_metas}x"""

            if divida > 0:
                msg += f"""
  ⚠️ Divida: R$ {divida:.2f}"""

            if total_emprestimos > 0:
                msg += f"""
  Emprestimos: {total_emprestimos}x"""

            # Calcular banca operacional e apostas base
            banca_operacional = saldo - reserva_total
            aposta_base_ns6 = banca_operacional / 63 if banca_operacional > 0 else 0
            aposta_base_ns7 = banca_operacional / 127 if banca_operacional > 0 else 0

            msg += f"""

<b>🚀 Estrategia [7,7,6]:</b>
  Padrao: {padrao_str}
  Proximo: NS{ns_atual}
  Gatilhos s/T6: {gatilhos_desde_t6}
  Banca Op: R$ {banca_operacional:.2f}
  Aposta NS6: R$ {aposta_base_ns6:.2f} | NS7: R$ {aposta_base_ns7:.2f}"""

            if total_gatilhos > 0:
                pct_ns6 = (total_ns6 / total_gatilhos * 100)
                msg += f"""
  NS6: {total_ns6} ({pct_ns6:.0f}%) | NS7: {total_ns7}"""

        # Secao de perdas detalhadas
        total_loss_apostas = sum(loss_por_tentativa.values())
        if total_loss_apostas > 0:
            msg += f"""

<b>📉 Detalhes de Loss:</b>
  T1: {loss_por_tentativa[1]} | T2: {loss_por_tentativa[2]} | T3: {loss_por_tentativa[3]}
  T4: {loss_por_tentativa[4]} | T5: {loss_por_tentativa[5]} | T6: {loss_por_tentativa[6]}
  Total perdido: R$ {total_perdas:.2f}"""

            if busts:
                msg += f"""
  💥 Busts: {len(busts)}"""
                # Mostrar ultimo bust com sequência do gatilho
                ultimo_bust = busts[-1]
                gatilho_mults = ultimo_bust.get('gatilho_mults', [])
                gatilho_str = ",".join([f"{m:.2f}" for m in gatilho_mults]) if gatilho_mults else "?"
                msg += f"""
  Ultimo: {ultimo_bust['horario']} T{ultimo_bust['tentativa']} -R$ {ultimo_bust['valor']:.2f}
  Gatilho: [{gatilho_str}]"""

        msg += f"""

<b>📈 Estatisticas:</b>
  WIN: {wins} | LOSS: {losses}
  Rodadas: {rodadas}

<b>🕐 Sessao:</b>
  Inicio: {inicio}
  Ultimo: {db_stats.get('last_mult', '?')}x
"""
        return msg.strip()

    def queue_command(self, command, params=None):
        """Adiciona comando na fila para o bot principal executar"""
        cmd = {
            'command': command,
            'params': params,
            'timestamp': agora_str(),  # Brasilia
            'executed': False
        }

        # Ler fila existente
        commands = []
        try:
            if os.path.exists(COMMANDS_FILE):
                with open(COMMANDS_FILE, 'r') as f:
                    commands = json.load(f)
        except:
            pass

        # Adicionar novo comando
        commands.append(cmd)

        # Manter apenas comandos nao executados e recentes
        commands = [c for c in commands if not c.get('executed')][-10:]

        # Salvar
        with open(COMMANDS_FILE, 'w') as f:
            json.dump(commands, f, indent=2)

        return True

    def handle_message(self, message):
        """Processa uma mensagem recebida"""
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '').strip()
        user_id = message.get('from', {}).get('id')
        username = message.get('from', {}).get('username', 'unknown')

        # Salvar chat_id se ainda nao tiver
        if not self.chat_id:
            self.chat_id = chat_id
            self.config['chat_id'] = chat_id
            self.save_config()
            print(f"Chat ID salvo: {chat_id}")

        # Autorizar primeiro usuario automaticamente
        if not self.authorized_users:
            self.authorized_users.append(user_id)
            self.config['authorized_users'] = self.authorized_users
            self.save_config()
            print(f"Usuario autorizado: {username} ({user_id})")

        # Verificar autorizacao
        if user_id not in self.authorized_users:
            self.send_message("Acesso nao autorizado.", chat_id)
            return

        # Processar comandos
        if text.startswith('/'):
            self.process_command(text, chat_id)
        else:
            self.send_message("Use /help para ver comandos disponiveis.", chat_id)

    def process_command(self, text, chat_id):
        """Processa um comando"""
        parts = text.split()
        cmd = parts[0].lower().replace('/', '')
        args = parts[1:] if len(parts) > 1 else []

        if cmd == 'start' or cmd == 'help':
            msg = """
<b>🤖 MartingaleV2 - Dual Account</b>

<b>📊 Status:</b>
/dual - Status das 2 contas

<b>💰 Operacao Diaria:</b>
/agressiva [valor] - Atualiza conta agressiva
/conservadora [valor] - Atualiza conta conservadora
/calcular - Quanto redistribuir?
/reset_dia [agr] [cons] - Novo dia
/saque [valor] - Registrar saque

<b>🚀 Primeira vez:</b>
/iniciar [agr] [cons] - Ex: /iniciar 2000 2000

<b>🔄 Automatico:</b>
• Migracao NS9→NS10 ao atingir +5.78%
"""
            self.send_message(msg, chat_id)

        elif cmd == 'status' or cmd == 's':
            msg = self.format_status()
            self.send_message(msg, chat_id)

        elif cmd == 'saque':
            if not args:
                self.send_message("Uso: /saque [valor]\nEx: /saque 50", chat_id)
                return

            try:
                valor = float(args[0].replace(',', '.'))
                if valor <= 0:
                    self.send_message("Valor deve ser positivo!", chat_id)
                    return

                self.queue_command('saque', {'valor': valor})
                self.send_message(f"✅ Comando enviado: saque R$ {valor:.2f}\n\nAguarde o bot processar...", chat_id)
            except ValueError:
                self.send_message("Valor invalido!", chat_id)

        elif cmd == 'nivel' or cmd == 'n':
            if not args:
                self.send_message("Uso: /nivel [6-10]\nEx: /nivel 8", chat_id)
                return

            try:
                nivel = int(args[0])
                if nivel not in [6, 7, 8, 9, 10]:
                    self.send_message("Nivel deve ser 6, 7, 8, 9 ou 10!", chat_id)
                    return

                self.queue_command('nivel', {'nivel': nivel})
                self.send_message(f"✅ Comando enviado: mudar para NS{nivel}\n\nAguarde o bot processar...", chat_id)
            except ValueError:
                self.send_message("Nivel invalido!", chat_id)

        elif cmd == 'reiniciar' or cmd == 'restart':
            self.queue_command('reiniciar', {})
            msg = """🔄 <b>Reinício solicitado!</b>

O bot vai reiniciar no próximo momento seguro:
• Após multiplicador >= 2.0
• Fora de sessão de martingale
• Longe de gatilho potencial

Isso libera memória RAM sem perder o estado.
Aguarde a notificação de restart..."""
            self.send_message(msg, chat_id)

        elif cmd == 'db':
            stats = self.get_database_stats()
            state = self.get_session_state()

            msg = f"""
<b>📊 Banco de Dados</b>

Multiplicadores: {stats.get('total_rounds', 0)}
Ultimo: {stats.get('last_mult', '?')}x
Hora: {stats.get('last_time', '?')}

Sessao ativa: {'Sim' if state else 'Nao'}
"""
            self.send_message(msg, chat_id)

        elif cmd == 'apostas' or cmd == 'a':
            bets = self.get_session_bets(15)

            if not bets:
                self.send_message("Nenhuma aposta registrada na sessao atual.", chat_id)
                return

            # Contar wins/losses
            wins = sum(1 for b in bets if b['result'] == 'WIN')
            losses = len(bets) - wins

            msg = f"<b>🎲 Apostas da Sessao</b>\n\n"
            msg += f"Total: {len(bets)} | ✅ {wins} | ❌ {losses}\n"
            msg += "─" * 20 + "\n\n"

            for bet in reversed(bets):  # Mostrar em ordem cronologica
                emoji = "✅" if bet['result'] == 'WIN' else "❌"
                hora = bet['timestamp'].split(' ')[1][:5] if ' ' in bet['timestamp'] else '?'
                pl = bet['pl'] or 0
                pl_str = f"+{pl:.2f}" if pl >= 0 else f"{pl:.2f}"

                msg += f"{emoji} <b>{bet['tentativa']}</b> | {hora}\n"
                msg += f"   R${bet['valor']:.2f} → {bet['alvo']}x (real: {bet['mult_real']}x)\n"
                msg += f"   P/L: R$ {pl_str}\n\n"

            self.send_message(msg.strip(), chat_id)

        elif cmd == 'dual' or cmd == 'd':
            # Status completo das duas contas
            msg = self.format_dual_status()
            self.send_message(msg, chat_id)

        elif cmd == 'iniciar':
            # Iniciar sessao dual account com saldos separados
            if len(args) < 2:
                self.send_message("Uso: /iniciar [saldo_A] [saldo_B]\nEx: /iniciar 2000 2000", chat_id)
                return

            try:
                saldo_a = float(args[0].replace(',', '.'))
                saldo_b = float(args[1].replace(',', '.'))
                if saldo_a <= 0 or saldo_b <= 0:
                    self.send_message("Valores devem ser positivos!", chat_id)
                    return

                if DUAL_ACCOUNT_AVAILABLE:
                    manager = DualAccountManager()
                    sessao_id = manager.iniciar_sessao(saldo_a, saldo_b)
                    msg = f"""✅ <b>Sessao Dual Account iniciada!</b>

ID: {sessao_id}
Conta A (NS9): R$ {saldo_a:.2f}
Conta B (NS10): R$ {saldo_b:.2f}
Total: R$ {saldo_a + saldo_b:.2f}

Meta migracao: +{STOP_WIN_PCT:.1f}%
Use /dual para ver status."""
                    self.send_message(msg, chat_id)
                else:
                    self.send_message("Dual Account Manager nao disponivel!", chat_id)
            except ValueError:
                self.send_message("Valores invalidos!", chat_id)

        elif cmd == 'agressiva' or cmd == 'agr' or cmd == 'saldo_a' or cmd == 'sa':
            # Atualizar saldo conta AGRESSIVA (migração automática se atingir meta)
            if not args:
                self.send_message("Uso: /agressiva [valor]\nEx: /agressiva 2150.50", chat_id)
                return

            try:
                valor = float(args[0].replace(',', '.'))
                if DUAL_ACCOUNT_AVAILABLE:
                    manager = DualAccountManager()
                    migrou = manager.atualizar_saldo_a(valor)

                    if migrou:
                        # Migração automática aconteceu!
                        status = manager.get_status()
                        lucro_pct = status['intraday']['conta_a']['lucro_pct']
                        msg = f"""🔄 <b>MIGRACAO AUTOMATICA!</b>

AGRESSIVA atingiu +{lucro_pct:.1f}% e migrou para NS10.

Saldo atual: R$ {valor:.2f}

⚠️ <b>Acao:</b> Mude o bot da conta agressiva para NS10!

Amanha use /reset_dia para voltar NS9."""
                        self.send_message(msg, chat_id)
                    else:
                        # Mostrar progresso
                        status = manager.get_status()
                        a = status['intraday']['conta_a']
                        meta = status['config']['meta_migracao_pct']

                        if a['migrou']:
                            self.send_message(f"✅ AGRESSIVA (NS10): R$ {valor:.2f}", chat_id)
                        else:
                            progresso = (a['lucro_pct'] / meta * 100) if meta > 0 else 0
                            barra = self._barra_progresso(min(100, progresso))
                            self.send_message(f"✅ AGRESSIVA (NS9): R$ {valor:.2f}\nMeta: {barra} {a['lucro_pct']:.1f}%/{meta:.1f}%", chat_id)
                else:
                    self.send_message("Dual Account Manager nao disponivel!", chat_id)
            except ValueError:
                self.send_message("Valor invalido!", chat_id)

        elif cmd == 'conservadora' or cmd == 'cons' or cmd == 'saldo_b' or cmd == 'sb':
            # Atualizar saldo conta CONSERVADORA
            if not args:
                self.send_message("Uso: /conservadora [valor]\nEx: /conservadora 2080.00", chat_id)
                return

            try:
                valor = float(args[0].replace(',', '.'))
                if DUAL_ACCOUNT_AVAILABLE:
                    manager = DualAccountManager()
                    manager.atualizar_saldo_b(valor)
                    self.send_message(f"✅ CONSERVADORA (NS10): R$ {valor:.2f}", chat_id)
                else:
                    self.send_message("Dual Account Manager nao disponivel!", chat_id)
            except ValueError:
                self.send_message("Valor invalido!", chat_id)

        elif cmd == 'calcular' or cmd == 'calc':
            # Calcular redistribuicao necessaria
            if not DUAL_ACCOUNT_AVAILABLE:
                self.send_message("Dual Account Manager nao disponivel!", chat_id)
                return

            manager = DualAccountManager()
            result = manager.calcular_redistribuicao()

            if result.get('erro'):
                self.send_message(f"Erro: {result['erro']}", chat_id)
                return

            if result.get('equilibrado'):
                msg = f"""✅ <b>Contas ja equilibradas!</b>

Conta A: R$ {result['conta_a']:.2f}
Conta B: R$ {result['conta_b']:.2f}
Total: R$ {result['total']:.2f}"""
            else:
                msg = f"""📊 <b>Redistribuicao Necessaria</b>

<b>Antes:</b>
  Conta A: R$ {result['conta_a_antes']:.2f}
  Conta B: R$ {result['conta_b_antes']:.2f}

<b>Acao:</b>
  {result['acao']}

<b>Depois:</b>
  Conta A: R$ {result['conta_a_depois']:.2f}
  Conta B: R$ {result['conta_b_depois']:.2f}

Total: R$ {result['total']:.2f}

Apos fazer a transferencia, use:
/reset_dia {result['conta_a_depois']:.0f} {result['conta_b_depois']:.0f}"""

            self.send_message(msg, chat_id)

        elif cmd == 'migrar':
            # Marcar migracao NS9 → NS10
            if not DUAL_ACCOUNT_AVAILABLE:
                self.send_message("Dual Account Manager nao disponivel!", chat_id)
                return

            manager = DualAccountManager()
            status = manager.get_status()

            if not status.get('ativo'):
                self.send_message("Nenhuma sessao ativa!", chat_id)
                return

            if status['intraday']['conta_a']['migrou']:
                self.send_message(f"Conta A ja migrou hoje as {status['intraday']['conta_a']['hora_migracao']}", chat_id)
                return

            manager.marcar_migracao()
            msg = f"""🔄 <b>Migracao registrada!</b>

Conta A agora opera em NS10.
Lucro do dia: {status['intraday']['conta_a']['lucro_pct']:.1f}%

Lembre-se de mudar a configuracao no bot da Conta A para NS10!
Amanha use /reset_dia para voltar NS9."""
            self.send_message(msg, chat_id)

        elif cmd == 'reset_dia' or cmd == 'resetdia':
            # Resetar sessao intraday com novos saldos
            if len(args) < 2:
                self.send_message("Uso: /reset_dia [saldo_A] [saldo_B]\nEx: /reset_dia 2150 2150", chat_id)
                return

            try:
                saldo_a = float(args[0].replace(',', '.'))
                saldo_b = float(args[1].replace(',', '.'))

                if DUAL_ACCOUNT_AVAILABLE:
                    manager = DualAccountManager()
                    status_antes = manager.get_status()

                    if not status_antes.get('ativo'):
                        self.send_message("Nenhuma sessao ativa! Use /iniciar primeiro.", chat_id)
                        return

                    lucro_dia = status_antes['intraday']['lucro_total']
                    manager.reset_dia(saldo_a, saldo_b)

                    msg = f"""✅ <b>Novo dia iniciado!</b>

<b>Dia anterior:</b>
  Lucro total: R$ {lucro_dia:+.2f}

<b>Novo dia:</b>
  Conta A (NS9): R$ {saldo_a:.2f}
  Conta B (NS10): R$ {saldo_b:.2f}
  Total: R$ {saldo_a + saldo_b:.2f}

Conta A volta para NS9.
Boa sorte hoje!"""
                    self.send_message(msg, chat_id)
                else:
                    self.send_message("Dual Account Manager nao disponivel!", chat_id)
            except ValueError:
                self.send_message("Valores invalidos!", chat_id)

        else:
            self.send_message(f"Comando desconhecido: /{cmd}\nUse /help", chat_id)

    def format_dual_status(self):
        """Formata status do sistema dual account"""
        if not DUAL_ACCOUNT_AVAILABLE:
            return "Dual Account Manager nao disponivel."

        try:
            manager = DualAccountManager()
            status = manager.get_status()

            if not status.get('ativo'):
                return "Nenhuma sessao dual account ativa.\n\nUse /iniciar [valor] para comecar."

            p = status['principal']
            i = status['intraday']
            a = i['conta_a']
            b = i['conta_b']
            cfg = status['config']

            # Emoji de lucro
            emoji_total = "🟢" if p['lucro'] >= 0 else "🔴"
            emoji_dia = "🟢" if i['lucro_total'] >= 0 else "🔴"

            # Barra de progresso para migracao
            meta_pct = cfg['meta_migracao_pct']
            if not a['migrou']:
                progresso = min(100, (a['lucro_pct'] / meta_pct) * 100) if meta_pct > 0 else 0
                barra = self._barra_progresso(progresso)
                status_migracao = f"Meta: {barra} {a['lucro_pct']:.1f}%/{meta_pct:.1f}%"
            else:
                status_migracao = f"✅ Migrou as {a['hora_migracao']}"

            msg = f"""
<b>📊 DUAL ACCOUNT STATUS</b>

<b>💰 Sessao Principal:</b>
  Deposito: R$ {p['deposito']:.2f}
  Banca atual: R$ {p['banca_atual']:.2f}
  Pico: R$ {p['pico']:.2f}
  {emoji_total} Lucro: R$ {p['lucro']:+.2f} ({p['lucro_pct']:+.1f}%)
  Saques: R$ {p['saques']:.2f}

<b>📅 Hoje ({i['data']}):</b>
  {emoji_dia} Lucro dia: R$ {i['lucro_total']:+.2f}

<b>🔥 AGRESSIVA ({a['modo']}):</b>
  Inicio: R$ {a['inicio']:.2f}
  Atual: R$ {a['atual']:.2f}
  Lucro: R$ {a['lucro']:+.2f} ({a['lucro_pct']:+.1f}%)
  {status_migracao}

<b>🛡️ CONSERVADORA (NS10):</b>{' 🌐' if b.get('remoto') else ''}
  Inicio: R$ {b['inicio']:.2f}
  Atual: R$ {b['atual']:.2f}
  Lucro: R$ {b['lucro']:+.2f} ({b['lucro_pct']:+.1f}%)
  {('🟢 Online' if b.get('remoto_online') else '🔴 Offline') if b.get('remoto') else '📍 Local'}

<b>📈 Historico:</b>
  Dias: {p['dias']} | Migracoes: {p['migracoes']}
"""
            return msg.strip()

        except Exception as e:
            return f"Erro ao obter status dual: {e}"

    def _barra_progresso(self, pct):
        """Gera barra de progresso visual"""
        total = 10
        preenchido = int(pct / 10)
        vazio = total - preenchido
        return "▓" * preenchido + "░" * vazio

    def check_dual_account_migracao(self):
        """Verifica se houve migracao NS9→NS10 e notifica"""
        if not self.chat_id or not DUAL_ACCOUNT_AVAILABLE:
            return

        now = time.time()
        if now - self.last_migracao_check < 10:  # Verificar a cada 10 segundos
            return

        self.last_migracao_check = now

        try:
            manager = DualAccountManager()
            status = manager.get_status_completo()

            if not status.get('ativo'):
                return

            intraday = status['intraday']
            conta_a = intraday['conta_a']

            # Verificar se migrou e ainda nao notificou
            if conta_a['migrou'] and not self.migracao_notificada:
                self.migracao_notificada = True

                msg = f"""
🔄 <b>MIGRACAO NS9 → NS10</b>

Conta A atingiu meta de +{conta_a['meta_migracao_pct']:.1f}% e migrou!

<b>Status atual:</b>
  Lucro Conta A: R$ {conta_a['lucro']:+.2f} ({conta_a['lucro_pct']:+.1f}%)
  Hora: {conta_a['hora_migracao']}

Conta A agora opera em NS10 (seguro).
Amanha volta para NS9 automaticamente.
"""
                self.send_message(msg.strip())

            # Reset flag no inicio de novo dia
            if not conta_a['migrou']:
                self.migracao_notificada = False

        except Exception as e:
            pass  # Silenciar erros

    def send_auto_status(self):
        """Envia status automatico se passou o intervalo"""
        if not self.chat_id:
            return

        now = time.time()
        if now - self.last_status_time >= self.status_interval:
            self.last_status_time = now
            hora = horario()[:5]  # HH:MM em Brasilia
            msg = f"⏰ <b>Status Automatico ({hora})</b>\n\n" + self.format_status()
            self.send_message(msg)

    def check_lucro_milestone(self):
        """Verifica se atingiu novo marco de 10% de lucro e notifica"""
        if not self.chat_id:
            return

        now = time.time()
        if now - self.last_lucro_check < self.lucro_check_interval:
            return

        self.last_lucro_check = now

        state = self.get_session_state()
        if not state:
            return

        deposito = state.get('deposito_inicial', 0)
        if deposito <= 0:
            return

        saldo = state.get('saldo_atual', 0)
        saques = state.get('total_saques', 0)
        lucro = saldo - deposito + saques
        lucro_pct = (lucro / deposito * 100)

        # Calcular qual marco de 10% deveria estar
        # Ex: 15% -> marco 10, 25% -> marco 20, 35% -> marco 30
        if lucro_pct >= 10:
            marco_atual = int(lucro_pct // 10) * 10

            # Se passou de um marco que ainda nao notificou
            if marco_atual > self.last_lucro_notificado:
                self.last_lucro_notificado = marco_atual

                reserva = self.get_reserva_state()
                reserva_total = reserva.get('reserva_total', 0)
                divida = reserva.get('divida_reserva', 0)

                # Patrimonio = apenas saldo (reserva é virtual, já está contida no saldo)
                patrimonio = saldo

                msg = f"""
🎉 <b>MARCO {marco_atual}% ATINGIDO!</b>

<b>💰 Lucro acumulado: {lucro_pct:.1f}%</b>
  Deposito: R$ {deposito:.2f}
  Saldo: R$ {saldo:.2f}
  Lucro: R$ {lucro:+.2f}

<b>💎 Patrimonio Total:</b>
  Saldo: R$ {saldo:.2f}
  Reserva: R$ {reserva_total:.2f}"""

                if divida > 0:
                    msg += f"""
  Divida: -R$ {divida:.2f}"""

                msg += f"""
  <b>TOTAL: R$ {patrimonio:.2f}</b>

🚀 Estrategia [7,7,6] funcionando!
"""
                self.send_message(msg.strip())

        # Reset se lucro cair abaixo do ultimo marco
        elif lucro_pct < self.last_lucro_notificado - 5:
            # Dar margem de 5% para nao resetar em pequenas oscilacoes
            self.last_lucro_notificado = max(0, int(lucro_pct // 10) * 10)

    def run(self, silent=False):
        """Loop principal do bot"""
        self.running = True
        self.last_status_time = time.time()  # Iniciar contagem
        self.last_lucro_check = time.time()  # Iniciar contagem de lucro

        if not silent:
            print("="*50)
            print("TELEGRAM BOT - MartingaleV2 [7,7,6]")
            print("="*50)
            print(f"Bot iniciado!")
            print(f"Chat ID: {self.chat_id or 'Aguardando primeira mensagem...'}")
            print(f"Status automatico: a cada 2 horas")
            print(f"Notificacao de lucro: a cada 10%")
            print("Ctrl+C para parar")
            print("="*50)

        # Enviar mensagem de inicio se tiver chat_id
        if self.chat_id:
            msg = """🟢 <b>Bot Telegram conectado!</b>

🚀 <b>Estrategia [7,7,6] ativa</b>
📊 Status automatico: a cada 2h
🎉 Notificacao: a cada 10% de lucro

Use /status para ver agora."""
            self.send_message(msg)

        while self.running:
            try:
                updates = self.get_updates()

                for update in updates:
                    self.last_update_id = update.get('update_id', 0)

                    if 'message' in update:
                        self.handle_message(update['message'])

                # Verificar se deve enviar status automatico
                self.send_auto_status()

                # Verificar se atingiu marco de 10% de lucro
                self.check_lucro_milestone()

                # Verificar migracao dual account
                self.check_dual_account_migracao()

            except KeyboardInterrupt:
                if not silent:
                    print("\nParando bot...")
                self.running = False
                break
            except Exception as e:
                if not silent:
                    print(f"Erro no loop: {e}")
                time.sleep(5)

        if self.chat_id:
            self.send_message("🔴 <b>Bot Telegram desconectado.</b>")


def main():
    bot = TelegramBot()
    bot.run()


if __name__ == "__main__":
    main()
