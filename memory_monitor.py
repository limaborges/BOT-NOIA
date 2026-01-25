#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MEMORY MONITOR - Monitora consumo de RAM do bot durante a noite

Uso:
1. Liga o bot normalmente
2. Abre outro terminal e roda: python memory_monitor.py
3. Deixa rodando a noite toda
4. De manhã, abre memory_log.csv no Excel ou me manda aqui
"""

import psutil
import time
import csv
import os
from datetime import datetime

# Configuracoes
INTERVALO_SEGUNDOS = 60  # Coleta a cada 1 minuto
LOG_FILE = "memory_log.csv"
PROCESSO_ALVO = "python"  # Nome do processo do bot

def get_python_processes():
    """Encontra todos os processos Python rodando"""
    python_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            name = proc.info['name'].lower()
            if 'python' in name:
                mem_mb = proc.info['memory_info'].rss / (1024 * 1024)
                cmdline = ' '.join(proc.info['cmdline'][:3]) if proc.info['cmdline'] else 'N/A'
                python_procs.append({
                    'pid': proc.info['pid'],
                    'mem_mb': mem_mb,
                    'cmdline': cmdline[:50]  # Primeiros 50 chars
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return python_procs

def get_system_memory():
    """Retorna uso de memoria do sistema"""
    mem = psutil.virtual_memory()
    return {
        'total_gb': mem.total / (1024**3),
        'used_gb': mem.used / (1024**3),
        'available_gb': mem.available / (1024**3),
        'percent': mem.percent
    }

def monitor():
    """Loop principal de monitoramento"""

    # Criar/abrir arquivo CSV
    file_exists = os.path.exists(LOG_FILE)

    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Cabecalho se arquivo novo
        if not file_exists:
            writer.writerow([
                'timestamp',
                'system_percent',
                'system_used_gb',
                'system_available_gb',
                'bot_mem_mb',
                'bot_pid',
                'all_python_mb',
                'num_python_procs'
            ])

    print("=" * 60)
    print("MEMORY MONITOR - Monitorando consumo de RAM")
    print("=" * 60)
    print(f"Intervalo: {INTERVALO_SEGUNDOS} segundos")
    print(f"Log: {LOG_FILE}")
    print("Pressione Ctrl+C para parar")
    print("=" * 60)

    coletas = 0
    mem_inicial = None

    try:
        while True:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Memoria do sistema
            sys_mem = get_system_memory()

            # Processos Python
            python_procs = get_python_processes()
            total_python_mb = sum(p['mem_mb'] for p in python_procs)
            num_procs = len(python_procs)

            # Encontrar o bot (maior processo Python, provavelmente)
            bot_proc = max(python_procs, key=lambda x: x['mem_mb']) if python_procs else None
            bot_mem = bot_proc['mem_mb'] if bot_proc else 0
            bot_pid = bot_proc['pid'] if bot_proc else 0

            # Guardar memoria inicial
            if mem_inicial is None and bot_mem > 100:  # Ignora se < 100MB
                mem_inicial = bot_mem

            # Salvar no CSV
            with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    now,
                    f"{sys_mem['percent']:.1f}",
                    f"{sys_mem['used_gb']:.2f}",
                    f"{sys_mem['available_gb']:.2f}",
                    f"{bot_mem:.1f}",
                    bot_pid,
                    f"{total_python_mb:.1f}",
                    num_procs
                ])

            coletas += 1

            # Print status
            delta = bot_mem - mem_inicial if mem_inicial else 0
            delta_str = f"+{delta:.0f}MB" if delta > 0 else f"{delta:.0f}MB"

            print(f"[{now}] Sistema: {sys_mem['percent']:.0f}% | "
                  f"Bot: {bot_mem:.0f}MB ({delta_str}) | "
                  f"Python total: {total_python_mb:.0f}MB ({num_procs} procs)")

            # Alerta se crescimento significativo
            if mem_inicial and delta > 500:
                print(f"    >>> ALERTA: Bot cresceu {delta:.0f}MB desde o inicio!")

            time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("MONITORAMENTO ENCERRADO")
        print("=" * 60)
        print(f"Total de coletas: {coletas}")
        print(f"Arquivo salvo: {LOG_FILE}")

        if mem_inicial:
            final_procs = get_python_processes()
            bot_final = max(final_procs, key=lambda x: x['mem_mb']) if final_procs else None
            if bot_final:
                crescimento = bot_final['mem_mb'] - mem_inicial
                print(f"\nMemoria inicial do bot: {mem_inicial:.0f} MB")
                print(f"Memoria final do bot: {bot_final['mem_mb']:.0f} MB")
                print(f"Crescimento: {crescimento:+.0f} MB")

                if crescimento > 100:
                    print("\n>>> CONCLUSAO: Ha vazamento de memoria!")
                else:
                    print("\n>>> CONCLUSAO: Memoria estavel, sem vazamento significativo.")

if __name__ == "__main__":
    monitor()
