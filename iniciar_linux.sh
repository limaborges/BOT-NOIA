#!/bin/bash

#═══════════════════════════════════════════════════════════════════════════════
#                    INICIAR MARTINGALE V2 - LINUX
#═══════════════════════════════════════════════════════════════════════════════

# Configurar display para pyautogui funcionar
export DISPLAY=:1

# Ir para o diretorio do bot
cd "$(dirname "$0")"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       MARTINGALE V2 - LINUX                                   ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Verificar se VNC esta rodando
if ! pgrep -x "Xtightvnc" > /dev/null; then
    echo "AVISO: VNC Server nao esta rodando!"
    echo "Execute primeiro: ./iniciar_vnc.sh"
    echo ""
    read -p "Deseja iniciar o VNC agora? (s/n): " resposta
    if [ "$resposta" = "s" ]; then
        vncserver :1 -geometry 1920x1080 -depth 24
        sleep 2
    else
        echo "Abortando. Inicie o VNC primeiro."
        exit 1
    fi
fi

echo "Iniciando bot..."
echo ""

# Iniciar o bot
python3 start_v2.py
