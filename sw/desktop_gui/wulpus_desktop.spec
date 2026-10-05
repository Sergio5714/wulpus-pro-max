# PyInstaller builds are native: run this specification on each target OS.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.win32 import versioninfo

from desktop_gui import APP_NAME, APP_VERSION

sw = Path(SPEC).resolve().parents[1]
onefile = os.environ.get("WULPUS_DESKTOP_ONEFILE") == "1"
app_name = f"WULPUS-Pro-Max-{APP_VERSION}" if onefile else "WULPUS-Pro-Max"
version_numbers = tuple(int(part) for part in APP_VERSION.split("."))
file_version = (*version_numbers, *(0 for _ in range(4 - len(version_numbers))))
windows_version = versioninfo.VSVersionInfo(
    ffi=versioninfo.FixedFileInfo(
        filevers=file_version,
        prodvers=file_version,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        versioninfo.StringFileInfo(
            [
                versioninfo.StringTable(
                    "040904B0",
                    [
                        versioninfo.StringStruct("FileDescription", APP_NAME),
                        versioninfo.StringStruct("FileVersion", APP_VERSION),
                        versioninfo.StringStruct("ProductName", APP_NAME),
                        versioninfo.StringStruct("ProductVersion", APP_VERSION),
                    ],
                )
            ]
        ),
        versioninfo.VarFileInfo([versioninfo.VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    [str(sw / "desktop_gui" / "entrypoint.py")],
    pathex=[str(sw)],
    binaries=[],
    datas=[(str(sw / "pyproject.toml"), "."), *collect_data_files("esptool")],
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
    a.binaries if onefile else [],
    a.datas if onefile else [],
    exclude_binaries=not onefile,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=os.environ.get("WULPUS_DESKTOP_CONSOLE") == "1",
    version=windows_version if os.name == "nt" else None,
)
if not onefile:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name=app_name,
    )
