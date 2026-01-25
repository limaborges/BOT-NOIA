#!/usr/bin/env python3
"""
INVESTIGACAO DOS DRAWDOWNS
Identifica quando ocorreram os maiores drawdowns e analisa se alertas poderiam prever
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple
from collections import deque, defaultdict
from datetime import datetime
import statistics

# Constantes
ALVO_LUCRO = 1.99
ALVO_DEFESA = 1.10
ALVO_ULTIMA = 2.50
THRESHOLD_BAIXO = 2.0
GATILHO_SIZE = 6

NIVEIS = {
    7: {'divisor': 127, 'tentativas': 7},
    8: {'divisor': 255, 'tentativas': 8},
}

BANCA_INICIAL = 1000.0
BANCA_ALVO = 60000.0
SAQUE_VALOR = 5000.0
SAQUE_TRIGGER = 65000.0
SAQUES_MAX_DIA = 50

# Alertas
JANELA_MULTS = 300
JANELA_GATILHOS = 30
ALERTA_TAXA_ALTOS = 0.42
ALERTA_TAXA_T5_PLUS = 0.10
ALERTA_TAXA_T6_PLUS = 0.06


@dataclass
class ConfigTentativa:
    slots: int
    alvo_lucro: float
    alvo_defesa: float
    is_parar: bool = False
    is_ultima: bool = False


@dataclass
class DrawdownEvent:
    data: str
    gatilho_num: int
    banca_antes: float
    banca_depois: float
    banca_pico: float
    drawdown_pct: float
    tentativa_final: int
    nivel_usado: int
    alertas_ativos: int
    taxa_altos: float
    taxa_t5: float


class InvestigadorDrawdowns:
    def __init__(self):
        self.banca = BANCA_INICIAL
        self.banca_maxima = BANCA_INICIAL
        self.nivel_atual = 7

        self.historico_mults: deque = deque(maxlen=JANELA_MULTS * 2)
        self.historico_gatilhos: List[int] = []

        self.gatilhos_total = 0
        self.saques_hoje = 0
        self.total_sacado = 0

        # Tracking de drawdowns
        self.drawdown_events: List[DrawdownEvent] = []
        self.drawdown_max_pct = 0

    def _get_config(self, nivel: int, tentativa: int) -> ConfigTentativa:
        max_t = NIVEIS[nivel]['tentativas']
        if tentativa == max_t:
            return ConfigTentativa(slots=2, alvo_lucro=ALVO_ULTIMA, alvo_defesa=ALVO_DEFESA, is_ultima=True)
        elif tentativa == max_t - 1:
            return ConfigTentativa(slots=2, alvo_lucro=ALVO_LUCRO, alvo_defesa=ALVO_DEFESA, is_parar=True)
        else:
            return ConfigTentativa(slots=1, alvo_lucro=ALVO_LUCRO, alvo_defesa=0)

    def _calcular_metricas(self) -> Tuple[int, float, float]:
        """Retorna (alertas_ativos, taxa_altos, taxa_t5)"""
        if len(self.historico_mults) < 100 or len(self.historico_gatilhos) < 10:
            return 0, 0, 0

        alertas = 0

        mults_recentes = list(self.historico_mults)[-JANELA_MULTS:]
        taxa_altos = sum(1 for m in mults_recentes if m >= 2.0) / len(mults_recentes) if mults_recentes else 0

        if taxa_altos < ALERTA_TAXA_ALTOS:
            alertas += 1

        gatilhos = self.historico_gatilhos[-JANELA_GATILHOS:]
        taxa_t5 = sum(1 for t in gatilhos if t >= 5) / len(gatilhos) if gatilhos else 0
        taxa_t6 = sum(1 for t in gatilhos if t >= 6) / len(gatilhos) if gatilhos else 0

        if taxa_t5 > ALERTA_TAXA_T5_PLUS:
            alertas += 1
        if taxa_t6 > ALERTA_TAXA_T6_PLUS:
            alertas += 1

        return alertas, taxa_altos, taxa_t5

    def _tentar_saque(self, data: str):
        while self.banca >= SAQUE_TRIGGER and self.saques_hoje < SAQUES_MAX_DIA:
            self.banca -= SAQUE_VALOR
            self.total_sacado += SAQUE_VALOR
            self.saques_hoje += 1

    def _executar_gatilho(self, multiplicadores: List[float], pos_inicio: int, nivel: int, data: str) -> int:
        self.gatilhos_total += 1

        max_t = NIVEIS[nivel]['tentativas']
        divisor = NIVEIS[nivel]['divisor']
        aposta_base = self.banca / divisor

        banca_antes = self.banca
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

        # Atualizar pico
        if self.banca > self.banca_maxima:
            self.banca_maxima = self.banca

        # Calcular drawdown
        dd_pct = ((self.banca_maxima - self.banca) / self.banca_maxima) * 100 if self.banca_maxima > 0 else 0

        # Registrar evento de drawdown significativo (> 20%)
        if dd_pct > 20 and lucro < 0:
            alertas, taxa_altos, taxa_t5 = self._calcular_metricas()

            self.drawdown_events.append(DrawdownEvent(
                data=data,
                gatilho_num=self.gatilhos_total,
                banca_antes=banca_antes,
                banca_depois=self.banca,
                banca_pico=self.banca_maxima,
                drawdown_pct=dd_pct,
                tentativa_final=tentativa_final,
                nivel_usado=nivel,
                alertas_ativos=alertas,
                taxa_altos=taxa_altos,
                taxa_t5=taxa_t5
            ))

        if dd_pct > self.drawdown_max_pct:
            self.drawdown_max_pct = dd_pct

        self.historico_gatilhos.append(tentativa_final)
        return tentativa_final

    def simular(self, dados_por_dia: Dict[str, List[float]]):
        for data in sorted(dados_por_dia.keys()):
            multiplicadores = dados_por_dia[data]
            self.saques_hoje = 0

            baixos = 0
            i = 0

            while i < len(multiplicadores):
                mult = multiplicadores[i]
                self.historico_mults.append(mult)

                if mult < THRESHOLD_BAIXO:
                    baixos += 1
                    if baixos == GATILHO_SIZE:
                        tent_final = self._executar_gatilho(multiplicadores, i + 1, 7, data)
                        i += tent_final
                        self._tentar_saque(data)
                        baixos = 0
                else:
                    baixos = 0

                i += 1

                if self.banca <= 0:
                    return

    def relatorio(self):
        print("=" * 120)
        print("INVESTIGACAO DOS DRAWDOWNS")
        print("=" * 120)

        print(f"\nTotal de eventos de drawdown > 20%: {len(self.drawdown_events)}")
        print(f"Drawdown maximo: {self.drawdown_max_pct:.2f}%")

        # Top 20 piores drawdowns
        piores = sorted(self.drawdown_events, key=lambda x: x.drawdown_pct, reverse=True)[:20]

        print("\n" + "-" * 120)
        print("TOP 20 PIORES DRAWDOWNS:")
        print("-" * 120)
        print(f"{'#':<3} {'DATA':<12} {'DD%':>8} {'BANCA ANTES':>15} {'BANCA DEPOIS':>15} {'TENT':>5} {'ALERTAS':>8} {'TAXA_ALTOS':>12} {'TAXA_T5+':>10}")
        print("-" * 120)

        for i, ev in enumerate(piores, 1):
            print(f"{i:<3} {ev.data:<12} {ev.drawdown_pct:>7.1f}% "
                  f"R${ev.banca_antes:>12,.0f} R${ev.banca_depois:>12,.0f} "
                  f"T{ev.tentativa_final:>3} {ev.alertas_ativos:>8} "
                  f"{ev.taxa_altos*100:>11.1f}% {ev.taxa_t5*100:>9.1f}%")

        # Analise: alertas estavam ativos nos piores momentos?
        print("\n" + "=" * 120)
        print("ANALISE: OS ALERTAS PREVIRAM OS DRAWDOWNS?")
        print("=" * 120)

        # Agrupar por numero de alertas ativos
        por_alertas = defaultdict(list)
        for ev in self.drawdown_events:
            por_alertas[ev.alertas_ativos].append(ev)

        print(f"\n{'ALERTAS ATIVOS':<20} {'QTD EVENTOS':>15} {'DD MEDIO':>12} {'DD MAX':>12}")
        print("-" * 65)
        for n_alertas in sorted(por_alertas.keys()):
            eventos = por_alertas[n_alertas]
            dd_medio = sum(e.drawdown_pct for e in eventos) / len(eventos)
            dd_max = max(e.drawdown_pct for e in eventos)
            print(f"{n_alertas} alertas{'':<12} {len(eventos):>15} {dd_medio:>11.1f}% {dd_max:>11.1f}%")

        # Analise por tentativa final
        print("\n" + "-" * 120)
        print("DRAWDOWNS POR TENTATIVA FINAL:")
        print("-" * 120)

        por_tentativa = defaultdict(list)
        for ev in self.drawdown_events:
            por_tentativa[ev.tentativa_final].append(ev)

        print(f"{'TENTATIVA':<15} {'QTD':>10} {'DD MEDIO':>12} {'DD MAX':>12} {'% DO TOTAL':>12}")
        print("-" * 65)
        for t in sorted(por_tentativa.keys()):
            eventos = por_tentativa[t]
            dd_medio = sum(e.drawdown_pct for e in eventos) / len(eventos)
            dd_max = max(e.drawdown_pct for e in eventos)
            pct = len(eventos) / len(self.drawdown_events) * 100
            print(f"T{t:<14} {len(eventos):>10} {dd_medio:>11.1f}% {dd_max:>11.1f}% {pct:>11.1f}%")

        # Quando taxa_altos estava baixa
        print("\n" + "-" * 120)
        print("CORRELACAO TAXA_ALTOS vs DRAWDOWN:")
        print("-" * 120)

        taxa_baixa = [e for e in self.drawdown_events if e.taxa_altos < 0.42]
        taxa_normal = [e for e in self.drawdown_events if e.taxa_altos >= 0.42]

        if taxa_baixa:
            dd_medio_baixa = sum(e.drawdown_pct for e in taxa_baixa) / len(taxa_baixa)
            print(f"  Taxa altos < 42%: {len(taxa_baixa)} eventos, DD medio {dd_medio_baixa:.1f}%")
        if taxa_normal:
            dd_medio_normal = sum(e.drawdown_pct for e in taxa_normal) / len(taxa_normal)
            print(f"  Taxa altos >= 42%: {len(taxa_normal)} eventos, DD medio {dd_medio_normal:.1f}%")

        # Conclusao
        print("\n" + "=" * 120)
        print("CONCLUSAO")
        print("=" * 120)

        # Verificar se drawdowns ocorrem mais quando alertas estao ativos
        eventos_com_alertas = [e for e in self.drawdown_events if e.alertas_ativos >= 2]
        eventos_sem_alertas = [e for e in self.drawdown_events if e.alertas_ativos < 2]

        print(f"\n  Drawdowns quando alertas >= 2: {len(eventos_com_alertas)} ({len(eventos_com_alertas)/len(self.drawdown_events)*100:.1f}%)")
        print(f"  Drawdowns quando alertas < 2:  {len(eventos_sem_alertas)} ({len(eventos_sem_alertas)/len(self.drawdown_events)*100:.1f}%)")

        if eventos_com_alertas and eventos_sem_alertas:
            dd_com = sum(e.drawdown_pct for e in eventos_com_alertas) / len(eventos_com_alertas)
            dd_sem = sum(e.drawdown_pct for e in eventos_sem_alertas) / len(eventos_sem_alertas)
            print(f"\n  DD medio com alertas: {dd_com:.1f}%")
            print(f"  DD medio sem alertas: {dd_sem:.1f}%")

            if dd_com > dd_sem:
                print("\n  >> ALERTAS DETECTAM momentos de maior risco!")
                print("  >> Trocar para NS8 quando alertas >= 2 FARIA SENTIDO")
            else:
                print("\n  >> Alertas NAO correlacionam com drawdowns")
                print("  >> Trocar para NS8 NAO ajudaria")


def carregar_por_dia(filepath: str) -> Dict[str, List[float]]:
    dias = defaultdict(list)
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()
                    dias[data].append(mult)
            except:
                continue
    return dict(dias)


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'

    print("Carregando dados...")
    dados = carregar_por_dia(csv_path)
    dados_2025 = {k: v for k, v in dados.items() if datetime.strptime(k, '%d/%m/%Y').year >= 2025}

    print(f"Periodo: {min(dados_2025.keys())} a {max(dados_2025.keys())}")
    print(f"Total dias: {len(dados_2025)}")

    investigador = InvestigadorDrawdowns()
    investigador.simular(dados_2025)
    investigador.relatorio()


if __name__ == "__main__":
    main()
