#!/usr/bin/env python3
"""
SIMULACAO DE EFETIVIDADE DOS ALERTAS
Compara NS7 pura vs NS7 com troca dinamica para NS8 baseada em alertas

Objetivo: Validar se os indicadores de alerta tem valor preditivo
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import deque
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

# Configuracao de alertas
JANELA_GATILHOS = 30  # Ultimos 30 gatilhos para analise
JANELA_MULTS = 500    # Ultimos 500 multiplicadores

# Thresholds de alerta
ALERTA_TAXA_ALTOS = 0.42      # < 42% de mult >= 2.0
ALERTA_TAXA_T5_PLUS = 0.08    # > 8% de T5+ nos ultimos gatilhos
ALERTA_TAXA_T6_PLUS = 0.05    # > 5% de T6+ nos ultimos gatilhos
ALERTA_CENARIO_B = 0.05       # > 5% de Cenario B
ALERTA_VOLATILIDADE = 1.20    # Aumento de 20% na volatilidade

# Quantos alertas para trocar de nivel
ALERTAS_PARA_TROCAR = 2


# ==============================================================================
# ESTRUTURAS
# ==============================================================================

@dataclass
class ConfigTentativa:
    slots: int
    alvo_lucro: float
    alvo_defesa: float
    is_parar: bool = False
    is_ultima: bool = False


@dataclass
class GatilhoResult:
    tentativa_final: int
    resultado: str  # 'win', 'win_parcial', 'parar', 'bust'
    cenario: str    # 'WIN', 'A', 'B', 'C'
    lucro: float
    nivel_usado: int


# ==============================================================================
# SIMULADOR COM ALERTAS
# ==============================================================================

class SimuladorComAlertas:
    def __init__(self, banca_inicial: float = 1000.0, usar_alertas: bool = True):
        self.banca_inicial = banca_inicial
        self.usar_alertas = usar_alertas

        # Estado
        self.banca = banca_inicial
        self.banca_maxima = banca_inicial
        self.nivel_atual = 7  # Comeca com NS7

        # Historico para alertas
        self.historico_gatilhos: deque = deque(maxlen=JANELA_GATILHOS)
        self.historico_mults: deque = deque(maxlen=JANELA_MULTS)
        self.volatilidade_baseline = None

        # Contadores
        self.gatilhos_total = 0
        self.gatilhos_ns7 = 0
        self.gatilhos_ns8 = 0
        self.wins = 0
        self.busts = 0
        self.trocas_nivel = 0
        self.alertas_disparados = 0

        # Tracking de drawdown
        self.drawdown_max = 0
        self.drawdown_max_pct = 0

        # Detalhes por nivel
        self.lucro_ns7 = 0
        self.lucro_ns8 = 0

    def _get_config(self, nivel: int, tentativa: int) -> ConfigTentativa:
        """Retorna configuracao da tentativa para o nivel"""
        max_t = NIVEIS[nivel]['tentativas']

        if tentativa == max_t:  # Ultima
            return ConfigTentativa(
                slots=2,
                alvo_lucro=ALVO_ULTIMA,
                alvo_defesa=ALVO_DEFESA,
                is_ultima=True
            )
        elif tentativa == max_t - 1:  # Penultima
            return ConfigTentativa(
                slots=2,
                alvo_lucro=ALVO_LUCRO,
                alvo_defesa=ALVO_DEFESA,
                is_parar=True
            )
        else:
            return ConfigTentativa(
                slots=1,
                alvo_lucro=ALVO_LUCRO,
                alvo_defesa=0
            )

    def _calcular_aposta_base(self, nivel: int) -> float:
        """Calcula aposta base (compound)"""
        divisor = NIVEIS[nivel]['divisor']
        return self.banca / divisor

    def _calcular_alertas(self) -> Tuple[int, List[str]]:
        """Calcula quantos alertas estao ativos"""
        alertas = []

        if len(self.historico_gatilhos) < 10:
            return 0, alertas

        # 1. Taxa de multiplicadores altos
        if len(self.historico_mults) >= 100:
            mults_recentes = list(self.historico_mults)[-100:]
            taxa_altos = sum(1 for m in mults_recentes if m >= 2.0) / len(mults_recentes)
            if taxa_altos < ALERTA_TAXA_ALTOS:
                alertas.append(f"TAXA_ALTOS={taxa_altos*100:.1f}%")

        # 2. Taxa de T5+
        gatilhos = list(self.historico_gatilhos)
        t5_plus = sum(1 for g in gatilhos if g.tentativa_final >= 5)
        taxa_t5 = t5_plus / len(gatilhos)
        if taxa_t5 > ALERTA_TAXA_T5_PLUS:
            alertas.append(f"T5+={taxa_t5*100:.1f}%")

        # 3. Taxa de T6+
        t6_plus = sum(1 for g in gatilhos if g.tentativa_final >= 6)
        taxa_t6 = t6_plus / len(gatilhos)
        if taxa_t6 > ALERTA_TAXA_T6_PLUS:
            alertas.append(f"T6+={taxa_t6*100:.1f}%")

        # 4. Taxa de Cenario B
        cenario_b = sum(1 for g in gatilhos if g.cenario == 'B')
        taxa_b = cenario_b / len(gatilhos)
        if taxa_b > ALERTA_CENARIO_B:
            alertas.append(f"CEN_B={taxa_b*100:.1f}%")

        # 5. Volatilidade
        if len(self.historico_mults) >= 200:
            mults_recentes = list(self.historico_mults)[-100:]
            mults_anteriores = list(self.historico_mults)[-200:-100]

            if len(mults_anteriores) > 1 and len(mults_recentes) > 1:
                vol_recente = statistics.stdev(mults_recentes)
                vol_anterior = statistics.stdev(mults_anteriores)

                if vol_anterior > 0 and vol_recente > vol_anterior * ALERTA_VOLATILIDADE:
                    alertas.append(f"VOL+{((vol_recente/vol_anterior)-1)*100:.0f}%")

        return len(alertas), alertas

    def _decidir_nivel(self) -> int:
        """Decide qual nivel usar baseado nos alertas"""
        if not self.usar_alertas:
            return 7  # Sempre NS7

        num_alertas, alertas = self._calcular_alertas()

        if num_alertas >= ALERTAS_PARA_TROCAR:
            self.alertas_disparados += 1
            if self.nivel_atual == 7:
                self.trocas_nivel += 1
            return 8  # Mudar para NS8
        else:
            return 7  # Manter/voltar para NS7

    def _processar_gatilho(self, multiplicadores: List[float], pos_inicio: int) -> GatilhoResult:
        """Processa um gatilho e retorna o resultado"""
        nivel = self._decidir_nivel()
        self.nivel_atual = nivel

        if nivel == 7:
            self.gatilhos_ns7 += 1
        else:
            self.gatilhos_ns8 += 1

        max_tentativas = NIVEIS[nivel]['tentativas']
        aposta_base = self._calcular_aposta_base(nivel)

        investido = 0
        retorno = 0
        tentativa_final = 0
        resultado = ''
        cenario = ''

        for t in range(1, max_tentativas + 1):
            idx = pos_inicio + t - 1
            if idx >= len(multiplicadores):
                break

            mult = multiplicadores[idx]
            config = self._get_config(nivel, t)

            # Calcular aposta desta tentativa
            aposta = aposta_base * (2 ** (t - 1)) * config.slots
            investido += aposta

            tentativa_final = t

            # Avaliar resultado
            if config.slots == 1:
                # 1 slot normal
                if mult >= config.alvo_lucro:
                    retorno = aposta * config.alvo_lucro
                    resultado = 'win'
                    cenario = 'WIN'
                    break
            else:
                # 2 slots (penultima ou ultima)
                if config.is_ultima:
                    if mult >= config.alvo_lucro:  # 2.50x
                        retorno = aposta * config.alvo_lucro
                        resultado = 'win'
                        cenario = 'A'
                        break
                    elif mult >= config.alvo_defesa:  # 1.10x
                        retorno = aposta * config.alvo_defesa
                        resultado = 'win_parcial'
                        cenario = 'B'
                        break
                    else:
                        resultado = 'bust'
                        cenario = 'C'
                        break
                else:  # Penultima (PARAR)
                    if mult >= config.alvo_lucro:  # 1.99x
                        retorno = aposta * config.alvo_lucro
                        resultado = 'win'
                        cenario = 'A'
                        break
                    elif mult >= config.alvo_defesa:  # 1.10x
                        retorno = aposta * config.alvo_defesa
                        resultado = 'parar'
                        cenario = 'B'
                        break
                    # else: continua para proxima tentativa

        lucro = retorno - investido

        # Atualizar banca
        self.banca += lucro

        # Tracking
        if self.banca > self.banca_maxima:
            self.banca_maxima = self.banca

        drawdown = self.banca_maxima - self.banca
        if drawdown > self.drawdown_max:
            self.drawdown_max = drawdown
            self.drawdown_max_pct = (drawdown / self.banca_maxima) * 100

        # Contadores
        self.gatilhos_total += 1
        if resultado in ['win', 'win_parcial']:
            self.wins += 1
        elif resultado == 'bust':
            self.busts += 1

        # Lucro por nivel
        if nivel == 7:
            self.lucro_ns7 += lucro
        else:
            self.lucro_ns8 += lucro

        return GatilhoResult(
            tentativa_final=tentativa_final,
            resultado=resultado,
            cenario=cenario,
            lucro=lucro,
            nivel_usado=nivel
        )

    def simular(self, multiplicadores: List[float]) -> Dict:
        """Executa simulacao completa"""
        self.banca = self.banca_inicial
        self.banca_maxima = self.banca_inicial

        baixos_consecutivos = 0
        i = 0

        while i < len(multiplicadores):
            mult = multiplicadores[i]
            self.historico_mults.append(mult)

            if mult < THRESHOLD_BAIXO:
                baixos_consecutivos += 1

                if baixos_consecutivos == GATILHO_SIZE:
                    # Gatilho ativado!
                    resultado = self._processar_gatilho(multiplicadores, i + 1)

                    # Registrar no historico
                    self.historico_gatilhos.append(resultado)

                    # Avancar para apos o gatilho
                    i += resultado.tentativa_final
                    baixos_consecutivos = 0
            else:
                baixos_consecutivos = 0

            i += 1

            # Verificar bust
            if self.banca <= 0:
                break

        return {
            'banca_final': self.banca,
            'lucro': self.banca - self.banca_inicial,
            'ganho_pct': ((self.banca / self.banca_inicial) - 1) * 100,
            'gatilhos': self.gatilhos_total,
            'gatilhos_ns7': self.gatilhos_ns7,
            'gatilhos_ns8': self.gatilhos_ns8,
            'wins': self.wins,
            'busts': self.busts,
            'drawdown_max': self.drawdown_max,
            'drawdown_max_pct': self.drawdown_max_pct,
            'trocas_nivel': self.trocas_nivel,
            'alertas_disparados': self.alertas_disparados,
            'lucro_ns7': self.lucro_ns7,
            'lucro_ns8': self.lucro_ns8,
        }


# ==============================================================================
# MAIN
# ==============================================================================

def carregar_multiplicadores(filepath: str) -> List[float]:
    """Carrega todos os multiplicadores"""
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


def carregar_por_mes(filepath: str) -> Dict[str, List[float]]:
    """Carrega multiplicadores agrupados por mes"""
    from collections import defaultdict
    meses = defaultdict(list)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f)
        for line in f:
            try:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    mult = float(parts[0])
                    data = parts[2].strip()
                    dt = datetime.strptime(data, '%d/%m/%Y')
                    chave = dt.strftime('%Y-%m')
                    meses[chave].append(mult)
            except:
                continue

    return dict(meses)


def main():
    csv_path = '/home/linnaldonitro/MartingaleV2_Build/brabet_unificado_1.3m_ate_20jan.csv'
    banca = 1000.0

    print("=" * 100)
    print("SIMULACAO DE EFETIVIDADE DOS ALERTAS")
    print("=" * 100)
    print(f"Banca inicial: R$ {banca:,.2f}")
    print(f"Estrategia base: NS7")
    print(f"Estrategia defensiva: NS8")
    print(f"Alertas para trocar: {ALERTAS_PARA_TROCAR}+")
    print()

    print("Carregando dados...")
    meses = carregar_por_mes(csv_path)

    # Filtrar 2025 e janeiro 2026
    meses_ordenados = sorted(meses.keys())
    meses_analise = {k: v for k, v in meses.items() if k >= '2025-01'}

    print(f"Meses para analise: {len(meses_analise)}")
    print()

    # Header
    print("=" * 130)
    print(f"{'MES':<10} │ {'--- NS7 PURA ---':^35} │ {'--- NS7 + ALERTAS ---':^50} │ {'DIFF':>10}")
    print(f"{'':10} │ {'Lucro':>12} {'%':>8} {'DD%':>8} {'B':>4} │ {'Lucro':>12} {'%':>8} {'DD%':>8} {'B':>4} {'Trocas':>8} {'NS8':>8} │ {'':>10}")
    print("-" * 130)

    # Acumuladores
    total_ns7_lucro = 0
    total_alerta_lucro = 0
    total_ns7_busts = 0
    total_alerta_busts = 0
    total_trocas = 0
    meses_alerta_melhor = 0
    meses_ns7_melhor = 0

    resultados = []

    for mes in sorted(meses_analise.keys()):
        multiplicadores = meses_analise[mes]

        # Simular NS7 pura
        sim_ns7 = SimuladorComAlertas(banca_inicial=banca, usar_alertas=False)
        rel_ns7 = sim_ns7.simular(multiplicadores)

        # Simular com alertas
        sim_alerta = SimuladorComAlertas(banca_inicial=banca, usar_alertas=True)
        rel_alerta = sim_alerta.simular(multiplicadores)

        # Diferenca
        diff = rel_alerta['lucro'] - rel_ns7['lucro']
        diff_str = f"+R${diff:,.0f}" if diff >= 0 else f"-R${-diff:,.0f}"

        # Acumular
        total_ns7_lucro += rel_ns7['lucro']
        total_alerta_lucro += rel_alerta['lucro']
        total_ns7_busts += rel_ns7['busts']
        total_alerta_busts += rel_alerta['busts']
        total_trocas += rel_alerta['trocas_nivel']

        if rel_alerta['lucro'] > rel_ns7['lucro']:
            meses_alerta_melhor += 1
        else:
            meses_ns7_melhor += 1

        # Formatar busts
        b1 = f"{rel_ns7['busts']}" if rel_ns7['busts'] == 0 else f"*{rel_ns7['busts']}*"
        b2 = f"{rel_alerta['busts']}" if rel_alerta['busts'] == 0 else f"*{rel_alerta['busts']}*"

        # % gatilhos em NS8
        pct_ns8 = (rel_alerta['gatilhos_ns8'] / rel_alerta['gatilhos'] * 100) if rel_alerta['gatilhos'] > 0 else 0

        print(f"{mes:<10} │ "
              f"R${rel_ns7['lucro']:>10,.0f} {rel_ns7['ganho_pct']:>7.1f}% {rel_ns7['drawdown_max_pct']:>7.1f}% {b1:>4} │ "
              f"R${rel_alerta['lucro']:>10,.0f} {rel_alerta['ganho_pct']:>7.1f}% {rel_alerta['drawdown_max_pct']:>7.1f}% {b2:>4} "
              f"{rel_alerta['trocas_nivel']:>8} {pct_ns8:>7.1f}% │ "
              f"{diff_str:>10}")

        resultados.append({
            'mes': mes,
            'ns7': rel_ns7,
            'alerta': rel_alerta,
            'diff': diff
        })

    # Totais
    print("-" * 130)
    diff_total = total_alerta_lucro - total_ns7_lucro
    diff_str = f"+R${diff_total:,.0f}" if diff_total >= 0 else f"-R${-diff_total:,.0f}"

    print(f"{'TOTAL':<10} │ "
          f"R${total_ns7_lucro:>10,.0f} {'-':>7} {'-':>7} {total_ns7_busts:>4} │ "
          f"R${total_alerta_lucro:>10,.0f} {'-':>7} {'-':>7} {total_alerta_busts:>4} "
          f"{total_trocas:>8} {'-':>7} │ "
          f"{diff_str:>10}")

    # Resumo
    print("\n" + "=" * 100)
    print("RESUMO DA EFETIVIDADE DOS ALERTAS")
    print("=" * 100)

    print(f"\n{'Metrica':<40} {'NS7 Pura':>20} {'NS7+Alertas':>20}")
    print("-" * 85)
    print(f"{'Lucro Total':<40} R${total_ns7_lucro:>17,.2f} R${total_alerta_lucro:>17,.2f}")
    print(f"{'Total Busts':<40} {total_ns7_busts:>20} {total_alerta_busts:>20}")
    print(f"{'Meses com melhor performance':<40} {meses_ns7_melhor:>20} {meses_alerta_melhor:>20}")
    print(f"{'Total trocas NS7->NS8':<40} {'-':>20} {total_trocas:>20}")

    print("\n" + "-" * 85)
    print("VEREDITO:")
    print("-" * 85)

    if total_alerta_lucro > total_ns7_lucro:
        ganho_extra = total_alerta_lucro - total_ns7_lucro
        ganho_pct = (ganho_extra / total_ns7_lucro) * 100 if total_ns7_lucro > 0 else 0
        print(f"  >> ALERTAS EFETIVOS: +R$ {ganho_extra:,.2f} ({ganho_pct:+.1f}%) de lucro adicional")
    else:
        perda = total_ns7_lucro - total_alerta_lucro
        perda_pct = (perda / total_ns7_lucro) * 100 if total_ns7_lucro > 0 else 0
        print(f"  >> ALERTAS NAO EFETIVOS: -R$ {perda:,.2f} ({perda_pct:.1f}%) de lucro perdido")

    if total_alerta_busts < total_ns7_busts:
        print(f"  >> REDUCAO DE RISCO: {total_ns7_busts - total_alerta_busts} busts evitados")
    elif total_alerta_busts > total_ns7_busts:
        print(f"  >> AUMENTO DE RISCO: {total_alerta_busts - total_ns7_busts} busts adicionais")

    # Analise dos meses com alertas ativos
    print("\n" + "-" * 85)
    print("MESES ONDE ALERTAS MAIS ATUARAM:")
    print("-" * 85)

    for r in sorted(resultados, key=lambda x: x['alerta']['trocas_nivel'], reverse=True)[:5]:
        if r['alerta']['trocas_nivel'] > 0:
            pct_ns8 = r['alerta']['gatilhos_ns8'] / r['alerta']['gatilhos'] * 100
            print(f"  {r['mes']}: {r['alerta']['trocas_nivel']} trocas, {pct_ns8:.0f}% em NS8, "
                  f"Diff: {'+'if r['diff']>=0 else ''}R${r['diff']:,.0f}")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
