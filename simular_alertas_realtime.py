#!/usr/bin/env python3
"""
SIMULACAO REALTIME - EFETIVIDADE DOS ALERTAS
Simulacao causal: cada decisao eh tomada APENAS com dados do passado.
Rodada a rodada, como o bot operaria em tempo real.

IMPORTANTE: Nenhuma informacao futura eh usada nas decisoes.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from collections import deque
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

# ==============================================================================
# CONFIGURACAO DE ALERTAS (parametros para testar)
# ==============================================================================

JANELA_MULTS = 300        # Ultimos N multiplicadores para calcular taxa de altos
JANELA_GATILHOS = 30      # Ultimos N gatilhos para calcular taxa T5+/T6+

ALERTA_TAXA_ALTOS = 0.42      # < 42% de mult >= 2.0 = ALERTA
ALERTA_TAXA_T5_PLUS = 0.10    # > 10% de T5+ = ALERTA
ALERTA_TAXA_T6_PLUS = 0.06    # > 6% de T6+ = ALERTA
ALERTA_VOLATILIDADE = 1.25    # Aumento de 25% na volatilidade = ALERTA

ALERTAS_PARA_TROCAR = 2  # Quantos alertas ativos para mudar NS7 -> NS8


# ==============================================================================
# SIMULADOR REALTIME
# ==============================================================================

@dataclass
class ConfigTentativa:
    slots: int
    alvo_lucro: float
    alvo_defesa: float
    is_parar: bool = False
    is_ultima: bool = False


class SimuladorRealtime:
    """
    Simulador que processa rodada a rodada.
    Todas as decisoes sao tomadas com base APENAS no historico passado.
    """

    def __init__(self, banca_inicial: float, usar_alertas: bool, usar_compound: bool = False):
        self.banca_inicial = banca_inicial
        self.usar_alertas = usar_alertas
        self.usar_compound = usar_compound

        # Estado
        self.banca = banca_inicial
        self.banca_maxima = banca_inicial
        self.nivel_atual = 7

        # Historico (apenas dados passados)
        self.historico_mults: deque = deque(maxlen=JANELA_MULTS * 2)  # Guardar mais para volatilidade
        self.historico_gatilhos: List[int] = []  # Lista de tentativas finais

        # Contadores
        self.gatilhos_total = 0
        self.gatilhos_ns7 = 0
        self.gatilhos_ns8 = 0
        self.wins = 0
        self.busts = 0
        self.trocas_para_ns8 = 0
        self.alertas_disparados = 0

        # Tracking
        self.drawdown_max_pct = 0
        self.lucro_ns7 = 0
        self.lucro_ns8 = 0

        # Log de decisoes (para debug)
        self.log_decisoes: List[Dict] = []

    def _get_config(self, nivel: int, tentativa: int) -> ConfigTentativa:
        max_t = NIVEIS[nivel]['tentativas']

        if tentativa == max_t:
            return ConfigTentativa(slots=2, alvo_lucro=ALVO_ULTIMA, alvo_defesa=ALVO_DEFESA, is_ultima=True)
        elif tentativa == max_t - 1:
            return ConfigTentativa(slots=2, alvo_lucro=ALVO_LUCRO, alvo_defesa=ALVO_DEFESA, is_parar=True)
        else:
            return ConfigTentativa(slots=1, alvo_lucro=ALVO_LUCRO, alvo_defesa=0)

    def _calcular_alertas_agora(self) -> Tuple[int, List[str]]:
        """
        Calcula alertas com base APENAS no historico atual.
        Chamado ANTES de cada gatilho para decidir qual nivel usar.
        """
        alertas = []

        # Precisamos de historico minimo
        if len(self.historico_mults) < 100 or len(self.historico_gatilhos) < 10:
            return 0, alertas

        # 1. Taxa de multiplicadores altos (ultimos JANELA_MULTS)
        mults_recentes = list(self.historico_mults)[-JANELA_MULTS:]
        if len(mults_recentes) >= 100:
            taxa_altos = sum(1 for m in mults_recentes if m >= 2.0) / len(mults_recentes)
            if taxa_altos < ALERTA_TAXA_ALTOS:
                alertas.append(f"BAIXOS={taxa_altos*100:.1f}%")

        # 2. Taxa de T5+ nos ultimos gatilhos
        gatilhos_recentes = self.historico_gatilhos[-JANELA_GATILHOS:]
        if len(gatilhos_recentes) >= 10:
            t5_plus = sum(1 for t in gatilhos_recentes if t >= 5)
            taxa_t5 = t5_plus / len(gatilhos_recentes)
            if taxa_t5 > ALERTA_TAXA_T5_PLUS:
                alertas.append(f"T5+={taxa_t5*100:.1f}%")

            # 3. Taxa de T6+
            t6_plus = sum(1 for t in gatilhos_recentes if t >= 6)
            taxa_t6 = t6_plus / len(gatilhos_recentes)
            if taxa_t6 > ALERTA_TAXA_T6_PLUS:
                alertas.append(f"T6+={taxa_t6*100:.1f}%")

        # 4. Aumento de volatilidade
        if len(self.historico_mults) >= 400:
            mults_recente = list(self.historico_mults)[-200:]
            mults_anterior = list(self.historico_mults)[-400:-200]

            if len(mults_recente) > 1 and len(mults_anterior) > 1:
                vol_recente = statistics.stdev(mults_recente)
                vol_anterior = statistics.stdev(mults_anterior)

                if vol_anterior > 0 and vol_recente > vol_anterior * ALERTA_VOLATILIDADE:
                    alertas.append(f"VOL+{((vol_recente/vol_anterior)-1)*100:.0f}%")

        return len(alertas), alertas

    def _decidir_nivel_para_proximo_gatilho(self) -> Tuple[int, int, List[str]]:
        """
        Decide qual nivel usar ANTES do gatilho comecar.
        Retorna (nivel, num_alertas, lista_alertas)
        """
        if not self.usar_alertas:
            return 7, 0, []

        num_alertas, alertas = self._calcular_alertas_agora()

        if num_alertas >= ALERTAS_PARA_TROCAR:
            self.alertas_disparados += 1
            if self.nivel_atual == 7:
                self.trocas_para_ns8 += 1
            return 8, num_alertas, alertas
        else:
            return 7, num_alertas, alertas

    def simular(self, multiplicadores: List[float]) -> Dict:
        """
        Simula rodada a rodada.
        Cada multiplicador eh processado sequencialmente.
        Decisoes sao tomadas apenas com dados passados.
        """
        baixos_consecutivos = 0
        pos = 0

        while pos < len(multiplicadores):
            mult = multiplicadores[pos]

            # REGISTRAR NO HISTORICO (dados passados)
            self.historico_mults.append(mult)

            if mult < THRESHOLD_BAIXO:
                baixos_consecutivos += 1

                # GATILHO ATIVADO?
                if baixos_consecutivos == GATILHO_SIZE:
                    # DECISAO: Qual nivel usar?
                    # Esta decisao eh tomada AGORA, ANTES de saber os proximos multiplicadores
                    nivel, num_alertas, alertas = self._decidir_nivel_para_proximo_gatilho()
                    self.nivel_atual = nivel

                    # Processar gatilho
                    pos_gatilho_inicio = pos + 1
                    resultado = self._executar_gatilho(multiplicadores, pos_gatilho_inicio, nivel)

                    # Log da decisao
                    self.log_decisoes.append({
                        'gatilho': self.gatilhos_total,
                        'nivel': nivel,
                        'alertas': num_alertas,
                        'lista_alertas': alertas,
                        'tentativa_final': resultado['tentativa_final'],
                        'resultado': resultado['resultado'],
                        'lucro': resultado['lucro']
                    })

                    # Avancar posicao
                    pos = pos_gatilho_inicio + resultado['tentativa_final'] - 1
                    baixos_consecutivos = 0

            else:
                baixos_consecutivos = 0

            pos += 1

            # Bust total?
            if self.banca <= 0:
                break

        return self._gerar_relatorio()

    def _executar_gatilho(self, multiplicadores: List[float], pos_inicio: int, nivel: int) -> Dict:
        """Executa um gatilho no nivel especificado"""
        self.gatilhos_total += 1

        if nivel == 7:
            self.gatilhos_ns7 += 1
        else:
            self.gatilhos_ns8 += 1

        max_tentativas = NIVEIS[nivel]['tentativas']
        divisor = NIVEIS[nivel]['divisor']

        # Banca fixa ou compound
        if self.usar_compound:
            aposta_base = self.banca / divisor
        else:
            aposta_base = self.banca_inicial / divisor

        investido = 0
        retorno = 0
        tentativa_final = 0
        resultado = ''

        for t in range(1, max_tentativas + 1):
            idx = pos_inicio + t - 1
            if idx >= len(multiplicadores):
                # Fim dos dados
                resultado = 'incompleto'
                tentativa_final = t
                break

            mult = multiplicadores[idx]
            config = self._get_config(nivel, t)

            # Aposta desta tentativa
            aposta = aposta_base * (2 ** (t - 1)) * config.slots
            investido += aposta
            tentativa_final = t

            # Registrar mult no historico
            self.historico_mults.append(mult)

            # Avaliar
            if config.slots == 1:
                if mult >= config.alvo_lucro:
                    retorno = aposta * config.alvo_lucro
                    resultado = 'win'
                    break
            else:
                if config.is_ultima:
                    if mult >= config.alvo_lucro:
                        retorno = aposta * config.alvo_lucro
                        resultado = 'win'
                        break
                    elif mult >= config.alvo_defesa:
                        retorno = aposta * config.alvo_defesa
                        resultado = 'win_parcial'
                        break
                    else:
                        resultado = 'bust'
                        break
                else:  # Penultima - PARAR
                    if mult >= config.alvo_lucro:
                        retorno = aposta * config.alvo_lucro
                        resultado = 'win'
                        break
                    elif mult >= config.alvo_defesa:
                        retorno = aposta * config.alvo_defesa
                        resultado = 'parar'
                        break

        lucro = retorno - investido

        # Atualizar banca
        self.banca += lucro
        if self.banca > self.banca_maxima:
            self.banca_maxima = self.banca

        dd_pct = ((self.banca_maxima - self.banca) / self.banca_maxima) * 100 if self.banca_maxima > 0 else 0
        if dd_pct > self.drawdown_max_pct:
            self.drawdown_max_pct = dd_pct

        # Contadores
        if resultado in ['win', 'win_parcial']:
            self.wins += 1
        elif resultado == 'bust':
            self.busts += 1

        if nivel == 7:
            self.lucro_ns7 += lucro
        else:
            self.lucro_ns8 += lucro

        # Registrar tentativa final no historico de gatilhos
        self.historico_gatilhos.append(tentativa_final)

        return {
            'tentativa_final': tentativa_final,
            'resultado': resultado,
            'lucro': lucro
        }

    def _gerar_relatorio(self) -> Dict:
        return {
            'banca_final': self.banca,
            'lucro': self.banca - self.banca_inicial,
            'ganho_pct': ((self.banca / self.banca_inicial) - 1) * 100 if self.banca_inicial > 0 else 0,
            'gatilhos': self.gatilhos_total,
            'gatilhos_ns7': self.gatilhos_ns7,
            'gatilhos_ns8': self.gatilhos_ns8,
            'wins': self.wins,
            'busts': self.busts,
            'drawdown_max_pct': self.drawdown_max_pct,
            'trocas_para_ns8': self.trocas_para_ns8,
            'alertas_disparados': self.alertas_disparados,
            'lucro_ns7': self.lucro_ns7,
            'lucro_ns8': self.lucro_ns8,
        }


# ==============================================================================
# MAIN
# ==============================================================================

def carregar_multiplicadores(filepath: str) -> List[float]:
    multiplicadores = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)
        for line in f:
            try:
                parts = line.strip().split(',')
                if parts:
                    multiplicadores.append(float(parts[0]))
            except:
                continue
    return multiplicadores


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'
    banca = 1000.0

    print("=" * 100)
    print("SIMULACAO REALTIME - EFETIVIDADE DOS ALERTAS")
    print("Cada decisao eh tomada APENAS com dados passados (causal)")
    print("COM COMPOUND - Banca recalculada a cada gatilho")
    print("=" * 100)
    print()
    print("PARAMETROS DOS ALERTAS:")
    print(f"  Janela multiplicadores: {JANELA_MULTS}")
    print(f"  Janela gatilhos: {JANELA_GATILHOS}")
    print(f"  Alerta taxa altos: < {ALERTA_TAXA_ALTOS*100:.0f}%")
    print(f"  Alerta T5+: > {ALERTA_TAXA_T5_PLUS*100:.0f}%")
    print(f"  Alerta T6+: > {ALERTA_TAXA_T6_PLUS*100:.0f}%")
    print(f"  Alerta volatilidade: > {(ALERTA_VOLATILIDADE-1)*100:.0f}%")
    print(f"  Alertas para trocar: {ALERTAS_PARA_TROCAR}+")
    print()

    print("Carregando dados...")
    multiplicadores = carregar_multiplicadores(csv_path)
    print(f"Total: {len(multiplicadores):,} multiplicadores")
    print()

    # NS7 PURA
    print("-" * 100)
    print("Simulando NS7 PURA (COM COMPOUND)...")
    sim_ns7 = SimuladorRealtime(banca_inicial=banca, usar_alertas=False, usar_compound=True)
    rel_ns7 = sim_ns7.simular(multiplicadores)
    print(f"  Concluido: {rel_ns7['gatilhos']:,} gatilhos")

    # NS7 + ALERTAS
    print("-" * 100)
    print("Simulando NS7 + ALERTAS (COM COMPOUND)...")
    sim_alerta = SimuladorRealtime(banca_inicial=banca, usar_alertas=True, usar_compound=True)
    rel_alerta = sim_alerta.simular(multiplicadores)
    print(f"  Concluido: {rel_alerta['gatilhos']:,} gatilhos")

    # COMPARATIVO
    print()
    print("=" * 100)
    print("RESULTADO COMPARATIVO")
    print("=" * 100)

    print(f"\n{'METRICA':<35} {'NS7 PURA':>25} {'NS7+ALERTAS':>25}")
    print("-" * 90)
    print(f"{'Banca Inicial':<35} R${banca:>22,.2f} R${banca:>22,.2f}")
    print(f"{'Banca Final':<35} R${rel_ns7['banca_final']:>22,.2f} R${rel_alerta['banca_final']:>22,.2f}")
    print(f"{'Lucro':<35} R${rel_ns7['lucro']:>22,.2f} R${rel_alerta['lucro']:>22,.2f}")
    print(f"{'Ganho %':<35} {rel_ns7['ganho_pct']:>24.2f}% {rel_alerta['ganho_pct']:>24.2f}%")
    print(f"{'Drawdown Max':<35} {rel_ns7['drawdown_max_pct']:>24.2f}% {rel_alerta['drawdown_max_pct']:>24.2f}%")
    print(f"{'Busts':<35} {rel_ns7['busts']:>25} {rel_alerta['busts']:>25}")
    print("-" * 90)
    print(f"{'Total Gatilhos':<35} {rel_ns7['gatilhos']:>25,} {rel_alerta['gatilhos']:>25,}")
    print(f"{'Gatilhos NS7':<35} {rel_ns7['gatilhos']:>25,} {rel_alerta['gatilhos_ns7']:>25,}")
    print(f"{'Gatilhos NS8':<35} {0:>25} {rel_alerta['gatilhos_ns8']:>25,}")
    print(f"{'Trocas para NS8':<35} {'-':>25} {rel_alerta['trocas_para_ns8']:>25,}")
    print(f"{'Alertas Disparados':<35} {'-':>25} {rel_alerta['alertas_disparados']:>25,}")

    if rel_alerta['gatilhos_ns8'] > 0:
        pct_ns8 = rel_alerta['gatilhos_ns8'] / rel_alerta['gatilhos'] * 100
        print(f"{'% em NS8':<35} {'-':>25} {pct_ns8:>24.2f}%")

        print("-" * 90)
        print(f"{'Lucro nos gatilhos NS7':<35} R${rel_ns7['lucro']:>22,.2f} R${rel_alerta['lucro_ns7']:>22,.2f}")
        print(f"{'Lucro nos gatilhos NS8':<35} {'-':>25} R${rel_alerta['lucro_ns8']:>22,.2f}")

    # VEREDITO
    print()
    print("=" * 100)
    print("VEREDITO")
    print("=" * 100)

    diff_lucro = rel_alerta['lucro'] - rel_ns7['lucro']
    diff_dd = rel_alerta['drawdown_max_pct'] - rel_ns7['drawdown_max_pct']
    diff_busts = rel_alerta['busts'] - rel_ns7['busts']

    print(f"\n  Diferenca Lucro:    {'+'if diff_lucro>=0 else ''}R$ {diff_lucro:,.2f}")
    print(f"  Diferenca Drawdown: {'+'if diff_dd>=0 else ''}{diff_dd:.2f} pp")
    print(f"  Diferenca Busts:    {'+'if diff_busts>=0 else ''}{diff_busts}")

    # Analise de quando NS8 foi usado
    if sim_alerta.log_decisoes:
        decisoes_ns8 = [d for d in sim_alerta.log_decisoes if d['nivel'] == 8]
        if decisoes_ns8:
            print()
            print("-" * 100)
            print("ANALISE DOS MOMENTOS EM NS8:")
            print("-" * 100)

            # Distribuicao de tentativas finais quando em NS8
            from collections import Counter
            tent_ns8 = Counter(d['tentativa_final'] for d in decisoes_ns8)
            print("\n  Distribuicao de tentativas finais em NS8:")
            for t in sorted(tent_ns8.keys()):
                pct = tent_ns8[t] / len(decisoes_ns8) * 100
                print(f"    T{t}: {tent_ns8[t]:>5} ({pct:>5.1f}%)")

            # Quantos T6+ evitados?
            t6_plus_ns8 = sum(1 for d in decisoes_ns8 if d['tentativa_final'] >= 6)
            print(f"\n  Gatilhos T6+ quando em NS8: {t6_plus_ns8} ({t6_plus_ns8/len(decisoes_ns8)*100:.1f}%)")

    print()
    print("-" * 100)

    if diff_lucro > 0 and diff_dd < 0:
        print("  >> ALERTAS EFETIVOS: Mais lucro E menos drawdown")
    elif diff_lucro > 0:
        print(f"  >> ALERTAS MAIS LUCRATIVOS: +R$ {diff_lucro:,.0f}")
        if diff_dd > 0:
            print(f"     Porem com +{diff_dd:.1f}pp de drawdown")
    elif diff_dd < -5:
        print(f"  >> ALERTAS MAIS SEGUROS: -{-diff_dd:.1f}pp de drawdown")
        print(f"     Mas custou R$ {-diff_lucro:,.0f} de lucro")
    else:
        print(f"  >> NS7 PURA FOI MELHOR neste dataset")

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()
