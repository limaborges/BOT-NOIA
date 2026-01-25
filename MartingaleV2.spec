# -*- mode: python ; coding: utf-8 -*-
# MartingaleV2 - PyInstaller Spec File

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Coletar dados do EasyOCR (modelos, etc)
easyocr_datas = collect_data_files('easyocr')

# Modulos ocultos que precisam ser incluidos
hidden_imports = [
    'easyocr',
    'torch',
    'torchvision',
    'PIL',
    'cv2',
    'numpy',
    'mss',
    'pyautogui',
    'pyperclip',
    'colorama',
    'pytesseract',
    'sqlite3',
]

a = Analysis(
    ['start_v2.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('database', 'database'),
    ] + easyocr_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MartingaleV2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Manter console para ver output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Pode adicionar icone depois
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MartingaleV2',
)
