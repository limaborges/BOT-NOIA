#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AUTONOMOUS BETTING V2 - Sistema de apostas otimizado

Melhorias:
- Movimento humanizado com curvas Bezier (anti-deteccao)
- Tempos balanceados (rapido mas confiavel)
- Verificacao se aposta entrou (comparando saldo)
- Fluxo correto: clica -> Ctrl+A -> Delete -> Ctrl+V
"""

import time
import pyautogui
import pyperclip
import random
import numpy as np
from typing import Dict, Optional, Tuple, Callable
from colorama import Fore, init
from dataclasses import dataclass

init(autoreset=True)


@dataclass
class BetResult:
    """Resultado da execucao da aposta"""
    success: bool
    confirmed: bool = False  # True se verificou que a aposta entrou
    error_message: str = ""
    execution_time: float = 0.0


class AutonomousBettingV2:
    """
    Sistema de apostas autonomas V2.
    - Movimento humanizado (curvas Bezier)
    - Tempos balanceados para confiabilidade
    - Verificacao de confirmacao via saldo
    """

    def __init__(self, config: Dict, verbose: bool = False):
        self.config = config
        self.current_profile = None
        self.profile_data = None
        self.verbose = verbose

        # Configuracoes RAPIDO (otimizado para 2 slots - ~2.3s total)
        self.click_delay_range = (0.02, 0.05)      # Delay apos clique
        self.paste_delay_range = (0.02, 0.04)      # Delay apos colar
        self.between_fields_delay = (0.03, 0.06)   # Delay entre campos
        self.confirm_delay_range = (0.04, 0.08)    # Delay apos confirmar
        self.mouse_speed_range = (0.05, 0.10)      # Velocidade do mouse (movimentos rapidos)
        self.mouse_speed_initial = (0.08, 0.15)    # Velocidade inicial (primeiro campo - mais lento)

        # Configurar PyAutoGUI
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.01  # Pausa minima global

        # Callback para captura de saldo (injetado pelo sistema principal)
        self.capture_balance_callback: Optional[Callable[[], Optional[float]]] = None

        if self.verbose:
            print(f"{Fore.GREEN}AutonomousBettingV2 inicializado (modo humanizado)")

    def set_balance_callback(self, callback: Callable[[], Optional[float]]):
        """Define callback para capturar saldo (usado para verificar se aposta entrou)"""
        self.capture_balance_callback = callback

    def set_profile(self, profile_name: str) -> bool:
        """Define o perfil de coordenadas"""
        if profile_name not in self.config.get('profiles', {}):
            print(f"{Fore.RED}Perfil '{profile_name}' nao encontrado")
            return False

        self.current_profile = profile_name
        self.profile_data = self.config['profiles'][profile_name]

        if self.verbose:
            print(f"{Fore.GREEN}Perfil: {profile_name}")
        return True

    def list_profiles(self) -> list:
        """Lista perfis disponiveis"""
        return list(self.config.get('profiles', {}).keys())

    def _log(self, message: str, color=Fore.WHITE):
        """Log condicional"""
        if self.verbose:
            print(f"{color}{message}")

    def _delay(self, delay_range: Tuple[float, float]):
        """Aplica delay humanizado aleatorio"""
        delay = random.uniform(delay_range[0], delay_range[1])
        time.sleep(delay)

    def _get_random_point_in_area(self, area: Dict) -> Tuple[int, int]:
        """
        Retorna ponto aleatorio dentro de uma area.
        Area pode ser: {x, y, width, height} ou {x, y} (ponto unico)
        """
        x = area.get('x', 0)
        y = area.get('y', 0)
        width = area.get('width', 0)
        height = area.get('height', 0)

        if width > 0 and height > 0:
            # Area: clica em ponto aleatorio dentro dela (com margem de 20%)
            margin_x = int(width * 0.2)
            margin_y = int(height * 0.2)
            rand_x = x + random.randint(margin_x, width - margin_x)
            rand_y = y + random.randint(margin_y, height - margin_y)
            return (rand_x, rand_y)
        else:
            # Ponto unico: retorna com pequena variacao
            return (x + random.randint(-2, 2), y + random.randint(-2, 2))

    def _generate_bezier_curve(self, start: Tuple[int, int], end: Tuple[int, int], num_points: int = 8) -> list:
        """Gera curva Bezier suave entre dois pontos (movimento humano)"""
        x1, y1 = start
        x2, y2 = end

        # Ponto de controle aleatorio (curvatura natural)
        control_x = (x1 + x2) / 2 + random.randint(-30, 30)
        control_y = (y1 + y2) / 2 + random.randint(-20, 20)

        t = np.linspace(0, 1, num_points)
        points = []

        for i in range(num_points):
            # Curva quadratica de Bezier
            x = (1 - t[i])**2 * x1 + 2 * (1 - t[i]) * t[i] * control_x + t[i]**2 * x2
            y = (1 - t[i])**2 * y1 + 2 * (1 - t[i]) * t[i] * control_y + t[i]**2 * y2

            # Pequena variacao aleatoria
            x += random.randint(-1, 1)
            y += random.randint(-1, 1)

            points.append((int(x), int(y)))

        return points

    def _move_mouse_humanized(self, x: int, y: int, speed_range: tuple = None):
        """Move mouse de forma humanizada com curva natural

        Args:
            x, y: Coordenadas destino
            speed_range: Tupla (min, max) para velocidade. Se None, usa mouse_speed_range
        """
        try:
            current_pos = pyautogui.position()
            target_pos = (x, y)

            # Usar velocidade customizada ou padrao
            speed = speed_range if speed_range else self.mouse_speed_range

            # Calcular distancia
            distance = ((x - current_pos.x)**2 + (y - current_pos.y)**2)**0.5

            # Distancia pequena: movimento direto rapido
            if distance < 50:
                duration = random.uniform(0.03, 0.06)
                # Pequena variacao na posicao final
                final_x = x + random.randint(-1, 1)
                final_y = y + random.randint(-1, 1)
                pyautogui.moveTo(final_x, final_y, duration=duration)
                return

            # Distancia maior: usar curva Bezier
            curve_points = self._generate_bezier_curve(current_pos, target_pos)

            total_duration = random.uniform(*speed)
            point_duration = total_duration / len(curve_points)

            for point in curve_points:
                # Variacao na velocidade de cada segmento
                segment_duration = point_duration * random.uniform(0.8, 1.2)
                pyautogui.moveTo(point[0], point[1], duration=segment_duration)

        except Exception as e:
            # Fallback para movimento direto
            self._log(f"Fallback movimento direto: {e}", Fore.YELLOW)
            pyautogui.moveTo(x, y, duration=0.1)

    def _humanized_click(self, x: int, y: int, speed_range: tuple = None) -> bool:
        """Clique humanizado com movimento de mouse customizavel

        Args:
            x, y: Coordenadas do clique
            speed_range: Velocidade do mouse. Se None, usa mouse_speed_range
        """
        try:
            # Pequena variacao na posicao (+-3 pixels)
            x_final = x + random.randint(-3, 3)
            y_final = y + random.randint(-3, 3)

            # Mover mouse primeiro (com velocidade customizada se especificada)
            self._move_mouse_humanized(x_final, y_final, speed_range)

            # Delay aleatorio antes do clique (50-150ms)
            time.sleep(random.uniform(0.05, 0.15))

            # Click na posicao atual
            pyautogui.click()

            # Delay aleatorio depois
            self._delay(self.click_delay_range)
            return True

        except Exception as e:
            self._log(f"Erro no clique: {e}", Fore.RED)
            return False

    def _clear_and_paste(self, text: str) -> bool:
        """
        Limpa campo e cola texto.
        Fluxo: Ctrl+A (selecionar) -> Delete (apagar) -> Ctrl+V (colar)
        """
        try:
            # 1. Copiar texto para clipboard
            pyperclip.copy(str(text))
            time.sleep(0.02)

            # 2. Selecionar tudo (Ctrl+A) com timing humanizado
            pyautogui.keyDown('ctrl')
            time.sleep(random.uniform(0.01, 0.02))
            pyautogui.press('a')
            time.sleep(random.uniform(0.01, 0.02))
            pyautogui.keyUp('ctrl')

            self._delay((0.02, 0.04))

            # 3. Apagar conteudo selecionado (Delete)
            pyautogui.press('delete')
            self._delay((0.02, 0.04))

            # 4. Colar novo valor (Ctrl+V)
            pyautogui.keyDown('ctrl')
            time.sleep(random.uniform(0.01, 0.02))
            pyautogui.press('v')
            time.sleep(random.uniform(0.01, 0.02))
            pyautogui.keyUp('ctrl')

            self._delay(self.paste_delay_range)

            return True
        except Exception as e:
            self._log(f"Erro ao colar: {e}", Fore.RED)
            return False

    def execute_bet(self, bet_amount: float, target_multiplier: float, bet_slot: int = 1) -> BetResult:
        """
        Executa aposta com movimento humanizado.

        Args:
            bet_amount: Valor da aposta
            target_multiplier: Multiplicador alvo
            bet_slot: Slot da aposta (1 ou 2)

        Returns:
            BetResult com status da execucao
        """
        start_time = time.time()

        if not self.profile_data:
            return BetResult(False, False, "Perfil nao definido")

        try:
            # Obter areas do perfil (agora todas sao areas, nao pontos)
            bet_value_area = self.profile_data.get(f'bet_value_area_{bet_slot}')
            target_area = self.profile_data.get(f'target_area_{bet_slot}')
            bet_button_area = self.profile_data.get(f'bet_button_area_{bet_slot}')

            # Fallback para formato antigo (pontos)
            if not bet_value_area:
                bet_value_area = self.profile_data.get(f'bet_value_click_{bet_slot}')
            if not target_area:
                target_area = self.profile_data.get(f'target_click_{bet_slot}')

            # Preparar valores no formato brasileiro
            bet_str = f"{bet_amount:.2f}".replace('.', ',')
            target_str = f"{target_multiplier:.2f}".replace('.', ',')

            self._log(f"Apostando R${bet_str} @ {target_str}x", Fore.CYAN)

            # ===== STEP 1: Campo do valor (velocidade inicial mais lenta) =====
            if not bet_value_area:
                return BetResult(False, False, "Coordenadas do valor nao configuradas")

            click_x, click_y = self._get_random_point_in_area(bet_value_area)
            if not self._humanized_click(click_x, click_y, speed_range=self.mouse_speed_initial):
                return BetResult(False, False, "Falha ao clicar campo valor")

            if not self._clear_and_paste(bet_str):
                return BetResult(False, False, "Falha ao inserir valor")

            self._delay(self.between_fields_delay)

            # ===== STEP 2: Campo do alvo =====
            if not target_area:
                return BetResult(False, False, "Coordenadas do alvo nao configuradas")

            click_x, click_y = self._get_random_point_in_area(target_area)
            if not self._humanized_click(click_x, click_y):
                return BetResult(False, False, "Falha ao clicar campo alvo")

            if not self._clear_and_paste(target_str):
                return BetResult(False, False, "Falha ao inserir alvo")

            self._delay(self.between_fields_delay)

            # ===== STEP 3: Capturar saldo ANTES do clique de confirmar =====
            saldo_antes = None
            if self.capture_balance_callback:
                saldo_antes = self.capture_balance_callback()

            # ===== STEP 4: Confirmar aposta =====
            if bet_button_area:
                click_x, click_y = self._get_random_point_in_area(bet_button_area)
                if not self._humanized_click(click_x, click_y):
                    return BetResult(False, False, "Falha ao clicar botao")
            else:
                self._delay((0.02, 0.04))
                pyautogui.press('enter')

            self._delay(self.confirm_delay_range)

            # ===== STEP 5: Verificar se aposta entrou (saldo mudou) =====
            confirmed = False
            if self.capture_balance_callback and saldo_antes is not None:
                time.sleep(0.3)  # Espera para saldo atualizar
                saldo_depois = self.capture_balance_callback()

                if saldo_depois is not None:
                    # Se saldo diminuiu, aposta entrou
                    if saldo_depois < saldo_antes - 0.01:
                        confirmed = True
                        self._log(f"Aposta CONFIRMADA! Saldo: {saldo_antes:.2f} -> {saldo_depois:.2f}", Fore.GREEN)
                    else:
                        self._log(f"Aposta NAO CONFIRMADA. Saldo nao mudou: {saldo_antes:.2f}", Fore.YELLOW)

            execution_time = time.time() - start_time
            self._log(f"Tempo: {execution_time:.2f}s", Fore.CYAN)

            return BetResult(True, confirmed, "", execution_time)

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Erro: {str(e)}"
            self._log(error_msg, Fore.RED)
            return BetResult(False, False, error_msg, execution_time)

    def execute_bet_fast(self, bet_amount: float, target_multiplier: float, bet_slot: int = 1) -> BetResult:
        """
        Versao RAPIDA - menos humanizacao, mais velocidade.
        Use em situacoes criticas de tempo.
        """
        start_time = time.time()

        if not self.profile_data:
            return BetResult(False, False, "Perfil nao definido")

        try:
            # Obter areas (com fallback para formato antigo)
            bet_value_area = self.profile_data.get(f'bet_value_area_{bet_slot}') or \
                             self.profile_data.get(f'bet_value_click_{bet_slot}')
            target_area = self.profile_data.get(f'target_area_{bet_slot}') or \
                          self.profile_data.get(f'target_click_{bet_slot}')
            bet_button_area = self.profile_data.get(f'bet_button_area_{bet_slot}')

            if not bet_value_area or not target_area:
                return BetResult(False, False, "Coordenadas nao configuradas")

            bet_str = f"{bet_amount:.2f}".replace('.', ',')
            target_str = f"{target_multiplier:.2f}".replace('.', ',')

            # Campo valor - ponto aleatorio na area
            x, y = self._get_random_point_in_area(bet_value_area)
            pyautogui.moveTo(x, y, duration=0.05)
            pyautogui.click()
            time.sleep(0.03)
            pyperclip.copy(bet_str)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.02)
            pyautogui.press('delete')
            time.sleep(0.02)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.03)

            # Campo alvo - ponto aleatorio na area
            x, y = self._get_random_point_in_area(target_area)
            pyautogui.moveTo(x, y, duration=0.05)
            pyautogui.click()
            time.sleep(0.03)
            pyperclip.copy(target_str)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.02)
            pyautogui.press('delete')
            time.sleep(0.02)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.03)

            # Confirmar - ponto aleatorio na area do botao
            if bet_button_area:
                x, y = self._get_random_point_in_area(bet_button_area)
                pyautogui.moveTo(x, y, duration=0.05)
                pyautogui.click()
            else:
                pyautogui.press('enter')

            time.sleep(0.05)

            execution_time = time.time() - start_time
            return BetResult(True, False, "", execution_time)

        except Exception as e:
            return BetResult(False, False, str(e), time.time() - start_time)

    def emergency_stop(self):
        """Para todas as operacoes"""
        print(f"{Fore.RED}PARADA DE EMERGENCIA")
        try:
            pyautogui.keyUp('ctrl')
            pyautogui.keyUp('shift')
            pyautogui.keyUp('alt')
            pyautogui.press('esc')
            time.sleep(0.02)
            pyautogui.press('esc')
        except:
            pass

    def get_status(self) -> Dict:
        """Retorna status do sistema"""
        return {
            'profile': self.current_profile,
            'ready': bool(self.current_profile and self.profile_data),
            'verbose': self.verbose,
            'has_balance_callback': self.capture_balance_callback is not None,
            'mode': 'humanized',
            'timing': {
                'click_delay': self.click_delay_range,
                'mouse_speed': self.mouse_speed_range,
            }
        }


# Teste
if __name__ == "__main__":
    import json

    print(f"{Fore.CYAN}=== TESTE AUTONOMOUS BETTING V2 ===\n")

    with open('config.json', 'r') as f:
        config = json.load(f)

    betting = AutonomousBettingV2(config, verbose=True)

    profiles = betting.list_profiles()
    print(f"Perfis: {profiles}\n")

    if profiles:
        betting.set_profile(profiles[0])

        print(f"\n{Fore.YELLOW}ATENCAO: Isso executara cliques reais!")
        confirm = input("Executar teste de aposta? (s/N): ").lower().strip()
        if confirm == 's':
            result = betting.execute_bet(5.00, 2.0, 1)
            print(f"\nResultado: success={result.success}, confirmed={result.confirmed}")
            print(f"Tempo: {result.execution_time:.2f}s")
