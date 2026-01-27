#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
START V2 - Script de inicializacao do Sistema Martingale V2

Este script inicia o sistema com o fluxo correto:
- Opcao de calibracao antes de iniciar
- Saldo lido apenas no INICIO e FIM do martingale
- WIN/LOSS baseado em multiplicador vs alvo
- P/L calculado uma vez no final
"""

import sys
import os
import json
import time
import pyautogui
from colorama import Fore, init
from martingale_session import (
    NIVEIS_SEGURANCA,
    ModoOperacao,
    ConfiguracaoModo,
    get_nivel_para_banca,
    EstadoSessao,
    existe_sessao_ativa,
    carregar_estado_sessao,
    get_session_state_path
)

init(autoreset=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
AUTO_RESTART_FLAG = os.path.join(os.path.dirname(__file__), 'auto_restart.flag')


def minimizar_janela():
    """Minimiza a janela do console (Windows)"""
    try:
        import ctypes
        # Obter handle da janela do console
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # SW_MINIMIZE = 6
            ctypes.windll.user32.ShowWindow(hwnd, 6)
            return True
    except:
        pass
    return False


def is_auto_restart():
    """Verifica se é um reinício automático"""
    return os.path.exists(AUTO_RESTART_FLAG)


def clear_auto_restart_flag():
    """Remove o flag de auto-restart após iniciar"""
    if os.path.exists(AUTO_RESTART_FLAG):
        try:
            os.remove(AUTO_RESTART_FLAG)
        except:
            pass


def check_dependencies():
    """Verifica se todas as dependencias estao instaladas"""
    required = [
        'pyautogui',
        'pyperclip',
        'numpy',
        'colorama',
        'mss',
        'pillow',
        'easyocr',
    ]

    missing = []
    for module in required:
        try:
            __import__(module.replace('-', '_').lower())
        except ImportError:
            alt_names = {'pillow': 'PIL', 'easyocr': 'easyocr'}
            alt = alt_names.get(module)
            if alt:
                try:
                    __import__(alt)
                    continue
                except ImportError:
                    pass
            missing.append(module)

    if missing:
        print(f"{Fore.RED}ERRO: Dependencias faltando:")
        for m in missing:
            print(f"{Fore.YELLOW}  - {m}")
        print(f"\n{Fore.CYAN}Instale com: pip install {' '.join(missing)}")
        return False

    return True


def load_config():
    """Carrega config.json"""
    if not os.path.exists(CONFIG_PATH):
        print(f"{Fore.RED}ERRO: config.json nao encontrado!")
        return None

    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}ERRO: config.json invalido: {e}")
        return None


def save_config(config):
    """Salva config.json"""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)


def capturar_area(nome_area: str) -> dict:
    """Captura uma area (retangulo) interativamente"""
    print(f"\n{Fore.YELLOW}>>> {nome_area}")

    print(f"{Fore.WHITE}    Posicione no CANTO SUPERIOR ESQUERDO")
    input(f"{Fore.GREEN}    [ENTER para capturar]")
    pos1 = pyautogui.position()
    print(f"{Fore.CYAN}    -> ({pos1.x}, {pos1.y})")

    print(f"{Fore.WHITE}    Posicione no CANTO INFERIOR DIREITO")
    input(f"{Fore.GREEN}    [ENTER para capturar]")
    pos2 = pyautogui.position()
    print(f"{Fore.CYAN}    -> ({pos2.x}, {pos2.y})")

    x = min(pos1.x, pos2.x)
    y = min(pos1.y, pos2.y)
    width = abs(pos2.x - pos1.x)
    height = abs(pos2.y - pos1.y)

    return {"x": x, "y": y, "width": width, "height": height}


def calibrar_perfil(config, profile_name):
    """Calibra um perfil completo"""
    print(f"\n{Fore.CYAN}{'='*50}")
    print(f"{Fore.CYAN}  CALIBRACAO DO PERFIL: {profile_name}")
    print(f"{Fore.CYAN}{'='*50}")

    profile = config['profiles'].get(profile_name, {})

    print(f"\n{Fore.YELLOW}Certifique-se que o jogo esta aberto e visivel!")
    input(f"{Fore.GREEN}[ENTER para iniciar calibracao]")

    # 1. Area do multiplicador (OCR)
    profile['multiplier_area'] = capturar_area("AREA DO MULTIPLICADOR (onde aparece o valor)")

    # 2. Area do saldo (OCR)
    profile['balance_area'] = capturar_area("AREA DO SALDO (onde aparece R$ xxx)")

    # 3. Area de deteccao BET
    profile['bet_area'] = capturar_area("AREA DE DETECCAO 'BET' (onde aparece a palavra)")

    # 4. Campo valor aposta - Slot 1 (AREA para variacao)
    profile['bet_value_area_1'] = capturar_area("CAMPO VALOR DA APOSTA - Slot 1")

    # 5. Campo alvo - Slot 1 (AREA para variacao)
    profile['target_area_1'] = capturar_area("CAMPO DO ALVO/TARGET - Slot 1")

    # 6. Botao confirmar - Slot 1 (AREA para variacao)
    profile['bet_button_area_1'] = capturar_area("BOTAO CONFIRMAR APOSTA - Slot 1")

    # Slot 2 opcional
    resp = input(f"\n{Fore.YELLOW}Calibrar Slot 2? (s/N): ").lower().strip()
    if resp == 's':
        profile['bet_value_area_2'] = capturar_area("CAMPO VALOR DA APOSTA - Slot 2")
        profile['target_area_2'] = capturar_area("CAMPO DO ALVO/TARGET - Slot 2")
        profile['bet_button_area_2'] = capturar_area("BOTAO CONFIRMAR APOSTA - Slot 2")
    else:
        profile['bet_value_area_2'] = None
        profile['target_area_2'] = None
        profile['bet_button_area_2'] = None

    config['profiles'][profile_name] = profile
    save_config(config)

    print(f"\n{Fore.GREEN}Perfil '{profile_name}' calibrado e salvo!")


def menu_inicial(config):
    """Menu inicial com opcao de calibracao"""
    profiles = list(config.get('profiles', {}).keys())

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}       SISTEMA MARTINGALE V2")
    print(f"{Fore.CYAN}{'='*60}")
    print(f"\n{Fore.YELLOW}PERFIS DISPONIVEIS:")

    for i, p in enumerate(profiles, 1):
        print(f"  {i}. {p}")

    print(f"\n{Fore.CYAN}OPCOES:")
    print(f"  C = Calibrar perfil existente")
    print(f"  N = Criar NOVO perfil")
    print(f"  Q = Sair")
    print(f"  [numero] = Iniciar com perfil")

    choice = input(f"\n{Fore.GREEN}Escolha: ").strip().upper()

    if choice == 'Q':
        print(f"{Fore.YELLOW}Saindo...")
        sys.exit(0)

    elif choice == 'C':
        # Calibrar existente
        print(f"\n{Fore.YELLOW}Qual perfil calibrar?")
        for i, p in enumerate(profiles, 1):
            print(f"  {i}. {p}")
        idx = input(f"{Fore.GREEN}Escolha: ").strip()
        try:
            profile_name = profiles[int(idx) - 1]
            calibrar_perfil(config, profile_name)
            return menu_inicial(config)  # Voltar ao menu
        except:
            print(f"{Fore.RED}Opcao invalida!")
            return menu_inicial(config)

    elif choice == 'N':
        # Novo perfil
        profile_name = input(f"{Fore.GREEN}Nome do novo perfil: ").strip()
        if not profile_name:
            print(f"{Fore.RED}Nome invalido!")
            return menu_inicial(config)
        config['profiles'][profile_name] = {}
        calibrar_perfil(config, profile_name)
        return profile_name

    else:
        # Iniciar com perfil
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(profiles):
                selected = profiles[idx]
                # Perguntar se quer recalibrar
                resp = input(f"\n{Fore.YELLOW}Recalibrar '{selected}'? (s/N): ").lower().strip()
                if resp == 's':
                    calibrar_perfil(config, selected)
                return selected
            else:
                print(f"{Fore.RED}Opcao invalida!")
                return menu_inicial(config)
        except:
            print(f"{Fore.RED}Opcao invalida!")
            return menu_inicial(config)


def selecionar_modo_operacao() -> ConfiguracaoModo:
    """Menu de selecao do modo de operacao"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}       SELECAO DE ESTRATEGIA")
    print(f"{Fore.CYAN}{'='*60}")

    print(f"\n{Fore.YELLOW}Escolha a estrategia:")

    print(f"\n{Fore.WHITE}  1. [7,7,6] Padrao")
    print(f"{Fore.WHITE}     - Alterna NS7-NS7-NS6 automaticamente")
    print(f"{Fore.WHITE}     - Reserva e emprestimo ativos")

    print(f"\n{Fore.WHITE}  2. [7,7,6] + Auto-upgrade")
    print(f"{Fore.WHITE}     - Mesmo que acima + sobe nivel ao atingir % lucro")

    print(f"\n{Fore.WHITE}  3. NS7 PURO (banca integral)")
    print(f"{Fore.WHITE}     - Sempre NS7, defesa 1.10x, sem reserva")

    print(f"\n{Fore.YELLOW}  4. G6+NS9 AGRESSIVO (NOVO)")
    print(f"{Fore.WHITE}     - Gatilho: 6 baixas | Divisor: 511")
    print(f"{Fore.WHITE}     - Protecao: 15 | Alvo: 2.00x")
    print(f"{Fore.WHITE}     - ~R$ 25k/mes por R$ 10k | 2 busts/ano")

    print(f"\n{Fore.GREEN}  5. G6+NS10 CONSERVADOR (NOVO)")
    print(f"{Fore.WHITE}     - Gatilho: 6 baixas | Divisor: 1023")
    print(f"{Fore.WHITE}     - Protecao: 16 | Alvo: 2.00x")
    print(f"{Fore.WHITE}     - ~R$ 12k/mes por R$ 10k | 0 busts")

    while True:
        choice = input(f"\n{Fore.GREEN}Escolha (1-5) [5]: ").strip()

        if choice == '' or choice == '5':
            modo = ModoOperacao.G6_NS10
            break
        elif choice == '4':
            modo = ModoOperacao.G6_NS9
            break
        elif choice == '1':
            modo = ModoOperacao.MANUAL
            break
        elif choice == '2':
            modo = ModoOperacao.AUTOMATICO
            break
        elif choice == '3':
            modo = ModoOperacao.NS7_PURO
            break
        else:
            print(f"{Fore.RED}Opcao invalida! Digite 1, 2, 3, 4 ou 5.")

    # Configurar nivel e alvo baseado no modo
    if modo == ModoOperacao.G6_NS9:
        nivel_inicial = 9
        alvo_defesa = 2.00  # Sem defesa, sempre 2.00x
        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"{Fore.YELLOW}       G6+NS9 AGRESSIVO")
        print(f"{Fore.YELLOW}{'='*60}")
        print(f"\n{Fore.WHITE}  Configuracao:")
        print(f"{Fore.WHITE}    - Gatilho: 6 baixas consecutivas")
        print(f"{Fore.WHITE}    - Nivel: NS9 (divisor 511, 9 tentativas)")
        print(f"{Fore.WHITE}    - Alvo: 2.00x")
        print(f"{Fore.WHITE}    - Protecao: 15 baixas")
        print(f"{Fore.RED}    - Busts esperados: 2 por ano")
        print(f"{Fore.GREEN}    - Retorno: ~R$ 25k/mes por R$ 10k")
        print(f"{Fore.CYAN}    - Auto-upgrade: NS9->NS10 ao atingir 5.8% lucro")

    elif modo == ModoOperacao.G6_NS10:
        nivel_inicial = 10
        alvo_defesa = 2.00  # Sem defesa, sempre 2.00x
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}       G6+NS10 CONSERVADOR")
        print(f"{Fore.GREEN}{'='*60}")
        print(f"\n{Fore.WHITE}  Configuracao:")
        print(f"{Fore.WHITE}    - Gatilho: 6 baixas consecutivas")
        print(f"{Fore.WHITE}    - Nivel: NS10 (divisor 1023, 10 tentativas)")
        print(f"{Fore.WHITE}    - Alvo: 2.00x")
        print(f"{Fore.WHITE}    - Protecao: 16 baixas")
        print(f"{Fore.GREEN}    - Busts esperados: 0 (dataset 1.3M)")
        print(f"{Fore.GREEN}    - Retorno: ~R$ 12k/mes por R$ 10k")

    elif modo == ModoOperacao.NS7_PURO:
        nivel_inicial = 7
        alvo_defesa = 1.10
        print(f"\n{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.MAGENTA}       NS7 PURO - BANCA INTEGRAL")
        print(f"{Fore.MAGENTA}{'='*60}")
        print(f"\n{Fore.WHITE}  Configuracao:")
        print(f"{Fore.WHITE}    - Nivel: NS7 (divisor 127)")
        print(f"{Fore.WHITE}    - Defesa: 1.10x (0 busts em 15k gatilhos)")
        print(f"{Fore.WHITE}    - Reserva: DESATIVADA")
        print(f"{Fore.WHITE}    - Banca: 100% operacional")

    else:
        # Modos [7,7,6]
        nivel_inicial = 7
        alvo_defesa = 1.25

    # Definir lucro_para_subir baseado no modo
    # G6_NS9/G6_NS10: 5.8% (meta diária para migração)
    # AUTOMATICO: 100% (default, mas pergunta ao usuário)
    if modo in [ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]:
        lucro_para_subir_default = 5.8
    else:
        lucro_para_subir_default = 100.0

    config_modo = ConfiguracaoModo(
        modo=modo,
        nivel_inicial=nivel_inicial,
        lucro_para_subir=lucro_para_subir_default,
        alvo_defesa=alvo_defesa
    )

    # Se modo automatico, perguntar % de lucro para subir
    if modo == ModoOperacao.AUTOMATICO:
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}       AUTO-UPGRADE DE NIVEL BASE")
        print(f"{Fore.CYAN}{'='*60}")

        print(f"\n{Fore.YELLOW}O padrao [7,7,6] mudara para [8,8,7] ao atingir X% de lucro.")
        print(f"{Fore.YELLOW}Recomendado: 100% (dobrar a banca)")

        while True:
            pct_str = input(f"\n{Fore.GREEN}% de lucro para upgrade [100]: ").strip()
            if not pct_str:
                config_modo.lucro_para_subir = 100.0
                break
            try:
                pct = float(pct_str)
                if 10 <= pct <= 500:
                    config_modo.lucro_para_subir = pct
                    break
                else:
                    print(f"{Fore.RED}Use um valor entre 10% e 500%.")
            except ValueError:
                print(f"{Fore.RED}Digite um numero valido!")

    # Resumo para modos [7,7,6]
    if modo in [ModoOperacao.MANUAL, ModoOperacao.AUTOMATICO]:
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}       CONFIGURACAO CONFIRMADA")
        print(f"{Fore.GREEN}{'='*60}")
        print(f"\n{Fore.CYAN}  [7,7,6] ATIVO")
        print(f"{Fore.WHITE}  Padrao: NS7 -> NS7 -> NS6 -> ...")
        print(f"{Fore.WHITE}  Reserva: 10% -> 50/50")
        print(f"{Fore.WHITE}  Emprestimo: 25 gatilhos sem T6")
        if modo == ModoOperacao.AUTOMATICO:
            print(f"{Fore.WHITE}  Auto-upgrade: ao atingir {config_modo.lucro_para_subir:.0f}% lucro")

    input(f"\n{Fore.GREEN}[ENTER para iniciar]")

    return config_modo


def menu_calibracao_inicial(config):
    """Menu de calibracao que aparece ANTES de escolher sessao"""
    profiles = list(config.get('profiles', {}).keys())

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}       CALIBRACAO DE PERFIL")
    print(f"{Fore.CYAN}{'='*60}")

    print(f"\n{Fore.YELLOW}PERFIS DISPONIVEIS:")
    for i, p in enumerate(profiles, 1):
        print(f"  {i}. {p}")

    print(f"\n{Fore.CYAN}OPCOES:")
    print(f"  C = Calibrar perfil existente")
    print(f"  N = Criar NOVO perfil")
    print(f"  [ENTER] = Pular calibracao")

    choice = input(f"\n{Fore.GREEN}Escolha: ").strip().upper()

    if choice == '':
        return config  # Pular calibracao

    elif choice == 'C':
        # Calibrar existente
        print(f"\n{Fore.YELLOW}Qual perfil calibrar?")
        for i, p in enumerate(profiles, 1):
            print(f"  {i}. {p}")
        idx = input(f"{Fore.GREEN}Escolha: ").strip()
        try:
            profile_name = profiles[int(idx) - 1]
            calibrar_perfil(config, profile_name)
        except:
            print(f"{Fore.RED}Opcao invalida!")
        return config

    elif choice == 'N':
        # Novo perfil
        profile_name = input(f"{Fore.GREEN}Nome do novo perfil: ").strip()
        if profile_name:
            config['profiles'][profile_name] = {}
            calibrar_perfil(config, profile_name)
        else:
            print(f"{Fore.RED}Nome invalido!")
        return config

    else:
        print(f"{Fore.YELLOW}Opcao nao reconhecida, pulando calibracao...")
        return config


def verificar_sessao_existente(config):
    """Verifica se existe sessao salva e pergunta se quer retomar"""
    if not existe_sessao_ativa():
        return None, None, None

    estado = carregar_estado_sessao()
    if not estado:
        return None, None, None

    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"{Fore.YELLOW}       SESSAO ANTERIOR ENCONTRADA")
    print(f"{Fore.YELLOW}{'='*60}")

    # Mostrar info da sessao
    print(f"\n{Fore.WHITE}  Iniciada em: {estado.inicio_timestamp}")
    print(f"{Fore.WHITE}  Perfil: {estado.perfil_ativo}")

    nivel_nome = NIVEIS_SEGURANCA.get(estado.nivel_seguranca, {}).get('nome', f'NS{estado.nivel_seguranca}')
    print(f"{Fore.WHITE}  Nivel: {nivel_nome}")

    modo_str = estado.config_modo.get('modo', 'manual').upper()
    print(f"{Fore.WHITE}  Modo: {modo_str}")

    print(f"\n{Fore.CYAN}  Deposito inicial: R$ {estado.deposito_inicial:.2f}")
    print(f"{Fore.CYAN}  Ultimo saldo: R$ {estado.saldo_atual:.2f}")

    resultado = estado.saldo_atual - estado.deposito_inicial + estado.total_saques
    cor = Fore.GREEN if resultado >= 0 else Fore.RED
    print(f"{cor}  Resultado: R$ {resultado:+.2f}")

    print(f"\n{Fore.WHITE}  Sessoes: WIN {estado.sessoes_win} | LOSS {estado.sessoes_loss}")
    print(f"{Fore.WHITE}  Rodadas: {estado.total_rodadas}")

    if estado.total_saques > 0:
        print(f"{Fore.GREEN}  Saques realizados: R$ {estado.total_saques:.2f}")

    # Listar perfis disponiveis
    profiles = list(config.get('profiles', {}).keys())

    print(f"\n{Fore.YELLOW}O que deseja fazer?")
    print(f"{Fore.WHITE}  1. Continuar sessao com perfil: {estado.perfil_ativo}")
    print(f"{Fore.WHITE}  2. Continuar sessao com OUTRO perfil")
    print(f"{Fore.WHITE}  3. Iniciar NOVA sessao")

    while True:
        choice = input(f"\n{Fore.GREEN}Escolha (1-3): ").strip()
        if choice == '1':
            # Recuperar config_modo do estado e usar perfil anterior
            config_modo = ConfiguracaoModo.from_dict(estado.config_modo)
            # Forçar lucro_para_subir correto para G6
            if config_modo.modo in [ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]:
                config_modo.lucro_para_subir = 5.8
            return estado, config_modo, estado.perfil_ativo

        elif choice == '2':
            # Continuar sessao mas com outro perfil
            print(f"\n{Fore.YELLOW}Selecione o perfil:")
            for i, p in enumerate(profiles, 1):
                marca = " <- anterior" if p == estado.perfil_ativo else ""
                print(f"  {i}. {p}{marca}")

            try:
                idx = int(input(f"{Fore.GREEN}Escolha: ").strip()) - 1
                if 0 <= idx < len(profiles):
                    novo_perfil = profiles[idx]
                    config_modo = ConfiguracaoModo.from_dict(estado.config_modo)
                    # Forçar lucro_para_subir correto para G6
                    if config_modo.modo in [ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]:
                        config_modo.lucro_para_subir = 5.8
                    return estado, config_modo, novo_perfil
                else:
                    print(f"{Fore.RED}Opcao invalida!")
            except:
                print(f"{Fore.RED}Opcao invalida!")

        elif choice == '3':
            print(f"{Fore.YELLOW}Iniciando nova sessao...")
            # Limpar TODOS os arquivos de estado para garantir sessao limpa
            base_dir = os.path.dirname(__file__)
            state_files = [
                'session_state.json',
                'reserva_state.json',
                'aceleracao_state.json',
            ]
            for state_file in state_files:
                try:
                    file_path = os.path.join(base_dir, state_file)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"{Fore.GREEN}  Limpo: {state_file}")
                except Exception as e:
                    print(f"{Fore.YELLOW}  Aviso: {state_file}: {e}")
            print(f"{Fore.GREEN}Estados anteriores limpos.")
            return None, None, None
        else:
            print(f"{Fore.RED}Opcao invalida!")


def main():
    """Ponto de entrada principal"""

    # Verificar se é auto-restart (reinício automático para liberar memória)
    auto_restart = is_auto_restart()

    if auto_restart:
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}       AUTO-RESTART - RETOMANDO SESSAO")
        print(f"{Fore.GREEN}{'='*60}\n")
        clear_auto_restart_flag()

        # Minimizar janela para não cobrir o multiplicador
        print(f"{Fore.YELLOW}Minimizando janela em 2 segundos...")
        time.sleep(2)
        if minimizar_janela():
            print(f"{Fore.GREEN}Janela minimizada!")
    else:
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}       SISTEMA MARTINGALE V2 - INICIALIZACAO")
        print(f"{Fore.CYAN}{'='*60}\n")

    # Verificar dependencias
    print(f"{Fore.YELLOW}Verificando dependencias...")
    if not check_dependencies():
        sys.exit(1)
    print(f"{Fore.GREEN}Dependencias OK\n")

    # Carregar config
    config = load_config()
    if not config:
        sys.exit(1)

    # Se for auto-restart, pular todos os menus e ir direto
    if auto_restart:
        # Verificar se existe sessão para retomar
        if existe_sessao_ativa():
            estado_anterior = carregar_estado_sessao()
            if estado_anterior:
                config_modo = ConfiguracaoModo.from_dict(estado_anterior.config_modo)
                # Forçar lucro_para_subir correto para G6
                if config_modo.modo in [ModoOperacao.G6_NS9, ModoOperacao.G6_NS10]:
                    config_modo.lucro_para_subir = 5.8
                selected_profile = estado_anterior.perfil_ativo
                print(f"{Fore.GREEN}Retomando sessao: {selected_profile}")
                print(f"{Fore.GREEN}Saldo: R$ {estado_anterior.saldo_atual:.2f}")
            else:
                print(f"{Fore.RED}Erro ao carregar estado! Iniciando normalmente...")
                auto_restart = False
        else:
            print(f"{Fore.RED}Nenhuma sessao ativa! Iniciando normalmente...")
            auto_restart = False

    # Fluxo normal (não é auto-restart ou falhou ao retomar)
    if not auto_restart:
        # PASSO 1: Menu de calibracao ANTES de tudo
        config = menu_calibracao_inicial(config)

        # Recarregar config (pode ter sido modificado na calibracao)
        config = load_config()

        # PASSO 2: Verificar se existe sessao anterior
        estado_anterior, config_modo, selected_profile = verificar_sessao_existente(config)

    if estado_anterior:
        # Continuar sessao anterior (perfil ja foi selecionado no menu)
        if selected_profile not in config.get('profiles', {}):
            print(f"{Fore.RED}Perfil '{selected_profile}' nao encontrado!")
            print(f"{Fore.YELLOW}Selecione um novo perfil...")
            selected_profile = menu_inicial(config)
    else:
        # Nova sessao
        selected_profile = menu_inicial(config)

        if not selected_profile:
            print(f"{Fore.RED}Nenhum perfil selecionado!")
            sys.exit(1)

        # Selecionar modo de operacao
        config_modo = selecionar_modo_operacao()

    print(f"\n{Fore.GREEN}Perfil selecionado: {selected_profile}")

    # Importar e iniciar o sistema
    try:
        print(f"{Fore.YELLOW}Carregando sistema...")

        # Recarregar config (pode ter sido modificado na calibracao)
        config = load_config()

        from hybrid_system_v2 import HybridSystemV2

        # Dashboard Web DESATIVADO - usando Telegram como interface principal
        # Para reativar, descomente o bloco abaixo
        # try:
        #     from dashboard_server import iniciar_dashboard
        #     import webbrowser
        #     import subprocess
        #     iniciar_dashboard(8080)
        #     url = 'http://localhost:8080/dashboard'
        #     firefox_opened = False
        #     firefox_paths = [
        #         r'C:\Program Files\Mozilla Firefox\firefox.exe',
        #         r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe',
        #     ]
        #     for firefox_path in firefox_paths:
        #         if os.path.exists(firefox_path):
        #             try:
        #                 subprocess.Popen([firefox_path, url])
        #                 firefox_opened = True
        #                 print(f"{Fore.GREEN}Dashboard aberto no Firefox")
        #                 break
        #             except:
        #                 pass
        #     if not firefox_opened:
        #         webbrowser.open(url)
        #         print(f"{Fore.YELLOW}Firefox nao encontrado, usando navegador padrao")
        # except Exception as e:
        #     print(f"{Fore.YELLOW}Dashboard nao iniciado: {e}")

        print(f"{Fore.GREEN}Sistema carregado! (Telegram ativo)\n")

        # Iniciar com perfil e configuracao de modo
        system = HybridSystemV2(
            selected_profile=selected_profile,
            config_modo=config_modo,
            estado_anterior=estado_anterior  # Passar estado para restaurar
        )
        system.start()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrompido pelo usuario")
    except Exception as e:
        print(f"\n{Fore.RED}ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
