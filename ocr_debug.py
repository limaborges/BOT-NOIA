#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR DEBUG - Script para visualizar o que o OCR está captando
Roda separado do bot, não interfere em nada
"""

import cv2
import numpy as np
import mss
import os
from datetime import datetime

# Perfil FIREFOX LENOVO 90% (fixo)
REGION = {
    "x": 846,
    "y": 353,
    "width": 143,
    "height": 56
}

# Tentar importar EasyOCR
try:
    import easyocr
    reader = easyocr.Reader(['en'], gpu=True)
    print("EasyOCR com CUDA carregado")
except:
    try:
        reader = easyocr.Reader(['en'], gpu=False)
        print("EasyOCR (CPU) carregado")
    except:
        reader = None
        print("EasyOCR nao disponivel")

# Tentar importar Tesseract
try:
    import pytesseract
    # Testar se tesseract está instalado
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
    print("Tesseract OCR disponivel")
except:
    HAS_TESSERACT = False
    print("Tesseract nao disponivel (pip install pytesseract + instalar tesseract-ocr)")

def capturar_regiao():
    """Captura região da tela"""
    with mss.mss() as sct:
        screenshot = sct.grab({
            "top": REGION['y'],
            "left": REGION['x'],
            "width": REGION['width'],
            "height": REGION['height']
        })
        return np.array(screenshot)

def processar_imagem_v1(img):
    """Processamento atual do bot"""
    if len(img.shape) == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    gray = cv2.convertScaleAbs(gray, alpha=1.2, beta=10)
    _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
    return binary

def processar_imagem_v2(img):
    """OTSU threshold"""
    if len(img.shape) == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary

def processar_imagem_v3(img):
    """Adaptive threshold"""
    if len(img.shape) == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 11, 2)
    return binary

def processar_imagem_v4(img):
    """Escala 2x + sharpen"""
    if len(img.shape) == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    height, width = gray.shape
    gray = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    gray = cv2.filter2D(gray, -1, kernel)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary

def processar_imagem_v5(img):
    """Invertido + dilatacao (para caracteres finos)"""
    if len(img.shape) == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Escalar 2x primeiro
    height, width = gray.shape
    gray = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

    # Aumentar contraste
    gray = cv2.convertScaleAbs(gray, alpha=1.8, beta=0)

    # OTSU threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Dilatar para engrossar caracteres finos
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.dilate(binary, kernel, iterations=1)

    # Inverter (texto escuro em fundo claro)
    binary = cv2.bitwise_not(binary)

    return binary

def processar_imagem_v7(img):
    """Dilatacao SEM inversao (para Tesseract)"""
    if len(img.shape) == 4:
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Escalar 2x
    height, width = gray.shape
    gray = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

    # Aumentar contraste
    gray = cv2.convertScaleAbs(gray, alpha=1.8, beta=0)

    # OTSU threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Dilatar para engrossar caracteres finos (sem inverter)
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.dilate(binary, kernel, iterations=1)

    return binary

def processar_imagem_v6(img):
    """Canal amarelo isolado (para fonte dourada)"""
    if len(img.shape) == 4:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
    elif len(img.shape) == 3:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        return processar_imagem_v1(img)

    # Escalar 2x
    height, width = img_rgb.shape[:2]
    img_rgb = cv2.resize(img_rgb, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

    # Converter para HSV
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)

    # Isolar tons amarelos/dourados (hue 15-45)
    lower = np.array([15, 80, 80])
    upper = np.array([45, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    # Dilatar para conectar caracteres
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    return mask

def ler_ocr_easy(img):
    """Lê texto com EasyOCR"""
    if reader is None:
        return "N/A", 0
    try:
        results = reader.readtext(img, allowlist='0123456789.x', detail=1)
        if results:
            return results[0][1], results[0][2]
        return "", 0
    except Exception as e:
        return f"Erro: {e}", 0

def ler_ocr_tesseract(img):
    """Lê texto com Tesseract"""
    if not HAS_TESSERACT:
        return "N/A", 0
    try:
        # Configuração para single line + whitelist
        config = '--psm 7 -c tessedit_char_whitelist=0123456789.x'
        texto = pytesseract.image_to_string(img, config=config).strip()

        # Tesseract não dá confiança fácil, vamos pegar do data
        try:
            data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data['conf'] if int(c) > 0]
            conf = sum(confs) / len(confs) / 100 if confs else 0
        except:
            conf = 0.5  # Assumir 50% se não conseguir

        return texto, conf
    except Exception as e:
        return f"Erro: {e}", 0

def salvar_captura(original, processados, resultados, numero):
    """Salva imagens de debug"""
    debug_dir = os.path.join(os.path.dirname(__file__), 'ocr_debug_output')
    os.makedirs(debug_dir, exist_ok=True)

    ts = datetime.now().strftime('%H%M%S')
    prefixo = f"{numero:03d}_{ts}"

    # Salvar original
    cv2.imwrite(f"{debug_dir}/{prefixo}_original.png", original)

    # Salvar processados
    for nome, img in processados.items():
        cv2.imwrite(f"{debug_dir}/{prefixo}_{nome}.png", img)

    # Salvar log
    with open(f"{debug_dir}/{prefixo}_resultado.txt", 'w') as f:
        f.write(f"Captura #{numero} - {datetime.now().strftime('%H:%M:%S')}\n\n")
        for nome, (texto, conf) in resultados.items():
            f.write(f"{nome}: '{texto}' (conf: {conf:.2f})\n")

    return prefixo

def capturar_e_processar():
    """Captura e processa uma vez"""
    original = capturar_regiao()

    processados = {
        'v1_atual': processar_imagem_v1(original),
        'v2_otsu': processar_imagem_v2(original),
        'v3_adaptive': processar_imagem_v3(original),
        'v4_scale': processar_imagem_v4(original),
        'v5_dilate': processar_imagem_v5(original),
        'v6_yellow': processar_imagem_v6(original),
        'v7_tess': processar_imagem_v7(original),
    }

    resultados = {}

    # EasyOCR em todas as versões
    for nome, img in processados.items():
        texto, conf = ler_ocr_easy(img)
        resultados[f"E_{nome}"] = (texto, conf)

    # Tesseract em versões selecionadas
    if HAS_TESSERACT:
        texto, conf = ler_ocr_tesseract(processados['v7_tess'])
        resultados["T_v7_tess"] = (texto, conf)

        texto, conf = ler_ocr_tesseract(processados['v2_otsu'])
        resultados["T_v2_otsu"] = (texto, conf)

        texto, conf = ler_ocr_tesseract(processados['v4_scale'])
        resultados["T_v4_scale"] = (texto, conf)

    return original, processados, resultados

def mostrar_resultado(resultados, numero, prefixo):
    """Mostra resultado no console"""
    print(f"\n[{numero:03d}] {prefixo}")

    # Separar EasyOCR e Tesseract
    easy_results = {k: v for k, v in resultados.items() if k.startswith('E_')}
    tess_results = {k: v for k, v in resultados.items() if k.startswith('T_')}

    print("  -- EasyOCR --")
    for nome, (texto, conf) in easy_results.items():
        status = "OK" if conf > 0.7 else "??" if conf > 0.4 else "XX"
        nome_curto = nome[2:]  # Remove "E_"
        print(f"  {status} {nome_curto:12}: '{texto}' ({conf:.0%})")

    if tess_results:
        print("  -- Tesseract --")
        for nome, (texto, conf) in tess_results.items():
            status = "OK" if conf > 0.7 else "??" if conf > 0.4 else "XX"
            nome_curto = nome[2:]  # Remove "T_"
            print(f"  {status} {nome_curto:12}: '{texto}' ({conf:.0%})")

def main():
    print(f"""
============================================
  OCR DEBUG - Captura Manual
  Perfil: FIREFOX LENOVO 90%
  Regiao: x={REGION['x']}, y={REGION['y']}, {REGION['width']}x{REGION['height']}
============================================

  ENTER = Capturar e salvar
  Q     = Sair

""")

    contador = 1

    while True:
        cmd = input(f"[{contador:03d}] Aguardando... ").strip().lower()

        if cmd == 'q':
            print("\nSaindo...")
            break

        # Capturar
        original, processados, resultados = capturar_e_processar()

        # Salvar
        prefixo = salvar_captura(original, processados, resultados, contador)

        # Mostrar
        mostrar_resultado(resultados, contador, prefixo)

        contador += 1

    print(f"\n{contador-1} capturas salvas em ocr_debug_output/")

if __name__ == "__main__":
    main()
