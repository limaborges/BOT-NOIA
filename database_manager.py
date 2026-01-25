#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DATABASE MANAGER - Sistema de banco de dados organizado
Gerencia 3 bases separadas: Rodadas, Apostas e Debug
"""

import json
import sqlite3
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from colorama import Fore, init

# Importar utilitario de timezone (Brasilia)
try:
    from timezone_util import agora_str
    TZ_UTIL = True
except ImportError:
    TZ_UTIL = False
    def agora_str(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

init(autoreset=True)

class DatabaseManager:
    """Gerenciador de banco de dados com 3 bases separadas"""
    
    def __init__(self, db_folder: str = "database"):
        self.db_folder = Path(db_folder)
        self.db_folder.mkdir(exist_ok=True)
        
        # Caminhos dos bancos
        self.rounds_db = self.db_folder / "rounds.db"
        self.bets_db = self.db_folder / "bets.db" 
        self.debug_db = self.db_folder / "debug.db"
        
        # Lock para thread safety
        self.lock = threading.Lock()
        
        # Inicializar bancos
        self.init_databases()
        
        print(f"{Fore.GREEN}💾 Database Manager inicializado")
        print(f"{Fore.CYAN}📁 Pasta: {self.db_folder}")
    
    def init_databases(self):
        """Inicializa as 3 bases de dados"""
        self.init_rounds_db()
        self.init_bets_db()
        self.init_debug_db()
    
    def init_rounds_db(self):
        """Base 1: Rodadas com timestamps"""
        with sqlite3.connect(self.rounds_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    multiplier REAL NOT NULL,
                    session_id TEXT,
                    regime TEXT,
                    score REAL,
                    capture_quality TEXT DEFAULT 'OK',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Índices para performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON rounds(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_multiplier ON rounds(multiplier)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON rounds(session_id)")
            
            conn.commit()
    
    def init_bets_db(self):
        """Base 2: Recomendações e apostas"""
        with sqlite3.connect(self.bets_db) as conn:
            # Tabela de recomendações
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    pattern_detected TEXT,
                    sequence_multipliers TEXT,
                    regime TEXT,
                    score REAL,
                    should_bet BOOLEAN,
                    recommended_amount REAL,
                    recommended_target REAL,
                    confidence_level TEXT,
                    reason TEXT,
                    filters_passed TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de apostas executadas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bets_executed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    recommendation_id INTEGER,
                    bet_amount REAL,
                    target_multiplier REAL,
                    actual_multiplier REAL,
                    result TEXT,
                    profit_loss REAL,
                    execution_time REAL,
                    bet_slot INTEGER DEFAULT 1,
                    profile_used TEXT,
                    working_balance_before REAL,
                    working_balance_after REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recommendation_id) REFERENCES recommendations (id)
                )
            """)
            
            # Índices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bets_timestamp ON bets_executed(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_timestamp ON recommendations(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bets_result ON bets_executed(result)")

            # Migração: adicionar coluna tentativa se não existir
            try:
                conn.execute("ALTER TABLE bets_executed ADD COLUMN tentativa INTEGER DEFAULT 1")
            except:
                pass  # Coluna já existe

            conn.commit()
    
    def init_debug_db(self):
        """Base 3: Debug e logs do sistema"""
        with sqlite3.connect(self.debug_db) as conn:
            # Logs de sistema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    level TEXT,
                    module TEXT,
                    message TEXT,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Erros de captura
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capture_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    error_type TEXT,
                    area_name TEXT,
                    coordinates TEXT,
                    error_message TEXT,
                    screenshot_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Eventos de refresh
            conn.execute("""
                CREATE TABLE IF NOT EXISTS refresh_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    reason TEXT,
                    time_since_last_explosion REAL,
                    manual BOOLEAN DEFAULT FALSE,
                    success BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Índices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)")
            
            conn.commit()
    
    # ===== MÉTODOS PARA RODADAS =====
    
    def save_round(self, multiplier: float, session_id: str, regime: str = None, 
                   score: float = None, capture_quality: str = "OK") -> int:
        """Salva uma rodada no banco"""
        with self.lock:
            with sqlite3.connect(self.rounds_db) as conn:
                cursor = conn.execute("""
                    INSERT INTO rounds (multiplier, session_id, regime, score, capture_quality)
                    VALUES (?, ?, ?, ?, ?)
                """, (multiplier, session_id, regime, score, capture_quality))
                
                round_id = cursor.lastrowid
                conn.commit()
                return round_id
    
    def get_recent_rounds(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Recupera rodadas recentes"""
        with sqlite3.connect(self.rounds_db) as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, multiplier, regime, score, capture_quality
                FROM rounds 
                WHERE session_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (session_id, limit))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_rounds_by_timeframe(self, hours: int = 24) -> List[Dict]:
        """Recupera rodadas por período"""
        since = datetime.now() - timedelta(hours=hours)
        
        with sqlite3.connect(self.rounds_db) as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, multiplier, session_id, regime, score
                FROM rounds 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (since,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # ===== MÉTODOS PARA APOSTAS =====
    
    def save_recommendation(self, session_id: str, pattern_detected: str, 
                          sequence_multipliers: List[float], regime: str, score: float,
                          should_bet: bool, recommended_amount: float = None,
                          recommended_target: float = None, confidence_level: str = None,
                          reason: str = None, filters_passed: List[str] = None) -> int:
        """Salva recomendação de aposta"""
        with self.lock:
            with sqlite3.connect(self.bets_db) as conn:
                cursor = conn.execute("""
                    INSERT INTO recommendations (
                        session_id, pattern_detected, sequence_multipliers, regime, score,
                        should_bet, recommended_amount, recommended_target, confidence_level,
                        reason, filters_passed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, pattern_detected, json.dumps(sequence_multipliers), regime, score,
                    should_bet, recommended_amount, recommended_target, confidence_level,
                    reason, json.dumps(filters_passed) if filters_passed else None
                ))
                
                rec_id = cursor.lastrowid
                conn.commit()
                return rec_id
    
    def save_bet_execution(self, session_id: str, recommendation_id: int,
                          bet_amount: float, target_multiplier: float,
                          actual_multiplier: float = None, result: str = "PENDING",
                          profit_loss: float = None, execution_time: float = None,
                          bet_slot: int = 1, profile_used: str = None,
                          working_balance_before: float = None,
                          working_balance_after: float = None,
                          tentativa: int = 1) -> int:
        """Salva execução de aposta"""
        with self.lock:
            with sqlite3.connect(self.bets_db) as conn:
                cursor = conn.execute("""
                    INSERT INTO bets_executed (
                        session_id, recommendation_id, bet_amount, target_multiplier,
                        actual_multiplier, result, profit_loss, execution_time,
                        bet_slot, profile_used, working_balance_before, working_balance_after,
                        tentativa
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, recommendation_id, bet_amount, target_multiplier,
                    actual_multiplier, result, profit_loss, execution_time,
                    bet_slot, profile_used, working_balance_before, working_balance_after,
                    tentativa
                ))

                bet_id = cursor.lastrowid
                conn.commit()
                return bet_id
    
    def update_bet_result(self, bet_id: int, actual_multiplier: float, 
                         result: str, profit_loss: float, working_balance_after: float):
        """Atualiza resultado da aposta"""
        with self.lock:
            with sqlite3.connect(self.bets_db) as conn:
                conn.execute("""
                    UPDATE bets_executed 
                    SET actual_multiplier = ?, result = ?, profit_loss = ?, 
                        working_balance_after = ?
                    WHERE id = ?
                """, (actual_multiplier, result, profit_loss, working_balance_after, bet_id))
                conn.commit()
    
    def get_bet_statistics(self, session_id: str = None, days: int = 7) -> Dict:
        """Calcula estatísticas de apostas"""
        since = datetime.now() - timedelta(days=days)
        
        where_clause = "WHERE timestamp >= ?"
        params = [since]
        
        if session_id:
            where_clause += " AND session_id = ?"
            params.append(session_id)
        
        with sqlite3.connect(self.bets_db) as conn:
            # Total de apostas
            cursor = conn.execute(f"""
                SELECT COUNT(*), 
                       SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(profit_loss) as total_profit,
                       AVG(bet_amount) as avg_bet,
                       AVG(target_multiplier) as avg_target
                FROM bets_executed 
                {where_clause}
            """, params)
            
            row = cursor.fetchone()
            total_bets, wins, total_profit, avg_bet, avg_target = row
            
            hit_rate = (wins / total_bets * 100) if total_bets > 0 else 0
            
            return {
                'total_bets': total_bets,
                'wins': wins,
                'losses': total_bets - wins,
                'hit_rate': hit_rate,
                'total_profit': total_profit or 0,
                'avg_bet_amount': avg_bet or 0,
                'avg_target': avg_target or 0,
                'roi': (total_profit / (avg_bet * total_bets) * 100) if total_bets > 0 and avg_bet else 0
            }
    
    # ===== MÉTODOS PARA DEBUG =====
    
    def log_system(self, session_id: str, level: str, module: str, 
                   message: str, details: str = None):
        """Log de sistema"""
        with self.lock:
            with sqlite3.connect(self.debug_db) as conn:
                conn.execute("""
                    INSERT INTO system_logs (session_id, level, module, message, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, level, module, message, details))
                conn.commit()
    
    def log_capture_error(self, session_id: str, error_type: str, area_name: str,
                         coordinates: str, error_message: str, screenshot_path: str = None):
        """Log de erro de captura"""
        with self.lock:
            with sqlite3.connect(self.debug_db) as conn:
                conn.execute("""
                    INSERT INTO capture_errors (
                        session_id, error_type, area_name, coordinates, 
                        error_message, screenshot_path
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, error_type, area_name, coordinates, error_message, screenshot_path))
                conn.commit()
    
    def log_refresh_event(self, session_id: str, reason: str, 
                         time_since_last_explosion: float, manual: bool = False, 
                         success: bool = True):
        """Log de evento de refresh"""
        with self.lock:
            with sqlite3.connect(self.debug_db) as conn:
                conn.execute("""
                    INSERT INTO refresh_events (
                        session_id, reason, time_since_last_explosion, manual, success
                    ) VALUES (?, ?, ?, ?, ?)
                """, (session_id, reason, time_since_last_explosion, manual, success))
                conn.commit()
    
    # ===== MÉTODOS DE LIMPEZA =====
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Remove dados antigos"""
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        
        with self.lock:
            # Limpeza das rodadas
            with sqlite3.connect(self.rounds_db) as conn:
                cursor = conn.execute("DELETE FROM rounds WHERE timestamp < ?", (cutoff,))
                rounds_deleted = cursor.rowcount
                conn.commit()
            
            # Limpeza dos logs de debug
            with sqlite3.connect(self.debug_db) as conn:
                cursor = conn.execute("DELETE FROM system_logs WHERE timestamp < ?", (cutoff,))
                logs_deleted = cursor.rowcount
                conn.commit()
            
            print(f"{Fore.YELLOW}🧹 Limpeza executada:")
            print(f"{Fore.WHITE}   Rodadas removidas: {rounds_deleted}")
            print(f"{Fore.WHITE}   Logs removidos: {logs_deleted}")
    
    # ===== MÉTODOS DE RELATÓRIO =====
    
    def generate_session_report(self, session_id: str) -> Dict:
        """Gera relatório completo da sessão"""
        report = {
            'session_id': session_id,
            'timestamp': agora_str()  # Brasilia
        }
        
        # Dados de rodadas
        rounds = self.get_recent_rounds(session_id, 1000)
        if rounds:
            multipliers = [r['multiplier'] for r in rounds]
            report['rounds'] = {
                'total': len(rounds),
                'avg_multiplier': sum(multipliers) / len(multipliers),
                'max_multiplier': max(multipliers),
                'min_multiplier': min(multipliers),
                'baixos_count': len([m for m in multipliers if m < 2.0])
            }
        
        # Estatísticas de apostas
        bet_stats = self.get_bet_statistics(session_id)
        report['betting'] = bet_stats
        
        return report
    
    def get_database_status(self) -> Dict:
        """Status dos bancos de dados"""
        status = {}
        
        # Status das rodadas
        with sqlite3.connect(self.rounds_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM rounds")
            status['rounds_total'] = cursor.fetchone()[0]
        
        # Status das apostas
        with sqlite3.connect(self.bets_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM recommendations")
            status['recommendations_total'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM bets_executed")
            status['bets_total'] = cursor.fetchone()[0]
        
        # Status dos logs
        with sqlite3.connect(self.debug_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM system_logs")
            status['logs_total'] = cursor.fetchone()[0]
        
        return status

def main():
    """Teste do Database Manager"""
    print(f"{Fore.MAGENTA}💾 TESTE DO DATABASE MANAGER")
    print(f"{Fore.CYAN}{'='*40}")
    
    # Inicializar
    db = DatabaseManager()
    
    session_id = f"test_{int(time.time())}"
    
    # Teste de rodadas
    print(f"\n{Fore.YELLOW}🎯 Testando salvamento de rodadas...")
    for i, mult in enumerate([1.5, 2.3, 1.8, 4.2, 1.1], 1):
        round_id = db.save_round(mult, session_id, "FAVORAVEL", 75.5)
        print(f"{Fore.GREEN}✅ Rodada {i}: {mult}x (ID: {round_id})")
    
    # Teste de recomendações
    print(f"\n{Fore.YELLOW}💡 Testando recomendações...")
    rec_id = db.save_recommendation(
        session_id=session_id,
        pattern_detected="KAMIKAZE_5_BAIXOS",
        sequence_multipliers=[1.5, 1.8, 1.1, 1.9, 1.6],
        regime="FAVORAVEL",
        score=82.3,
        should_bet=True,
        recommended_amount=25.0,
        recommended_target=3.5,
        confidence_level="HIGH",
        reason="5 consecutivos < 2.0x detectados",
        filters_passed=["regime_ok", "score_ok", "volatilidade_ok"]
    )
    print(f"{Fore.GREEN}✅ Recomendação salva (ID: {rec_id})")
    
    # Teste de aposta
    print(f"\n{Fore.YELLOW}💰 Testando execução de aposta...")
    bet_id = db.save_bet_execution(
        session_id=session_id,
        recommendation_id=rec_id,
        bet_amount=25.0,
        target_multiplier=3.5,
        execution_time=2.3,
        profile_used="Monitor LG",
        working_balance_before=500.0
    )
    print(f"{Fore.GREEN}✅ Aposta executada (ID: {bet_id})")
    
    # Simular resultado
    db.update_bet_result(bet_id, 4.2, "WIN", 62.5, 562.5)
    print(f"{Fore.GREEN}✅ Resultado atualizado: GANHOU!")
    
    # Teste de logs
    print(f"\n{Fore.YELLOW}📋 Testando logs...")
    db.log_system(session_id, "INFO", "KamikazeSystem", "Sistema iniciado")
    db.log_refresh_event(session_id, "Timeout 133s", 135.2, False, True)
    print(f"{Fore.GREEN}✅ Logs salvos")
    
    # Status final
    print(f"\n{Fore.CYAN}📊 STATUS DOS BANCOS:")
    status = db.get_database_status()
    for key, value in status.items():
        print(f"{Fore.WHITE}   {key}: {value}")
    
    # Relatório da sessão
    print(f"\n{Fore.CYAN}📈 RELATÓRIO DA SESSÃO:")
    report = db.generate_session_report(session_id)
    print(f"{Fore.WHITE}   Total rodadas: {report.get('rounds', {}).get('total', 0)}")
    print(f"{Fore.WHITE}   Total apostas: {report.get('betting', {}).get('total_bets', 0)}")
    print(f"{Fore.WHITE}   Hit rate: {report.get('betting', {}).get('hit_rate', 0):.1f}%")
    
    print(f"\n{Fore.GREEN}🎉 Database Manager funcionando perfeitamente!")

if __name__ == "__main__":
    main()