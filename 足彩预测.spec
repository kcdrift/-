# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['web/app.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web'), ('data/raw/historical_real.csv', 'data/raw'), ('data/raw/upcoming_fixtures.csv', 'data/raw')],
    hiddenimports=['src.value_betting', 'src.calibration'],
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
    name='足彩预测',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
