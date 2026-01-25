#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DUAL ACCOUNT MANAGER - Gerenciador Semi-Automatico de Duas Contas

Operacao REAL com duas contas separadas:
- Conta A: NS9 (agressiva) - migra para NS10 ao atingir meta
- Conta B: NS10 (conservadora) - sempre fixa

Fluxo diario (MANUAL):
1. Usuario informa saldo inicial de cada conta via Telegram
2. Bot rastreia operacoes e calcula lucros
3. Ao atingir meta, Conta A "migra" para NS10 (usuario muda config)
4. Fim do dia: Bot calcula redistribuicao necessaria
5. Usuario faz saque/deposito manual entre contas
6. Usuario executa /reset_dia para iniciar novo dia

Comandos Telegram:
- /dual - Status completo
- /saldo_a [valor] - Atualizar saldo Conta A
- /saldo_b [valor] - Atualizar saldo Conta B
- /saque [valor] - Registrar saque (retira do total)
- /calcular - Calcular redistribuicao necessaria
- /reset_dia - Finalizar dia e preparar proximo
- /migrar - Marcar que Conta A migrou para NS10
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional


# Caminho base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DUAL_ACCOUNT_STATE_FILE = os.path.join(BASE_DIR, 'dual_account_state.json')
CONSERVADORA_REMOTE_STATE_FILE = os.path.join(BASE_DIR, 'conservadora_remote_state.json')


# ============================================================
# CONFIGURACOES
# ============================================================

# Rentabilidade media diaria do NS9 (calculada do dataset 1.3M)
MEDIA_DIARIA_NS9_PCT = 8.26

# Stop-win em 70% da media
STOP_WIN_PCT = MEDIA_DIARIA_NS9_PCT * 0.70  # 5.78%


# ============================================================
# SESSAO INTRADAY
# ============================================================

@dataclass
class SessaoIntraday:
    """Estatisticas do dia atual"""

    data: str = ""

    # Conta A (dinamica NS9/NS10)
    conta_a_inicio: float = 0.0
    conta_a_atual: float = 0.0
    conta_a_modo: str = "NS9"
    conta_a_migrou: bool = False
    conta_a_hora_migracao: str = ""

    # Conta B (fixa NS10)
    conta_b_inicio: float = 0.0
    conta_b_atual: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'data': self.data,
            'conta_a': {
                'inicio': self.conta_a_inicio,
                'atual': self.conta_a_atual,
                'modo': self.conta_a_modo,
                'migrou': self.conta_a_migrou,
                'hora_migracao': self.conta_a_hora_migracao,
            },
            'conta_b': {
                'inicio': self.conta_b_inicio,
                'atual': self.conta_b_atual,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SessaoIntraday':
        s = cls()
        s.data = data.get('data', '')

        ca = data.get('conta_a', {})
        s.conta_a_inicio = ca.get('inicio', 0)
        s.conta_a_atual = ca.get('atual', 0)
        s.conta_a_modo = ca.get('modo', 'NS9')
        s.conta_a_migrou = ca.get('migrou', False)
        s.conta_a_hora_migracao = ca.get('hora_migracao', '')

        cb = data.get('conta_b', {})
        s.conta_b_inicio = cb.get('inicio', 0)
        s.conta_b_atual = cb.get('atual', 0)

        return s

    @property
    def lucro_a(self) -> float:
        return self.conta_a_atual - self.conta_a_inicio

    @property
    def lucro_b(self) -> float:
        return self.conta_b_atual - self.conta_b_inicio

    @property
    def lucro_total(self) -> float:
        return self.lucro_a + self.lucro_b

    @property
    def lucro_a_pct(self) -> float:
        if self.conta_a_inicio <= 0:
            return 0
        return (self.lucro_a / self.conta_a_inicio) * 100

    @property
    def total_atual(self) -> float:
        return self.conta_a_atual + self.conta_b_atual

    def deve_migrar(self) -> bool:
        """Verifica se Conta A deve migrar para NS10"""
        if self.conta_a_migrou:
            return False
        return self.lucro_a_pct >= STOP_WIN_PCT


# ============================================================
# SESSAO PRINCIPAL
# ============================================================

@dataclass
class SessaoPrincipal:
    """Acumulado total da estrategia"""

    sessao_id: str = ""
    inicio_timestamp: str = ""

    # Financeiro
    deposito_inicial: float = 0.0
    total_saques: float = 0.0

    # Estatisticas
    total_dias: int = 0
    total_migracoes: int = 0

    # Historico
    historico_dias: List[Dict] = field(default_factory=list)
    historico_saques: List[Dict] = field(default_factory=list)

    # Pico
    banca_pico: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'sessao_id': self.sessao_id,
            'inicio_timestamp': self.inicio_timestamp,
            'deposito_inicial': self.deposito_inicial,
            'total_saques': self.total_saques,
            'total_dias': self.total_dias,
            'total_migracoes': self.total_migracoes,
            'historico_dias': self.historico_dias[-30:],
            'historico_saques': self.historico_saques[-50:],
            'banca_pico': self.banca_pico,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SessaoPrincipal':
        s = cls()
        s.sessao_id = data.get('sessao_id', '')
        s.inicio_timestamp = data.get('inicio_timestamp', '')
        s.deposito_inicial = data.get('deposito_inicial', 0)
        s.total_saques = data.get('total_saques', 0)
        s.total_dias = data.get('total_dias', 0)
        s.total_migracoes = data.get('total_migracoes', 0)
        s.historico_dias = data.get('historico_dias', [])
        s.historico_saques = data.get('historico_saques', [])
        s.banca_pico = data.get('banca_pico', 0)
        return s


# ============================================================
# DUAL ACCOUNT MANAGER
# ============================================================

class DualAccountManager:
    """Gerenciador das duas contas"""

    def __init__(self):
        self.principal: Optional[SessaoPrincipal] = None
        self.intraday: Optional[SessaoIntraday] = None
        self.carregar()

    def carregar(self):
        """Carrega estado salvo"""
        try:
            if os.path.exists(DUAL_ACCOUNT_STATE_FILE):
                with open(DUAL_ACCOUNT_STATE_FILE, 'r') as f:
                    data = json.load(f)
                self.principal = SessaoPrincipal.from_dict(data.get('principal', {}))
                self.intraday = SessaoIntraday.from_dict(data.get('intraday', {}))
        except Exception as e:
            print(f"Erro ao carregar dual account: {e}")

    def salvar(self):
        """Salva estado atual"""
        data = {
            'principal': self.principal.to_dict() if self.principal else {},
            'intraday': self.intraday.to_dict() if self.intraday else {},
            'ultima_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        with open(DUAL_ACCOUNT_STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def iniciar_sessao(self, saldo_a: float, saldo_b: float) -> str:
        """Inicia nova sessao com saldos das duas contas"""
        import uuid

        self.principal = SessaoPrincipal()
        self.principal.sessao_id = str(uuid.uuid4())[:8]
        self.principal.inicio_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.principal.deposito_inicial = saldo_a + saldo_b
        self.principal.banca_pico = saldo_a + saldo_b

        self.intraday = SessaoIntraday()
        self.intraday.data = date.today().isoformat()
        self.intraday.conta_a_inicio = saldo_a
        self.intraday.conta_a_atual = saldo_a
        self.intraday.conta_b_inicio = saldo_b
        self.intraday.conta_b_atual = saldo_b

        self.salvar()
        return self.principal.sessao_id

    def atualizar_saldo_a(self, valor: float) -> bool:
        """Atualiza saldo atual da Conta A. Retorna True se migrou automaticamente."""
        if not self.intraday:
            return False

        self.intraday.conta_a_atual = valor
        self._verificar_pico()

        # Verificar migração automática
        migrou_agora = False
        if self.intraday.deve_migrar():
            self.marcar_migracao()
            migrou_agora = True

        self.salvar()
        return migrou_agora

    def atualizar_saldo_b(self, valor: float):
        """Atualiza saldo atual da Conta B"""
        if self.intraday:
            self.intraday.conta_b_atual = valor
            self._verificar_pico()
            self.salvar()

    def _verificar_pico(self):
        """Atualiza pico se necessario"""
        if self.principal and self.intraday:
            total = self.intraday.total_atual
            if total > self.principal.banca_pico:
                self.principal.banca_pico = total

    def marcar_migracao(self):
        """Marca que Conta A migrou de NS9 para NS10"""
        if self.intraday and not self.intraday.conta_a_migrou:
            self.intraday.conta_a_migrou = True
            self.intraday.conta_a_modo = 'NS10'
            self.intraday.conta_a_hora_migracao = datetime.now().strftime('%H:%M:%S')
            if self.principal:
                self.principal.total_migracoes += 1
            self.salvar()

    def verificar_deve_migrar(self) -> tuple:
        """Verifica se deve migrar e retorna (deve_migrar, lucro_pct, meta_pct)"""
        if not self.intraday:
            return False, 0, STOP_WIN_PCT

        if self.intraday.conta_a_migrou:
            return False, self.intraday.lucro_a_pct, STOP_WIN_PCT

        return self.intraday.deve_migrar(), self.intraday.lucro_a_pct, STOP_WIN_PCT

    def calcular_redistribuicao(self, usar_remoto: bool = True) -> Dict:
        """Calcula quanto transferir entre contas para igualar 50/50"""
        if not self.intraday:
            return {'erro': 'Nenhuma sessao ativa'}

        # Usar dados remotos da CONSERVADORA se disponível
        conta_a_atual = self.intraday.conta_a_atual
        conta_b_atual = self.intraday.conta_b_atual

        if usar_remoto:
            remoto = ler_estado_remoto_conservadora()
            if remoto and remoto.get('saldo_atual'):
                conta_b_atual = remoto.get('saldo_atual')

        total = conta_a_atual + conta_b_atual
        meta_cada = total / 2

        diff_a = conta_a_atual - meta_cada
        diff_b = conta_b_atual - meta_cada

        if abs(diff_a) < 1:  # Ja esta equilibrado
            return {
                'equilibrado': True,
                'conta_a': conta_a_atual,
                'conta_b': conta_b_atual,
                'total': total,
            }

        if diff_a > 0:
            # Conta A tem mais, transferir para B
            return {
                'equilibrado': False,
                'acao': f'Sacar R$ {diff_a:.2f} da AGRESSIVA e depositar na CONSERVADORA',
                'de': 'AGRESSIVA',
                'para': 'CONSERVADORA',
                'valor': diff_a,
                'conta_a_antes': conta_a_atual,
                'conta_b_antes': conta_b_atual,
                'conta_a_depois': meta_cada,
                'conta_b_depois': meta_cada,
                'total': total,
            }
        else:
            # Conta B tem mais, transferir para A
            return {
                'equilibrado': False,
                'acao': f'Sacar R$ {-diff_a:.2f} da CONSERVADORA e depositar na AGRESSIVA',
                'de': 'CONSERVADORA',
                'para': 'AGRESSIVA',
                'valor': -diff_a,
                'conta_a_antes': conta_a_atual,
                'conta_b_antes': conta_b_atual,
                'conta_a_depois': meta_cada,
                'conta_b_depois': meta_cada,
                'total': total,
            }

    def registrar_saque(self, valor: float, conta: str = 'total') -> bool:
        """Registra saque (dinheiro retirado do sistema)"""
        if not self.principal or not self.intraday:
            return False

        total = self.intraday.total_atual
        if valor > total:
            return False

        self.principal.total_saques += valor
        self.principal.historico_saques.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'valor': valor,
            'conta': conta,
        })

        # Descontar proporcionalmente das duas contas
        if total > 0:
            prop_a = self.intraday.conta_a_atual / total
            self.intraday.conta_a_atual -= valor * prop_a
            self.intraday.conta_b_atual -= valor * (1 - prop_a)

        self.salvar()
        return True

    def reset_dia(self, novo_saldo_a: float, novo_saldo_b: float):
        """Finaliza dia atual e inicia novo com saldos informados"""
        if not self.principal:
            return

        # Registrar dia no historico
        if self.intraday:
            self.principal.historico_dias.append({
                'data': self.intraday.data,
                'lucro_a': self.intraday.lucro_a,
                'lucro_b': self.intraday.lucro_b,
                'lucro_total': self.intraday.lucro_total,
                'migrou': self.intraday.conta_a_migrou,
            })
            self.principal.total_dias += 1

        # Criar novo intraday
        self.intraday = SessaoIntraday()
        self.intraday.data = date.today().isoformat()
        self.intraday.conta_a_inicio = novo_saldo_a
        self.intraday.conta_a_atual = novo_saldo_a
        self.intraday.conta_a_modo = 'NS9'  # Volta para NS9
        self.intraday.conta_b_inicio = novo_saldo_b
        self.intraday.conta_b_atual = novo_saldo_b

        self._verificar_pico()
        self.salvar()

    def get_status(self, usar_remoto: bool = True) -> Dict:
        """Retorna status completo para Telegram

        Args:
            usar_remoto: Se True, tenta usar dados remotos da CONSERVADORA (Windows)
        """
        if not self.principal or not self.intraday:
            return {'ativo': False}

        # Verificar dados remotos da CONSERVADORA
        remoto = None
        if usar_remoto:
            remoto = ler_estado_remoto_conservadora()

        # Se temos dados remotos, usar para Conta B
        if remoto and remoto.get('saldo_atual'):
            conta_b_atual = remoto.get('saldo_atual', self.intraday.conta_b_atual)
            conta_b_inicio = remoto.get('saldo_inicial', self.intraday.conta_b_inicio)
            conta_b_lucro = conta_b_atual - conta_b_inicio
            conta_b_lucro_pct = remoto.get('lucro_percentual', 0)
            remoto_online = conservadora_remota_online()
            remoto_timestamp = remoto.get('ultima_atualizacao', '')
        else:
            conta_b_atual = self.intraday.conta_b_atual
            conta_b_inicio = self.intraday.conta_b_inicio
            conta_b_lucro = self.intraday.lucro_b
            conta_b_lucro_pct = (self.intraday.lucro_b / self.intraday.conta_b_inicio * 100) if self.intraday.conta_b_inicio > 0 else 0
            remoto_online = False
            remoto_timestamp = ''

        total_atual = self.intraday.conta_a_atual + conta_b_atual
        lucro_total = total_atual + self.principal.total_saques - self.principal.deposito_inicial
        lucro_pct = (lucro_total / self.principal.deposito_inicial * 100) if self.principal.deposito_inicial > 0 else 0

        # Atualizar pico se necessário
        if total_atual > self.principal.banca_pico:
            self.principal.banca_pico = total_atual
            self.salvar()

        return {
            'ativo': True,
            'principal': {
                'sessao_id': self.principal.sessao_id,
                'deposito': self.principal.deposito_inicial,
                'saques': self.principal.total_saques,
                'banca_atual': total_atual,
                'lucro': lucro_total,
                'lucro_pct': lucro_pct,
                'pico': self.principal.banca_pico,
                'dias': self.principal.total_dias,
                'migracoes': self.principal.total_migracoes,
            },
            'intraday': {
                'data': self.intraday.data,
                'conta_a': {
                    'modo': self.intraday.conta_a_modo,
                    'inicio': self.intraday.conta_a_inicio,
                    'atual': self.intraday.conta_a_atual,
                    'lucro': self.intraday.lucro_a,
                    'lucro_pct': self.intraday.lucro_a_pct,
                    'migrou': self.intraday.conta_a_migrou,
                    'hora_migracao': self.intraday.conta_a_hora_migracao,
                },
                'conta_b': {
                    'modo': 'NS10',
                    'inicio': conta_b_inicio,
                    'atual': conta_b_atual,
                    'lucro': conta_b_lucro,
                    'lucro_pct': conta_b_lucro_pct,
                    'remoto': remoto is not None,
                    'remoto_online': remoto_online,
                    'remoto_timestamp': remoto_timestamp,
                },
                'lucro_total': self.intraday.lucro_a + conta_b_lucro,
            },
            'config': {
                'meta_migracao_pct': STOP_WIN_PCT,
                'media_ns9': MEDIA_DIARIA_NS9_PCT,
            },
        }


# ============================================================
# FUNCOES AUXILIARES
# ============================================================

def existe_sessao_dual_account() -> bool:
    return os.path.exists(DUAL_ACCOUNT_STATE_FILE)


def ler_estado_remoto_conservadora() -> Optional[Dict]:
    """Le o estado remoto da CONSERVADORA (enviado pelo Windows)"""
    try:
        if os.path.exists(CONSERVADORA_REMOTE_STATE_FILE):
            with open(CONSERVADORA_REMOTE_STATE_FILE, 'r') as f:
                data = json.load(f)
            return data
    except Exception as e:
        print(f"Erro ao ler estado remoto: {e}")
    return None


def conservadora_remota_online() -> bool:
    """Verifica se há dados recentes da CONSERVADORA remota (< 5 min)"""
    data = ler_estado_remoto_conservadora()
    if not data:
        return False

    try:
        ultima = datetime.fromisoformat(data.get('ultima_atualizacao', ''))
        diff = (datetime.now() - ultima).total_seconds()
        return diff < 300  # 5 minutos
    except:
        return False


if __name__ == "__main__":
    # Teste
    manager = DualAccountManager()

    if not manager.principal:
        print("Iniciando sessao: Conta A = R$ 2000, Conta B = R$ 2000")
        manager.iniciar_sessao(2000, 2000)

    status = manager.get_status()
    print(json.dumps(status, indent=2))
