# -*- coding: utf-8 -*-
"""机器指纹：用于卡密的单机绑定。跨平台，返回稳定且不可逆的机器 ID。"""
import hashlib
import platform
import socket


def _try(fn, default=""):
    try:
        return fn()
    except Exception:
        return default


def _win_machine_guid():
    import winreg
    k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
    v, _ = winreg.QueryValueEx(k, "MachineGuid")
    winreg.CloseKey(k)
    return v


def get_machine_id() -> str:
    """Windows 使用注册表 MachineGuid + 主机名 + MAC；Linux 使用 machine-id。"""
    parts = []
    if platform.system() == "Windows":
        parts.append(_try(_win_machine_guid))
    else:
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            v = _try(lambda: open(p).read().strip())
            if v:
                parts.append(v)
                break
    parts.append(_try(socket.gethostname))
    try:
        import uuid
        parts.append(str(uuid.getnode()))
    except Exception:
        pass
    raw = "|".join(x for x in parts if x)
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:16].upper()
