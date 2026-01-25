#!/bin/bash

#═══════════════════════════════════════════════════════════════════════════════
#                    INSTALADOR MARTINGALE V2 - LINUX (Ubuntu)
#                    Instalacao 100% AUTOMATICA
#═══════════════════════════════════════════════════════════════════════════════

set -e  # Parar em caso de erro

# Senha padrao do VNC (pode mudar depois com: vncpasswd)
VNC_PASSWORD="bot12345"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       INSTALADOR MARTINGALE V2 - UBUNTU                       ║"
echo "║       Instalacao 100% AUTOMATICA - NAO PRECISA FAZER NADA     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Este processo leva 10-20 minutos. Va tomar um cafe!"
echo "Tudo sera configurado automaticamente."
echo ""
sleep 3

# ============================================================
# CONFIGURAR TIMEZONE BRASILIA
# ============================================================
echo ""
echo "[1/8] Configurando timezone para Brasilia..."
timedatectl set-timezone America/Sao_Paulo
echo "      OK - Timezone configurado!"

# ============================================================
# ATUALIZAR SISTEMA
# ============================================================
echo ""
echo "[2/8] Atualizando sistema (pode demorar)..."
apt update -y
apt upgrade -y
echo "      OK - Sistema atualizado!"

# ============================================================
# INSTALAR AMBIENTE GRAFICO (XFCE)
# ============================================================
echo ""
echo "[3/8] Instalando ambiente grafico XFCE..."
apt install -y xfce4 xfce4-goodies
echo "      OK - XFCE instalado!"

# ============================================================
# INSTALAR VNC SERVER
# ============================================================
echo ""
echo "[4/8] Instalando servidor VNC..."
apt install -y tightvncserver
echo "      OK - VNC Server instalado!"

# ============================================================
# INSTALAR FIREFOX
# ============================================================
echo ""
echo "[5/8] Instalando Firefox..."
apt install -y firefox
echo "      OK - Firefox instalado!"

# ============================================================
# INSTALAR PYTHON E PIP
# ============================================================
echo ""
echo "[6/8] Instalando Python 3 e pip..."
apt install -y python3 python3-pip python3-venv python3-tk python3-dev
echo "      OK - Python instalado!"

# ============================================================
# INSTALAR TESSERACT OCR
# ============================================================
echo ""
echo "[7/8] Instalando Tesseract OCR..."
apt install -y tesseract-ocr tesseract-ocr-por
echo "      OK - Tesseract instalado!"

# ============================================================
# INSTALAR DEPENDENCIAS PYTHON
# ============================================================
echo ""
echo "[8/8] Instalando dependencias Python (pode demorar)..."

# Instalar dependencias do sistema para pyautogui
apt install -y scrot python3-xlib

# Instalar pacotes pip
pip3 install --upgrade pip

echo "      Instalando pyautogui..."
pip3 install pyautogui

echo "      Instalando pyperclip..."
pip3 install pyperclip

echo "      Instalando numpy..."
pip3 install numpy

echo "      Instalando colorama..."
pip3 install colorama

echo "      Instalando mss..."
pip3 install mss

echo "      Instalando pillow..."
pip3 install pillow

echo "      Instalando psutil..."
pip3 install psutil

echo "      Instalando requests..."
pip3 install requests

echo "      Instalando pytesseract..."
pip3 install pytesseract

echo "      Instalando rich..."
pip3 install rich

echo "      Instalando python-telegram-bot..."
pip3 install python-telegram-bot

echo "      Instalando opencv-python..."
pip3 install opencv-python-headless

echo "      Instalando easyocr (pode demorar 2-3 min)..."
pip3 install easyocr

echo ""
echo "      OK - Todas as dependencias Python instaladas!"

# ============================================================
# CONFIGURAR VNC (100% AUTOMATICO)
# ============================================================
echo ""
echo "[9/9] Configurando VNC Server automaticamente..."

# Criar diretorio vnc
mkdir -p ~/.vnc

# Criar senha VNC automaticamente (sem interacao)
echo "$VNC_PASSWORD" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Configurar xstartup para XFCE
cat > ~/.vnc/xstartup << 'EOF'
#!/bin/bash
xrdb $HOME/.Xresources
startxfce4 &
EOF

chmod +x ~/.vnc/xstartup

echo "      OK - VNC configurado com senha: $VNC_PASSWORD"

# ============================================================
# CRIAR SCRIPT DE INICIO DO VNC
# ============================================================
cat > /root/iniciar_vnc.sh << 'EOF'
#!/bin/bash
vncserver -kill :1 2>/dev/null
vncserver :1 -geometry 1920x1080 -depth 24
echo ""
echo "VNC Server iniciado!"
echo "Conecte usando: SEU_IP:5901"
echo ""
EOF
chmod +x /root/iniciar_vnc.sh

# ============================================================
# INICIAR VNC AUTOMATICAMENTE
# ============================================================
echo ""
echo "Iniciando VNC Server..."
vncserver :1 -geometry 1920x1080 -depth 24
sleep 2

# Pegar IP publico
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "SEU_IP")

# ============================================================
# CONCLUSAO
# ============================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       INSTALACAO CONCLUIDA COM SUCESSO!                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  DADOS PARA CONECTAR:                                         ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║                                                               ║"
echo "║  VNC Viewer: $PUBLIC_IP:5901"
echo "║  Senha VNC:  $VNC_PASSWORD"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "PROXIMO PASSO:"
echo ""
echo "1. No seu PC, abra o VNC Viewer"
echo "2. Conecte em: $PUBLIC_IP:5901"
echo "3. Senha: $VNC_PASSWORD"
echo "4. Abra Firefox, faca login no site"
echo "5. Abra terminal e execute: python3 /root/MartingaleV2_Build/start_v2.py"
echo ""
echo "Instalacao finalizada!"
