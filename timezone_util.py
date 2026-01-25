#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TIMEZONE UTIL - Forca fuso horario de Brasilia em todo o bot
"""

from datetime import datetime, timedelta, timezone

# Brasilia = UTC-3
BRASILIA_OFFSET = timezone(timedelta(hours=-3))

def agora():
    """Retorna datetime atual em Brasilia"""
    return datetime.now(BRASILIA_OFFSET)

def agora_str(formato='%Y-%m-%d %H:%M:%S'):
    """Retorna string formatada em Brasilia"""
    return agora().strftime(formato)

def horario():
    """Retorna apenas horario HH:MM:SS em Brasilia"""
    return agora().strftime('%H:%M:%S')

def data():
    """Retorna apenas data YYYY-MM-DD em Brasilia"""
    return agora().strftime('%Y-%m-%d')

def timestamp_sql():
    """Retorna timestamp para SQL em Brasilia"""
    return agora().strftime('%Y-%m-%d %H:%M:%S')

def converter_utc_para_brasilia(dt_utc):
    """Converte datetime UTC para Brasilia"""
    if dt_utc.tzinfo is None:
        # Assumir que é UTC se não tem timezone
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(BRASILIA_OFFSET)

def converter_str_utc_para_brasilia(dt_str, formato='%Y-%m-%d %H:%M:%S'):
    """Converte string datetime UTC para Brasilia"""
    dt_utc = datetime.strptime(dt_str, formato).replace(tzinfo=timezone.utc)
    dt_brasilia = dt_utc.astimezone(BRASILIA_OFFSET)
    return dt_brasilia.strftime(formato)


# Teste
if __name__ == "__main__":
    print(f"Agora em Brasilia: {agora_str()}")
    print(f"Horario: {horario()}")
    print(f"Data: {data()}")
