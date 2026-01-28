#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DASHBOARD WEB - Monitoramento Centralizado 3 Máquinas
Interface elegante com gráficos em tempo real
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

# Configuração
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_PORT = 8080

# Carregar configuração de overrides (depositos iniciais corretos)
DASHBOARD_CONFIG = {}
config_file = os.path.join(BASE_DIR, 'dashboard_config.json')
if os.path.exists(config_file):
    try:
        with open(config_file, 'r') as f:
            DASHBOARD_CONFIG = json.load(f)
        print(f"[DASHBOARD] Config carregada: {config_file}")
    except Exception as e:
        print(f"[DASHBOARD] Erro ao carregar config: {e}")

# Função para obter nome/cor baseado no modo
def get_display_info(modo, machine_type):
    """Retorna nome, subtítulo e cor baseado no modo atual"""
    if modo in ['g6_ns9', 'G6_NS9']:
        return {
            'name': 'AGRESSIVA',
            'subtitle': f'{machine_type} - NS9',
            'color': '#ff6b6b'  # Vermelho
        }
    else:  # NS10
        return {
            'name': 'CONSERVADORA',
            'subtitle': f'{machine_type} - NS10',
            'color': '#4ecdc4'  # Verde/Cyan
        }

# Tipos de máquina (fixos)
MACHINE_TYPES = {
    'agressiva': 'Linux',
    'conservadora': 'Windows Dual',
    'isolada': 'Windows Solo'
}

# Estado das máquinas
machines_state = {
    'agressiva': {
        'name': 'AGRESSIVA',
        'subtitle': 'Linux - NS9',
        'color': '#ff6b6b',
        'machine_type': 'Linux',
        'status': 'offline',
        'last_update': None,
        'last_mult': None,
        'last_mult_time': None,
        'saldo': 0,
        'deposito_inicial': 0,
        'aposta_base': 0,
        'nivel': 9,
        'modo': 'g6_ns9',
        'lucro_para_subir': 5.8,
        'sessoes_win': 0,
        'sessoes_loss': 0,
        'uptime_start': None,
        'ultimos_gatilhos': [],
        'total_rodadas': 0,
        'historico_saldo': [],  # Para o gráfico
    },
    'conservadora': {
        'name': 'CONSERVADORA',
        'subtitle': 'Windows Dual - NS10',
        'color': '#4ecdc4',
        'machine_type': 'Windows Dual',
        'status': 'offline',
        'last_update': None,
        'last_mult': None,
        'last_mult_time': None,
        'saldo': 0,
        'deposito_inicial': 0,
        'aposta_base': 0,
        'nivel': 10,
        'modo': 'g6_ns10',
        'sessoes_win': 0,
        'sessoes_loss': 0,
        'uptime_start': None,
        'ultimos_gatilhos': [],
        'total_rodadas': 0,
        'historico_saldo': [],
    },
    'isolada': {
        'name': 'ISOLADA',
        'subtitle': 'Windows Solo - NS10',
        'color': '#a66cff',
        'machine_type': 'Windows Solo',
        'status': 'offline',
        'last_update': None,
        'last_mult': None,
        'last_mult_time': None,
        'saldo': 0,
        'deposito_inicial': 0,
        'aposta_base': 0,
        'nivel': 10,
        'modo': 'g6_ns10',
        'sessoes_win': 0,
        'sessoes_loss': 0,
        'uptime_start': None,
        'ultimos_gatilhos': [],
        'total_rodadas': 0,
        'historico_saldo': [],
    }
}

# Última distribuição
ultima_distribuicao = {
    'timestamp': None,
    'agressiva': 0,
    'conservadora': 0,
}

app = Flask(__name__)

def carregar_estado_local():
    """Carrega estado da máquina local (AGRESSIVA)"""
    try:
        state_file = os.path.join(BASE_DIR, 'session_state.json')
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)

            config = state.get('config_modo', {})
            nivel = state.get('nivel_seguranca', 9)
            saldo = state.get('saldo_atual', 0)

            # Calcular aposta base
            divisores = {6: 63, 7: 127, 8: 255, 9: 511, 10: 1023}
            divisor = divisores.get(nivel, 511)
            aposta_base = saldo / divisor

            # Extrair últimos gatilhos do histórico
            historico = state.get('historico_apostas', [])
            ultimos = []
            for h in historico[-10:]:
                ultimos.append({
                    'tentativa': h.get('tentativa', 1),
                    'resultado': 'WIN' if h.get('ganhou', False) else 'LOSS',
                    'horario': h.get('horario', ''),
                    'mult': h.get('multiplicador_real', 0)
                })

            # Histórico de saldo para gráfico (baseado nas apostas)
            historico_saldo = []
            saldo_acumulado = state.get('deposito_inicial', 0)
            for h in historico:
                resultado = h.get('resultado', 0)
                saldo_acumulado += resultado
                historico_saldo.append({
                    'horario': h.get('horario', ''),
                    'saldo': saldo_acumulado
                })

            # Pegar último multiplicador
            last_mult = None
            last_mult_time = None
            if historico:
                last = historico[-1]
                last_mult = last.get('multiplicador_real')
                last_mult_time = last.get('horario')

            # Usar override de deposito_inicial se existir no config (valor != null)
            deposito_inicial = state.get('deposito_inicial', 0)
            override = DASHBOARD_CONFIG.get('agressiva', {}).get('deposito_inicial_override')
            if override is not None:
                deposito_inicial = override

            machines_state['agressiva'].update({
                'status': 'online',
                'last_update': datetime.now(),
                'last_mult': last_mult,
                'last_mult_time': last_mult_time,
                'saldo': saldo,
                'deposito_inicial': deposito_inicial,
                'aposta_base': aposta_base,
                'nivel': nivel,
                'modo': config.get('modo', 'g6_ns9'),
                'lucro_para_subir': config.get('lucro_para_subir', 5.8),
                'sessoes_win': state.get('sessoes_win', 0),
                'sessoes_loss': state.get('sessoes_loss', 0),
                'uptime_start': state.get('inicio_timestamp'),
                'ultimos_gatilhos': ultimos,
                'total_rodadas': state.get('total_rodadas', 0),
                'historico_saldo': historico_saldo[-50:],  # Últimos 50 pontos
            })
    except Exception as e:
        print(f"[DASHBOARD] Erro ao carregar estado local: {e}")

def calcular_uptime(start_str):
    """Calcula uptime a partir de string de timestamp"""
    if not start_str:
        return "N/A"
    try:
        start = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
        delta = datetime.now() - start
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}min"
    except:
        return "N/A"

def calcular_tempo_desde(time_str):
    """Calcula tempo desde um horário (formato HH:MM:SS)"""
    if not time_str:
        return "N/A"
    try:
        hoje = datetime.now().date()
        hora = datetime.strptime(time_str, '%H:%M:%S').time()
        momento = datetime.combine(hoje, hora)
        if momento > datetime.now():
            momento -= timedelta(days=1)
        delta = datetime.now() - momento
        segundos = int(delta.total_seconds())
        if segundos < 60:
            return f"{segundos}s"
        elif segundos < 3600:
            return f"{segundos // 60}min"
        else:
            return f"{segundos // 3600}h {(segundos % 3600) // 60}min"
    except:
        return time_str

def get_machine_status(machine):
    """Verifica se máquina está online"""
    last = machine.get('last_update')
    if not last:
        return 'offline'
    if isinstance(last, str):
        try:
            last = datetime.strptime(last, '%Y-%m-%d %H:%M:%S')
        except:
            return 'offline'
    delta = datetime.now() - last
    return 'online' if delta.total_seconds() < 120 else 'offline'

# Template HTML Elegante
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MartingaleV2 Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-card: #16213e;
            --accent-1: #ff6b6b;
            --accent-2: #4ecdc4;
            --accent-3: #a66cff;
            --text-primary: #ffffff;
            --text-secondary: #a0a0a0;
            --border: rgba(255,255,255,0.1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }

        /* Header */
        .header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 20px;
        }
        .header h1 {
            font-size: 2.2em;
            font-weight: 300;
            letter-spacing: 3px;
            background: linear-gradient(135deg, var(--accent-1), var(--accent-2), var(--accent-3));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header .tagline {
            color: var(--text-secondary);
            margin-top: 5px;
            font-size: 1em;
        }

        /* Grafico Unificado */
        .unified-chart-card {
            background: var(--bg-card);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 25px;
            border: 1px solid var(--border);
        }
        .unified-chart-container {
            height: 200px;
        }
        .chart-legend {
            display: flex;
            justify-content: center;
            gap: 25px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9em;
        }
        .legend-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }

        /* Grid de Máquinas */
        .machines-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 25px;
        }
        @media (max-width: 1200px) {
            .machines-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 800px) {
            .machines-grid { grid-template-columns: 1fr; }
        }

        /* Card de Máquina */
        .machine-card {
            background: var(--bg-card);
            border-radius: 20px;
            padding: 20px;
            border: 1px solid var(--border);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .machine-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.3);
        }
        .machine-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }
        .machine-title {
            font-size: 1.3em;
            font-weight: 600;
        }
        .machine-subtitle {
            color: var(--text-secondary);
            font-size: 0.8em;
            margin-top: 2px;
        }
        .status-badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .status-online { background: #00c853; color: white; }
        .status-offline { background: #ff5252; color: white; }

        /* Métricas */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 15px;
        }
        .metric {
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            padding: 12px;
        }
        .metric-label {
            color: var(--text-secondary);
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }
        .metric-value {
            font-size: 1.3em;
            font-weight: 600;
        }
        .metric-subvalue {
            font-size: 0.85em;
            color: var(--text-secondary);
            margin-top: 2px;
        }
        .metric-value.positive { color: #00e676; }
        .metric-value.negative { color: #ff5252; }

        /* Barra de Progresso */
        .progress-section {
            margin-bottom: 15px;
            background: rgba(255,107,107,0.1);
            border-radius: 10px;
            padding: 12px;
            border: 1px solid rgba(255,107,107,0.3);
        }
        .progress-label {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.85em;
        }
        .progress-bar {
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
            height: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 8px;
            transition: width 0.5s ease;
        }

        /* Ciclos/Gatilhos detalhados */
        .ciclos-section {
            margin-top: 12px;
        }
        .ciclos-label {
            color: var(--text-secondary);
            font-size: 0.75em;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .ciclos-list {
            display: flex;
            flex-direction: column;
            gap: 4px;
            max-height: 180px;
            overflow-y: auto;
        }
        .ciclo-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 0.8em;
        }
        .ciclo-win { background: rgba(0,200,83,0.15); }
        .ciclo-loss { background: rgba(255,82,82,0.15); }
        .ciclo-time { color: var(--text-secondary); }
        .ciclo-result { font-weight: 600; }
        .ciclo-result.win { color: #00e676; }
        .ciclo-result.loss { color: #ff5252; }

        /* Seção Totais e Distribuição */
        .bottom-section {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 25px;
        }
        @media (max-width: 900px) {
            .bottom-section { grid-template-columns: 1fr; }
        }

        .totals-card, .dist-card {
            background: var(--bg-card);
            border-radius: 20px;
            padding: 20px;
            border: 1px solid var(--border);
        }
        .totals-card {
            background: linear-gradient(135deg, var(--bg-card), rgba(78,205,196,0.1));
            border-color: rgba(78,205,196,0.3);
        }
        .dist-card {
            background: linear-gradient(135deg, var(--bg-card), rgba(255,193,7,0.1));
            border-color: rgba(255,193,7,0.3);
        }
        .section-title {
            font-size: 1.2em;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Distribuição */
        .dist-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
        }
        .dist-row:last-child { border-bottom: none; }
        .dist-action {
            color: #ffc107;
            font-weight: 600;
        }
        .dist-calc {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 15px;
            margin-top: 15px;
        }
        .dist-calc-title {
            text-align: center;
            color: #ffc107;
            margin-bottom: 12px;
            font-weight: 600;
            font-size: 0.95em;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 15px;
            color: var(--text-secondary);
            font-size: 0.85em;
            margin-top: 25px;
            border-top: 1px solid var(--border);
        }
        .update-time { color: var(--accent-2); }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>MARTINGALE V2</h1>
            <p class="tagline">Dashboard de Monitoramento em Tempo Real</p>
        </header>

        <!-- Grafico Unificado -->
        <div class="unified-chart-card">
            <div class="unified-chart-container">
                <canvas id="unified-chart"></canvas>
            </div>
            <div class="chart-legend" id="chart-legend"></div>
        </div>

        <div class="machines-grid" id="machines-grid"></div>

        <div class="bottom-section">
            <div class="totals-card" id="totals-card"></div>
            <div class="dist-card" id="dist-card"></div>
        </div>

        <footer class="footer">
            Última atualização: <span class="update-time" id="update-time">--</span>
            &nbsp;|&nbsp; Auto-refresh: 5s
        </footer>
    </div>

    <script>
        let unifiedChart = null;

        function formatMoney(value) {
            return new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'BRL'
            }).format(value);
        }

        function formatPct(value) {
            return (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
        }

        function createUnifiedChart(data) {
            const ctx = document.getElementById('unified-chart');
            if (!ctx) return;

            // Preparar dados - normalizar para % de lucro
            const datasets = [];
            const machines = [
                { key: 'agressiva', label: 'CONSERVADORA', color: data.agressiva.color },
                { key: 'conservadora', label: 'AGRESSIVA', color: data.conservadora.color },
                { key: 'isolada', label: 'ISOLADA', color: '#a66cff' }
            ];

            // Pegar o maior historico para usar como labels
            let maxLen = 0;
            let allLabels = [];
            machines.forEach(m => {
                const hist = data[m.key].historico_saldo || [];
                if (hist.length > maxLen) {
                    maxLen = hist.length;
                    allLabels = hist.map(h => h.horario);
                }
            });

            machines.forEach(m => {
                const hist = data[m.key].historico_saldo || [];
                const deposito = data[m.key].deposito_inicial || 1;
                // Converter para % de lucro
                const valores = hist.map(h => ((h.saldo - deposito) / deposito * 100));
                datasets.push({
                    label: m.label,
                    data: valores,
                    borderColor: m.color,
                    backgroundColor: 'transparent',
                    tension: 0.3,
                    pointRadius: 0,
                    borderWidth: 2,
                });
            });

            if (unifiedChart) {
                unifiedChart.data.labels = allLabels;
                unifiedChart.data.datasets = datasets;
                unifiedChart.update('none');
            } else {
                unifiedChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: allLabels,
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false,
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return context.dataset.label + ': ' + context.parsed.y.toFixed(2) + '%';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { display: false },
                            y: {
                                display: true,
                                grid: { color: 'rgba(255,255,255,0.05)' },
                                ticks: {
                                    color: '#666',
                                    font: { size: 10 },
                                    callback: function(value) {
                                        return value.toFixed(1) + '%';
                                    }
                                }
                            }
                        }
                    }
                });
            }

            // Atualizar legenda
            document.getElementById('chart-legend').innerHTML = machines.map(m =>
                `<div class="legend-item">
                    <span class="legend-dot" style="background: ${m.color};"></span>
                    <span>${m.label}</span>
                </div>`
            ).join('');
        }

        function renderMachine(id, data) {
            const lucroSessao = data.saldo - data.deposito_inicial;
            const lucroNs9 = data.lucro_ns9 || 0;
            const lucroAcumuladoAnterior = data.lucro_acumulado_anterior || 0;
            const lucroTotal = lucroSessao + lucroAcumuladoAnterior + lucroNs9;
            const lucroPct = data.deposito_inicial > 0 ? (lucroSessao / data.deposito_inicial * 100) : 0;
            const lucroTotalPct = data.deposito_inicial > 0 ? (lucroTotal / data.deposito_inicial * 100) : 0;
            const winRate = (data.sessoes_win + data.sessoes_loss) > 0
                ? (data.sessoes_win / (data.sessoes_win + data.sessoes_loss) * 100) : 0;

            // Barra de progresso para qualquer maquina em NS9
            let progressHtml = '';
            const modo = (data.modo || '').toLowerCase();
            if (modo.includes('ns9') || data.nivel === 9) {
                const progresso = Math.min(100, (lucroPct / data.lucro_para_subir) * 100);
                progressHtml = `
                    <div class="progress-section">
                        <div class="progress-label">
                            <span>Meta NS9 → NS10</span>
                            <span style="color: #ff6b6b; font-weight: 600;">${lucroPct.toFixed(2)}% / ${data.lucro_para_subir}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${progresso}%; background: linear-gradient(90deg, #ff6b6b, #00e676);"></div>
                        </div>
                    </div>
                `;
            }

            // Ultimos 10 ciclos com horario e tentativa
            let ciclosHtml = '';
            if (data.ultimos_gatilhos && data.ultimos_gatilhos.length > 0) {
                const ciclos = data.ultimos_gatilhos.slice(-10).reverse();
                ciclosHtml = `
                    <div class="ciclos-section">
                        <div class="ciclos-label">Últimos 10 Ciclos</div>
                        <div class="ciclos-list">
                            ${ciclos.map(g => {
                                const isWin = g.resultado === 'WIN';
                                return `<div class="ciclo-item ciclo-${isWin ? 'win' : 'loss'}">
                                    <span class="ciclo-time">${g.horario || '--:--'}</span>
                                    <span>T${g.tentativa}</span>
                                    <span class="ciclo-result ${isWin ? 'win' : 'loss'}">${isWin ? 'WIN' : 'LOSS'} ${g.mult ? g.mult.toFixed(2) + 'x' : ''}</span>
                                </div>`;
                            }).join('')}
                        </div>
                    </div>
                `;
            }

            return `
                <div class="machine-card" style="border-top: 3px solid ${data.color};">
                    <div class="machine-header">
                        <div>
                            <div class="machine-title" style="color: ${data.color};">${data.name}</div>
                            <div class="machine-subtitle">${data.subtitle}</div>
                        </div>
                        <span class="status-badge status-${data.status}">${data.status}</span>
                    </div>

                    ${progressHtml}

                    <div class="metrics-grid">
                        <div class="metric">
                            <div class="metric-label">Saldo</div>
                            <div class="metric-value" style="color: ${data.color};">${formatMoney(data.saldo)}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Lucro Sessão</div>
                            <div class="metric-value ${lucroSessao >= 0 ? 'positive' : 'negative'}">${formatMoney(lucroSessao)}</div>
                            <div class="metric-subvalue">${formatPct(lucroPct)}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Lucro Total</div>
                            <div class="metric-value ${lucroTotal >= 0 ? 'positive' : 'negative'}" style="font-weight: bold;">${formatMoney(lucroTotal)}</div>
                            <div class="metric-subvalue">${formatPct(lucroTotalPct)}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Nível</div>
                            <div class="metric-value">NS${data.nivel}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Sessão</div>
                            <div class="metric-value">W:${data.sessoes_win} L:${data.sessoes_loss}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Taxa</div>
                            <div class="metric-value">${winRate.toFixed(0)}%</div>
                        </div>
                    </div>

                    ${ciclosHtml}
                </div>
            `;
        }

        function renderTotals(data) {
            const depositoTotal = data.agressiva.deposito_inicial + data.conservadora.deposito_inicial + data.isolada.deposito_inicial;
            const saldoTotal = data.agressiva.saldo + data.conservadora.saldo + data.isolada.saldo;
            const lucroSessao = (data.agressiva.saldo - data.agressiva.deposito_inicial) +
                               (data.conservadora.saldo - data.conservadora.deposito_inicial) +
                               (data.isolada.saldo - data.isolada.deposito_inicial);
            const lucroNs9Total = (data.agressiva.lucro_ns9 || 0) + (data.conservadora.lucro_ns9 || 0) + (data.isolada.lucro_ns9 || 0);
            const lucroAcumulado = (data.agressiva.lucro_acumulado_anterior || 0) +
                                  (data.conservadora.lucro_acumulado_anterior || 0) +
                                  (data.isolada.lucro_acumulado_anterior || 0);
            const lucroTotal = lucroSessao + lucroAcumulado + lucroNs9Total;
            const lucroPct = depositoTotal > 0 ? (lucroSessao / depositoTotal * 100) : 0;
            const lucroTotalPct = depositoTotal > 0 ? (lucroTotal / depositoTotal * 100) : 0;
            const winsTotal = data.agressiva.sessoes_win + data.conservadora.sessoes_win + data.isolada.sessoes_win;
            const lossTotal = data.agressiva.sessoes_loss + data.conservadora.sessoes_loss + data.isolada.sessoes_loss;
            const winRate = (winsTotal + lossTotal) > 0 ? (winsTotal / (winsTotal + lossTotal) * 100) : 0;

            return `
                <div class="section-title">📊 Totais Combinados</div>
                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-label">Saldo Total</div>
                        <div class="metric-value" style="color: var(--accent-2);">${formatMoney(saldoTotal)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Lucro Sessão</div>
                        <div class="metric-value ${lucroSessao >= 0 ? 'positive' : 'negative'}">${formatMoney(lucroSessao)}</div>
                        <div class="metric-subvalue">${formatPct(lucroPct)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Lucro Total</div>
                        <div class="metric-value ${lucroTotal >= 0 ? 'positive' : 'negative'}" style="font-weight: bold;">${formatMoney(lucroTotal)}</div>
                        <div class="metric-subvalue">${formatPct(lucroTotalPct)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Taxa Geral</div>
                        <div class="metric-value">${winRate.toFixed(1)}%</div>
                    </div>
                </div>
                <div class="metrics-grid" style="margin-top: 10px;">
                    <div class="metric">
                        <div class="metric-label">Wins / Losses</div>
                        <div class="metric-value">W:${winsTotal} L:${lossTotal}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Acum. Anterior</div>
                        <div class="metric-value" style="color: #ffc107;">${formatMoney(lucroAcumulado)}</div>
                    </div>
                </div>
            `;
        }

        function renderDistribuicao(data) {
            // Pegar saldos baseado no modo (agressiva = quem está em NS9)
            let saldoAgressiva = 0;
            let saldoConservadora = 0;
            let nomeA = 'AGRESSIVA';
            let nomeC = 'CONSERVADORA';

            // Determinar qual máquina é qual baseado no modo
            if ((data.agressiva.modo || '').toLowerCase().includes('ns9')) {
                saldoAgressiva = data.agressiva.saldo;
                nomeA = data.agressiva.name;
            } else {
                saldoConservadora = data.agressiva.saldo;
                nomeC = data.agressiva.name;
            }
            if ((data.conservadora.modo || '').toLowerCase().includes('ns9')) {
                saldoAgressiva = data.conservadora.saldo;
                nomeA = data.conservadora.name;
            } else {
                saldoConservadora = data.conservadora.saldo;
                nomeC = data.conservadora.name;
            }

            // Se nenhuma está em NS9, usar os nomes/saldos padrão
            if (saldoAgressiva === 0 && saldoConservadora === 0) {
                saldoAgressiva = data.agressiva.saldo;
                saldoConservadora = data.conservadora.saldo;
                nomeA = data.agressiva.name;
                nomeC = data.conservadora.name;
            }

            const total = saldoAgressiva + saldoConservadora;
            const metade = total / 2;

            const diffA = metade - saldoAgressiva;
            const diffC = metade - saldoConservadora;

            const acaoA = diffA > 1 ? `depositar ${formatMoney(diffA)}` :
                         diffA < -1 ? `sacar ${formatMoney(Math.abs(diffA))}` : 'manter';
            const acaoC = diffC > 1 ? `depositar ${formatMoney(diffC)}` :
                         diffC < -1 ? `sacar ${formatMoney(Math.abs(diffC))}` : 'manter';

            return `
                <div class="section-title">💰 Distribuição Dual</div>
                <div class="dist-row">
                    <span style="color: var(--accent-1);">${nomeA}</span>
                    <span style="color: var(--accent-1);">${formatMoney(saldoAgressiva)}</span>
                </div>
                <div class="dist-row">
                    <span style="color: var(--accent-2);">${nomeC}</span>
                    <span style="color: var(--accent-2);">${formatMoney(saldoConservadora)}</span>
                </div>
                <div class="dist-row" style="border-top: 2px solid var(--border); padding-top: 12px;">
                    <span><strong>TOTAL DUAL</strong></span>
                    <span><strong>${formatMoney(total)}</strong></span>
                </div>

                <div class="dist-calc">
                    <div class="dist-calc-title">📊 Redistribuir 50/50</div>
                    <div class="dist-row">
                        <span>${nomeA} → ${formatMoney(metade)}</span>
                        <span class="dist-action">${acaoA}</span>
                    </div>
                    <div class="dist-row">
                        <span>${nomeC} → ${formatMoney(metade)}</span>
                        <span class="dist-action">${acaoC}</span>
                    </div>
                </div>
            `;
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                // Render unified chart
                createUnifiedChart(data);

                // Render machines
                document.getElementById('machines-grid').innerHTML =
                    renderMachine('agressiva', data.agressiva) +
                    renderMachine('conservadora', data.conservadora) +
                    renderMachine('isolada', data.isolada);

                // Render totals and distribution
                document.getElementById('totals-card').innerHTML = renderTotals(data);
                document.getElementById('dist-card').innerHTML = renderDistribuicao(data);

                // Update time
                document.getElementById('update-time').textContent = new Date().toLocaleTimeString('pt-BR');

            } catch (error) {
                console.error('Erro ao atualizar:', error);
            }
        }

        // Initial load and auto-refresh
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
        m['last_mult_ago'] = calcular_tempo_desde(machine.get('last_mult_time'))

        if m.get('last_update') and isinstance(m['last_update'], datetime):
            m['last_update'] = m['last_update'].strftime('%Y-%m-%d %H:%M:%S')

        # Atualizar nome/cor baseado no modo atual (exceto ISOLADA que mantém nome fixo)
        if key != 'isolada':
            modo = m.get('modo', 'g6_ns10')
            machine_type = MACHINE_TYPES.get(key, 'Unknown')
            display_info = get_display_info(modo, machine_type)
            m['name'] = display_info['name']
            m['subtitle'] = display_info['subtitle']
            m['color'] = display_info['color']

        # Adicionar lucro acumulado anterior e lucro NS9 do config
        config_machine = DASHBOARD_CONFIG.get(key, {})
        m['lucro_acumulado_anterior'] = config_machine.get('lucro_acumulado_anterior', 0) or 0
        m['lucro_ns9'] = config_machine.get('lucro_ns9', 0) or 0

        result[key] = m

    return jsonify(result)

def calcular_aposta_base(saldo, modo):
    """Calcula aposta base baseado em saldo e modo"""
    if saldo <= 0:
        return 0
    # NS9: divisor 511, NS10: divisor 1023
    if modo and modo.lower() in ['g6_ns9', 'ns9']:
        return saldo / 511
    return saldo / 1023  # NS10 padrão


@app.route('/api/update/<machine_id>', methods=['POST'])
def api_update(machine_id):
    """Recebe atualização de uma máquina remota"""
    if machine_id not in machines_state:
        return jsonify({'error': 'Máquina não encontrada'}), 404

    try:
        data = request.json

        # Usar override de deposito_inicial se existir no config (valor != null)
        deposito_inicial = data.get('deposito_inicial', 0)
        override = DASHBOARD_CONFIG.get(machine_id, {}).get('deposito_inicial_override')
        if override is not None:
            deposito_inicial = override

        # Calcular aposta_base se não foi enviado ou é 0
        saldo = data.get('saldo', 0)
        modo = data.get('modo', 'g6_ns10')
        aposta_base = data.get('aposta_base', 0)
        if aposta_base == 0 and saldo > 0:
            aposta_base = calcular_aposta_base(saldo, modo)

        machines_state[machine_id].update({
            'status': 'online',
            'last_update': datetime.now(),
            'last_mult': data.get('last_mult'),
            'last_mult_time': data.get('last_mult_time'),
            'saldo': saldo,
            'deposito_inicial': deposito_inicial,
            'aposta_base': aposta_base,
            'nivel': data.get('nivel', 10),
            'modo': modo,
            'sessoes_win': data.get('sessoes_win', 0),
            'sessoes_loss': data.get('sessoes_loss', 0),
            'uptime_start': data.get('uptime_start'),
            'ultimos_gatilhos': data.get('ultimos_gatilhos', []),
            'total_rodadas': data.get('total_rodadas', 0),
            'historico_saldo': data.get('historico_saldo', []),
        })

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_dashboard():
    """Inicia o servidor do dashboard"""
    print(f"\n{'='*60}")
    print(f"  DASHBOARD WEB - MartingaleV2")
    print(f"{'='*60}")
    print(f"  Acesse: http://localhost:{DASHBOARD_PORT}")
    print(f"  Rede local: http://SEU_IP:{DASHBOARD_PORT}")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=False, threaded=True)

if __name__ == '__main__':
    run_dashboard()
