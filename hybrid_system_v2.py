#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HYBRID SYSTEM V2 - Sistema refatorado com fluxo correto de martingale

Mudancas principais:
- Saldo lido apenas no INICIO e FIM do martingale
- WIN/LOSS baseado apenas em multiplicador vs alvo
- P/L calculado uma vez so, no final
- Sessao de martingale gerenciada como unidade unica
"""

import time
import threading
import json
import sys
import os

# Som: winsound no Windows, alternativa no Linux
if sys.platform == 'win32':
    import winsound
    def beep(freq, duration):
        beep(freq, duration)
else:
    def beep(freq, duration):
        # Tentar usar paplay ou speaker-test no Linux
        try:
            os.system(f'paplay /usr/share/sounds/freedesktop/stereo/bell.oga 2>/dev/null &')
        except:
            pass  # Ignorar se nao tiver som
from datetime import datetime
from typing import Dict, Optional, List
from colorama import Fore, init
from collections import deque

# Importar utilitario de timezone (Brasilia) - apenas para display
try:
    from timezone_util import agora_str, horario as horario_brasilia
    TZ_UTIL = True
except ImportError:
    TZ_UTIL = False
    def agora_str(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    def horario_brasilia(): return datetime.now().strftime('%H:%M:%S')

from vision_system import VisionSystem
from martingale_session import (
    MartingaleSession, SessionState,
    ModoOperacao, ConfiguracaoModo,
    NIVEIS_SEGURANCA, get_nivel_para_banca,
    EstadoSessao, salvar_estado_sessao,
    NIVEL_GAGO
)
from regime_detector import RegimeDetector
from reserva_manager import ReservaManager
from aceleracao_manager import AceleracaoManager

# Dual Account Manager (estrategia NS9+NS10)
try:
    from dual_account_manager import DualAccountManager, existe_sessao_dual_account
    DUAL_ACCOUNT_ENABLED = True
except ImportError:
    DUAL_ACCOUNT_ENABLED = False
    DualAccountManager = None

import uuid
import os

# Arquivo de comandos do Telegram
TELEGRAM_COMMANDS_FILE = os.path.join(os.path.dirname(__file__), 'telegram_commands.json')

# Flag de auto-restart para liberar memória
AUTO_RESTART_FLAG = os.path.join(os.path.dirname(__file__), 'auto_restart.flag')

# Arquivo de auditoria (log de decisoes para diagnostico)
AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), 'audit_log.jsonl')

# Intervalo para auto-restart (em segundos) - DESATIVADO
# Era 6 horas, agora desativado (1 ano = nunca vai acontecer)
AUTO_RESTART_INTERVAL = 365 * 24 * 60 * 60  # 1 ano
from autonomous_betting_v2 import AutonomousBettingV2
# UI Rich (nova interface elegante)
try:
    from hybrid_ui_rich import HybridUIRich as HybridUI
except ImportError:
    from hybrid_ui import HybridUI  # Fallback para UI antiga
from session_manager import SessionManager
from refresh_manager import RefreshManager

init(autoreset=True)


class RallyDetector:
    """Detecta padroes de rally baseado em frequencia de triggers"""

    # Baseline: intervalo medio entre triggers (minutos)
    BASELINE_INTERVALO = 51.0  # Calculado do historico de 63h

    # Thresholds como porcentagem do baseline
    THRESHOLDS = {
        'rally': 0.50,   # < 50% do baseline = < 26 min
        'quente': 0.75,  # < 75% do baseline = < 39 min
        'normal_max': 1.25,  # > 125% do baseline = > 64 min
    }

    def __init__(self):
        self.trigger_timestamps: List[datetime] = []
        self.max_history = 10  # Manter ultimos 10 triggers

    def registrar_trigger(self, timestamp: datetime = None):
        """Registra um novo trigger"""
        ts = timestamp or datetime.now()
        self.trigger_timestamps.append(ts)
        # Manter apenas os ultimos N
        if len(self.trigger_timestamps) > self.max_history:
            self.trigger_timestamps = self.trigger_timestamps[-self.max_history:]

    def get_ultimo_intervalo(self) -> float:
        """Retorna intervalo desde o ultimo trigger em minutos"""
        if not self.trigger_timestamps:
            return float('inf')
        ultimo = self.trigger_timestamps[-1]
        agora = datetime.now()
        return (agora - ultimo).total_seconds() / 60

    def get_media_intervalos(self, n: int = 3) -> float:
        """Retorna media dos ultimos N intervalos em minutos"""
        if len(self.trigger_timestamps) < 2:
            return float('inf')

        intervalos = []
        timestamps = self.trigger_timestamps[-min(n+1, len(self.trigger_timestamps)):]
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i-1]).total_seconds() / 60
            intervalos.append(delta)

        return sum(intervalos) / len(intervalos) if intervalos else float('inf')

    def get_estado(self) -> str:
        """Retorna estado atual: rally, quente, normal, lento"""
        intervalo = self.get_ultimo_intervalo()

        limite_rally = self.BASELINE_INTERVALO * self.THRESHOLDS['rally']
        limite_quente = self.BASELINE_INTERVALO * self.THRESHOLDS['quente']
        limite_lento = self.BASELINE_INTERVALO * self.THRESHOLDS['normal_max']

        if intervalo < limite_rally:
            return 'rally'
        elif intervalo < limite_quente:
            return 'quente'
        elif intervalo > limite_lento:
            return 'lento'
        else:
            return 'normal'

    def get_estado_icon(self) -> str:
        """Retorna icone do estado"""
        estado = self.get_estado()
        icons = {
            'rally': 'RALLY',
            'quente': 'QUENTE',
            'normal': 'NORMAL',
            'lento': 'LENTO'
        }
        return icons.get(estado, 'NORMAL')

    def to_dict(self) -> Dict:
        """Exporta para dicionario"""
        return {
            'estado': self.get_estado(),
            'estado_icon': self.get_estado_icon(),
            'ultimo_intervalo': self.get_ultimo_intervalo(),
            'media_3_intervalos': self.get_media_intervalos(3),
            'total_triggers': len(self.trigger_timestamps),
            'baseline': self.BASELINE_INTERVALO,
            'limite_rally': self.BASELINE_INTERVALO * self.THRESHOLDS['rally'],
            'limite_quente': self.BASELINE_INTERVALO * self.THRESHOLDS['quente'],
        }


class EstatisticasValidacao:
    """Rastreia estatisticas para validacao em tempo real"""

    # Valores esperados baseados nos 99k multiplicadores
    ESPERADO = {
        'resolveu_t1_t4': 95.6,
        'foi_t5': 4.4,
        't5_cenario_a': 64.0,
        't5_cenario_b': 16.0,
        't5_cenario_c': 20.0,
        't6_win': 80.0,
        't6_loss': 20.0,
        'sangrou_60': 0.18,
        'zerou_banca': 0.0,
    }

    def __init__(self):
        # Contadores de gatilhos
        self.gatilhos_total = 0
        self.resolveu_t1_t4 = 0
        self.foi_t5 = 0

        # T5 cenarios
        self.t5_cenario_a = 0  # >= 1.99x (ambos ganham)
        self.t5_cenario_b = 0  # 1.25x - 1.98x (so seguranca ganha)
        self.t5_cenario_c = 0  # < 1.25x (ambos perdem)

        # T6+ resultados
        self.t6_total = 0
        self.t6_win = 0
        self.t6_loss = 0

        # Piores cenarios
        self.sangrou_60 = 0
        self.zerou_banca = 0

    def registrar_win_t1_t4(self, tentativa: int):
        """Registra WIN em T1-T4"""
        self.gatilhos_total += 1
        self.resolveu_t1_t4 += 1

    def registrar_t5(self, cenario: str):
        """Registra resultado em T5"""
        self.gatilhos_total += 1
        self.foi_t5 += 1
        if cenario == 'A':
            self.t5_cenario_a += 1
        elif cenario == 'B':
            self.t5_cenario_b += 1
        elif cenario == 'C':
            self.t5_cenario_c += 1

    def registrar_t6_plus(self, ganhou: bool):
        """Registra resultado em T6+"""
        self.t6_total += 1
        if ganhou:
            self.t6_win += 1
        else:
            self.t6_loss += 1

    def registrar_sangrou(self):
        """Registra sangria de -60%"""
        self.sangrou_60 += 1

    def registrar_zerou(self):
        """Registra banca zerada"""
        self.zerou_banca += 1

    def get_porcentagem(self, campo: str) -> float:
        """Calcula porcentagem real"""
        if campo == 'resolveu_t1_t4':
            return (self.resolveu_t1_t4 / self.gatilhos_total * 100) if self.gatilhos_total > 0 else 0
        elif campo == 'foi_t5':
            return (self.foi_t5 / self.gatilhos_total * 100) if self.gatilhos_total > 0 else 0
        elif campo == 't5_cenario_a':
            return (self.t5_cenario_a / self.foi_t5 * 100) if self.foi_t5 > 0 else 0
        elif campo == 't5_cenario_b':
            return (self.t5_cenario_b / self.foi_t5 * 100) if self.foi_t5 > 0 else 0
        elif campo == 't5_cenario_c':
            return (self.t5_cenario_c / self.foi_t5 * 100) if self.foi_t5 > 0 else 0
        elif campo == 't6_win':
            return (self.t6_win / self.t6_total * 100) if self.t6_total > 0 else 0
        elif campo == 't6_loss':
            return (self.t6_loss / self.t6_total * 100) if self.t6_total > 0 else 0
        elif campo == 'sangrou_60':
            return (self.sangrou_60 / self.gatilhos_total * 100) if self.gatilhos_total > 0 else 0
        elif campo == 'zerou_banca':
            return (self.zerou_banca / self.gatilhos_total * 100) if self.gatilhos_total > 0 else 0
        return 0

    def get_amostra(self, campo: str) -> int:
        """Retorna tamanho da amostra para o campo"""
        if campo in ['resolveu_t1_t4', 'foi_t5', 'sangrou_60', 'zerou_banca']:
            return self.gatilhos_total
        elif campo.startswith('t5_'):
            return self.foi_t5
        elif campo.startswith('t6_'):
            return self.t6_total
        return 0

    def get_status(self, campo: str) -> str:
        """Retorna simbolo de status (check/warning/error)"""
        amostra = self.get_amostra(campo)
        if amostra < 10:
            return '?'  # Amostra pequena

        real = self.get_porcentagem(campo)
        esperado = self.ESPERADO.get(campo, 0)
        diferenca = abs(real - esperado)

        if diferenca <= 5:
            return 'ok'  # Dentro do esperado
        elif diferenca <= 10:
            return '?'  # Margem
        else:
            return 'X'  # Fora do esperado

    def to_dict(self) -> Dict:
        """Exporta estatisticas para dicionario"""
        return {
            'gatilhos_total': self.gatilhos_total,
            'resolveu_t1_t4': self.resolveu_t1_t4,
            'foi_t5': self.foi_t5,
            't5_cenario_a': self.t5_cenario_a,
            't5_cenario_b': self.t5_cenario_b,
            't5_cenario_c': self.t5_cenario_c,
            't6_total': self.t6_total,
            't6_win': self.t6_win,
            't6_loss': self.t6_loss,
            'sangrou_60': self.sangrou_60,
            'zerou_banca': self.zerou_banca,
            # Porcentagens calculadas
            'pct_resolveu_t1_t4': self.get_porcentagem('resolveu_t1_t4'),
            'pct_foi_t5': self.get_porcentagem('foi_t5'),
            'pct_t5_a': self.get_porcentagem('t5_cenario_a'),
            'pct_t5_b': self.get_porcentagem('t5_cenario_b'),
            'pct_t5_c': self.get_porcentagem('t5_cenario_c'),
            'pct_t6_win': self.get_porcentagem('t6_win'),
            'pct_t6_loss': self.get_porcentagem('t6_loss'),
            # Status
            'status_t1_t4': self.get_status('resolveu_t1_t4'),
            'status_t5': self.get_status('foi_t5'),
            'status_t5_a': self.get_status('t5_cenario_a'),
            'status_t5_b': self.get_status('t5_cenario_b'),
            'status_t5_c': self.get_status('t5_cenario_c'),
            'status_t6_win': self.get_status('t6_win'),
            # Esperado
            'esperado': self.ESPERADO,
        }


class HybridSystemV2:
    """Sistema Hibrido V2 - Fluxo de martingale corrigido"""

    def __init__(self, config_path='config.json', selected_profile: str = None,
                 silent_mode: bool = True, config_modo: ConfiguracaoModo = None,
                 estado_anterior: EstadoSessao = None):
        self.config_path = config_path
        self.config = self.load_config()
        self.silent_mode = silent_mode  # Quando True, suprime todos os prints

        # Configuracao de modo de operacao
        self.config_modo = config_modo or ConfiguracaoModo()

        # Estado da sessao para persistencia
        self.estado_anterior = estado_anterior
        self.sessao_id = estado_anterior.sessao_id if estado_anterior else str(uuid.uuid4())[:8]

        self._log(f"\n{Fore.CYAN}{'='*60}")
        self._log(f"{Fore.CYAN}       SISTEMA MARTINGALE V2")
        self._log(f"{Fore.CYAN}       {NIVEIS_SEGURANCA[self.config_modo.nivel_inicial]['nome']} | {self.config_modo.modo.value.upper()}")
        self._log(f"{Fore.CYAN}{'='*60}\n")

        # ===== SELECAO DE PERFIL =====
        if selected_profile and selected_profile in self.config.get('profiles', {}):
            self.selected_profile = selected_profile
            self.configure_vision_areas(selected_profile)
            self._log(f"{Fore.GREEN}Perfil: {selected_profile}")
        else:
            self.selected_profile = self.select_machine_profile()

        # ===== MODULOS PRINCIPAIS =====
        self.vision = VisionSystem(config_path)
        self.martingale = MartingaleSession()  # NOVO: Gerenciador de sessao

        # Configurar modo de operacao
        if self.config_modo.modo == ModoOperacao.GAGO:
            # Modo GAGO: usar divisor 7 e progressao 1-2-4-1-2-4
            self.martingale.set_modo_gago(True)
            self._log(f"{Fore.MAGENTA}Modo GAGO ativo: Divisor 7, Progressao 1-2-4-1-2-4")
        elif self.config_modo.modo == ModoOperacao.NS7_PURO:
            # Modo NS7_PURO: NS7 sempre, defesa 1.10x, sem reserva
            self.martingale.set_nivel_seguranca(7)
            self.martingale.alvo_defesa = self.config_modo.alvo_defesa  # 1.10x
            self._log(f"{Fore.MAGENTA}Modo NS7 PURO: Defesa {self.config_modo.alvo_defesa}x, Banca integral")
        elif self.config_modo.modo == ModoOperacao.G6_NS9:
            # Modo G6+NS9: Agressivo, protecao 15, 2 busts/ano
            self.martingale.set_nivel_seguranca(9)
            self.martingale.alvo_defesa = 1.99  # Sempre 1.99x
            self._log(f"{Fore.YELLOW}Modo G6+NS9 AGRESSIVO: Divisor 511, Protecao 15, Alvo 1.99x")
        elif self.config_modo.modo == ModoOperacao.G6_NS10:
            # Modo G6+NS10: Conservador, protecao 16, 0 busts
            self.martingale.set_nivel_seguranca(10)
            self.martingale.alvo_defesa = 1.99  # Sempre 1.99x
            self._log(f"{Fore.GREEN}Modo G6+NS10 CONSERVADOR: Divisor 1023, Protecao 16, Alvo 1.99x")
        else:
            # Modos normais: usar nivel de seguranca
            self.martingale.set_nivel_seguranca(self.config_modo.nivel_inicial)
            self.martingale.alvo_defesa = self.config_modo.alvo_defesa  # 1.25x default
            self._log(f"{Fore.GREEN}Nivel de Seguranca: {NIVEIS_SEGURANCA[self.config_modo.nivel_inicial]['nome']}")

        # ===== COMPONENTES =====
        self.regime_detector = RegimeDetector()
        self.reserva_manager = ReservaManager()  # Gerenciador de reserva de lucros
        self.aceleracao_manager = AceleracaoManager()  # Estrategia [7,7,6]

        # Desativar aceleracao [7,7,6] para modos que nao usam
        if self.config_modo.modo in [ModoOperacao.NS7_PURO, ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]:
            self.aceleracao_manager.ativar(False)
            modo_nome = self.config_modo.modo.value.upper().replace('_', '+')
            self._log(f"{Fore.YELLOW}Aceleracao [7,7,6] DESATIVADA ({modo_nome})")
        # Carregar estado da aceleracao se existir (para modos [7,7,6])
        elif self.aceleracao_manager.carregar():
            self._log(f"{Fore.CYAN}Aceleracao [7,7,6] carregada | Padrao: {self.aceleracao_manager.get_posicao_padrao()}")
        else:
            self._log(f"{Fore.CYAN}Aceleracao [7,7,6] iniciada | Padrao: 7-7-6")

        self.bet_executor = AutonomousBettingV2(self.config, verbose=not silent_mode)
        self.bet_executor.set_profile(self.selected_profile)
        self.bet_executor.set_balance_callback(self.capture_balance)  # Para verificacao

        # ===== BANCO DE DADOS =====
        # Passar session_id existente se retomando sessão
        existing_session_id = None
        if self.estado_anterior and self.estado_anterior.sessao_id:
            # Converter formato curto para formato do banco
            existing_session_id = f"session_{self.estado_anterior.inicio_timestamp.replace('-', '').replace(' ', '_').replace(':', '')}_{self.estado_anterior.sessao_id}"
        self.session = SessionManager(existing_session_id=existing_session_id)

        # ===== AUTO-REFRESH =====
        # Carregar configuração de máquina (browser, etc)
        browser = 'firefox'  # Padrão
        machine_config_path = os.path.join(os.path.dirname(__file__), 'machine_config.json')
        if os.path.exists(machine_config_path):
            try:
                with open(machine_config_path, 'r') as f:
                    machine_config = json.load(f)
                    browser = machine_config.get('browser', 'firefox')
                    self._log(f"{Fore.CYAN}Navegador configurado: {browser}")
            except Exception as e:
                self._log(f"{Fore.YELLOW}Aviso ao ler machine_config.json: {e}")
        self.refresh_manager = RefreshManager(browser=browser)
        self.setup_refresh_callbacks()

        # ===== ESTADO DO SISTEMA =====
        self.running = False
        self.session_start = datetime.now()
        self.saldo_atual = 0.0
        self.deposito_inicial = None
        self.total_rodadas = 0

        # ===== BUFFER E THREADING =====
        self.frame_buffer = deque(maxlen=10)
        self.buffer_lock = threading.Lock()
        self.last_bet_detection_time = 0

        # ===== HISTORICO =====
        self.multiplier_history = deque(maxlen=1000)  # Limitado para evitar memory leak
        self.historico_apostas = []  # Lista de apostas para a interface

        # ===== ESTATISTICAS =====
        self.stats = {
            'capturas_ok': 0,
            'capturas_erro': 0,
            'sessoes_win': 0,
            'sessoes_loss': 0,
            'lucro_total': 0.0
        }

        # ===== VALIDACAO ESTATISTICA =====
        self.estatisticas_validacao = EstatisticasValidacao()

        # ===== DETECTOR DE RALLY =====
        self.rally_detector = RallyDetector()

        # ===== CONTROLE DE APOSTAS =====
        self.last_bet_id = None
        self.last_bet_ids = {}  # Armazena info de TODOS os slots

        # ===== AUTO-RESTART PARA LIBERAR MEMÓRIA =====
        self.auto_restart_timestamp = time.time()  # Quando iniciou
        self.auto_restart_pending = False  # Se tem reinício pendente
        self.ultimo_multiplicador = 0.0  # Para verificar momento seguro

        # ===== CONTROLE DE REFRESH =====
        self.waiting_first_mult_after_refresh = False  # Aguardando confirmação pós-refresh

        # ===== INTERFACE =====
        self.ui = HybridUI(self)

        # ===== CAPTURA INICIAL DO SALDO =====
        self._log(f"{Fore.YELLOW}Capturando saldo inicial da tela...")
        time.sleep(2)

        saldo_capturado = self.capture_balance()
        if saldo_capturado and saldo_capturado > 0:
            self.saldo_atual = saldo_capturado

            # Restaurar sessao anterior se existir
            if self.estado_anterior:
                self.restaurar_estado()
                # Validar se saldo atual bate aproximadamente com o esperado
                diff = abs(saldo_capturado - self.estado_anterior.saldo_atual)
                if diff > 50:  # Diferenca maior que R$50
                    print(f"{Fore.YELLOW}ATENCAO: Saldo atual (R$ {saldo_capturado:.2f}) difere do esperado (R$ {self.estado_anterior.saldo_atual:.2f})")
                    print(f"{Fore.YELLOW}Usando saldo atual da tela.")
            else:
                self.deposito_inicial = saldo_capturado

            self._log(f"{Fore.GREEN}Saldo atual: R$ {saldo_capturado:.2f}")
        else:
            # Erro critico - sempre mostrar
            print(f"{Fore.RED}ERRO: Nao foi possivel capturar saldo!")
            print(f"{Fore.YELLOW}Verifique se o jogo esta aberto e visivel.")
            exit(1)

        # Inicializar variaveis de controle
        self.total_saques = getattr(self, 'total_saques', 0.0)
        self.total_depositos = getattr(self, 'total_depositos', 0.0)

        # ===== INICIALIZAR RESERVA DE LUCROS =====
        # NS7_PURO, G6_NS9, G6_NS10: sem reserva - usar 100% da banca
        modos_sem_reserva = [ModoOperacao.NS7_PURO, ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]
        if self.config_modo.modo in modos_sem_reserva:
            modo_nome = self.config_modo.modo.value.upper().replace('_', '+')
            self._log(f"{Fore.MAGENTA}{modo_nome}: Reserva DESATIVADA - 100% banca operacional")
            # Inicializar com reserva zerada
            self.reserva_manager.inicializar(self.saldo_atual)
            self.reserva_manager.estado.reserva_total = 0.0
            self.reserva_manager.salvar()
        elif self.estado_anterior:
            # Continuar sessao anterior - carregar reserva
            if self.reserva_manager.carregar():
                self._log(f"{Fore.GREEN}Reserva restaurada!")
                self._log(f"{Fore.MAGENTA}  Reserva: R$ {self.reserva_manager.get_reserva():.2f}")
                self._log(f"{Fore.MAGENTA}  Metas batidas: {self.reserva_manager.estado.total_metas_batidas}x")
            else:
                # Arquivo nao existe, inicializar
                self.reserva_manager.inicializar(self.saldo_atual)
                self._log(f"{Fore.GREEN}Reserva inicializada: R$ {self.saldo_atual:.2f}")
        else:
            # Nova sessao - inicializar reserva do zero
            self.reserva_manager.inicializar(self.saldo_atual)
            self._log(f"{Fore.GREEN}Nova sessao - Reserva zerada, banca base: R$ {self.saldo_atual:.2f}")

        # Modos sem reserva: nao mostrar meta
        if self.config_modo.modo not in modos_sem_reserva:
            self._log(f"{Fore.CYAN}Meta 10%: R$ {self.reserva_manager.get_meta_valor():.2f}")

        # Salvar estado inicial
        self.salvar_estado()

        self._log(f"\n{Fore.GREEN}Sistema pronto!")
        self._log(f"{Fore.WHITE}Pressione Ctrl+C para parar\n")

    def _log(self, msg: str, force: bool = False):
        """Print condicional - so exibe se silent_mode=False ou force=True"""
        if not self.silent_mode or force:
            print(msg)

    def _audit(self, evento: str, dados: Dict):
        """
        Registra evento de auditoria em arquivo JSONL (uma linha por evento).
        Leve e auditavel - nao carrega arquivo na memoria.
        """
        try:
            registro = {
                'timestamp': agora_str(),  # Brasilia
                'evento': evento,
                **dados
            }
            with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(registro, ensure_ascii=False) + '\n')
        except Exception as e:
            pass  # Silencioso - auditoria nao pode travar o bot

    def _som_trigger(self):
        """Som de notificacao quando gatilho e atingido - beep agudo curto"""
        try:
            threading.Thread(target=lambda: beep(1500, 200), daemon=True).start()
        except:
            pass

    def _som_win(self):
        """Som de notificacao quando aposta ganha - beep grave longo"""
        try:
            threading.Thread(target=lambda: beep(800, 400), daemon=True).start()
        except:
            pass

    def _telegram_enabled(self) -> bool:
        """Verifica se Telegram está habilitado nesta máquina"""
        try:
            config_file = os.path.join(os.path.dirname(__file__), 'telegram_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    tg_config = json.load(f)
                return tg_config.get('enabled', True) and tg_config.get('token')
            return False
        except:
            return False

    def _enviar_confirmacao_refresh(self, multiplicador: float):
        """Envia confirmação via Telegram que o bot voltou após refresh"""
        if not self._telegram_enabled():
            return
        try:
            import requests
            config_file = os.path.join(os.path.dirname(__file__), 'telegram_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    tg_config = json.load(f)
                token = tg_config.get('token')
                chat_id = tg_config.get('chat_id')
                if token and chat_id:
                    hora = horario_brasilia() if TZ_UTIL else datetime.now().strftime('%H:%M:%S')
                    msg = f"✅ <b>REFRESH OK - BOT OPERANTE</b>\n\n"
                    msg += f"⏰ Horário: {hora}\n"
                    msg += f"🎯 Primeiro multiplicador: {multiplicador:.2f}x\n"
                    msg += f"💰 Saldo: R$ {self.saldo_atual:.2f}"

                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url, data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
                    self._log(f"{Fore.GREEN}Confirmação pós-refresh enviada via Telegram")
        except Exception as e:
            self._log(f"{Fore.YELLOW}Aviso: Não foi possível enviar confirmação Telegram: {e}")

    def load_config(self) -> Dict:
        """Carrega configuracao"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Erro ao carregar config: {e}")  # Erro critico
            return {}

    def setup_refresh_callbacks(self):
        """Configura callbacks do refresh manager"""
        def on_refresh(event):
            self._log(f"{Fore.YELLOW}Auto-refresh executado: {event.reason}")
            # Salvar no banco de dados
            try:
                time_since = self.refresh_manager.get_time_since_last_explosion()
                self.session.log_refresh_event(
                    reason=event.reason,
                    time_since_last_explosion=time_since,
                    manual=event.manual,
                    success=event.success
                )
                # Salvar também em arquivo de log
                import os
                os.makedirs("logs", exist_ok=True)
                with open("logs/refresh_log.txt", "a", encoding="utf-8") as f:
                    ts = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{ts} | {event.reason} | manual={event.manual} | success={event.success}\n")
            except Exception as e:
                self._log(f"{Fore.RED}Erro ao logar refresh: {e}")

            # Notificar via Telegram (se habilitado)
            if self._telegram_enabled():
                try:
                    import requests
                    config_file = os.path.join(os.path.dirname(__file__), 'telegram_config.json')
                    if os.path.exists(config_file):
                        with open(config_file, 'r') as f:
                            tg_config = json.load(f)
                        token = tg_config.get('token')
                        chat_id = tg_config.get('chat_id')
                        if token and chat_id:
                            hora = event.timestamp.strftime("%H:%M")
                            msg = f"🔄 <b>REFRESH EXECUTADO</b>\n\n"
                            msg += f"⏰ Horário: {hora}\n"
                            msg += f"📋 Motivo: {event.reason}\n"
                            msg += f"💰 Saldo: R$ {self.saldo_atual:.2f}\n"
                            msg += f"✅ Sucesso: {'Sim' if event.success else 'Não'}"

                            url = f"https://api.telegram.org/bot{token}/sendMessage"
                            requests.post(url, data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
                except Exception as e:
                    self._log(f"{Fore.YELLOW}Aviso: Não foi possível enviar Telegram: {e}")

            # Ativar flag para enviar confirmação após primeiro multiplicador
            self.waiting_first_mult_after_refresh = True

            # Reset da sessao de martingale para evitar estado inconsistente
            if self.martingale.state == SessionState.EM_MARTINGALE:
                self._log(f"{Fore.RED}ATENCAO: Refresh durante martingale! Resetando sessao.")
            self.martingale.reset()

        def on_anomaly(time_since):
            self._log(f"{Fore.RED}Anomalia: {time_since:.0f}s sem explosoes")

        def check_balance_for_refresh():
            """Leitura de saldo APENAS para detectar página travada - NÃO atualiza saldo do sistema"""
            try:
                profile_config = self.config.get('profiles', {}).get(self.selected_profile, {})
                balance_area = profile_config.get('balance_area')
                if balance_area:
                    return self.vision.get_balance(balance_area)
            except:
                pass
            return None

        self.refresh_manager.set_refresh_callback(on_refresh)
        self.refresh_manager.set_anomaly_callback(on_anomaly)
        self.refresh_manager.set_balance_check_callback(check_balance_for_refresh)

    def select_machine_profile(self) -> str:
        """Selecao de perfil de maquina"""
        profiles = list(self.config.get('profiles', {}).keys())

        if not profiles:
            print(f"{Fore.RED}Nenhum perfil encontrado!")  # Erro critico
            exit(1)

        # Menu de selecao sempre aparece
        print(f"{Fore.CYAN}SELECAO DE PERFIL")
        print(f"{Fore.WHITE}{'='*40}")

        for i, profile in enumerate(profiles, 1):
            print(f"  {i}. {profile}")

        while True:
            try:
                choice = input(f"\n{Fore.CYAN}Escolha (1-{len(profiles)}): ")
                profile_idx = int(choice) - 1

                if 0 <= profile_idx < len(profiles):
                    selected = profiles[profile_idx]
                    print(f"\n{Fore.GREEN}Perfil: {selected}")
                    self.configure_vision_areas(selected)
                    return selected
                else:
                    print(f"{Fore.RED}Opcao invalida")

            except ValueError:
                print(f"{Fore.RED}Digite um numero")
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Cancelado")
                exit(0)

    def configure_vision_areas(self, profile_name: str):
        """Configura areas de captura"""
        profile_data = self.config['profiles'][profile_name]
        areas = {}

        if 'multiplier_area' in profile_data:
            areas['multiplier_area'] = profile_data['multiplier_area']
        if 'balance_area' in profile_data:
            areas['balance_area'] = profile_data['balance_area']

        self.config['areas'] = areas

    def capture_balance(self) -> Optional[float]:
        """Captura saldo da tela"""
        try:
            profile_config = self.config.get('profiles', {}).get(self.selected_profile, {})
            balance_area = profile_config.get('balance_area')

            if balance_area:
                return self.vision.get_balance(balance_area)
        except Exception as e:
            self._log(f"{Fore.RED}Erro ao capturar saldo: {e}")

        return None

    def capture_multipliers_continuously(self):
        """Thread de captura continua de multiplicadores"""
        while self.running:
            try:
                profile_config = self.config.get('profiles', {}).get(self.selected_profile, {})
                multiplier_area = profile_config.get('multiplier_area')

                if multiplier_area:
                    multiplier = self.vision.get_multiplier(multiplier_area)

                    if multiplier and multiplier > 0:
                        with self.buffer_lock:
                            self.frame_buffer.append({
                                'timestamp': time.time(),
                                'value': multiplier
                            })

                time.sleep(0.05)

            except Exception:
                time.sleep(0.1)

    def detect_bet_and_process(self):
        """Thread de deteccao de BET e processamento"""
        while self.running:
            try:
                profile_config = self.config.get('profiles', {}).get(self.selected_profile, {})
                bet_area = profile_config.get('bet_area')

                if not bet_area:
                    time.sleep(0.1)
                    continue

                bet_detected = self.vision.detect_bet_text(bet_area)

                if bet_detected:
                    current_time = time.time()

                    # Cooldown de 8 segundos
                    if current_time - self.last_bet_detection_time < 8.0:
                        time.sleep(0.1)
                        continue

                    self.last_bet_detection_time = current_time

                    # Buscar valor da explosao
                    explosion_value = self.get_explosion_from_buffer()

                    if explosion_value:
                        # Processar explosao (cooldown de 8s ja previne duplicacao)
                        self.process_explosion(explosion_value)
                        self.stats['capturas_ok'] += 1

                        # Limpar buffer apos processar para evitar dados antigos
                        with self.buffer_lock:
                            self.frame_buffer.clear()
                    else:
                        self.stats['capturas_erro'] += 1

                time.sleep(0.05)

            except Exception as e:
                self.stats['capturas_erro'] += 1
                time.sleep(0.1)

    def get_explosion_from_buffer(self) -> Optional[float]:
        """Obtem valor da explosao do buffer - retorna o MAIS RECENTE"""
        with self.buffer_lock:
            buffer_copy = list(self.frame_buffer)

        # Iterar do mais recente para o mais antigo
        for frame in reversed(buffer_copy):
            value = frame.get('value')
            if value and 0 < value <= 500.0:
                return value

        return None

    def process_explosion(self, multiplicador: float):
        """
        FLUXO PRINCIPAL - Processa uma explosao detectada.

        Este eh o coracao do sistema. O fluxo eh:
        1. Registrar multiplicador
        2. Passar para o MartingaleSession processar
        3. Se precisar ler saldo (inicio ou fim), ler
        4. Se precisar apostar, apostar
        5. Se finalizou, registrar resultado
        """
        self.total_rodadas += 1
        self.multiplier_history.append(multiplicador)
        self.ultimo_multiplicador = multiplicador

        # ===== VERIFICAR AUTO-RESTART =====
        self._verificar_auto_restart(multiplicador)

        # ===== ALIMENTAR REGIME DETECTOR (sempre, para monitorar) =====
        self.regime_detector.adicionar_multiplicador(multiplicador)

        # Verificar comandos do Telegram
        self.processar_comandos_telegram()

        # Atualizar refresh manager
        self.refresh_manager.update_explosion_time()

        # ===== CONFIRMAÇÃO PÓS-REFRESH VIA TELEGRAM =====
        if self.waiting_first_mult_after_refresh:
            self.waiting_first_mult_after_refresh = False  # Reset flag
            self._enviar_confirmacao_refresh(multiplicador)

        # Verificar restart preventivo do Firefox (6h) - só se não está em martingale
        em_martingale = self.martingale.state == SessionState.EM_MARTINGALE
        if self.refresh_manager.should_do_preventive_restart(multiplicador, em_martingale):
            horas = self.refresh_manager.get_time_since_last_restart() / 3600
            self._log(f"{Fore.CYAN}🔥 Restart Firefox (RAM) após {horas:.1f}h")
            self.refresh_manager.execute_firefox_restart(f"Preventivo {horas:.1f}h (RAM)")
            return  # Sair para não processar duas vezes após restart

        # Salvar multiplicador no banco
        self.session.save_multiplier(
            multiplier=multiplicador,
            regime="MARTINGALE_V2",
            score=None,
            capture_quality="OK"
        )

        # ===== PROCESSAR COM MARTINGALE SESSION =====
        estava_em_martingale = self.martingale.state == SessionState.EM_MARTINGALE
        tentativa_antes = self.martingale.tentativa_atual

        # Verificar se slot 2 foi executado (importante para T5 com 2 slots)
        slot2_executado = True
        if hasattr(self, 'last_bet_ids') and self.last_bet_ids:
            # Se tem slot 2 configurado, verificar se foi executado
            if 2 in self.last_bet_ids:
                slot2_executado = self.last_bet_ids[2].get('executado', False)
            elif estava_em_martingale and tentativa_antes == 5:
                # T5 deveria ter 2 slots, mas slot 2 nao esta registrado = nao entrou!
                slot2_executado = False
                print(f"{Fore.RED}>>> ALERTA: Slot 2 NAO foi executado! Tratando como Cenario C")

        resultado = self.martingale.processar_multiplicador(multiplicador, slot2_executado)

        # ===== ATUALIZAR RESULTADO DA APOSTA NO BANCO (TODOS OS SLOTS) =====
        if estava_em_martingale and hasattr(self, 'last_bet_ids') and self.last_bet_ids:
            profit_loss_total = 0

            for slot_id, slot_info in self.last_bet_ids.items():
                if not slot_info.get('executado'):
                    continue

                bet_id = slot_info['bet_id']
                valor = slot_info['valor']
                alvo = slot_info['alvo']

                ganhou = multiplicador >= alvo

                if ganhou:
                    profit_loss = valor * (alvo - 1)
                else:
                    profit_loss = -valor

                profit_loss_total += profit_loss

                # Atualizar no banco
                self.session.update_bet_result(
                    bet_id=bet_id,
                    actual_multiplier=multiplicador,
                    result="WIN" if ganhou else "LOSS",
                    profit_loss=profit_loss,
                    working_balance_after=self.saldo_atual + profit_loss_total
                )

                print(f"{Fore.CYAN}[DB] Slot {slot_id}: {('WIN' if ganhou else 'LOSS')} | P/L: R$ {profit_loss:+.2f}")

            # Limpar após processar
            self.last_bet_ids = {}

        # Log do estado atual
        estado_str = f"[{self.martingale.state.value}]"
        if self.martingale.state == SessionState.AGUARDANDO_GATILHO:
            estado_str += f" Baixos: {self.martingale.sequencia_baixos}/{self.martingale.GATILHO}"
        elif self.martingale.state == SessionState.EM_MARTINGALE:
            estado_str += f" T{self.martingale.tentativa_atual}/{self.martingale.MAX_TENTATIVAS}"

        self._log(f"{Fore.CYAN}Explosao: {multiplicador:.2f}x {estado_str}")

        # ===== LER SALDO SE NECESSARIO (INICIO) =====
        if resultado.get('precisa_ler_saldo_inicio'):
            print(f"[DEBUG TRIGGER] mult={multiplicador:.2f} seq={self.martingale.sequencia_baixos} GATILHO={self.martingale.GATILHO} -> TRIGGER! Som tocando agora")
            self._som_trigger()  # Som de notificacao: gatilho atingido!

            # ===== VERIFICAR GATILHO ANOMALO =====
            qtd_mults = len(self.martingale.multiplicadores_gatilho)
            if qtd_mults != 6:
                self._alertar_gatilho_anomalo(qtd_mults, self.martingale.multiplicadores_gatilho)
                # ABORTAR: Voltar para AGUARDANDO mas MANTER a contagem
                self._log(f"{Fore.RED}GATILHO ABORTADO! Aguardando mais {6 - qtd_mults} baixo(s)...")
                # Reverter estado sem zerar contador
                self.martingale.state = SessionState.AGUARDANDO_GATILHO
                self.martingale.tentativa_atual = 0
                self.martingale.tentativas = []
                # NÃO zera sequencia_baixos nem multiplicadores_gatilho
                return  # Espera próximo multiplicador completar o gatilho

            # ===== ESTRATEGIA [7,7,6] - DEFINIR NS ANTES DO GATILHO =====
            if self.config_modo.modo != ModoOperacao.GAGO and self.aceleracao_manager.is_ativo():
                proximo_ns = self.aceleracao_manager.proximo_ns()
                self.martingale.set_nivel_seguranca(proximo_ns)
                posicao_padrao = self.aceleracao_manager.get_posicao_padrao()
                self._log(f"{Fore.CYAN}[7,7,6] NS{proximo_ns} | Padrao: {posicao_padrao}")

            saldo = self.capture_balance()

            if saldo and saldo > 0:
                self.saldo_atual = saldo

                # NS7_PURO, G6_NS9, G6_NS10: usar 100% do saldo (sem reserva)
                if self.config_modo.modo in [ModoOperacao.NS7_PURO, ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]:
                    reserva = 0.0
                    banca_operacional = saldo
                    self.martingale.definir_saldo_inicio(banca_operacional)
                    modo_nome = self.config_modo.modo.value.upper().replace('_', '+')
                    self._log(f"{Fore.MAGENTA}{modo_nome} | Banca: R$ {saldo:.2f} | Aposta base: R$ {self.martingale.aposta_base:.2f}")
                else:
                    # CORRECAO: Usar banca operacional (saldo - reserva) para calcular apostas
                    reserva = self.reserva_manager.get_reserva()

                    # NOVO: Se reserva = 0 (inicio fresco), inicializar com 50% do saldo
                    # Isso permite manter metade como reserva fisica na plataforma
                    if reserva <= 0:
                        reserva = saldo / 2  # 50% vira reserva
                        banca_base = saldo / 2  # 50% vira banca operacional
                        self.reserva_manager.estado.reserva_total = reserva
                        self.reserva_manager.estado.banca_base = banca_base
                        self.reserva_manager.salvar()
                        self._log(f"{Fore.YELLOW}[INICIO] Reserva inicializada: 50% do saldo = R$ {reserva:.2f}")

                    banca_operacional = saldo - reserva
                    self.martingale.definir_saldo_inicio(banca_operacional)
                    self._log(f"{Fore.GREEN}Saldo total: R$ {saldo:.2f} | Reserva: R$ {reserva:.2f} | Banca op: R$ {banca_operacional:.2f}")
                    self._log(f"{Fore.GREEN}Aposta base calculada: R$ {self.martingale.aposta_base:.2f} ({NIVEIS_SEGURANCA[self.martingale.nivel_seguranca]['nome']})")

                # AUDITORIA: Inicio do gatilho
                self._audit('GATILHO_INICIO', {
                    'saldo_total': saldo,
                    'reserva': reserva,
                    'banca_operacional': banca_operacional,
                    'divida': self.reserva_manager.estado.divida_reserva,
                    'aposta_base_ns6': banca_operacional / 63,
                    'aposta_base_ns7': banca_operacional / 127,
                    'nivel_seguranca': self.martingale.nivel_seguranca,
                    'multiplicadores_gatilho': list(self.martingale.multiplicadores_gatilho),
                    'gatilhos_desde_t6': self.aceleracao_manager.estado.gatilhos_desde_t6,
                    'padrao_posicao': self.aceleracao_manager.get_posicao_padrao()
                })
            else:
                self._log(f"{Fore.RED}ERRO: Falha ao ler saldo! Abortando martingale.")
                self.martingale.reset()
                return

        # ===== EXECUTAR ACAO =====
        if resultado['acao'] == 'apostar':
            self.executar_aposta()

        elif resultado['acao'] == 'finalizar':
            # ===== LER SALDO (FIM) =====
            if resultado.get('precisa_ler_saldo_fim'):
                saldo = self.capture_balance()
                if saldo and saldo > 0:
                    self.saldo_atual = saldo
                    # CORRECAO: usar banca operacional (saldo - reserva) para P/L correto
                    banca_op_fim = saldo - self.reserva_manager.get_reserva()
                    self.martingale.definir_saldo_fim(banca_op_fim)

            # Som de WIN se ganhou
            if resultado.get('resultado_sessao') == 'win':
                self._som_win()

            # Registrar resultado
            self.registrar_resultado_sessao(resultado)

            # Resetar para proxima sessao
            self.martingale.reset()

        elif resultado['acao'] == 'parar':
            # ===== CENARIO B: PARAR VOLUNTARIAMENTE =====
            # T5 com cenário B - só slot de segurança ganhou, aceitar perda parcial
            if resultado.get('precisa_ler_saldo_fim'):
                saldo = self.capture_balance()
                if saldo and saldo > 0:
                    self.saldo_atual = saldo
                    # CORRECAO: usar banca operacional (saldo - reserva) para P/L correto
                    banca_op_fim = saldo - self.reserva_manager.get_reserva()
                    self.martingale.definir_saldo_fim(banca_op_fim)

            # Registrar como loss (perda parcial)
            self.registrar_resultado_sessao(resultado)

            # Resetar para proxima sessao
            self.martingale.reset()

            self._log(f"{Fore.YELLOW}CENARIO B: Parando para evitar perda maior!")

        # Info adicional
        if resultado.get('info'):
            cenario = resultado.get('cenario')
            cenario_str = f" [{cenario.value}]" if cenario else ""
            if 'WIN' in resultado.get('info', '') or 'CENARIO A' in resultado.get('info', ''):
                cor = Fore.GREEN
            elif 'PARAR' in resultado.get('info', '') or 'CENARIO B' in resultado.get('info', ''):
                cor = Fore.YELLOW
            else:
                cor = Fore.RED
            self._log(f"{cor}{resultado['info']}{cenario_str}")

        # ===== SALVAR ESTADO PERIODICAMENTE (para Telegram atualizar) =====
        # Salvar a cada 5 rodadas para nao sobrecarregar I/O
        if self.total_rodadas % 5 == 0:
            # Capturar saldo atual para manter atualizado
            saldo = self.capture_balance()
            if saldo and saldo > 0:
                self.saldo_atual = saldo
            self.salvar_estado()

    def executar_aposta(self):
        """
        Executa a aposta da tentativa atual (V4 - suporta 2 slots).

        Usa get_config_aposta_atual() para obter configuracao:
        - T1-T4: 1 slot @ 1.99x
        - T5: 2 slots (6/16 @ 1.99x + 10/16 @ 1.25x)
        - T6+: 1 slot @ 1.99x
        - Ultima: 1 slot @ 1.25x
        """
        # Verificar se está pausado para teste
        if getattr(self, '_pausado_para_teste', False):
            self._log(f"{Fore.YELLOW}Sistema pausado - aposta ignorada")
            return

        config = self.martingale.get_config_aposta_atual()
        tentativa = config['tentativa']
        num_slots = config['num_slots']
        slots = config['slots']

        # DEBUG: Mostrar configuracao da aposta
        print(f"\n{Fore.GREEN}{'='*50}")
        print(f"{Fore.GREEN}>>> EXECUTANDO APOSTA T{tentativa} ({num_slots} slot{'s' if num_slots > 1 else ''})")
        for s in slots:
            print(f"{Fore.GREEN}>>>   Slot {s['slot_id']}: R$ {s['valor']:.2f} @ {s['alvo']}x ({s['proporcao']})")
        print(f"{Fore.GREEN}>>> Profile: {self.bet_executor.current_profile}")
        if config['parar_cenario_b']:
            print(f"{Fore.YELLOW}>>> ATENCAO: Se Cenario B, vai PARAR!")
        print(f"{Fore.GREEN}{'='*50}")

        # Salvar recommendation no banco
        rec_id = self.session.save_recommendation(
            pattern_detected=f"MARTINGALE_T{tentativa}_V4",
            sequence_multipliers=self.martingale.multiplicadores_gatilho,
            regime="MARTINGALE_V4",
            score=0,
            should_bet=True,
            recommended_amount=config['valor_total'],
            recommended_target=slots[0]['alvo'],  # Alvo principal
            confidence_level="HIGH",
            reason=f"T{tentativa} V4 - {num_slots} slot(s)"
        )

        tempo_total = 0
        sucesso_total = True

        # ===== EXECUTAR CADA SLOT =====
        for slot_info in slots:
            slot_id = slot_info['slot_id']
            valor = slot_info['valor']
            alvo = slot_info['alvo']

            print(f"\n{Fore.CYAN}--- Slot {slot_id}: R$ {valor:.2f} @ {alvo}x ---")

            # PRIMEIRO: Executar aposta
            result = self.bet_executor.execute_bet(valor, alvo, bet_slot=slot_id)
            tempo_total += result.execution_time

            if result.success:
                print(f"{Fore.GREEN}Slot {slot_id}: OK ({result.execution_time:.2f}s)")

                # DEPOIS: Registrar no banco apenas se executou com sucesso
                bet_id = self.session.execute_bet(
                    recommendation_id=rec_id,
                    bet_amount=valor,
                    target_multiplier=alvo,
                    profile_used=self.selected_profile,
                    working_balance_before=self.saldo_atual,
                    bet_slot=slot_id,
                    tentativa=tentativa
                )

                # Salvar bet_id de TODOS os slots (não só slot 1)
                self.last_bet_ids[slot_id] = {
                    'bet_id': bet_id,
                    'valor': valor,
                    'alvo': alvo,
                    'executado': True
                }
                # Manter compatibilidade
                if slot_id == 1:
                    self.last_bet_id = bet_id
            else:
                print(f"{Fore.RED}Slot {slot_id}: FALHA - {result.error_message}")
                print(f"{Fore.RED}>>> APOSTA NAO REGISTRADA (não foi executada)")
                sucesso_total = False

                # Registrar que o slot NAO foi executado (importante para cenario)
                self.last_bet_ids[slot_id] = {
                    'bet_id': None,
                    'valor': valor,
                    'alvo': alvo,
                    'executado': False  # CRUCIAL: Marca como nao executado!
                }

        # ===== RESULTADO FINAL =====
        print(f"\n{Fore.CYAN}>>> Tempo total: {tempo_total:.2f}s")

        if sucesso_total:
            self._log(f"{Fore.GREEN}T{tentativa}: {num_slots} aposta(s) executada(s) em {tempo_total:.2f}s")
        else:
            self._log(f"{Fore.RED}T{tentativa}: Falha em uma ou mais apostas")

    def registrar_resultado_sessao(self, resultado: Dict):
        """Registra o resultado final da sessao de martingale (V4 com cenarios)"""
        resumo = self.martingale.get_resumo()
        cenario = resultado.get('cenario')

        # Inicializar variaveis para auditoria
        resultado_pagamento = None
        resultado_emprestimo = None

        # Determinar tipo de resultado
        if resultado['resultado_sessao'] == 'win':
            self.stats['sessoes_win'] += 1
            cor = Fore.GREEN
            emoji = "WIN"
        elif resultado['resultado_sessao'] == 'parar_cenario_b':
            self.stats['sessoes_loss'] += 1  # Conta como loss (perda parcial)
            cor = Fore.YELLOW
            emoji = "PARAR [B]"
        else:
            self.stats['sessoes_loss'] += 1
            cor = Fore.RED
            emoji = "LOSS"

        self.stats['lucro_total'] += resumo['lucro_perda']

        # ===== RESERVA DE LUCROS (pular para NS7_PURO) =====
        if self.config_modo.modo != ModoOperacao.NS7_PURO:
            resultado_reserva = self.reserva_manager.registrar_resultado(
                resumo['lucro_perda'],
                self.saldo_atual
            )

            if resultado_reserva:
                # Bateu meta de 10%!
                self._log(f"\n{Fore.MAGENTA}{'='*50}")
                self._log(f"{Fore.MAGENTA}  META 10% BATIDA!")
                self._log(f"{Fore.MAGENTA}  Reserva: +R$ {resultado_reserva['valor_reserva']:.2f}")
                self._log(f"{Fore.MAGENTA}  Compound: +R$ {resultado_reserva['valor_compound']:.2f}")
                self._log(f"{Fore.MAGENTA}  Total reservado: R$ {resultado_reserva['reserva_total']:.2f}")
                self._log(f"{Fore.MAGENTA}  Nova banca base: R$ {resultado_reserva['nova_banca_base']:.2f}")
                self._log(f"{Fore.MAGENTA}{'='*50}\n")

            # ===== PAGAMENTO DE DIVIDA (PRIORIDADE) =====
            if self.reserva_manager.tem_divida() and resumo['lucro_perda'] > 0:
                resultado_pagamento = self.reserva_manager.pagar_divida(resumo['lucro_perda'])
                if resultado_pagamento:
                    self._log(f"{Fore.YELLOW}[DIVIDA] Pagamento: R$ {resultado_pagamento['pagamento']:.2f}")
                    if resultado_pagamento['quitado']:
                        self._log(f"{Fore.GREEN}[DIVIDA] Quitada! Reserva: R$ {resultado_pagamento['reserva_apos']:.2f}")
                    else:
                        self._log(f"{Fore.YELLOW}[DIVIDA] Restante: R$ {resultado_pagamento['divida_restante']:.2f}")

        # ===== ESTRATEGIA [7,7,6] - REGISTRAR GATILHO FINALIZADO =====
        tentativa_final = len(self.martingale.tentativas)
        chegou_t6 = tentativa_final >= 6

        if self.config_modo.modo != ModoOperacao.GAGO and self.aceleracao_manager.is_ativo():
            # Atualizar banca pico
            banca_pico_atual = self.aceleracao_manager.estado.banca_pico
            if self.saldo_atual > banca_pico_atual:
                banca_pico_atual = self.saldo_atual

            # Registrar gatilho finalizado (avanca o padrao [7,7,6])
            self.aceleracao_manager.registrar_gatilho_finalizado(
                chegou_t6=chegou_t6,
                banca_atual=self.saldo_atual
            )

            # Verificar emprestimo da reserva
            resultado_emprestimo = self.reserva_manager.verificar_emprestimo(
                gatilhos_desde_t6=self.aceleracao_manager.estado.gatilhos_desde_t6,
                banca_atual=self.saldo_atual,
                banca_pico=banca_pico_atual
            )

            if resultado_emprestimo:
                self._log(f"\n{Fore.CYAN}{'='*50}")
                self._log(f"{Fore.CYAN}  EMPRESTIMO DA RESERVA!")
                self._log(f"{Fore.CYAN}  Valor: R$ {resultado_emprestimo['valor_emprestado']:.2f}")
                self._log(f"{Fore.CYAN}  Reserva restante: R$ {resultado_emprestimo['reserva_restante']:.2f}")
                self._log(f"{Fore.CYAN}  Divida total: R$ {resultado_emprestimo['divida_total']:.2f}")
                self._log(f"{Fore.CYAN}{'='*50}\n")
                # Resetar contador de gatilhos para evitar emprestimo imediato
                self.aceleracao_manager.estado.gatilhos_desde_t6 = 0
                self.aceleracao_manager.salvar()

        # ===== AUDITORIA: Fim do gatilho =====
        reserva_atual = self.reserva_manager.get_reserva()
        banca_op_final = self.saldo_atual - reserva_atual
        audit_pagamento = 0
        audit_emprestimo = 0
        try:
            if resultado_pagamento:
                audit_pagamento = resultado_pagamento.get('pagamento', 0)
        except:
            pass
        try:
            if resultado_emprestimo:
                audit_emprestimo = resultado_emprestimo.get('valor_emprestado', 0)
        except:
            pass
        self._audit('GATILHO_FIM', {
            'resultado': emoji,
            'tentativa_final': tentativa_final,
            'cenario': cenario.value if cenario else None,
            'lucro_perda': resumo['lucro_perda'],
            'saldo_total': self.saldo_atual,
            'reserva': reserva_atual,
            'banca_operacional': banca_op_final,
            'divida': self.reserva_manager.estado.divida_reserva,
            'aposta_base_ns6': banca_op_final / 63,
            'aposta_base_ns7': banca_op_final / 127,
            'meta_batida': resultado_reserva is not None,
            'valor_reserva_add': resultado_reserva['valor_reserva'] if resultado_reserva else 0,
            'pagamento_divida': audit_pagamento,
            'emprestimo': audit_emprestimo,
            'gatilhos_desde_t6': self.aceleracao_manager.estado.gatilhos_desde_t6,
            'padrao_posicao': self.aceleracao_manager.get_posicao_padrao()
        })

        # ===== REGISTRAR TRIGGER NO RALLY DETECTOR =====
        self.rally_detector.registrar_trigger()

        # ===== VALIDACAO ESTATISTICA =====
        # (tentativa_final ja definida acima)

        if tentativa_final <= 4:
            # Resolveu em T1-T4
            self.estatisticas_validacao.registrar_win_t1_t4(tentativa_final)
        elif tentativa_final == 5:
            # Foi para T5 - registrar cenario
            cenario_val = cenario.value if cenario else 'C'
            self.estatisticas_validacao.registrar_t5(cenario_val)
        elif tentativa_final >= 6:
            # T6+ - registrar win/loss
            ganhou_sessao = resultado['resultado_sessao'] == 'win'
            self.estatisticas_validacao.registrar_t6_plus(ganhou_sessao)

        # Verificar piores cenarios (considerando saques)
        if self.deposito_inicial and self.deposito_inicial > 0:
            saques = getattr(self, 'total_saques', 0.0)
            perda_real = self.deposito_inicial - self.saldo_atual - saques
            perda_pct = (perda_real / self.deposito_inicial) * 100 if perda_real > 0 else 0
            if perda_pct >= 60:
                self.estatisticas_validacao.registrar_sangrou()
            if self.saldo_atual <= 0:
                self.estatisticas_validacao.registrar_zerou()

        # Registrar cada tentativa no historico de apostas
        for tentativa in self.martingale.tentativas:
            # Usar propriedade resultado que considera cenario
            ganhou = tentativa.resultado == "WIN"

            # Calcular resultado financeiro considerando 2 slots
            if tentativa.is_2_slots:
                # 2 slots: calcular ganho de cada slot separadamente
                # IMPORTANTE: Usar ALVO (não mult) para calcular ganho - payout é baseado no alvo!
                mult = tentativa.multiplicador_resultado or 0
                ganho_slot1 = (tentativa.valor_slot1 * (tentativa.alvo_slot1 - 1)) if mult >= tentativa.alvo_slot1 else -tentativa.valor_slot1
                ganho_slot2 = (tentativa.valor_slot2 * (tentativa.alvo_slot2 - 1)) if mult >= tentativa.alvo_slot2 else -tentativa.valor_slot2
                resultado_financeiro = ganho_slot1 + ganho_slot2
            else:
                # 1 slot: calculo simples
                if ganhou:
                    resultado_financeiro = tentativa.valor_slot1 * tentativa.alvo_slot1 - tentativa.valor_slot1
                else:
                    resultado_financeiro = -tentativa.valor_slot1

            # Determinar alvo para exibicao
            if tentativa.is_2_slots:
                alvo_display = f"{tentativa.alvo_slot1}/{tentativa.alvo_slot2}"
            else:
                alvo_display = tentativa.alvo_slot1

            aposta_registro = {
                'horario': tentativa.timestamp.strftime('%H:%M:%S') if tentativa.timestamp else '--:--:--',
                'tentativa': tentativa.numero,
                'valor_apostado': tentativa.valor_total,
                'alvo': alvo_display,
                'multiplicador_real': tentativa.multiplicador_resultado or 0,
                'ganhou': ganhou,
                'resultado': resultado_financeiro,
                'cenario': tentativa.cenario.value if tentativa.cenario else None,
            }

            # Adicionar multiplicadores do gatilho na T1 ou quando há perda (para auditoria)
            if tentativa.numero == 1 or not ganhou:
                aposta_registro['gatilho_mults'] = list(self.martingale.multiplicadores_gatilho)
                aposta_registro['gatilho_count'] = len(self.martingale.multiplicadores_gatilho)

            self.historico_apostas.append(aposta_registro)

        # Limitar histórico de apostas para evitar memory leak
        if len(self.historico_apostas) > 500:
            self.historico_apostas = self.historico_apostas[-250:]

        # Mostrar cenario na saida
        cenario_str = f" [{cenario.value}]" if cenario else ""
        self._log(f"\n{cor}{'='*50}")
        self._log(f"{cor}  SESSAO {emoji}{cenario_str} | T{len(self.martingale.tentativas)} | P/L: R$ {resumo['lucro_perda']:+.2f}")
        self._log(f"{cor}{'='*50}\n")

        # Registrar no banco de dados
        self.session.save_recommendation(
            pattern_detected=f"MARTINGALE_V4_{emoji}",
            sequence_multipliers=self.martingale.multiplicadores_gatilho,
            regime="MARTINGALE_V4",
            score=0,
            should_bet=True,
            recommended_amount=resumo['aposta_base'],
            recommended_target=self.martingale.ALVOS[0],
            confidence_level="HIGH",
            reason=f"Sessao {emoji}{cenario_str} em T{len(self.martingale.tentativas)}"
        )

        # ===== VERIFICAR UPGRADE AUTOMATICO DE NIVEL =====
        # Funciona para AUTOMATICO, G6_NS9 e G6_NS10
        modos_com_upgrade = [ModoOperacao.AUTOMATICO, ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]
        if self.config_modo.modo in modos_com_upgrade:
            self.verificar_upgrade_nivel()

        # ===== AUTO-SAVE APOS CADA SESSAO =====
        self.salvar_estado()

    def verificar_upgrade_nivel(self):
        """Verifica se deve subir de nivel (AUTOMATICO, G6_NS9, G6_NS10)"""
        if not self.deposito_inicial or self.deposito_inicial <= 0:
            return

        # Calcular lucro atual em % (considerando saques)
        saques = getattr(self, 'total_saques', 0.0)
        lucro_atual = self.saldo_atual - self.deposito_inicial + saques
        lucro_percentual = (lucro_atual / self.deposito_inicial) * 100

        # Verificar se atingiu o threshold para subir (sempre em %)
        if lucro_percentual >= self.config_modo.lucro_para_subir:
            nivel_atual = self.martingale.nivel_seguranca
            nivel_maximo = get_nivel_para_banca(self.saldo_atual)

            # Pode subir de nivel?
            if nivel_atual < nivel_maximo and nivel_atual < 10:
                novo_nivel = nivel_atual + 1
                self.martingale.set_nivel_seguranca(novo_nivel)

                # Resetar base de lucro para o novo nivel
                self.deposito_inicial = self.saldo_atual  # Nova base!

                print(f"\n{Fore.GREEN}{'='*50}")
                print(f"{Fore.GREEN}  UPGRADE AUTOMATICO DE NIVEL!")
                print(f"{Fore.GREEN}{'='*50}")
                print(f"{Fore.WHITE}  Meta: {self.config_modo.lucro_para_subir:.1f}% | Lucro: {lucro_percentual:.1f}%")
                print(f"{Fore.WHITE}  {NIVEIS_SEGURANCA[nivel_atual]['nome']} -> {NIVEIS_SEGURANCA[novo_nivel]['nome']}")
                print(f"{Fore.WHITE}  Nova base: R$ {self.deposito_inicial:.2f}")
                print(f"{Fore.GREEN}{'='*50}\n")

    def mudar_nivel_manual(self, novo_nivel: int) -> bool:
        """Muda o nivel manualmente (para modo manual)"""
        if novo_nivel not in [6, 7, 8, 9, 10]:
            return False

        # Verificar se a banca permite
        nivel_maximo = get_nivel_para_banca(self.saldo_atual)
        if novo_nivel > nivel_maximo:
            print(f"{Fore.RED}Banca insuficiente para {NIVEIS_SEGURANCA[novo_nivel]['nome']}!")
            print(f"{Fore.RED}Banca minima: R$ {NIVEIS_SEGURANCA[novo_nivel]['threshold']:.0f}")
            return False

        nivel_anterior = self.martingale.nivel_seguranca
        self.martingale.set_nivel_seguranca(novo_nivel)

        print(f"\n{Fore.CYAN}Nivel alterado: {NIVEIS_SEGURANCA[nivel_anterior]['nome']} -> {NIVEIS_SEGURANCA[novo_nivel]['nome']}")

        # Salvar estado apos mudanca de nivel
        self.salvar_estado()
        return True

    def salvar_estado(self):
        """Salva o estado atual da sessao para persistencia"""
        estado = EstadoSessao(
            sessao_id=self.sessao_id,
            inicio_timestamp=self.session_start.strftime('%Y-%m-%d %H:%M:%S'),
            deposito_inicial=self.deposito_inicial or 0.0,
            saldo_atual=self.saldo_atual,
            total_saques=getattr(self, 'total_saques', 0.0),
            total_depositos=getattr(self, 'total_depositos', 0.0),
            nivel_seguranca=self.martingale.nivel_seguranca,
            config_modo=self.config_modo.to_dict(),
            sessoes_win=self.stats['sessoes_win'],
            sessoes_loss=self.stats['sessoes_loss'],
            total_rodadas=self.total_rodadas,
            perfil_ativo=self.selected_profile,
            historico_apostas=self.historico_apostas,
        )
        salvar_estado_sessao(estado)

    def registrar_saque(self, valor: float):
        """Registra um saque e salva o estado"""
        if not hasattr(self, 'total_saques'):
            self.total_saques = 0.0
        self.total_saques += valor
        self.saldo_atual -= valor

        print(f"\n{Fore.GREEN}{'='*50}")
        print(f"{Fore.GREEN}  SAQUE REGISTRADO: R$ {valor:.2f}")
        print(f"{Fore.GREEN}{'='*50}")
        print(f"{Fore.WHITE}  Novo saldo: R$ {self.saldo_atual:.2f}")
        print(f"{Fore.WHITE}  Total sacado: R$ {self.total_saques:.2f}")

        # Salvar estado apos saque
        self.salvar_estado()

    def restaurar_estado(self):
        """Restaura o estado da sessao anterior"""
        if not self.estado_anterior:
            return False

        self._log(f"{Fore.YELLOW}Restaurando sessao anterior...")

        # Restaurar timestamp de inicio (IMPORTANTE para dashboard!)
        if self.estado_anterior.inicio_timestamp:
            try:
                self.session_start = datetime.strptime(
                    self.estado_anterior.inicio_timestamp,
                    '%Y-%m-%d %H:%M:%S'
                )
                self._log(f"{Fore.WHITE}  Inicio original: {self.estado_anterior.inicio_timestamp}")
            except:
                pass  # Manter o atual se falhar

        # Restaurar estatisticas
        self.stats['sessoes_win'] = self.estado_anterior.sessoes_win
        self.stats['sessoes_loss'] = self.estado_anterior.sessoes_loss
        self.total_rodadas = self.estado_anterior.total_rodadas

        # Restaurar nivel
        self.martingale.set_nivel_seguranca(self.estado_anterior.nivel_seguranca)

        # Restaurar financeiro
        self.deposito_inicial = self.estado_anterior.deposito_inicial
        self.total_saques = self.estado_anterior.total_saques
        self.total_depositos = self.estado_anterior.total_depositos

        # Restaurar historico de apostas (importante para o grafico!)
        if hasattr(self.estado_anterior, 'historico_apostas') and self.estado_anterior.historico_apostas:
            self.historico_apostas = self.estado_anterior.historico_apostas
            self._log(f"{Fore.WHITE}  Historico: {len(self.historico_apostas)} apostas restauradas")

        # NAO restaurar config_modo - usar o que veio do start_v2.py
        # O config_modo do start_v2.py tem os valores corretos (lucro_para_subir=5.8 para G6)
        self._log(f"{Fore.WHITE}  Modo: {self.config_modo.modo.value} | Meta: {self.config_modo.lucro_para_subir:.1f}%")

        self._log(f"{Fore.GREEN}Sessao restaurada!")
        self._log(f"{Fore.WHITE}  Nivel: {NIVEIS_SEGURANCA[self.estado_anterior.nivel_seguranca]['nome']}")
        self._log(f"{Fore.WHITE}  Deposito: R$ {self.deposito_inicial:.2f}")
        self._log(f"{Fore.WHITE}  WIN: {self.stats['sessoes_win']} | LOSS: {self.stats['sessoes_loss']}")

        return True

    def processar_comandos_telegram(self):
        """Verifica e executa comandos enviados pelo Telegram"""
        try:
            if not os.path.exists(TELEGRAM_COMMANDS_FILE):
                return

            with open(TELEGRAM_COMMANDS_FILE, 'r') as f:
                commands = json.load(f)

            modified = False
            for cmd in commands:
                if cmd.get('executed'):
                    continue

                command = cmd.get('command')
                params = cmd.get('params', {})

                if command == 'saque':
                    valor = params.get('valor', 0)
                    if valor > 0:
                        self.registrar_saque(valor)
                        print(f"{Fore.CYAN}[TELEGRAM] Saque de R$ {valor:.2f} executado!")

                elif command == 'nivel':
                    nivel = params.get('nivel', 7)
                    if self.mudar_nivel_manual(nivel):
                        print(f"{Fore.CYAN}[TELEGRAM] Nivel alterado para NS{nivel}!")
                    else:
                        print(f"{Fore.RED}[TELEGRAM] Falha ao mudar nivel!")

                elif command == 'reiniciar':
                    if self.solicitar_restart_manual():
                        print(f"{Fore.CYAN}[TELEGRAM] Reinicio solicitado! Aguardando momento seguro...")
                    else:
                        print(f"{Fore.YELLOW}[TELEGRAM] Reinicio ja estava pendente.")

                cmd['executed'] = True
                modified = True

            if modified:
                with open(TELEGRAM_COMMANDS_FILE, 'w') as f:
                    json.dump(commands, f, indent=2)

        except Exception as e:
            pass  # Silencioso para nao atrapalhar o bot

    # ===== REDEFINIR SESSÃO (RESET PARCIAL) =====

    def _detectar_machine_id(self) -> str:
        """Detecta o ID da máquina atual para o dashboard."""
        import platform

        # 1. Tentar ler de sync_client.py (mais confiável para Windows)
        try:
            sync_client_path = os.path.join(os.path.dirname(__file__), 'sync_client.py')
            if os.path.exists(sync_client_path):
                with open(sync_client_path, 'r') as f:
                    content = f.read()
                    import re
                    match = re.search(r'MACHINE_ID\s*=\s*["\'](\w+)["\']', content)
                    if match:
                        return match.group(1).lower()
        except:
            pass

        # 2. Tentar ler de machine_config.json
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'machine_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    name = config.get('machine_name', '').lower()
                    if 'isolada' in name:
                        return 'isolada'
                    elif 'dual' in name or 'conservadora' in name:
                        return 'conservadora'
        except:
            pass

        # 3. Fallback: detectar pelo sistema operacional
        if platform.system() == 'Linux':
            return 'agressiva'
        else:
            # Windows - assumir conservadora por padrão
            return 'conservadora'

    def redefinir_sessao(self, novo_modo: str = None) -> bool:
        """
        Faz reset parcial da sessão:
        1. Salva lucro atual no lucro_acumulado_anterior (dashboard_config.json)
        2. Reseta deposito_inicial para saldo atual
        3. Zera contadores de sessão
        4. Opcionalmente muda o modo (ns9/ns10)

        Args:
            novo_modo: 'ns9' ou 'ns10' (opcional, se None mantém o atual)

        Returns:
            True se sucesso, False se erro
        """
        try:
            from colorama import Fore
            import platform

            saldo_atual = self.saldo_atual
            deposito_inicial = self.deposito_inicial
            lucro_sessao = saldo_atual - deposito_inicial

            self._log(f"{Fore.CYAN}[REDEFINIR] Iniciando reset parcial...")
            self._log(f"{Fore.WHITE}  Saldo atual: R$ {saldo_atual:.2f}")
            self._log(f"{Fore.WHITE}  Lucro da sessão: R$ {lucro_sessao:.2f}")

            # Detectar qual máquina é esta
            machine_id = self._detectar_machine_id()
            self._log(f"{Fore.WHITE}  Machine ID: {machine_id}")

            # 1. Atualizar dashboard_config.json com lucro acumulado (opcional)
            dashboard_config_path = os.path.join(os.path.dirname(__file__), 'dashboard_config.json')
            if os.path.exists(dashboard_config_path):
                try:
                    with open(dashboard_config_path, 'r') as f:
                        dash_config = json.load(f)

                    if machine_id in dash_config:
                        lucro_anterior = dash_config[machine_id].get('lucro_acumulado_anterior', 0) or 0
                        novo_acumulado = lucro_anterior + lucro_sessao
                        dash_config[machine_id]['lucro_acumulado_anterior'] = round(novo_acumulado, 2)

                        with open(dashboard_config_path, 'w') as f:
                            json.dump(dash_config, f, indent=2)

                        self._log(f"{Fore.GREEN}  Lucro acumulado atualizado: R$ {lucro_anterior:.2f} + R$ {lucro_sessao:.2f} = R$ {novo_acumulado:.2f}")
                    else:
                        self._log(f"{Fore.YELLOW}  Machine ID '{machine_id}' não encontrado no dashboard_config.json")
                except Exception as e:
                    self._log(f"{Fore.YELLOW}  Aviso: Não foi possível atualizar dashboard_config.json: {e}")
            else:
                self._log(f"{Fore.YELLOW}  dashboard_config.json não encontrado - pulando atualização do acumulado")

            # 2. Resetar deposito_inicial para saldo atual
            self.deposito_inicial = saldo_atual
            self._log(f"{Fore.GREEN}  Novo depósito inicial: R$ {saldo_atual:.2f}")

            # 3. Zerar contadores de sessão
            self.sessoes_win = 0
            self.sessoes_loss = 0
            self.total_rodadas = 0
            self._log(f"{Fore.GREEN}  Contadores zerados")

            # 4. Mudar modo se solicitado
            if novo_modo:
                novo_modo = novo_modo.lower()
                if novo_modo == 'ns9':
                    self.config_modo.modo = ModoOperacao.G6_NS9
                    self.nivel_seguranca = 9
                    self._log(f"{Fore.GREEN}  Modo alterado para NS9 (Agressivo)")
                elif novo_modo == 'ns10':
                    self.config_modo.modo = ModoOperacao.G6_NS10
                    self.nivel_seguranca = 10
                    self._log(f"{Fore.GREEN}  Modo alterado para NS10 (Conservador)")

                # Recalcular aposta base
                self._atualizar_aposta_base()

            # 5. Salvar estado
            self.salvar_estado()

            self._log(f"{Fore.CYAN}[REDEFINIR] Reset parcial concluído!")
            return True

        except Exception as e:
            import traceback
            self._log(f"{Fore.RED}[REDEFINIR] Erro: {e}")
            self._log(f"{Fore.RED}{traceback.format_exc()}")
            print(f"\n[REDEFINIR] ERRO DETALHADO: {e}")
            print(traceback.format_exc())
            return False

    # ===== AUTO-RESTART PARA LIBERAR MEMÓRIA =====

    def _verificar_auto_restart(self, multiplicador: float):
        """Verifica se deve fazer auto-restart para liberar memória"""
        tempo_rodando = time.time() - self.auto_restart_timestamp

        # Se ainda não passou o intervalo, não faz nada
        if tempo_rodando < AUTO_RESTART_INTERVAL:
            return

        # Marcar que tem reinício pendente
        if not self.auto_restart_pending:
            self.auto_restart_pending = True
            self._log(f"{Fore.YELLOW}[AUTO-RESTART] Tempo limite atingido ({tempo_rodando/3600:.1f}h). Aguardando momento seguro...")

        # Verificar se é momento seguro para reiniciar
        if self._pode_reiniciar_seguro(multiplicador):
            self._executar_auto_restart()

    def _pode_reiniciar_seguro(self, multiplicador: float) -> bool:
        """
        Verifica se é seguro reiniciar agora.

        Condições:
        1. Não está no meio de martingale (state == AGUARDANDO_GATILHO)
        2. Multiplicador foi alto (>= 2.0) - sequência de baixos zerou
        3. Não está próximo de um gatilho (sequencia_baixos < 3)
        4. Último gatilho foi há mais de 10 minutos (não está em rally)
        """
        # 1. Não está apostando
        if self.martingale.state != SessionState.AGUARDANDO_GATILHO:
            return False

        # 2. Multiplicador alto (acabou de zerar sequência)
        if multiplicador < 2.0:
            return False

        # 3. Longe de um gatilho
        if self.martingale.sequencia_baixos >= 3:
            return False

        # 4. Não está em rally
        ultimo_intervalo = self.rally_detector.get_ultimo_intervalo()
        if ultimo_intervalo < 10:  # Menos de 10 minutos desde último gatilho
            return False

        return True

    def _executar_auto_restart(self):
        """Executa o auto-restart de forma segura"""
        self._log(f"\n{Fore.GREEN}{'='*60}")
        self._log(f"{Fore.GREEN}  AUTO-RESTART INICIANDO")
        self._log(f"{Fore.GREEN}  Momento seguro detectado (mult={self.ultimo_multiplicador:.2f}x)")
        self._log(f"{Fore.GREEN}{'='*60}\n")

        # 1. Salvar estado atual
        self._salvar_estado_sessao()
        self._log(f"{Fore.GREEN}  [OK] Estado salvo")

        # 2. Criar flag de auto-restart
        try:
            with open(AUTO_RESTART_FLAG, 'w') as f:
                f.write(f"restart_time={agora_str()}\n")
                f.write(f"saldo={self.saldo_atual}\n")
                f.write(f"rodadas={self.total_rodadas}\n")
            self._log(f"{Fore.GREEN}  [OK] Flag criado")
        except Exception as e:
            self._log(f"{Fore.RED}  [ERRO] Falha ao criar flag: {e}")
            return

        # 3. Notificar via Telegram (se possível)
        try:
            self._notificar_telegram_restart()
        except:
            pass

        self._log(f"{Fore.GREEN}  [OK] Reiniciando em 3 segundos...")
        time.sleep(3)

        # 4. Sair com código 42 (sinaliza auto-restart para o batch)
        sys.exit(42)

    def _notificar_telegram_restart(self):
        """Envia notificação de restart via Telegram"""
        if not self._telegram_enabled():
            return
        try:
            import requests
            config_file = os.path.join(os.path.dirname(__file__), 'telegram_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    tg_config = json.load(f)
                token = tg_config.get('token')
                chat_id = tg_config.get('chat_id')
                if token and chat_id:
                    tempo_rodando = (time.time() - self.auto_restart_timestamp) / 3600
                    msg = f"🔄 <b>AUTO-RESTART</b>\n\n"
                    msg += f"Tempo rodando: {tempo_rodando:.1f}h\n"
                    msg += f"Saldo: R$ {self.saldo_atual:.2f}\n"
                    msg += f"Rodadas: {self.total_rodadas}\n\n"
                    msg += f"Reiniciando para liberar memória..."

                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url, data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
        except:
            pass

    def _alertar_gatilho_anomalo(self, qtd_mults: int, multiplicadores: list):
        """Envia alerta URGENTE via Telegram quando gatilho dispara fora de 6"""
        if not self._telegram_enabled():
            return
        try:
            import requests
            config_file = os.path.join(os.path.dirname(__file__), 'telegram_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    tg_config = json.load(f)
                token = tg_config.get('token')
                chat_id = tg_config.get('chat_id')
                if token and chat_id:
                    mults_str = ", ".join([f"{m:.2f}" for m in multiplicadores])
                    msg = f"🚨🚨🚨 <b>BUG DETECTADO!</b> 🚨🚨🚨\n\n"
                    msg += f"<b>Gatilho disparou com {qtd_mults} baixos!</b>\n"
                    msg += f"Esperado: 6\n\n"
                    msg += f"<b>Multiplicadores:</b>\n{mults_str}\n\n"
                    msg += f"Horário: {horario_brasilia()}\n"
                    msg += f"Saldo: R$ {self.saldo_atual:.2f}"

                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url, data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)

                    # Log local também
                    print(f"\n{Fore.RED}{'='*60}")
                    print(f"{Fore.RED}  BUG! GATILHO COM {qtd_mults} BAIXOS (esperado 6)")
                    print(f"{Fore.RED}  Mults: {mults_str}")
                    print(f"{Fore.RED}{'='*60}\n")
        except Exception as e:
            print(f"{Fore.RED}Erro ao enviar alerta Telegram: {e}")

    def solicitar_restart_manual(self) -> bool:
        """
        Solicita reinício manual (pode ser chamado via Telegram).
        Retorna True se o reinício foi agendado.
        """
        if self.auto_restart_pending:
            return False  # Já tem um pendente

        self.auto_restart_pending = True
        self._log(f"{Fore.YELLOW}[RESTART] Reinício manual solicitado. Aguardando momento seguro...")
        return True

    def get_current_status(self) -> Dict:
        """Retorna status para interface"""
        uptime = datetime.now() - self.session_start
        resumo = self.martingale.get_resumo()

        # Resultado considera saques realizados (saque não é perda!)
        saques = getattr(self, 'total_saques', 0.0)
        resultado_bruto = (self.saldo_atual - self.deposito_inicial + saques) if self.deposito_inicial else 0
        resultado_percent = (resultado_bruto / self.deposito_inicial * 100) if self.deposito_inicial else 0

        # Calcular estatisticas
        total_sessoes = self.stats['sessoes_win'] + self.stats['sessoes_loss']
        taxa_acerto = (self.stats['sessoes_win'] / total_sessoes * 100) if total_sessoes > 0 else 0

        # Status do refresh manager
        refresh_status = self.refresh_manager.get_status() if hasattr(self, 'refresh_manager') else {}

        # Contar sequencias >= 11
        sequencias_longas = sum(1 for m in self.multiplier_history if m >= 11.0)

        # Maior sequencia de baixos (estimativa baseada no historico)
        maior_seq = 0
        seq_atual = 0
        for m in self.multiplier_history:
            if m < 2.0:
                seq_atual += 1
                maior_seq = max(maior_seq, seq_atual)
            else:
                seq_atual = 0

        return {
            'running': self.running,
            'uptime': str(uptime).split('.')[0],
            'total_rodadas': self.total_rodadas,
            'saldo_atual': self.saldo_atual,
            'deposito_inicial': self.deposito_inicial,
            'resultado_bruto': resultado_bruto,
            'resultado_percent': resultado_percent,
            'sequencia_baixos': resumo['sequencia_baixos'],
            'gatilho': self.martingale.GATILHO,
            'em_martingale': resumo['state'] == 'em_martingale',
            'tentativa_atual': resumo['tentativa_atual'],
            'max_tentativas': self.martingale.MAX_TENTATIVAS,
            'alvo_atual': self.martingale.get_alvo_atual(),
            # Mostra aposta base real se em martingale, senao mostra projecao
            # CORRECAO: usar banca_operacional (saldo - reserva), nao saldo total
            'aposta_base': resumo['aposta_base'] if resumo['aposta_base'] > 0 else (
                ((self.saldo_atual - self.reserva_manager.get_reserva()) * self.martingale.PCT_RISCO) / sum(self.martingale.MULTIPLICADORES_APOSTA)
                if self.saldo_atual > 0 else 0.0
            ),
            'sessoes_win': self.stats['sessoes_win'],
            'sessoes_loss': self.stats['sessoes_loss'],
            'lucro_total': self.stats['lucro_total'],
            'multiplier_history': list(self.multiplier_history)[-14:],
            # Campos adicionais para interface
            'historico_apostas': getattr(self, 'historico_apostas', []),
            'taxa_acerto': taxa_acerto,
            'sequencias_11_mais': sequencias_longas,
            'stats': {
                'total_oportunidades': total_sessoes,
                'apostas_ganhas': self.stats['sessoes_win'],
                'apostas_perdidas': self.stats['sessoes_loss'],
                'martingales_recuperados': self.stats['sessoes_win'],
                'martingales_completos': self.stats['sessoes_loss'],
                'maior_sequencia_baixos': maior_seq,
            },
            'time_since_explosion': refresh_status.get('time_since_last_explosion', 0),
            'refresh_timeout': refresh_status.get('timeout_threshold', 133),
            'total_refreshes': refresh_status.get('total_refreshes', 0),
            # Informacoes de nivel e modo
            'nivel_seguranca': self.martingale.nivel_seguranca,
            'nome_nivel': self.martingale.NOME_NIVEL,
            'modo_operacao': self.config_modo.modo.value,
            'lucro_para_subir': self.config_modo.lucro_para_subir if self.config_modo.modo in [ModoOperacao.AUTOMATICO, ModoOperacao.G6_NS9, ModoOperacao.G6_NS10] else None,
            'nivel_maximo_permitido': get_nivel_para_banca(self.saldo_atual),
            'total_saques': getattr(self, 'total_saques', 0.0),
            # Validacao estatistica
            'estatisticas_validacao': self.estatisticas_validacao.to_dict(),
            # Rally detector
            'rally': self.rally_detector.to_dict(),
            # Regime detector (para monitoramento)
            'regime': self.regime_detector.to_dict(),
            # Reserva de lucros
            'reserva': self.reserva_manager.get_status(),
        }

    def iniciar_telegram_bot(self):
        """Inicia o bot do Telegram em thread separada"""
        if not self._telegram_enabled():
            self._log(f"{Fore.YELLOW}Telegram desabilitado nesta máquina")
            return
        try:
            from telegram_bot import TelegramBot
            self.telegram_bot = TelegramBot()

            def run_telegram():
                try:
                    self.telegram_bot.run(silent=True)
                except:
                    pass

            telegram_thread = threading.Thread(target=run_telegram, daemon=True)
            telegram_thread.start()
            self._log(f"{Fore.GREEN}Telegram Bot iniciado!")
        except Exception as e:
            self._log(f"{Fore.YELLOW}Telegram Bot nao disponivel: {e}")

    def start(self):
        """Inicia sistema"""
        if self.running:
            return

        self.running = True

        # Thread de captura
        capture_thread = threading.Thread(target=self.capture_multipliers_continuously, daemon=True)
        capture_thread.start()

        # Thread de deteccao
        detection_thread = threading.Thread(target=self.detect_bet_and_process, daemon=True)
        detection_thread.start()

        # Iniciar Telegram Bot
        self.iniciar_telegram_bot()

        # Iniciar refresh manager
        self._log(f"{Fore.CYAN}Iniciando auto-refresh (timeout: {self.refresh_manager.auto_refresh_timeout}s)")
        self.refresh_manager.start_monitoring()

        # Iniciar interface
        try:
            self.ui.start()
        except KeyboardInterrupt:
            pass

        self.stop()

    def pausar_para_teste(self):
        """Pausa o sistema para teste manual de slots"""
        self._log(f"{Fore.YELLOW}Sistema pausado para teste de slots...")
        self._pausado_para_teste = True

    def retomar_apos_teste(self):
        """Retoma o sistema após teste manual"""
        self._log(f"{Fore.GREEN}Retomando sistema após teste...")
        self._pausado_para_teste = False

    def stop(self):
        """Para sistema"""
        self._log(f"\n{Fore.YELLOW}Parando sistema...")
        self.running = False

        if hasattr(self, 'refresh_manager'):
            self.refresh_manager.stop_monitoring()

        if self.ui:
            self.ui.stop()

        if hasattr(self, 'session'):
            self.session.close_session()

        self.print_final_report()

    def print_final_report(self):
        """Relatorio final - sempre exibido"""
        uptime = datetime.now() - self.session_start

        # Resultado considera saques realizados (saque não é perda!)
        saques = getattr(self, 'total_saques', 0.0)
        resultado_bruto = (self.saldo_atual - self.deposito_inicial + saques) if self.deposito_inicial else 0
        resultado_percent = (resultado_bruto / self.deposito_inicial * 100) if self.deposito_inicial else 0

        total_sessoes = self.stats['sessoes_win'] + self.stats['sessoes_loss']
        win_rate = (self.stats['sessoes_win'] / total_sessoes * 100) if total_sessoes > 0 else 0

        # Relatorio final SEMPRE aparece (force=True)
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}       RELATORIO FINAL")
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.WHITE}  Modo: {self.config_modo.modo.value.upper()} | Nivel: {NIVEIS_SEGURANCA[self.martingale.nivel_seguranca]['nome']}")
        print(f"{Fore.WHITE}  Duracao: {str(uptime).split('.')[0]} | Rodadas: {self.total_rodadas}")
        print(f"{Fore.WHITE}  Deposito: R$ {self.deposito_inicial:.2f} | Saldo: R$ {self.saldo_atual:.2f}")
        cor = Fore.GREEN if resultado_bruto >= 0 else Fore.RED
        print(f"{cor}  Resultado: R$ {resultado_bruto:+.2f} ({resultado_percent:+.1f}%)")
        print(f"{Fore.WHITE}  WIN: {self.stats['sessoes_win']} | LOSS: {self.stats['sessoes_loss']} | Rate: {win_rate:.1f}%")
        print(f"{Fore.CYAN}{'='*60}\n")


# Ponto de entrada
if __name__ == "__main__":
    system = HybridSystemV2()
    system.start()
