# -*- mode: python ; coding: utf-8 -*-
# NovaForge PyInstaller 打包配置（Windows 单文件 EXE）
import os

root = os.path.abspath(os.getcwd())

datas = [
    ("manifest.json", "assets"),
    ("banlist.json", "assets"),
    ("assets/public_key.pem", "assets"),
    ("assets/icon.png", "assets"),
    ("assets/icon.ico", "assets"),
    ("assets/logo_main.png", "assets"),
    ("assets/logo_alt.png", "assets"),
    ("assets/bg.png", "assets"),
    ("update/updater.bat", "update"),
    ("update/updater.sh", "update"),
]

binaries = []

a = Analysis(
    ["main.py"],
    pathex=[root],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "cryptography",
        "cryptography.hazmat.primitives.asymmetric.padding",
        "cryptography.hazmat.primitives.asymmetric.rsa",
        "cryptography.hazmat.primitives.serialization",
        "cryptography.hazmat.backends.openssl",
        "requests",
        "PIL",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "setuptools", "pip"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NovaForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=os.path.join(root, "assets", "icon.ico"),
)
