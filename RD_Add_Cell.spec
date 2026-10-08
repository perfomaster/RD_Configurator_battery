# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('C:\\Users\\Nick\\Documents\\RD\\Конфигуратор АКБ\\cells_db.txt', '.'), ('C:\\Users\\Nick\\Documents\\RD\\Конфигуратор АКБ\\logo_RD.png', '.'), ('C:\\Users\\Nick\\Documents\\RD\\Конфигуратор АКБ\\logo_RD.svg', '.'), ('C:\\Users\\Nick\\Documents\\RD\\Конфигуратор АКБ\\logo_RD_ico.ico', '.'), ('C:\\Users\\Nick\\Documents\\RD\\Конфигуратор АКБ\\main_state.json', '.')]
datas += collect_data_files('customtkinter')


a = Analysis(
    ['C:\\Users\\Nick\\Documents\\RD\\Конфигуратор АКБ\\add_cell.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RD_Add_Cell',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Nick\\Documents\\RD\\Конфигуратор АКБ\\logo_RD_ico.ico'],
)
