#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DASHBOARD WEB V2 - Monitoramento Completo
- Gráfico unificado com 3 máquinas em R$
- Métricas por período (2h, 6h, 12h, 24h)
- Persistência de dados históricos
- Tracking de sequências de baixos
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
from collections import defaultdict

# Configuração
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_PORT = 8080
HISTORY_FILE = os.path.join(BASE_DIR, 'dashboard_history.json')

# Carregar configuração
DASHBOARD_CONFIG = {}
config_file = os.path.join(BASE_DIR, 'dashboard_config.json')
if os.path.exists(config_file):
    try:
        with open(config_file, 'r') as f:
            DASHBOARD_CONFIG = json.load(f)
    except:
        pass

# Tipos de máquina
MACHINE_TYPES = {
    'agressiva': 'Linux',
    'conservadora': 'Windows Dual',
    'isolada': 'Windows Solo'
}

# Histórico persistente
historical_data = {
    'agressiva': {'saldo_history': [], 'gatilhos_history': [], 'start_date': None, 'initial_deposit': 0, 'initial_bet': 0},
    'conservadora': {'saldo_history': [], 'gatilhos_history': [], 'start_date': None, 'initial_deposit': 0, 'initial_bet': 0},
    'isolada': {'saldo_history': [], 'gatilhos_history': [], 'start_date': None, 'initial_deposit': 0, 'initial_bet': 0},
}

# Estado atual das máquinas
machines_state = {
    'agressiva': {'status': 'offline', 'saldo': 0, 'deposito_inicial': 0, 'modo': 'g6_ns10', 'nivel': 10,
                  'sessoes_win': 0, 'sessoes_loss': 0, 'total_rodadas': 0, 'last_update': None,
                  'aposta_base': 0, 'uptime_start': None, 'last_mult': None, 'last_mult_time': None,
                  'historico_saldo': [], 'ultimos_gatilhos': []},
    'conservadora': {'status': 'offline', 'saldo': 0, 'deposito_inicial': 0, 'modo': 'g6_ns10', 'nivel': 10,
                     'sessoes_win': 0, 'sessoes_loss': 0, 'total_rodadas': 0, 'last_update': None,
                     'aposta_base': 0, 'uptime_start': None, 'last_mult': None, 'last_mult_time': None,
                     'historico_saldo': [], 'ultimos_gatilhos': []},
    'isolada': {'status': 'offline', 'saldo': 0, 'deposito_inicial': 0, 'modo': 'g6_ns10', 'nivel': 10,
                'sessoes_win': 0, 'sessoes_loss': 0, 'total_rodadas': 0, 'last_update': None,
                'aposta_base': 0, 'uptime_start': None, 'last_mult': None, 'last_mult_time': None,
                'historico_saldo': [], 'ultimos_gatilhos': []},
}

app = Flask(__name__)


def load_history():
    """Carrega histórico persistente do arquivo"""
    global historical_data
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                historical_data = json.load(f)
            print(f"[DASHBOARD] Histórico carregado: {HISTORY_FILE}")
        except Exception as e:
            print(f"[DASHBOARD] Erro ao carregar histórico: {e}")


def save_history():
    """Salva histórico persistente no arquivo"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(historical_data, f, indent=2, default=str)
    except Exception as e:
        print(f"[DASHBOARD] Erro ao salvar histórico: {e}")


def update_historical_data(machine_id, data):
    """Atualiza dados históricos de uma máquina"""
    hist = historical_data[machine_id]

    # Inicializar data de início se não existir
    if not hist['start_date']:
        hist['start_date'] = datetime.now().isoformat()
        hist['initial_deposit'] = data.get('deposito_inicial', 0)
        hist['initial_bet'] = data.get('aposta_base', 0)

    # Adicionar ponto de saldo com timestamp completo
    saldo = data.get('saldo', 0)
    if saldo > 0:
        timestamp = datetime.now().isoformat()
        # Evitar duplicatas muito próximas (menos de 1 minuto)
        if hist['saldo_history']:
            last_time = datetime.fromisoformat(hist['saldo_history'][-1]['timestamp'])
            if (datetime.now() - last_time).total_seconds() < 60:
                return

        hist['saldo_history'].append({
            'timestamp': timestamp,
            'saldo': saldo
        })

    # Manter apenas últimos 7 dias de dados (para não crescer infinitamente)
    cutoff = datetime.now() - timedelta(days=7)
    hist['saldo_history'] = [
        h for h in hist['saldo_history']
        if datetime.fromisoformat(h['timestamp']) > cutoff
    ]

    # Salvar periodicamente (a cada 5 minutos)
    save_history()


def get_profit_by_period(machine_id, hours):
    """Calcula lucro nos últimos X horas"""
    hist = historical_data[machine_id]['saldo_history']
    if not hist:
        return 0, 0

    cutoff = datetime.now() - timedelta(hours=hours)

    # Encontrar saldo no início do período
    saldo_inicio = None
    for h in hist:
        ts = datetime.fromisoformat(h['timestamp'])
        if ts >= cutoff:
            saldo_inicio = h['saldo']
            break

    if saldo_inicio is None and hist:
        saldo_inicio = hist[0]['saldo']

    saldo_atual = machines_state[machine_id].get('saldo', 0)
    if saldo_inicio and saldo_atual:
        lucro = saldo_atual - saldo_inicio
        pct = (lucro / saldo_inicio * 100) if saldo_inicio > 0 else 0
        return lucro, pct

    return 0, 0


def get_daily_average(machine_id):
    """Calcula média diária desde o início"""
    hist = historical_data[machine_id]
    if not hist['start_date'] or not hist['saldo_history']:
        return 0, 0

    start = datetime.fromisoformat(hist['start_date'])
    days = max(1, (datetime.now() - start).days + 1)

    deposito_inicial = hist['initial_deposit'] or hist['saldo_history'][0]['saldo']
    saldo_atual = machines_state[machine_id].get('saldo', 0)

    lucro_total = saldo_atual - deposito_inicial
    media_diaria = lucro_total / days
    media_pct = (lucro_total / deposito_inicial * 100 / days) if deposito_inicial > 0 else 0

    return media_diaria, media_pct


def get_display_info(modo, machine_type):
    """Retorna nome/cor baseado no modo"""
    if modo and 'ns9' in modo.lower():
        return {'name': 'AGRESSIVA', 'subtitle': f'{machine_type} - NS9', 'color': '#ff6b6b'}
    return {'name': 'CONSERVADORA', 'subtitle': f'{machine_type} - NS10', 'color': '#4ecdc4'}


def carregar_estado_local():
    """Carrega estado da máquina local (Linux)"""
    try:
        state_file = os.path.join(BASE_DIR, 'session_state.json')
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)

            config = state.get('config_modo', {})
            nivel = state.get('nivel_seguranca', 10)
            saldo = state.get('saldo_atual', 0)
            deposito = state.get('deposito_inicial', 0)

            # Calcular aposta base
            divisor = {9: 511, 10: 1023}.get(nivel, 1023)
            aposta_base = saldo / divisor if saldo > 0 else 0

            # Construir histórico de saldo
            historico_apostas = state.get('historico_apostas', [])
            historico_saldo = []
            saldo_acum = deposito
            for ap in historico_apostas:
                saldo_acum += ap.get('resultado', 0)
                historico_saldo.append({
                    'horario': ap.get('horario', ''),
                    'saldo': saldo_acum
                })

            # Construir gatilhos
            ultimos = []
            for h in historico_apostas[-20:]:
                ultimos.append({
                    'tentativa': h.get('tentativa', 1),
                    'resultado': 'WIN' if h.get('ganhou', False) else 'LOSS',
                    'horario': h.get('horario', ''),
                    'mult': h.get('multiplicador_real', 0)
                })

            # Override deposito se configurado
            override = DASHBOARD_CONFIG.get('agressiva', {}).get('deposito_inicial_override')
            if override is not None:
                deposito = override

            last_mult = None
            last_mult_time = None
            if historico_apostas:
                last = historico_apostas[-1]
                last_mult = last.get('multiplicador_real')
                last_mult_time = last.get('horario')

            machines_state['agressiva'].update({
                'status': 'online',
                'last_update': datetime.now(),
                'saldo': saldo,
                'deposito_inicial': deposito,
                'aposta_base': aposta_base,
                'nivel': nivel,
                'modo': config.get('modo', 'g6_ns10'),
                'sessoes_win': state.get('sessoes_win', 0),
                'sessoes_loss': state.get('sessoes_loss', 0),
                'total_rodadas': state.get('total_rodadas', 0),
                'uptime_start': state.get('inicio_timestamp'),
                'historico_saldo': historico_saldo,
                'ultimos_gatilhos': ultimos,
                'last_mult': last_mult,
                'last_mult_time': last_mult_time,
            })

            update_historical_data('agressiva', machines_state['agressiva'])

    except Exception as e:
        print(f"[DASHBOARD] Erro ao carregar estado local: {e}")


def calcular_aposta_base(saldo, modo):
    """Calcula aposta base"""
    if saldo <= 0:
        return 0
    divisor = 511 if modo and 'ns9' in modo.lower() else 1023
    return saldo / divisor


def get_machine_status(machine):
    """Verifica se máquina está online"""
    last = machine.get('last_update')
    if not last:
        return 'offline'
    if isinstance(last, str):
        try:
            last = datetime.fromisoformat(last)
        except:
            return 'offline'
    delta = datetime.now() - last
    return 'online' if delta.total_seconds() < 120 else 'offline'


def calcular_uptime(start_str):
    """Calcula uptime"""
    if not start_str:
        return "N/A"
    try:
        start = datetime.fromisoformat(start_str) if 'T' in str(start_str) else datetime.strptime(str(start_str), '%Y-%m-%d %H:%M:%S')
        delta = datetime.now() - start
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}min"
    except:
        return "N/A"


# Template HTML V2
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MartingaleV2 Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        :root {
            --bg-primary: #0a0a12;
            --bg-card: #12121e;
            --accent-1: #ff6b6b;
            --accent-2: #4ecdc4;
            --accent-3: #a66cff;
            --text-primary: #ffffff;
            --text-secondary: #888;
            --border: rgba(255,255,255,0.08);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            font-size: 14px;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 15px; }

        .header {
            text-align: center;
            padding: 15px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 15px;
        }
        .header h1 {
            font-size: 1.8em;
            font-weight: 300;
            background: linear-gradient(135deg, var(--accent-1), var(--accent-2), var(--accent-3));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* Gráfico Principal */
        .main-chart-card {
            background: var(--bg-card);
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid var(--border);
        }
        .main-chart-container { height: 250px; }
        .chart-legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 10px;
            flex-wrap: wrap;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85em;
        }
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        /* Grid de Máquinas */
        .machines-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 15px;
        }
        @media (max-width: 1000px) { .machines-grid { grid-template-columns: 1fr; } }

        .machine-card {
            background: var(--bg-card);
            border-radius: 15px;
            padding: 15px;
            border: 1px solid var(--border);
        }
        .machine-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }
        .machine-title { font-size: 1.1em; font-weight: 600; }
        .machine-subtitle { color: var(--text-secondary); font-size: 0.75em; margin-top: 2px; }
        .machine-initial { color: var(--text-secondary); font-size: 0.7em; margin-top: 4px; }
        .status-badge {
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 0.65em;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-online { background: #00c853; }
        .status-offline { background: #ff5252; }

        /* Métricas */
        .metrics-row {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }
        .metric-box {
            flex: 1;
            min-width: 70px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            padding: 8px;
            text-align: center;
        }
        .metric-label { color: var(--text-secondary); font-size: 0.65em; text-transform: uppercase; }
        .metric-value { font-size: 1.1em; font-weight: 600; margin-top: 2px; }
        .metric-sub { font-size: 0.7em; color: var(--text-secondary); }
        .positive { color: #00e676; }
        .negative { color: #ff5252; }

        /* Lucros por Período */
        .period-profits {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 6px;
            margin-bottom: 10px;
        }
        .period-box {
            background: rgba(255,255,255,0.02);
            border-radius: 6px;
            padding: 6px;
            text-align: center;
        }
        .period-label { font-size: 0.6em; color: var(--text-secondary); }
        .period-value { font-size: 0.9em; font-weight: 600; }

        /* Gatilhos */
        .gatilhos-section { margin-top: 10px; }
        .gatilhos-label { color: var(--text-secondary); font-size: 0.7em; margin-bottom: 6px; }
        .gatilhos-list { display: flex; flex-wrap: wrap; gap: 4px; }
        .gatilho-item {
            font-size: 0.7em;
            padding: 3px 6px;
            border-radius: 4px;
        }
        .gatilho-win { background: rgba(0,200,83,0.2); color: #00e676; }
        .gatilho-loss { background: rgba(255,82,82,0.2); color: #ff5252; }

        /* Totais */
        .totals-section {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }
        @media (max-width: 800px) { .totals-section { grid-template-columns: 1fr; } }

        .totals-card {
            background: var(--bg-card);
            border-radius: 15px;
            padding: 15px;
            border: 1px solid var(--border);
        }
        .section-title { font-size: 1em; margin-bottom: 12px; }

        .footer {
            text-align: center;
            padding: 10px;
            color: var(--text-secondary);
            font-size: 0.8em;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>MARTINGALE V2</h1>
        </header>

        <div class="main-chart-card">
            <div class="main-chart-container">
                <canvas id="main-chart"></canvas>
            </div>
            <div class="chart-legend" id="chart-legend"></div>
        </div>

        <div class="machines-grid" id="machines-grid"></div>

        <div class="totals-section">
            <div class="totals-card" id="totals-card"></div>
            <div class="totals-card" id="stats-card"></div>
        </div>

        <footer class="footer">
            Atualizado: <span id="update-time">--</span> | Refresh: 5s
        </footer>
    </div>

    <script>
        let mainChart = null;

        function formatMoney(v) {
            return 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }

        function formatPct(v) {
            return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
        }

        function createMainChart(data) {
            const ctx = document.getElementById('main-chart');
            if (!ctx) return;

            const machines = [
                { key: 'agressiva', color: data.agressiva.color, name: data.agressiva.name },
                { key: 'conservadora', color: data.conservadora.color, name: data.conservadora.name },
                { key: 'isolada', color: '#a66cff', name: 'ISOLADA' }
            ];

            const datasets = [];
            let allLabels = [];

            machines.forEach(m => {
                const hist = data[m.key].historico_saldo || [];
                if (hist.length > allLabels.length) {
                    allLabels = hist.map(h => h.horario);
                }
                datasets.push({
                    label: m.name,
                    data: hist.map(h => h.saldo),
                    borderColor: m.color,
                    backgroundColor: 'transparent',
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 2,
                });
            });

            if (mainChart) {
                mainChart.data.labels = allLabels;
                mainChart.data.datasets = datasets;
                mainChart.update('none');
            } else {
                mainChart = new Chart(ctx, {
                    type: 'line',
                    data: { labels: allLabels, datasets: datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: ctx => ctx.dataset.label + ': ' + formatMoney(ctx.parsed.y)
                                }
                            }
                        },
                        scales: {
                            x: { display: false },
                            y: {
                                grid: { color: 'rgba(255,255,255,0.03)' },
                                ticks: {
                                    color: '#666',
                                    font: { size: 10 },
                                    callback: v => 'R$ ' + (v/1000).toFixed(1) + 'k'
                                }
                            }
                        }
                    }
                });
            }

            document.getElementById('chart-legend').innerHTML = machines.map(m =>
                `<div class="legend-item"><span class="legend-dot" style="background:${m.color}"></span>${m.name}</div>`
            ).join('');
        }

        function renderMachine(id, data) {
            const lucro = data.saldo - data.deposito_inicial;
            const lucroPct = data.deposito_inicial > 0 ? (lucro / data.deposito_inicial * 100) : 0;
            const winRate = (data.sessoes_win + data.sessoes_loss) > 0
                ? (data.sessoes_win / (data.sessoes_win + data.sessoes_loss) * 100) : 0;

            // Lucros por período
            const p2h = data.profit_2h || {lucro: 0, pct: 0};
            const p6h = data.profit_6h || {lucro: 0, pct: 0};
            const p12h = data.profit_12h || {lucro: 0, pct: 0};
            const p24h = data.profit_24h || {lucro: 0, pct: 0};

            // Gatilhos
            let gatilhosHtml = '';
            if (data.ultimos_gatilhos && data.ultimos_gatilhos.length > 0) {
                gatilhosHtml = `
                    <div class="gatilhos-section">
                        <div class="gatilhos-label">Últimos Ciclos</div>
                        <div class="gatilhos-list">
                            ${data.ultimos_gatilhos.slice(-10).map(g =>
                                `<span class="gatilho-item gatilho-${g.resultado.toLowerCase()}">${g.horario} T${g.tentativa}</span>`
                            ).join('')}
                        </div>
                    </div>`;
            }

            return `
                <div class="machine-card" style="border-top: 3px solid ${data.color}">
                    <div class="machine-header">
                        <div>
                            <div class="machine-title" style="color:${data.color}">${data.name}</div>
                            <div class="machine-subtitle">${data.subtitle}</div>
                            <div class="machine-initial">Inicial: ${formatMoney(data.initial_deposit || data.deposito_inicial)} | Base: ${formatMoney(data.initial_bet || data.aposta_base)}</div>
                        </div>
                        <span class="status-badge status-${data.status}">${data.status}</span>
                    </div>

                    <div class="metrics-row">
                        <div class="metric-box">
                            <div class="metric-label">Saldo</div>
                            <div class="metric-value" style="color:${data.color}">${formatMoney(data.saldo)}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Lucro</div>
                            <div class="metric-value ${lucro >= 0 ? 'positive' : 'negative'}">${formatMoney(lucro)}</div>
                            <div class="metric-sub">${formatPct(lucroPct)}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Taxa</div>
                            <div class="metric-value">${winRate.toFixed(0)}%</div>
                            <div class="metric-sub">W:${data.sessoes_win} L:${data.sessoes_loss}</div>
                        </div>
                    </div>

                    <div class="period-profits">
                        <div class="period-box">
                            <div class="period-label">2H</div>
                            <div class="period-value ${p2h.lucro >= 0 ? 'positive' : 'negative'}">${formatMoney(p2h.lucro)}</div>
                        </div>
                        <div class="period-box">
                            <div class="period-label">6H</div>
                            <div class="period-value ${p6h.lucro >= 0 ? 'positive' : 'negative'}">${formatMoney(p6h.lucro)}</div>
                        </div>
                        <div class="period-box">
                            <div class="period-label">12H</div>
                            <div class="period-value ${p12h.lucro >= 0 ? 'positive' : 'negative'}">${formatMoney(p12h.lucro)}</div>
                        </div>
                        <div class="period-box">
                            <div class="period-label">24H</div>
                            <div class="period-value ${p24h.lucro >= 0 ? 'positive' : 'negative'}">${formatMoney(p24h.lucro)}</div>
                        </div>
                    </div>

                    <div class="metrics-row">
                        <div class="metric-box">
                            <div class="metric-label">Média/Dia</div>
                            <div class="metric-value ${(data.daily_avg || 0) >= 0 ? 'positive' : 'negative'}">${formatMoney(data.daily_avg || 0)}</div>
                            <div class="metric-sub">${formatPct(data.daily_avg_pct || 0)}/dia</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Uptime</div>
                            <div class="metric-value">${data.uptime || 'N/A'}</div>
                        </div>
                    </div>

                    ${gatilhosHtml}
                </div>
            `;
        }

        function renderTotals(data) {
            const saldoTotal = data.agressiva.saldo + data.conservadora.saldo + data.isolada.saldo;
            const lucroTotal = (data.agressiva.saldo - data.agressiva.deposito_inicial) +
                              (data.conservadora.saldo - data.conservadora.deposito_inicial) +
                              (data.isolada.saldo - data.isolada.deposito_inicial);
            const depositoTotal = data.agressiva.deposito_inicial + data.conservadora.deposito_inicial + data.isolada.deposito_inicial;
            const lucroPct = depositoTotal > 0 ? (lucroTotal / depositoTotal * 100) : 0;

            const lucroAcum = (data.agressiva.lucro_acumulado_anterior || 0) +
                             (data.conservadora.lucro_acumulado_anterior || 0) +
                             (data.isolada.lucro_acumulado_anterior || 0);

            return `
                <div class="section-title">Totais Combinados</div>
                <div class="metrics-row">
                    <div class="metric-box">
                        <div class="metric-label">Saldo Total</div>
                        <div class="metric-value" style="color:var(--accent-2)">${formatMoney(saldoTotal)}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Lucro Sessão</div>
                        <div class="metric-value ${lucroTotal >= 0 ? 'positive' : 'negative'}">${formatMoney(lucroTotal)}</div>
                        <div class="metric-sub">${formatPct(lucroPct)}</div>
                    </div>
                </div>
                <div class="metrics-row">
                    <div class="metric-box">
                        <div class="metric-label">Lucro Acumulado</div>
                        <div class="metric-value" style="color:#ffc107">${formatMoney(lucroAcum)}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Lucro Total</div>
                        <div class="metric-value ${(lucroTotal + lucroAcum) >= 0 ? 'positive' : 'negative'}">${formatMoney(lucroTotal + lucroAcum)}</div>
                    </div>
                </div>
            `;
        }

        function renderStats(data) {
            const winsTotal = data.agressiva.sessoes_win + data.conservadora.sessoes_win + data.isolada.sessoes_win;
            const lossTotal = data.agressiva.sessoes_loss + data.conservadora.sessoes_loss + data.isolada.sessoes_loss;
            const winRate = (winsTotal + lossTotal) > 0 ? (winsTotal / (winsTotal + lossTotal) * 100) : 0;
            const rodadasTotal = data.agressiva.total_rodadas + data.conservadora.total_rodadas + data.isolada.total_rodadas;

            return `
                <div class="section-title">Estatísticas</div>
                <div class="metrics-row">
                    <div class="metric-box">
                        <div class="metric-label">Wins/Losses</div>
                        <div class="metric-value">W:${winsTotal} L:${lossTotal}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Taxa Geral</div>
                        <div class="metric-value">${winRate.toFixed(1)}%</div>
                    </div>
                </div>
                <div class="metrics-row">
                    <div class="metric-box">
                        <div class="metric-label">Rodadas Total</div>
                        <div class="metric-value">${rodadasTotal.toLocaleString()}</div>
                    </div>
                </div>
            `;
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                createMainChart(data);

                document.getElementById('machines-grid').innerHTML =
                    renderMachine('agressiva', data.agressiva) +
                    renderMachine('conservadora', data.conservadora) +
                    renderMachine('isolada', data.isolada);

                document.getElementById('totals-card').innerHTML = renderTotals(data);
                document.getElementById('stats-card').innerHTML = renderStats(data);
                document.getElementById('update-time').textContent = new Date().toLocaleTimeString('pt-BR');

            } catch (error) {
                console.error('Erro:', error);
            }
        }

        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
'''


@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/status')
def api_status():
    """Retorna status de todas as máquinas"""
    carregar_estado_local()

    result = {}
    for key, machine in machines_state.items():
        m = machine.copy()
        m['status'] = get_machine_status(machine)
        m['uptime'] = calcular_uptime(machine.get('uptime_start'))

        if m.get('last_update') and isinstance(m['last_update'], datetime):
            m['last_update'] = m['last_update'].isoformat()

        # Display info baseado no modo
        if key != 'isolada':
            modo = m.get('modo', 'g6_ns10')
            machine_type = MACHINE_TYPES.get(key, 'Unknown')
            display = get_display_info(modo, machine_type)
            m['name'] = display['name']
            m['subtitle'] = display['subtitle']
            m['color'] = display['color']
        else:
            m['name'] = 'ISOLADA'
            m['subtitle'] = 'Windows Solo - NS10'
            m['color'] = '#a66cff'

        # Lucro acumulado
        m['lucro_acumulado_anterior'] = DASHBOARD_CONFIG.get(key, {}).get('lucro_acumulado_anterior', 0) or 0

        # Dados históricos
        hist = historical_data.get(key, {})
        m['initial_deposit'] = hist.get('initial_deposit', m.get('deposito_inicial', 0))
        m['initial_bet'] = hist.get('initial_bet', m.get('aposta_base', 0))

        # Lucros por período
        for hours, label in [(2, '2h'), (6, '6h'), (12, '12h'), (24, '24h')]:
            lucro, pct = get_profit_by_period(key, hours)
            m[f'profit_{label}'] = {'lucro': lucro, 'pct': pct}

        # Média diária
        daily_avg, daily_pct = get_daily_average(key)
        m['daily_avg'] = daily_avg
        m['daily_avg_pct'] = daily_pct

        result[key] = m

    return jsonify(result)


@app.route('/api/update/<machine_id>', methods=['POST'])
def api_update(machine_id):
    """Recebe atualização de uma máquina remota"""
    if machine_id not in machines_state:
        return jsonify({'error': 'Máquina não encontrada'}), 404

    try:
        data = request.json

        # Override deposito se configurado
        deposito_inicial = data.get('deposito_inicial', 0)
        override = DASHBOARD_CONFIG.get(machine_id, {}).get('deposito_inicial_override')
        if override is not None:
            deposito_inicial = override

        # Calcular aposta_base se necessário
        saldo = data.get('saldo', 0)
        modo = data.get('modo', 'g6_ns10')
        aposta_base = data.get('aposta_base', 0)
        if aposta_base == 0 and saldo > 0:
            aposta_base = calcular_aposta_base(saldo, modo)

        machines_state[machine_id].update({
            'status': 'online',
            'last_update': datetime.now(),
            'saldo': saldo,
            'deposito_inicial': deposito_inicial,
            'aposta_base': aposta_base,
            'nivel': data.get('nivel', 10),
            'modo': modo,
            'sessoes_win': data.get('sessoes_win', 0),
            'sessoes_loss': data.get('sessoes_loss', 0),
            'total_rodadas': data.get('total_rodadas', 0),
            'uptime_start': data.get('uptime_start'),
            'historico_saldo': data.get('historico_saldo', []),
            'ultimos_gatilhos': data.get('ultimos_gatilhos', []),
            'last_mult': data.get('last_mult'),
            'last_mult_time': data.get('last_mult_time'),
        })

        update_historical_data(machine_id, machines_state[machine_id])

        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_dashboard():
    """Inicia o servidor"""
    load_history()
    print(f"\n{'='*50}")
    print(f"  DASHBOARD V2 - MartingaleV2")
    print(f"{'='*50}")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print(f"{'='*50}\n")
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=False, threaded=True)


if __name__ == '__main__':
    run_dashboard()
