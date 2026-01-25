#!/bin/bash

cd "$(dirname "$0")"

# Ativar ambiente virtual
source venv/bin/activate

echo ""
echo "   ╔═══════════════════════════════════════╗"
echo "   ║       MARTINGALE V2 + DASHBOARD       ║"
echo "   ╚═══════════════════════════════════════╝"
echo ""

while true; do
    python start_v2.py
    EXIT_CODE=$?

    # Verificar se foi reinicio automatico (exit code 42)
    if [ $EXIT_CODE -eq 42 ]; then
        echo ""
        echo "   [AUTO-RESTART] Reiniciando em 5 segundos..."
        echo ""
        sleep 5
    else
        echo ""
        echo "   [FIM] Bot encerrado normalmente."
        break
    fi
done
