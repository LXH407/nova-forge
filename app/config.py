# -*- coding: utf-8 -*-
"""全局配置读写。配置文件位于 %APPDATA%/NovaForge/config.json（Windows）
或 ~/.novaforge/config.json（其他平台）。"""
import json
import os
import sys

APP_NAME = "NovaForge"
APP_DISPLAY = "NOVA FORGE"
APP_TAGLINE = "Hyperdrive Content Forge"
VERSION = "2.1.0"
APP_EXE = "NovaForge.exe"

DEFAULTS = {
    "version": VERSION,
    "first_run": True,
    # GitHub 仓库（作为“无服务器”场景下的更新/同步通道；不在界面中展示）
    "github_owner": "LXH407",
    "github_repo": "nova-forge",
    "manifest_url": "",
    # 下载 / 镜像加速
    "default_download_dir": "",
    "aria2_path": "aria2c",
    "download_threads": 16,
    "auto_mirror": True,            # 慢速自动切换国内镜像源
    "hf_mirror": "https://hf-mirror.com",
    "speed_threshold_kb": 200,      # 低于该速度(KB/s)视为过慢
    "slow_seconds": 8,              # 持续过慢 N 秒后切换镜像
    "max_mirror_retry": 2,
    # 卡密 / 积分 / 会员
    "max_trials": 0,            # 试用次数（积分制下默认 0，关闭试用）
    "trial_used": 0,
    "activated": None,          # 会员卡信息（激活后为 dict）
    "redeemed": [],             # 本机已使用过的卡密 UID（防重复兑换）
    "points": 0,                # 积分余额（1 积分 = 下载 1 个商品）
    "member_expire": "",        # 会员到期日（"" 表示非会员，9999-12-31 表示永久）
    "wallet_orders": [],        # 充值登记（本地留存）
    "local_content": [],
    "last_sync": "",
}


def app_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, APP_NAME)
    else:
        d = os.path.join(os.path.expanduser("~"), "." + APP_NAME.lower())
    os.makedirs(d, exist_ok=True)
    return d


def logs_dir() -> str:
    d = os.path.join(app_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def cache_dir() -> str:
    d = os.path.join(app_dir(), "cache")
    os.makedirs(d, exist_ok=True)
    return d


def icons_dir() -> str:
    d = os.path.join(cache_dir(), "icons")
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    return os.path.join(app_dir(), "config.json")


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    p = config_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    p = config_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[config] 保存配置失败:", e)


def default_manifest_url(cfg: dict) -> str:
    if cfg.get("manifest_url"):
        return cfg["manifest_url"]
    owner = cfg.get("github_owner", "").strip()
    repo = cfg.get("github_repo", "").strip()
    if owner and repo and owner != "YOUR_GITHUB_USERNAME":
        return f"https://raw.githubusercontent.com/{owner}/{repo}/main/manifest.json"
    return ""


def update_api_url(cfg: dict) -> str:
    owner = cfg.get("github_owner", "").strip()
    repo = cfg.get("github_repo", "").strip()
    if owner and repo and owner != "YOUR_GITHUB_USERNAME":
        return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    return ""
