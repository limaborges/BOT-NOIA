#!/usr/bin/env python3
"""
SIMULACAO REALISTA COM SAQUES DIARIOS
- Comeca com R$ 1000
- Compound ate atingir R$ 60k
- A partir dai, saca diariamente (max R$ 50k/dia)
- Mantem R$ 60k operando

Compara NS7 pura vs NS7+Alertas
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple
from collections import deque, defaultdict
from datetime import datetime
import statistics

# ==============================================================================
# CONSTANTES
# ==============================================================================

ALVO_LUCRO = 1.99
ALVO_DEFESA = 1.10
ALVO_ULTIMA = 2.50
THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6

NIVEIS = {
    7: {'nome': 'NS7', 'divisor': 127, 'tentativas': 7},
    8: {'nome': 'NS8', 'divisor': 255, 'tentativas': 8},
}

# Configuracao de saques
BANCA_INICIAL = 1000.0
BANCA_ALVO = 60000.0      # Manter este valor operando
SAQUE_VALOR = 5000.0      # Valor de cada saque
SAQUE_TRIGGER = 65000.0   # Sacar quando banca passar deste valor
SAQUES_MAX_DIA = 50       # Aumentar limite para manter banca controlada

# Alertas
JANELA_MULTS = 300
JANELA_GATILHOS = 30
ALERTA_TAXA_ALTOS = 0.42
ALERTA_TAXA_T5_PLUS = 0.10
ALERTA_TAXA_T6_PLUS = 0.06
ALERTAS_PARA_TROCAR = 2


# ==============================================================================
# SIMULADOR
# ==============================================================================

@dataclass
class ConfigTentativa:
    slots: int
    alvo_lucro: float
    alvo_defesa: float
    is_parar: bool = False
    is_ultima: bool = False


class SimuladorRealista:
    def __init__(self, usar_alertas: bool = False):
        self.usar_alertas = usar_alertas

        # Banca
        self.banca = BANCA_INICIAL
        self.banca_maxima = BANCA_INICIAL
        self.nivel_atual = 7

        # Saques
        self.total_sacado = 0.0
        self.saques_por_dia: Dict[str, float] = {}
        self.dias_com_saque = 0
        self.saques_hoje = 0  # Contador de saques no dia atual

        # Historico para alertas
        self.historico_mults: deque = deque(maxlen=JANELA_MULTS * 2)
        self.historico_gatilhos: List[int] = []

        # Contadores
        self.gatilhos_total = 0
        self.gatilhos_ns7 = 0
        self.gatilhos_ns8 = 0
        self.busts = 0
        self.trocas_para_ns8 = 0

        # Drawdown
        self.drawdown_max_pct = 0

        # Tracking diario
        self.banca_inicio_dia = BANCA_INICIAL
        self.lucro_dia = 0

    def _get_config(self, nivel: int, tentativa: int) -> ConfigTentativa:
        max_t = NIVEIS[nivel]['tentativas']
        if tentativa == max_t:
            return ConfigTentativa(slots=2, alvo_lucro=ALVO_ULTIMA, alvo_defesa=ALVO_DEFESA, is_ultima=True)
        elif tentativa == max_t - 1:
            return ConfigTentativa(slots=2, alvo_lucro=ALVO_LUCRO, alvo_defesa=ALVO_DEFESA, is_parar=True)
        else:
            return ConfigTentativa(slots=1, alvo_lucro=ALVO_LUCRO, alvo_defesa=0)

    def _calcular_alertas(self) -> int:
        if len(self.historico_mults) < 100 or len(self.historico_gatilhos) < 10:
            return 0

        alertas = 0

        # Taxa de altos
        mults_recentes = list(self.historico_mults)[-JANELA_MULTS:]
        if len(mults_recentes) >= 100:
            taxa = sum(1 for m in mults_recentes if m >= 2.0) / len(mults_recentes)
            if taxa < ALERTA_TAXA_ALTOS:
                alertas += 1

        # Taxa T5+
        gatilhos = self.historico_gatilhos[-JANELA_GATILHOS:]
        if len(gatilhos) >= 10:
            t5_plus = sum(1 for t in gatilhos if t >= 5)
            if t5_plus / len(gatilhos) > ALERTA_TAXA_T5_PLUS:
                alertas += 1

            t6_plus = sum(1 for t in gatilhos if t >= 6)
            if t6_plus / len(gatilhos) > ALERTA_TAXA_T6_PLUS:
                alertas += 1

        return alertas

    def _decidir_nivel(self) -> int:
        if not self.usar_alertas:
            return 7

        if self._calcular_alertas() >= ALERTAS_PARA_TROCAR:
            if self.nivel_atual == 7:
                self.trocas_para_ns8 += 1
            return 8
        return 7

    def _tentar_saque(self, data: str):
        """Tenta fazer saque se banca passou do trigger e ainda tem saques disponiveis no dia"""
        while self.banca >= SAQUE_TRIGGER and self.saques_hoje < SAQUES_MAX_DIA:
            self.banca -= SAQUE_VALOR
            self.total_sacado += SAQUE_VALOR
            self.saques_hoje += 1

            if data not in self.saques_por_dia:
                self.saques_por_dia[data] = 0
            self.saques_por_dia[data] += SAQUE_VALOR

    def _processar_fim_dia(self, data: str):
        """Processa fim do dia"""
        if self.saques_hoje > 0:
            self.dias_com_saque += 1

        # Reset para proximo dia
        self.saques_hoje = 0
        self.banca_inicio_dia = self.banca
        self.lucro_dia = 0

    def _executar_gatilho(self, multiplicadores: List[float], pos_inicio: int, nivel: int) -> int:
        """Executa gatilho e retorna tentativa final"""
        self.gatilhos_total += 1

        if nivel == 7:
            self.gatilhos_ns7 += 1
        else:
            self.gatilhos_ns8 += 1

        max_t = NIVEIS[nivel]['tentativas']
        divisor = NIVEIS[nivel]['divisor']
        aposta_base = self.banca / divisor

        investido = 0
        retorno = 0
        tentativa_final = 0

        for t in range(1, max_t + 1):
            idx = pos_inicio + t - 1
            if idx >= len(multiplicadores):
                break

            mult = multiplicadores[idx]
            config = self._get_config(nivel, t)

            aposta = aposta_base * (2 ** (t - 1)) * config.slots
            investido += aposta
            tentativa_final = t

            self.historico_mults.append(mult)

            if config.slots == 1:
                if mult >= config.alvo_lucro:
                    retorno = aposta * config.alvo_lucro
                    break
            else:
                if config.is_ultima:
                    if mult >= config.alvo_lucro:
                        retorno = aposta * config.alvo_lucro
                        break
                    elif mult >= config.alvo_defesa:
                        retorno = aposta * config.alvo_defesa
                        break
                    else:
                        self.busts += 1
                        break
                else:
                    if mult >= config.alvo_lucro:
                        retorno = aposta * config.alvo_lucro
                        break
                    elif mult >= config.alvo_defesa:
                        retorno = aposta * config.alvo_defesa
                        break

        lucro = retorno - investido
        self.banca += lucro
        self.lucro_dia += lucro

        if self.banca > self.banca_maxima:
            self.banca_maxima = self.banca

        dd = ((self.banca_maxima - self.banca) / self.banca_maxima) * 100 if self.banca_maxima > 0 else 0
        if dd > self.drawdown_max_pct:
            self.drawdown_max_pct = dd

        self.historico_gatilhos.append(tentativa_final)

        return tentativa_final

    def simular(self, dados_por_dia: Dict[str, List[float]]) -> Dict:
        """Simula dia a dia"""
        for data in sorted(dados_por_dia.keys()):
            multiplicadores = dados_por_dia[data]

            self.banca_inicio_dia = self.banca
            self.lucro_dia = 0
            self.saques_hoje = 0  # Reset saques do dia

            # Processar multiplicadores do dia
            baixos = 0
            i = 0

            while i < len(multiplicadores):
                mult = multiplicadores[i]
                self.historico_mults.append(mult)

                if mult < THRESHOLD_BAIXO:
                    baixos += 1
                    if baixos == GATILHO_SIZE:
                        nivel = self._decidir_nivel()
                        self.nivel_atual = nivel

                        # Criar lista completa para o gatilho
                        mults_completo = multiplicadores[i+1:]
                        if len(mults_completo) > 0:
                            tent_final = self._executar_gatilho(multiplicadores, i + 1, nivel)
                            i += tent_final

                            # TENTAR SAQUE APOS CADA GATILHO
                            self._tentar_saque(data)

                        baixos = 0
                else:
                    baixos = 0

                i += 1

                if self.banca <= 0:
                    return self._gerar_relatorio()

            # Fim do dia
            self._processar_fim_dia(data)

        return self._gerar_relatorio()

    def _gerar_relatorio(self) -> Dict:
        return {
            'banca_final': self.banca,
            'total_sacado': self.total_sacado,
            'patrimonio_total': self.banca + self.total_sacado,
            'dias_com_saque': self.dias_com_saque,
            'media_saque_dia': self.total_sacado / self.dias_com_saque if self.dias_com_saque > 0 else 0,
            'gatilhos': self.gatilhos_total,
            'gatilhos_ns7': self.gatilhos_ns7,
            'gatilhos_ns8': self.gatilhos_ns8,
            'busts': self.busts,
            'drawdown_max_pct': self.drawdown_max_pct,
            'trocas_ns8': self.trocas_para_ns8,
        }


# ==============================================================================
# MAIN
# ==============================================================================

def carregar_por_dia(filepath: str) -> Dict[str, List[float]]:
    """Carrega multiplicadores agrupados por dia"""
    dias = defaultdict(list)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()  # DD/MM/YYYY
                    dias[data].append(mult)
            except:
                continue

    return dict(dias)


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("=" * 100)
    print("SIMULACAO REALISTA COM SAQUES DIARIOS")
    print("=" * 100)
    print(f"Banca inicial: R$ {BANCA_INICIAL:,.2f}")
    print(f"Banca alvo (manter operando): R$ {BANCA_ALVO:,.2f}")
    print(f"Trigger de saque: R$ {SAQUE_TRIGGER:,.2f}")
    print(f"Valor por saque: R$ {SAQUE_VALOR:,.2f}")
    print(f"Max saques/dia: {SAQUES_MAX_DIA} (= R$ {SAQUES_MAX_DIA * SAQUE_VALOR:,.2f}/dia)")
    print()

    print("Carregando dados...")
    dados_por_dia = carregar_por_dia(csv_path)

    # Filtrar 2025 em diante
    dados_filtrados = {k: v for k, v in dados_por_dia.items()
                       if datetime.strptime(k, '%d/%m/%Y').year >= 2025}

    dias_total = len(dados_filtrados)
    mults_total = sum(len(v) for v in dados_filtrados.values())

    print(f"Periodo: {min(dados_filtrados.keys())} a {max(dados_filtrados.keys())}")
    print(f"Total dias: {dias_total}")
    print(f"Total multiplicadores: {mults_total:,}")
    print()

    # NS7 PURA
    print("-" * 100)
    print("Simulando NS7 PURA...")
    sim_ns7 = SimuladorRealista(usar_alertas=False)
    rel_ns7 = sim_ns7.simular(dados_filtrados)
    print(f"  Concluido: {rel_ns7['gatilhos']:,} gatilhos")

    # NS7 + ALERTAS
    print("-" * 100)
    print("Simulando NS7 + ALERTAS...")
    sim_alerta = SimuladorRealista(usar_alertas=True)
    rel_alerta = sim_alerta.simular(dados_filtrados)
    print(f"  Concluido: {rel_alerta['gatilhos']:,} gatilhos")

    # RESULTADO
    print()
    print("=" * 100)
    print("RESULTADO COMPARATIVO")
    print("=" * 100)

    print(f"\n{'METRICA':<35} {'NS7 PURA':>25} {'NS7+ALERTAS':>25}")
    print("-" * 90)
    print(f"{'Banca Final':<35} R${rel_ns7['banca_final']:>22,.2f} R${rel_alerta['banca_final']:>22,.2f}")
    print(f"{'Total Sacado':<35} R${rel_ns7['total_sacado']:>22,.2f} R${rel_alerta['total_sacado']:>22,.2f}")
    print(f"{'PATRIMONIO TOTAL':<35} R${rel_ns7['patrimonio_total']:>22,.2f} R${rel_alerta['patrimonio_total']:>22,.2f}")
    print("-" * 90)
    print(f"{'Dias com saque':<35} {rel_ns7['dias_com_saque']:>25} {rel_alerta['dias_com_saque']:>25}")
    print(f"{'Media saque/dia':<35} R${rel_ns7['media_saque_dia']:>22,.2f} R${rel_alerta['media_saque_dia']:>22,.2f}")
    print("-" * 90)
    print(f"{'Drawdown Maximo':<35} {rel_ns7['drawdown_max_pct']:>24.2f}% {rel_alerta['drawdown_max_pct']:>24.2f}%")
    print(f"{'Busts':<35} {rel_ns7['busts']:>25} {rel_alerta['busts']:>25}")
    print("-" * 90)
    print(f"{'Total Gatilhos':<35} {rel_ns7['gatilhos']:>25,} {rel_alerta['gatilhos']:>25,}")
    print(f"{'Gatilhos NS7':<35} {rel_ns7['gatilhos']:>25,} {rel_alerta['gatilhos_ns7']:>25,}")
    print(f"{'Gatilhos NS8':<35} {0:>25} {rel_alerta['gatilhos_ns8']:>25,}")

    if rel_alerta['gatilhos'] > 0:
        pct_ns8 = rel_alerta['gatilhos_ns8'] / rel_alerta['gatilhos'] * 100
        print(f"{'% em NS8':<35} {'-':>25} {pct_ns8:>24.1f}%")

    # VEREDITO
    print()
    print("=" * 100)
    print("VEREDITO")
    print("=" * 100)

    diff_sacado = rel_alerta['total_sacado'] - rel_ns7['total_sacado']
    diff_patrimonio = rel_alerta['patrimonio_total'] - rel_ns7['patrimonio_total']
    diff_dd = rel_alerta['drawdown_max_pct'] - rel_ns7['drawdown_max_pct']

    print(f"\n  Diferenca Total Sacado: {'+'if diff_sacado>=0 else ''}R$ {diff_sacado:,.2f}")
    print(f"  Diferenca Patrimonio: {'+'if diff_patrimonio>=0 else ''}R$ {diff_patrimonio:,.2f}")
    print(f"  Diferenca Drawdown: {'+'if diff_dd>=0 else ''}{diff_dd:.2f}pp")

    print("\n" + "-" * 100)

    if diff_patrimonio > 0 and diff_dd <= 0:
        print("  >> ALERTAS SUPERIORES: Mais patrimonio com igual ou menos drawdown")
    elif diff_patrimonio > 0:
        print(f"  >> ALERTAS MAIS LUCRATIVOS: +R$ {diff_patrimonio:,.0f}")
    elif diff_dd < -5:
        print(f"  >> ALERTAS MAIS SEGUROS: -{-diff_dd:.1f}pp de drawdown")
        print(f"     Custou R$ {-diff_patrimonio:,.0f} de patrimonio")
    else:
        print("  >> NS7 PURA FOI MELHOR")

    # Projecao mensal
    print("\n" + "-" * 100)
    print("PROJECAO:")
    print("-" * 100)
    dias_operados = dias_total
    meses = dias_operados / 30

    print(f"\n  NS7 PURA:")
    print(f"    Saque total em {dias_operados} dias: R$ {rel_ns7['total_sacado']:,.2f}")
    print(f"    Media mensal: R$ {rel_ns7['total_sacado']/meses:,.2f}")
    print(f"    Media diaria: R$ {rel_ns7['total_sacado']/dias_operados:,.2f}")

    print(f"\n  NS7 + ALERTAS:")
    print(f"    Saque total em {dias_operados} dias: R$ {rel_alerta['total_sacado']:,.2f}")
    print(f"    Media mensal: R$ {rel_alerta['total_sacado']/meses:,.2f}")
    print(f"    Media diaria: R$ {rel_alerta['total_sacado']/dias_operados:,.2f}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
