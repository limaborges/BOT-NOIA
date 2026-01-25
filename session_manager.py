#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SESSION MANAGER - Gerenciador de sessão com banco de dados
Integra o DatabaseManager ao sistema Kamikaze
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Optional
from colorama import Fore, init
from database_manager import DatabaseManager

init(autoreset=True)

class SessionManager:
    """Gerenciador de sessão com persistência completa"""

    def __init__(self, existing_session_id: str = None):
        self.db = DatabaseManager()

        # Se retomando sessão, usar ID existente; senão, gerar novo
        if existing_session_id:
            self.session_id = existing_session_id
            self.is_resumed = True
            print(f"{Fore.GREEN}🎮 Session Manager inicializado (RETOMANDO)")
            print(f"{Fore.CYAN}📋 Session ID: {self.session_id}")
            self.log_system("INFO", "SessionManager", f"Sessão retomada: {self.session_id}")
        else:
            self.session_id = self.generate_session_id()
            self.is_resumed = False
            print(f"{Fore.GREEN}🎮 Session Manager inicializado (NOVA)")
            print(f"{Fore.CYAN}📋 Session ID: {self.session_id}")
            self.log_system("INFO", "SessionManager", "Nova sessão iniciada")

        self.session_start = datetime.now()

        # Contadores em memória para performance
        self.rounds_count = 0
        self.bets_count = 0
        self.recommendations_count = 0

        # Cache de dados recentes
        self.recent_multipliers = []
        self.last_bet_id = None
    
    def generate_session_id(self) -> str:
        """Gera ID único da sessão"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"session_{timestamp}_{unique_id}"
    
    # ===== MÉTODOS PARA RODADAS =====
    
    def save_multiplier(self, multiplier: float, regime: str = None, 
                       score: float = None, capture_quality: str = "OK") -> int:
        """Salva multiplicador capturado"""
        try:
            round_id = self.db.save_round(
                multiplier=multiplier,
                session_id=self.session_id,
                regime=regime,
                score=score,
                capture_quality=capture_quality
            )
            
            self.rounds_count += 1
            
            # Manter cache de multiplicadores recentes
            self.recent_multipliers.append(multiplier)
            if len(self.recent_multipliers) > 100:
                self.recent_multipliers = self.recent_multipliers[-100:]
            
            # Log verbose apenas a cada 10 multiplicadores
            if self.rounds_count % 10 == 0:
                self.log_system("DEBUG", "SessionManager", 
                              f"{self.rounds_count} multiplicadores salvos")
            
            return round_id
            
        except Exception as e:
            self.log_system("ERROR", "SessionManager", 
                          f"Erro ao salvar multiplicador: {e}")
            return None
    
    def get_recent_multipliers(self, count: int = 50) -> list:
        """Recupera multiplicadores recentes (cache + BD)"""
        if len(self.recent_multipliers) >= count:
            return self.recent_multipliers[-count:]
        else:
            # Buscar no BD se necessário
            rounds = self.db.get_recent_rounds(self.session_id, count)
            return [r['multiplier'] for r in rounds]
    
    # ===== MÉTODOS PARA RECOMENDAÇÕES E APOSTAS =====
    
    def save_recommendation(self, pattern_detected: str, sequence_multipliers: list,
                          regime: str, score: float, should_bet: bool,
                          recommended_amount: float = None, recommended_target: float = None,
                          confidence_level: str = None, reason: str = None,
                          filters_passed: list = None) -> int:
        """Salva recomendação de aposta"""
        try:
            rec_id = self.db.save_recommendation(
                session_id=self.session_id,
                pattern_detected=pattern_detected,
                sequence_multipliers=sequence_multipliers,
                regime=regime,
                score=score,
                should_bet=should_bet,
                recommended_amount=recommended_amount,
                recommended_target=recommended_target,
                confidence_level=confidence_level,
                reason=reason,
                filters_passed=filters_passed
            )
            
            self.recommendations_count += 1
            
            status = "RECOMENDA APOSTAR" if should_bet else "NÃO RECOMENDA"
            self.log_system("INFO", "Strategy", 
                          f"Recomendação {rec_id}: {status} - {reason}")
            
            return rec_id
            
        except Exception as e:
            self.log_system("ERROR", "SessionManager", 
                          f"Erro ao salvar recomendação: {e}")
            return None
    
    def execute_bet(self, recommendation_id: int, bet_amount: float,
                   target_multiplier: float, profile_used: str = None,
                   working_balance_before: float = None, execution_time: float = None,
                   bet_slot: int = 1, tentativa: int = 1) -> int:
        """Registra execução de aposta"""
        try:
            bet_id = self.db.save_bet_execution(
                session_id=self.session_id,
                recommendation_id=recommendation_id,
                bet_amount=bet_amount,
                target_multiplier=target_multiplier,
                result="PENDING",
                execution_time=execution_time,
                bet_slot=bet_slot,
                profile_used=profile_used,
                working_balance_before=working_balance_before,
                tentativa=tentativa
            )
            
            self.bets_count += 1
            self.last_bet_id = bet_id
            
            self.log_system("INFO", "BetExecutor", 
                          f"Aposta {bet_id} executada: R$ {bet_amount:.2f} @ {target_multiplier}x")
            
            return bet_id
            
        except Exception as e:
            self.log_system("ERROR", "SessionManager", 
                          f"Erro ao registrar aposta: {e}")
            return None
    
    def update_bet_result(self, bet_id: int, actual_multiplier: float,
                         result: str, profit_loss: float, working_balance_after: float):
        """Atualiza resultado da aposta"""
        try:
            self.db.update_bet_result(
                bet_id=bet_id,
                actual_multiplier=actual_multiplier,
                result=result,
                profit_loss=profit_loss,
                working_balance_after=working_balance_after
            )
            
            status_emoji = "🎉" if result == "WIN" else "💔"
            profit_text = f"+R$ {profit_loss:.2f}" if profit_loss > 0 else f"-R$ {abs(profit_loss):.2f}"
            
            self.log_system("INFO", "BetResult", 
                          f"Aposta {bet_id}: {result} @ {actual_multiplier}x → {profit_text}")
            
        except Exception as e:
            self.log_system("ERROR", "SessionManager", 
                          f"Erro ao atualizar resultado: {e}")
    
    # ===== MÉTODOS DE DEBUG E LOG =====
    
    def log_system(self, level: str, module: str, message: str, details: str = None):
        """Log de sistema com timestamp"""
        try:
            self.db.log_system(
                session_id=self.session_id,
                level=level,
                module=module,
                message=message,
                details=details
            )
            
            # Print apenas para níveis importantes
            if level in ["INFO", "ERROR", "WARNING"]:
                color = {
                    "INFO": Fore.CYAN,
                    "ERROR": Fore.RED,
                    "WARNING": Fore.YELLOW
                }.get(level, Fore.WHITE)
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"{color}[{timestamp}] {module}: {message}")
                
        except Exception as e:
            print(f"{Fore.RED}❌ Erro no log: {e}")
    
    def log_capture_error(self, error_type: str, area_name: str, coordinates: str,
                         error_message: str, screenshot_path: str = None):
        """Log específico para erros de captura"""
        try:
            self.db.log_capture_error(
                session_id=self.session_id,
                error_type=error_type,
                area_name=area_name,
                coordinates=coordinates,
                error_message=error_message,
                screenshot_path=screenshot_path
            )
            
            self.log_system("ERROR", "VisionSystem", 
                          f"Erro de captura em {area_name}: {error_message}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Erro no log de captura: {e}")
    
    def log_refresh_event(self, reason: str, time_since_last_explosion: float,
                         manual: bool = False, success: bool = True):
        """Log de evento de refresh"""
        try:
            self.db.log_refresh_event(
                session_id=self.session_id,
                reason=reason,
                time_since_last_explosion=time_since_last_explosion,
                manual=manual,
                success=success
            )
            
            event_type = "MANUAL" if manual else "AUTO"
            result = "SUCCESS" if success else "FAILED"
            
            self.log_system("INFO", "RefreshManager", 
                          f"Refresh {event_type}: {reason} ({time_since_last_explosion:.1f}s) - {result}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Erro no log de refresh: {e}")
    
    # ===== MÉTODOS DE ESTATÍSTICAS =====
    
    def get_session_stats(self) -> Dict:
        """Estatísticas da sessão atual"""
        try:
            # Stats de apostas
            bet_stats = self.db.get_bet_statistics(self.session_id)
            
            # Uptime
            uptime = datetime.now() - self.session_start
            uptime_seconds = uptime.total_seconds()
            
            # Multipliers recentes
            recent_mults = self.get_recent_multipliers(10)
            
            return {
                'session_id': self.session_id,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': str(uptime).split('.')[0],
                'rounds_captured': self.rounds_count,
                'recommendations_made': self.recommendations_count,
                'bets_executed': bet_stats['total_bets'],
                'bets_won': bet_stats['wins'],
                'hit_rate': bet_stats['hit_rate'],
                'total_profit': bet_stats['total_profit'],
                'roi': bet_stats['roi'],
                'avg_multiplier': sum(recent_mults) / len(recent_mults) if recent_mults else 0,
                'recent_multipliers': recent_mults[-5:] if recent_mults else []
            }
            
        except Exception as e:
            self.log_system("ERROR", "SessionManager", f"Erro ao obter stats: {e}")
            return {}
    
    def generate_session_report(self) -> Dict:
        """Relatório completo da sessão"""
        try:
            return self.db.generate_session_report(self.session_id)
        except Exception as e:
            self.log_system("ERROR", "SessionManager", f"Erro ao gerar relatório: {e}")
            return {}
    
    def get_database_status(self) -> Dict:
        """Status geral dos bancos"""
        try:
            return self.db.get_database_status()
        except Exception as e:
            self.log_system("ERROR", "SessionManager", f"Erro ao obter status BD: {e}")
            return {}
    
    # ===== MÉTODOS DE LIMPEZA =====
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Limpa dados antigos"""
        try:
            self.db.cleanup_old_data(days_to_keep)
            self.log_system("INFO", "SessionManager", 
                          f"Limpeza executada: dados > {days_to_keep} dias removidos")
        except Exception as e:
            self.log_system("ERROR", "SessionManager", f"Erro na limpeza: {e}")
    
    def close_session(self):
        """Encerra sessão com relatório final"""
        try:
            # Gerar relatório final
            final_stats = self.get_session_stats()
            
            self.log_system("INFO", "SessionManager", 
                          f"Sessão encerrada após {final_stats.get('uptime_formatted', 'N/A')}")
            self.log_system("INFO", "SessionManager", 
                          f"Total: {final_stats.get('rounds_captured', 0)} rodadas, " +
                          f"{final_stats.get('bets_executed', 0)} apostas")
            
            print(f"\n{Fore.CYAN}📊 SESSÃO ENCERRADA")
            print(f"{Fore.WHITE}ID: {self.session_id}")
            print(f"{Fore.WHITE}Duração: {final_stats.get('uptime_formatted', 'N/A')}")
            print(f"{Fore.WHITE}Rodadas: {final_stats.get('rounds_captured', 0)}")
            print(f"{Fore.WHITE}Apostas: {final_stats.get('bets_executed', 0)}")
            print(f"{Fore.WHITE}Hit Rate: {final_stats.get('hit_rate', 0):.1f}%")
            print(f"{Fore.WHITE}ROI: {final_stats.get('roi', 0):+.2f}%")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao encerrar sessão: {e}")

def main():
    """Teste do Session Manager"""
    print(f"{Fore.MAGENTA}🎮 TESTE DO SESSION MANAGER")
    print(f"{Fore.CYAN}{'='*40}")
    
    # Inicializar sessão
    session = SessionManager()
    
    # Simular algumas rodadas
    print(f"\n{Fore.YELLOW}🎯 Simulando rodadas...")
    multipliers = [1.5, 2.3, 1.8, 1.1, 1.9, 1.6, 3.4, 1.2]
    
    for mult in multipliers:
        session.save_multiplier(mult, "FAVORAVEL", 75.5)
        time.sleep(0.1)  # Simular tempo
    
    # Simular recomendação
    print(f"\n{Fore.YELLOW}💡 Simulando recomendação...")
    rec_id = session.save_recommendation(
        pattern_detected="KAMIKAZE_5_BAIXOS",
        sequence_multipliers=[1.5, 1.8, 1.1, 1.9, 1.6],
        regime="FAVORAVEL",
        score=82.3,
        should_bet=True,
        recommended_amount=25.0,
        recommended_target=3.5,
        confidence_level="HIGH",
        reason="5 consecutivos < 2.0x detectados"
    )
    
    # Simular aposta
    print(f"\n{Fore.YELLOW}💰 Simulando aposta...")
    bet_id = session.execute_bet(
        recommendation_id=rec_id,
        bet_amount=25.0,
        target_multiplier=3.5,
        profile_used="Monitor LG",
        working_balance_before=500.0,
        execution_time=2.3
    )
    
    # Simular resultado
    session.update_bet_result(bet_id, 4.2, "WIN", 62.5, 562.5)
    
    # Mostrar stats
    print(f"\n{Fore.CYAN}📊 ESTATÍSTICAS DA SESSÃO:")
    stats = session.get_session_stats()
    for key, value in stats.items():
        if key not in ['session_id', 'recent_multipliers']:
            print(f"{Fore.WHITE}   {key}: {value}")
    
    # Encerrar sessão
    session.close_session()
    
    print(f"\n{Fore.GREEN}🎉 Session Manager funcionando perfeitamente!")

if __name__ == "__main__":
    main()