#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VISION SYSTEM - Simplified OCR Module
Basic and reliable OCR for multiplier and balance detection
Focus on accuracy over complexity
"""

import cv2
import numpy as np
import pytesseract
import mss
import os
import json
import time
import logging
import random
from collections import deque
from typing import Optional, List, Dict, Tuple
import re

# Tentar importar EasyOCR como fallback
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("EasyOCR não instalado. Usando apenas pytesseract.")

class VisionSystem:
    """Simple and reliable vision system for OCR detection"""

    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self.load_config()

        # Carregar template path do projeto atual  
        self.template_path = os.path.join(os.getcwd(), "templates_debug")

        # Inicializar EasyOCR se disponível COM CUDA
        self.easyocr_reader = None
        if EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['en'], gpu=True)  # CUDA habilitado
                print("✅ EasyOCR inicializado com CUDA - Muito mais preciso!")
            except Exception as e:
                print(f"⚠️ Erro CUDA, tentando CPU: {e}")
                try:
                    self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
                    print("✅ EasyOCR inicializado (CPU)")
                except Exception as e2:
                    print(f"⚠️ Erro ao inicializar EasyOCR: {e2}")

        # Simple value history for basic context
        self.value_history = []  # NECESSÁRIO para o método do backup funcionar
        self.balance_corrections = self.load_balance_corrections()

        # Controle de progressão para detectar erro OCR (1.xx lido como 4.xx)
        self.round_start_time = None  # Quando viu 1.0x pela primeira vez
        self.max_mult_seen = 0.0  # Maior multiplicador visto na rodada atual
        
        # Cache para templates
        self.template_cache = {}
        self.load_templates()

        # Logger
        self.logger = logging.getLogger(__name__)
        print("✅ VisionSystem inicializado (modo simples)")

    def load_config(self) -> Dict:
        """Carrega configuração básica"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def load_balance_corrections(self) -> Dict:
        """Carrega correções de saldo básicas"""
        return {
            'O': '0', 'l': '1', 'I': '1', 'S': '5',
            'o': '0', 'B': '8', 'G': '6'
        }

    def load_templates(self):
        """Carrega templates se existirem"""
        if os.path.exists(self.template_path):
            for file in os.listdir(self.template_path):
                if file.endswith('.png'):
                    template_name = file.replace('.png', '')
                    template_path = os.path.join(self.template_path, file)
                    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        self.template_cache[template_name] = template

    def capture_region(self, region: Dict) -> Optional[np.ndarray]:
        """Captura região da tela usando mss"""
        try:
            with mss.mss() as sct:
                screenshot = sct.grab({
                    "top": region['y'],
                    "left": region['x'],
                    "width": region['width'],
                    "height": region['height']
                })
                return np.array(screenshot)
        except Exception as e:
            self.logger.error(f"Erro na captura: {e}")
            return None

    def preprocess_for_ocr(self, img: np.ndarray, target_type: str = 'general') -> np.ndarray:
        """Preprocessing básico para OCR"""
        if len(img.shape) == 4:  # BGRA
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        elif len(img.shape) == 3:  # BGR
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        if target_type == 'balance':
            # Para saldo: processamento específico
            height, width = gray.shape
            scale_factor = 2
            gray = cv2.resize(gray, (width * scale_factor, height * scale_factor), interpolation=cv2.INTER_CUBIC)
            gray = cv2.medianBlur(gray, 3)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary

        elif target_type == 'multiplier':
            # Para multiplicador: v2_otsu (melhor precisão)
            # Escalar 2x para melhor leitura
            height, width = gray.shape
            gray = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
            # Aumentar contraste
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
            # OTSU threshold (automático)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary

        elif target_type == 'bet_detection':
            # Para detecção de BET
            gray = cv2.convertScaleAbs(gray, alpha=1.3, beta=0)
            _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
            return binary

        # Processamento geral
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
        return binary

    def parse_multiplier_simple(self, text: str) -> Optional[float]:
        """Parse BÁSICO - Tesseract é preciso, correções mínimas"""
        if not text:
            return None

        try:
            original_text = text
            ocr_original = text  # Guardar para log
            
            # Limpar texto básico
            text = text.upper().replace('X', '').strip()
            text = text.replace('O', '0').replace('l', '1').replace('I', '1')
            text = text.replace(' ', '')
            
            # CORREÇÃO ESPECÍFICA: 7 decimal sendo lido como 0
            # 1.70 → 1.17 (0 final → 7)  
            # (sem debug para manter interface limpa)
            
            # Manter apenas números e ponto
            cleaned = ""
            for char in text:
                if char.isdigit() or char == '.':
                    cleaned += char
            text = cleaned
            
            if not text or not any(c.isdigit() for c in text):
                return None
            
            # Adicionar ponto decimal se necessário
            if '.' not in text:
                if len(text) == 3:
                    text = text[0] + '.' + text[1:]
                elif len(text) == 4:
                    text = text[0] + '.' + text[1:3]
            
            value = float(text)
            valor_antes_correcao = value  # Guardar para comparar

            # CORREÇÃO CONTEXTUAL: 7 sendo lido como 0 em decimais
            if len(self.value_history) >= 1:
                last_value = self.value_history[-1]
                
                # Caso 1: X.01 pode ser X.71 (como 1.71 → 1.01)
                if '.' in text and text.endswith('01'):
                    if 1.60 <= last_value <= 1.80:
                        candidate_text = text[:-2] + '71'
                        try:
                            candidate_value = float(candidate_text)
                            if abs(candidate_value - last_value) < abs(value - last_value):
                                value = candidate_value
                                text = candidate_text
                        except:
                            pass

                # Caso 1b: X.10 pode ser X.71 (como 11.71 → 11.10)
                elif '.' in text and text.endswith('10'):
                    int_part = int(float(text))
                    expected_range_low = int_part + 0.60
                    expected_range_high = int_part + 0.80
                    if expected_range_low <= last_value <= expected_range_high:
                        candidate_text = text[:-2] + '71'
                        try:
                            candidate_value = float(candidate_text)
                            if abs(candidate_value - last_value) < abs(value - last_value):
                                value = candidate_value
                                text = candidate_text
                        except:
                            pass

                # Caso 2: 1.X0 pode ser 1.X7 (como 1.70 → 1.17)
                elif '.' in text and text.endswith('.70'):
                    if 1.10 <= last_value <= 1.20:
                        candidate_text = text[:-1] + '7'
                        try:
                            candidate_value = float(candidate_text)
                            if abs(candidate_value - last_value) < abs(value - last_value):
                                value = candidate_value
                                text = candidate_text
                        except:
                            pass

                # Caso 3: 1.00 pode ser 1.11
                elif '.' in text and text.endswith('.00'):
                    if 1.05 <= last_value <= 1.15:
                        candidate_text = text[:-2] + '11'
                        try:
                            candidate_value = float(candidate_text)
                            if abs(candidate_value - last_value) < abs(value - last_value):
                                value = candidate_value
                                text = candidate_text
                        except:
                            pass

                # Caso 4: X.X0 pode ser X.X1 (qualquer 0 final → 1)
                elif '.' in text and text.endswith('0') and not text.endswith('.00'):
                    if 0.05 <= abs(value - last_value) <= 0.15:
                        candidate_text = text[:-1] + '1'
                        try:
                            candidate_value = float(candidate_text)
                            if abs(candidate_value - last_value) < abs(value - last_value):
                                value = candidate_value
                                text = candidate_text
                        except:
                            pass
            
            # Validação simples
            if 1.0 <= value <= 999.99:
                # ========== CORREÇÃO DE PROGRESSÃO (1.xx lido como 4.xx) ==========
                from datetime import datetime
                import time as time_module

                # Detectar início de nova rodada (1.0x após valor alto ou primeiro)
                if 1.0 <= value < 1.5:
                    if self.max_mult_seen >= 2.0 or self.round_start_time is None:
                        # Nova rodada começou
                        self.round_start_time = time_module.time()
                        self.max_mult_seen = value

                # Atualizar max_mult_seen
                if value > self.max_mult_seen:
                    self.max_mult_seen = value

                # Corrigir 4.xx → 1.xx se condições atenderem
                if 4.0 <= value < 5.0 and self.round_start_time is not None:
                    elapsed = time_module.time() - self.round_start_time
                    # Dentro de 15s do início E nunca vimos 2.xx ou 3.xx
                    if elapsed <= 15.0 and self.max_mult_seen < 2.0:
                        valor_corrigido = value - 3.0  # 4.xx → 1.xx
                        # Se valor corrigido < max_seen, usar max_seen (multiplicador só sobe)
                        if valor_corrigido < self.max_mult_seen:
                            valor_corrigido = self.max_mult_seen
                        try:
                            with open('ocr_correcoes.log', 'a') as f:
                                f.write(f"{datetime.now().strftime('%H:%M:%S')} | PROGRESSÃO: {value:.2f} → {valor_corrigido:.2f} | max_visto: {self.max_mult_seen:.2f} | elapsed: {elapsed:.1f}s\n")
                        except:
                            pass
                        value = valor_corrigido
                        self.max_mult_seen = value  # Atualizar com valor corrigido
                # ========== FIM CORREÇÃO DE PROGRESSÃO ==========

                # Log se houve correção - salva em arquivo
                if abs(valor_antes_correcao - value) > 0.001:
                    try:
                        with open('ocr_correcoes.log', 'a') as f:
                            f.write(f"{datetime.now().strftime('%H:%M:%S')} | {valor_antes_correcao:.2f} → {value:.2f} | raw: '{ocr_original}'\n")
                    except:
                        pass

                if hasattr(self, 'value_history'):
                    self.value_history.append(value)
                    if len(self.value_history) > 100:
                        self.value_history = self.value_history[-50:]
                return value
            
            return None
            
        except Exception as e:
            return None

    def get_multiplier(self, region: Dict) -> Optional[float]:
        """Multiplier detection com Tesseract (mais preciso que EasyOCR)"""
        try:
            # Capture the region
            img = self.capture_region(region)
            if img is None:
                return None

            # Preprocessamento v2_otsu
            processed_img = self.preprocess_for_ocr(img, 'multiplier')

            # TESSERACT - mais preciso para essa fonte
            try:
                config = '--psm 7 -c tessedit_char_whitelist=0123456789.x'
                text = pytesseract.image_to_string(processed_img, config=config).strip()

                if text:
                    value = self.parse_multiplier_simple(text)
                    if value:
                        return value

                # Fallback: tentar PSM 8 (single word)
                config = '--psm 8 -c tessedit_char_whitelist=0123456789.x'
                text = pytesseract.image_to_string(processed_img, config=config).strip()

                if text:
                    value = self.parse_multiplier_simple(text)
                    if value:
                        return value

                return None

            except Exception as e:
                self.logger.error(f"Erro Tesseract: {e}")
                return None

        except Exception as e:
            self.logger.error(f"Erro na detecção de multiplicador: {e}")
            return None

    def get_balance(self, region: Dict, current_balance: Optional[float] = None) -> Optional[float]:
        """Balance detection com EasyOCR CUDA"""
        try:
            img = self.capture_region(region)
            if img is None:
                return None

            processed_img = self.preprocess_for_ocr(img, 'balance')
            
            # APENAS EasyOCR para saldo também
            if self.easyocr_reader:
                try:
                    results = self.easyocr_reader.readtext(
                        processed_img, 
                        allowlist='0123456789.,',
                        width_ths=0.4,
                        height_ths=0.4,
                        detail=1
                    )
                    
                    for (bbox, text, confidence) in results:
                        if confidence > 0.3 and text:  # Confiança menor para saldo
                            balance = self.parse_balance_simple(text)
                            if balance:
                                # SEM DEBUG - interface limpa
                                return balance
                    
                    # SEM DEBUG - retorna None silenciosamente
                    return None
                    
                except Exception as e:
                    # SEM DEBUG - só retorna None
                    return None
            else:
                # SEM DEBUG - não inicializado
                return None

        except Exception as e:
            self.logger.error(f"Erro na detecção de saldo: {e}")
            return None

    def parse_balance_simple(self, text: str) -> Optional[float]:
        """Simple balance parsing"""
        if not text:
            return None

        try:
            # Clean text
            for old, new in self.balance_corrections.items():
                text = text.replace(old, new)
            
            text = text.replace(',', '.')
            
            # Remove non-numeric characters except dots
            cleaned = re.sub(r'[^\d.]', '', text)
            
            if not cleaned:
                return None
            
            # Handle multiple dots
            if cleaned.count('.') > 1:
                parts = cleaned.split('.')
                cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
            
            balance = float(cleaned)
            
            # Correção: Se o valor é muito alto e não tem ponto decimal, adicionar
            if balance > 10000 and '.' not in text:
                # Assumir que os últimos 2 dígitos são decimais
                balance = balance / 100
                print(f"🔧 Correção decimal: {cleaned} → {balance:.2f}")
            
            if 0 <= balance <= 999999:
                return balance
            
            return None

        except Exception:
            return None

    def detect_bet_text(self, region: Dict) -> bool:
        """Simple BET detection"""
        try:
            img = self.capture_region(region)
            if img is None:
                return False

            processed_img = self.preprocess_for_ocr(img, 'bet_detection')

            # Try multiple OCR configs
            configs = [
                '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--psm 6'
            ]

            for config in configs:
                text = pytesseract.image_to_string(processed_img, config=config).strip().upper()
                
                # Check for BET patterns
                bet_patterns = ['BET', 'APOSTA', '8S', 'BET8S', 'BET 8S']
                for pattern in bet_patterns:
                    if pattern in text:
                        return True

            return False

        except Exception as e:
            self.logger.error(f"Erro na detecção de BET: {e}")
            return False