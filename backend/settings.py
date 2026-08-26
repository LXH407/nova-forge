# -*- coding: utf-8 -*-
"""后端配置：GitHub 连接 / 管理员密码 / 端口 / 台账与日志路径。
数据一律存 backend/data/（不入库）。"""
import json
import os
import uuid
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # 仓库根目录
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

MANIFEST = os.path.join(ROOT, "manifest.json")                          # 商城清单
BANLIST = os.path.join(ROOT, "banlist.json")                            # 封禁名单（随仓库分发）
PRIVKEY = os.path.join(ROOT, "keys", "private.pem")                     # 签发私钥（本地）
CARDS_DB = os.path.join(DATA, "cards_db.json")                          # 卡密台账（本地）
SETTINGS = os.path.join(DATA, "settings.json")                          # 后端设置（本地）
LOG = os.path.join(DATA, "admin.log")                                   # 操作日志

DEFAULTS = {
    "owner": "",            # GitHub 用户名
    "repo": "",             # 仓库名
    "pat": "",              # Personal Access Token（repo 权限）
    "password": "novaforge-admin",   # 后台登录密码（首次登录后请修改）
    "port": 8642,
    "branch": "main",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load() -> dict:
    os.makedirs(DATA, exist_ok=True)
    s = dict(DEFAULTS)
    if os.path.exists(SETTINGS):
        try:
            with open(SETTINGS, "r", encoding="utf-8") as f:
                s.update(json.load(f))
        except Exception:
            pass
    return s


def save(s: dict):
    os.makedirs(DATA, exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def add_log(action: str, detail: str = ""):
    os.makedirs(DATA, exist_ok=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{_now()}] {action} {detail}\n")
    except Exception:
        pass


def read_logs(n: int = 100) -> list:
    if not os.path.exists(LOG):
        return []
    with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    return lines[-n:]


def new_token() -> str:
    return uuid.uuid4().hex
