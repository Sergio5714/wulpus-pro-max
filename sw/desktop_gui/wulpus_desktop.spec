# PyInstaller builds are native: run this specification on each target OS.
from pathlib import Path

sw = Path(SPEC).resolve().parents[1]

a = Analysis(
    [str(sw / "desktop_gui" / "entrypoint.py")],
    pathex=[str(sw)],
    binaries=[],
    datas=[],
    hiddenimports=["esptool", "scipy.signal", "serial.tools.list_ports", "zeroconf"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["jupyter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WULPUS-Pro-Max",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="WULPUS-Pro-Max",
)
