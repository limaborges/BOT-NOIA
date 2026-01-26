#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
REFRESH MANAGER - Sistema de refresh automático
- F5: para anomalias (saldo ilegível, conexão perdida)
- Restart Firefox: preventivo a cada 6h para liberar RAM
"""

import time
import os
import subprocess
import pyautogui
import threading
import cv2
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Callable
from colorama import Fore, init
from dataclasses import dataclass
import platform

init(autoreset=True)

# Detectar sistema operacional
IS_LINUX = platform.system() == 'Linux'
IS_WINDOWS = platform.system() == 'Windows'

@dataclass
class RefreshEvent:
    """Evento de refresh executado"""
    timestamp: datetime
    reason: str
    manual: bool = False
    success: bool = True

class RefreshManager:
    """Gerenciador de refresh automático F5 + Restart Browser (Firefox/Chrome)"""

    def __init__(self, browser: str = 'firefox'):
        # Configurações principais
        self.auto_refresh_timeout = 133  # 133 segundos sem explosões (para multiplicador girando)
        self.black_screen_timeout = 15   # 15 segundos de tela preta ou sem atividade
        self.stuck_multiplier_timeout = 15  # 15 segundos com multiplicador realmente travado
        self.monitoring_enabled = False
        self.last_explosion_time = datetime.now()

        # Configuração do navegador (firefox ou chrome)
        self.browser = browser.lower()

        # Restart Browser preventivo (RAM) - a cada 6 horas
        self.preventive_restart_interval = 6 * 60 * 60  # 6 horas
        self.last_restart_time = datetime.now()
        self.preventive_restart_pending = False

        # URL do jogo para restart
        self.game_url = "https://www.brabet.com/?f=game_Crash"

        # Threading
        self.monitor_thread = None
        self.running = False

        # Callbacks
        self.on_refresh_callback: Optional[Callable] = None
        self.on_anomaly_detected_callback: Optional[Callable] = None

        # Histórico
        self.refresh_history = []
        self.anomaly_count = 0

        # Estatísticas
        self.stats = {
            'total_refreshes': 0,
            'auto_refreshes': 0,
            'manual_refreshes': 0,
            'anomalies_detected': 0,
            'black_screen_refreshes': 0,
            'firefox_restarts': 0,
            'last_refresh': None
        }

        # Detecção de anomalias visuais
        self.last_multiplier_value = None
        self.last_multiplier_change_time = datetime.now()
        self.last_activity_time = datetime.now()
        self.black_screen_start_time = None
        self.multiplier_update_count = 0

        # Verificação de saldo (apenas para detectar página travada)
        self.balance_check_callback: Optional[Callable] = None
        self.balance_check_interval = 5
        self.balance_fail_count = 0
        self.balance_fail_threshold = 3
        self.last_balance_check_time = datetime.now()

        print(f"{Fore.GREEN}🔄 Refresh Manager inicializado")
        print(f"{Fore.CYAN}⏰ Timeout explosões: {self.auto_refresh_timeout}s | Timeout saldo: {self.balance_check_interval * self.balance_fail_threshold}s")
        print(f"{Fore.CYAN}🔥 Restart Firefox (RAM): {self.preventive_restart_interval // 3600}h")

    def update_explosion_time(self):
        """Atualiza timestamp da última explosão detectada"""
        self.last_explosion_time = datetime.now()
        self.last_activity_time = datetime.now()

    def get_time_since_last_explosion(self) -> float:
        """Retorna tempo em segundos desde a última explosão"""
        return (datetime.now() - self.last_explosion_time).total_seconds()

    def update_multiplier_status(self, multiplier_value: Optional[float]):
        """Atualiza status do multiplicador para detectar travamento"""
        if multiplier_value is not None:
            self.last_activity_time = datetime.now()
            self.multiplier_update_count += 1

            if self.last_multiplier_value != multiplier_value:
                self.last_multiplier_value = multiplier_value
                self.last_multiplier_change_time = datetime.now()

    def capture_screen_for_analysis(self) -> Optional[np.ndarray]:
        """Captura tela para análise de tela preta"""
        try:
            screenshot = pyautogui.screenshot()
            screenshot_np = np.array(screenshot)
            screenshot_rgb = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            return screenshot_rgb
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Erro ao capturar tela: {e}")
            return None

    def is_black_screen_detected(self) -> bool:
        """Detecta se a tela está preta"""
        try:
            img = self.capture_screen_for_analysis()
            if img is None:
                return False

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mean_brightness = np.mean(gray)
            is_black = mean_brightness < 30

            if is_black:
                if self.black_screen_start_time is None:
                    self.black_screen_start_time = datetime.now()
                    print(f"{Fore.YELLOW}🖤 Tela preta detectada! Brilho: {mean_brightness:.1f}")

                time_black = (datetime.now() - self.black_screen_start_time).total_seconds()
                return time_black >= self.black_screen_timeout
            else:
                self.black_screen_start_time = None
                return False

        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Erro na detecção de tela preta: {e}")
            return False

    def is_no_activity_detected(self) -> bool:
        """Detecta se não há atividade"""
        if self.last_activity_time is None:
            return False

        time_inactive = (datetime.now() - self.last_activity_time).total_seconds()
        return time_inactive >= self.black_screen_timeout

    def is_anomaly_detected(self):
        """Verifica se uma anomalia foi detectada (retorna bool e motivo)"""
        # 1. Timeout de explosões (133s)
        time_since_explosion = self.get_time_since_last_explosion()
        if time_since_explosion >= self.auto_refresh_timeout:
            return True, f"Timeout: {time_since_explosion:.1f}s sem explosões"

        # 2. Falha na leitura de saldo (15s = 3 falhas consecutivas)
        if self.balance_fail_count >= self.balance_fail_threshold:
            return True, f"Saldo ilegível: {self.balance_fail_count} falhas consecutivas"

        return False, ""

    # ==================== F5 REFRESH (ANOMALIAS) ====================
    def execute_refresh(self, reason: str = "Automático", manual: bool = False) -> RefreshEvent:
        """Executa refresh F5 da página - para anomalias"""
        try:
            timestamp = datetime.now()

            print(f"\n{Fore.YELLOW}EXECUTANDO F5 REFRESH")
            print(f"{Fore.WHITE}Motivo: {reason}")

            # Pegar centro da tela
            screen_width, screen_height = pyautogui.size()
            click_x = screen_width // 2
            click_y = screen_height // 2

            # 1. Clicar no centro
            print(f"{Fore.CYAN}Clicando no centro...")
            pyautogui.click(click_x, click_y)
            time.sleep(0.3)

            # 2. Apertar F5
            print(f"{Fore.CYAN}Apertando F5...")
            pyautogui.press('f5')

            # 3. Aguardar carregamento
            print(f"{Fore.CYAN}Aguardando carregar...")
            time.sleep(8)

            # Atualizar estatísticas
            self.stats['total_refreshes'] += 1
            if manual:
                self.stats['manual_refreshes'] += 1
            else:
                self.stats['auto_refreshes'] += 1
                self.stats['anomalies_detected'] += 1

                if "Sem atividade" in reason:
                    self.stats['black_screen_refreshes'] += 1

            self.stats['last_refresh'] = timestamp

            # Criar evento
            event = RefreshEvent(
                timestamp=timestamp,
                reason=reason,
                manual=manual,
                success=True
            )

            # Adicionar ao histórico
            self.refresh_history.append(event)
            if len(self.refresh_history) > 50:
                self.refresh_history = self.refresh_history[-50:]

            # Reset timers
            self.last_explosion_time = datetime.now()
            self.balance_fail_count = 0

            print(f"{Fore.GREEN}✅ F5 Refresh executado com sucesso!")

            # Callback
            if self.on_refresh_callback:
                try:
                    self.on_refresh_callback(event)
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Erro no callback: {e}")

            return event

        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao executar refresh: {e}")

            event = RefreshEvent(
                timestamp=datetime.now(),
                reason=f"ERRO: {reason}",
                manual=manual,
                success=False
            )

            self.refresh_history.append(event)
            return event

    def force_refresh(self, reason: str = "Forçado pelo usuário") -> RefreshEvent:
        """Força refresh F5 manual"""
        return self.execute_refresh(reason, manual=True)

    # ==================== BROWSER RESTART (PREVENTIVO RAM) ====================
    def _kill_browser(self) -> bool:
        """Fecha o navegador (Firefox ou Chrome) - cross-platform"""
        browser_name = self.browser.capitalize()

        if IS_LINUX:
            # Linux: usar pkill
            process_name = 'firefox' if self.browser == 'firefox' else 'chrome'
            try:
                result = subprocess.run(['pkill', '-f', process_name], capture_output=True, timeout=10)
                if result.returncode == 0:
                    print(f"{Fore.GREEN}{browser_name} fechado com sucesso (Linux)")
                    return True
                else:
                    print(f"{Fore.YELLOW}{browser_name} pode não estar aberto")
                    return True  # Continuar mesmo assim
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ Aviso ao fechar {browser_name}: {e}")
                return False

        elif IS_WINDOWS:
            # Windows: usar taskkill
            process_name = 'firefox.exe' if self.browser == 'firefox' else 'chrome.exe'
            try:
                result = subprocess.run(
                    ['taskkill', '/IM', process_name, '/F'],
                    capture_output=True, timeout=10
                )
                if result.returncode == 0:
                    print(f"{Fore.GREEN}{browser_name} fechado com sucesso (Windows)")
                    return True
                else:
                    print(f"{Fore.YELLOW}{browser_name} pode não estar aberto")
                    return True
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ Aviso ao fechar {browser_name}: {e}")
                return False

        return False

    def _open_browser(self) -> bool:
        """Abre o navegador na URL do jogo - cross-platform"""
        browser_name = self.browser.capitalize()

        if IS_LINUX:
            # Linux: tentar comando direto, depois xdg-open
            if self.browser == 'firefox':
                commands = [
                    ['firefox', self.game_url],
                    ['firefox-esr', self.game_url],
                    ['/usr/bin/firefox', self.game_url],
                ]
            else:  # chrome
                commands = [
                    ['google-chrome', self.game_url],
                    ['google-chrome-stable', self.game_url],
                    ['chromium', self.game_url],
                    ['chromium-browser', self.game_url],
                ]

            for cmd in commands:
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"{Fore.GREEN}{browser_name} aberto: {cmd[0]} (Linux)")
                    return True
                except FileNotFoundError:
                    continue

            # Fallback: xdg-open
            try:
                subprocess.Popen(['xdg-open', self.game_url])
                print(f"{Fore.GREEN}Navegador aberto via xdg-open (Linux)")
                return True
            except Exception as e:
                print(f"{Fore.RED}❌ Erro ao abrir navegador no Linux: {e}")
                return False

        elif IS_WINDOWS:
            if self.browser == 'firefox':
                paths = [
                    r'C:\Program Files\Mozilla Firefox\firefox.exe',
                    r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe',
                ]
            else:  # chrome
                paths = [
                    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                    os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
                ]

            for browser_path in paths:
                if os.path.exists(browser_path):
                    try:
                        subprocess.Popen([browser_path, self.game_url])
                        print(f"{Fore.GREEN}{browser_name} aberto: {browser_path}")
                        return True
                    except Exception:
                        continue

            # Fallback: os.startfile (abre no navegador padrão)
            try:
                os.startfile(self.game_url)
                print(f"{Fore.GREEN}URL aberta no navegador padrão (Windows)")
                return True
            except Exception as e:
                print(f"{Fore.RED}❌ Erro ao abrir navegador no Windows: {e}")
                return False

        return False

    def execute_firefox_restart(self, reason: str = "Preventivo RAM") -> RefreshEvent:
        """Fecha e reabre navegador - para liberar RAM (a cada 6h)"""
        return self.execute_browser_restart(reason)

    def execute_browser_restart(self, reason: str = "Preventivo RAM") -> RefreshEvent:
        """Fecha e reabre navegador (Firefox/Chrome) - para liberar RAM (a cada 6h)"""
        browser_name = self.browser.capitalize()
        try:
            timestamp = datetime.now()
            os_name = "Linux" if IS_LINUX else "Windows"

            print(f"\n{Fore.YELLOW}{'='*50}")
            print(f"{Fore.YELLOW}EXECUTANDO RESTART DO {browser_name.upper()} ({os_name})")
            print(f"{Fore.WHITE}Motivo: {reason}")
            print(f"{Fore.YELLOW}{'='*50}")

            # 1. Fechar navegador
            print(f"{Fore.CYAN}Fechando {browser_name}...")
            self._kill_browser()

            # 2. Esperar fechar e liberar memória
            print(f"{Fore.CYAN}Aguardando liberação de memória (5s)...")
            time.sleep(5)

            # 3. Reabrir navegador na URL do jogo
            print(f"{Fore.CYAN}Abrindo {browser_name} na página do jogo...")
            self._open_browser()

            # 4. Aguardar carregar página
            print(f"{Fore.CYAN}Aguardando página carregar (12s)...")
            time.sleep(12)

            # Atualizar estatísticas
            self.stats['firefox_restarts'] += 1  # Manter nome por compatibilidade
            self.stats['last_refresh'] = timestamp

            # Criar evento
            event = RefreshEvent(
                timestamp=timestamp,
                reason=reason,
                manual=False,
                success=True
            )

            self.refresh_history.append(event)
            if len(self.refresh_history) > 50:
                self.refresh_history = self.refresh_history[-50:]

            # Reset timers
            self.last_explosion_time = datetime.now()
            self.last_restart_time = datetime.now()
            self.preventive_restart_pending = False
            self.balance_fail_count = 0

            print(f"{Fore.GREEN}✅ {browser_name} reiniciado com sucesso!")

            # Callback
            if self.on_refresh_callback:
                try:
                    self.on_refresh_callback(event)
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Erro no callback: {e}")

            return event

        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao reiniciar {browser_name}: {e}")

            event = RefreshEvent(
                timestamp=datetime.now(),
                reason=f"ERRO: {reason}",
                manual=False,
                success=False
            )

            self.refresh_history.append(event)
            return event

    # ==================== VERIFICAÇÕES PREVENTIVAS ====================
    def check_preventive_restart(self) -> bool:
        """Verifica se passou tempo suficiente para restart preventivo do Firefox"""
        time_since_restart = (datetime.now() - self.last_restart_time).total_seconds()
        if time_since_restart >= self.preventive_restart_interval:
            self.preventive_restart_pending = True
            return True
        return False

    def should_do_preventive_restart(self, multiplier: float, em_martingale: bool) -> bool:
        """
        Verifica se deve fazer restart preventivo do Firefox agora.
        Condições: 6h+ desde último restart E multiplicador > 2x E não está em martingale
        """
        self.check_preventive_restart()

        if self.preventive_restart_pending and multiplier >= 2.0 and not em_martingale:
            return True
        return False

    def get_time_since_last_restart(self) -> float:
        """Retorna tempo em segundos desde o último restart do Firefox"""
        return (datetime.now() - self.last_restart_time).total_seconds()

    # ==================== MONITORAMENTO ====================
    def monitor_loop(self):
        """Loop de monitoramento de anomalias"""
        print(f"{Fore.GREEN}🔍 Iniciando monitoramento de anomalias...")

        log_counter = 0

        while self.running and self.monitoring_enabled:
            try:
                time_since = self.get_time_since_last_explosion()

                # Verificar saldo periodicamente (a cada 5s)
                self.check_balance_health()

                # Log periódico a cada 30 segundos
                log_counter += 1
                if log_counter >= 6:
                    log_counter = 0

                # Verificar anomalias
                anomaly_detected, reason = self.is_anomaly_detected()

                if anomaly_detected:
                    print(f"\n{Fore.RED}🚨 ANOMALIA DETECTADA!")
                    print(f"{Fore.YELLOW}📋 Motivo: {reason}")

                    if self.on_anomaly_detected_callback:
                        try:
                            self.on_anomaly_detected_callback(time_since)
                        except Exception as e:
                            print(f"{Fore.YELLOW}⚠️ Erro no callback de anomalia: {e}")

                    # Executar F5 refresh (não restart)
                    self.execute_refresh(reason)

                    # Reset dos timers
                    self.black_screen_start_time = None
                    self.last_activity_time = datetime.now()
                    self.balance_fail_count = 0

                    time.sleep(5)

                time.sleep(5)

            except Exception as e:
                print(f"{Fore.RED}❌ Erro no loop de monitoramento: {e}")
                time.sleep(10)

    def start_monitoring(self):
        """Inicia monitoramento automático"""
        if self.monitoring_enabled:
            print(f"{Fore.YELLOW}⚠️ Monitoramento já está ativo")
            return

        self.monitoring_enabled = True
        self.running = True

        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        print(f"{Fore.GREEN}✅ Monitoramento de anomalias iniciado")
        print(f"{Fore.CYAN}🔍 Timeout configurado: {self.auto_refresh_timeout}s")

    def stop_monitoring(self):
        """Para monitoramento automático"""
        if not self.monitoring_enabled:
            print(f"{Fore.YELLOW}⚠️ Monitoramento já está parado")
            return

        print(f"{Fore.YELLOW}🛑 Parando monitoramento...")

        self.monitoring_enabled = False
        self.running = False

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3)

        print(f"{Fore.GREEN}✅ Monitoramento parado")

    # ==================== CALLBACKS ====================
    def set_refresh_callback(self, callback: Callable[[RefreshEvent], None]):
        """Define callback para eventos de refresh"""
        self.on_refresh_callback = callback

    def set_anomaly_callback(self, callback: Callable[[float], None]):
        """Define callback para detecção de anomalias"""
        self.on_anomaly_detected_callback = callback

    def set_balance_check_callback(self, callback: Callable[[], Optional[float]]):
        """Define callback para verificar saldo"""
        self.balance_check_callback = callback

    def check_balance_health(self) -> bool:
        """Verifica se consegue ler o saldo - retorna True se OK"""
        if not self.balance_check_callback:
            return True

        try:
            balance = self.balance_check_callback()
            if balance is not None and balance > 0:
                self.balance_fail_count = 0
                return True
            else:
                self.balance_fail_count += 1
                return False
        except Exception:
            self.balance_fail_count += 1
            return False

    # ==================== STATUS ====================
    def get_status(self) -> dict:
        """Retorna status atual do sistema"""
        time_since_explosion = self.get_time_since_last_explosion()

        return {
            'monitoring_enabled': self.monitoring_enabled,
            'time_since_last_explosion': time_since_explosion,
            'timeout_threshold': self.auto_refresh_timeout,
            'anomaly_detected': self.is_anomaly_detected(),
            'time_until_refresh': max(0, self.auto_refresh_timeout - time_since_explosion),
            'stats': self.stats.copy(),
            'recent_refreshes': len([r for r in self.refresh_history if
                                   (datetime.now() - r.timestamp).total_seconds() < 3600])
        }

    def get_refresh_history(self, limit: int = 10) -> list:
        """Retorna histórico de refreshes"""
        return self.refresh_history[-limit:] if self.refresh_history else []

    def print_status_report(self):
        """Exibe relatório de status"""
        status = self.get_status()

        print(f"\n{Fore.CYAN}📊 REFRESH MANAGER - STATUS")
        print(f"{Fore.CYAN}{'='*40}")
        print(f"{Fore.WHITE}Monitoramento: {'🟢 ATIVO' if status['monitoring_enabled'] else '🔴 PARADO'}")
        print(f"{Fore.WHITE}Tempo desde explosão: {status['time_since_last_explosion']:.1f}s")
        print(f"{Fore.WHITE}Limite timeout: {status['timeout_threshold']}s")

        if status['anomaly_detected']:
            print(f"{Fore.RED}Status: 🚨 ANOMALIA DETECTADA")
        else:
            print(f"{Fore.GREEN}Status: ✅ Normal")
            print(f"{Fore.YELLOW}Próximo refresh em: {status['time_until_refresh']:.1f}s")

        print(f"\n{Fore.CYAN}📈 ESTATÍSTICAS:")
        stats = status['stats']
        print(f"{Fore.WHITE}Total refreshes: {stats['total_refreshes']}")
        print(f"{Fore.GREEN}Automáticos (F5): {stats['auto_refreshes']}")
        print(f"{Fore.YELLOW}Manuais: {stats['manual_refreshes']}")
        print(f"{Fore.MAGENTA}Firefox restarts: {stats.get('firefox_restarts', 0)}")
        print(f"{Fore.RED}Anomalias: {stats['anomalies_detected']}")

        if stats['last_refresh']:
            print(f"{Fore.CYAN}Último refresh: {stats['last_refresh'].strftime('%H:%M:%S')}")

def main():
    """Teste do Refresh Manager"""
    try:
        print(f"{Fore.MAGENTA}🔄 TESTE DO REFRESH MANAGER")
        print(f"{Fore.CYAN}{'='*40}")

        manager = RefreshManager()

        def on_refresh(event: RefreshEvent):
            print(f"{Fore.GREEN}📞 Callback refresh: {event.reason}")

        def on_anomaly(time_since: float):
            print(f"{Fore.RED}📞 Callback anomalia: {time_since:.1f}s")

        manager.set_refresh_callback(on_refresh)
        manager.set_anomaly_callback(on_anomaly)

        print(f"\n{Fore.YELLOW}Opções de teste:")
        print(f"{Fore.WHITE}1. Iniciar monitoramento")
        print(f"{Fore.WHITE}2. Simular explosão")
        print(f"{Fore.WHITE}3. Forçar F5 refresh")
        print(f"{Fore.WHITE}4. Forçar Firefox restart")
        print(f"{Fore.WHITE}5. Status")
        print(f"{Fore.WHITE}6. Sair")

        while True:
            try:
                choice = input(f"\n{Fore.CYAN}Escolha uma opção: ").strip()

                if choice == '1':
                    manager.start_monitoring()
                elif choice == '2':
                    manager.update_explosion_time()
                    print(f"{Fore.GREEN}💥 Explosão simulada!")
                elif choice == '3':
                    manager.force_refresh("Teste manual")
                elif choice == '4':
                    manager.execute_firefox_restart("Teste manual")
                elif choice == '5':
                    manager.print_status_report()
                elif choice == '6':
                    break
                else:
                    print(f"{Fore.RED}❌ Opção inválida")

            except KeyboardInterrupt:
                break

        manager.stop_monitoring()
        print(f"\n{Fore.GREEN}👋 Teste finalizado!")

    except Exception as e:
        print(f"{Fore.RED}❌ Erro no teste: {e}")

if __name__ == "__main__":
    main()
