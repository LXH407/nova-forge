# -*- coding: utf-8 -*-
"""自动更新模块：通过 GitHub Releases 检查/下载/安装新版本（无服务器方案）。"""
import json
import os
import re
import subprocess
import sys
from urllib import request

from . import config
from .config import VERSION

TIMEOUT = 30


def _http_get_json(url: str, timeout: int = TIMEOUT):
    req = request.Request(url, headers={"User-Agent": "NovaForge/2.0",
                                        "Accept": "application/vnd.github+json"})
    with request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _ver_tuple(v: str):
    nums = re.findall(r"\d+", v)
    return tuple(int(x) for x in nums[:3]) or (0, 0, 0)


def check_update(cfg: dict) -> dict:
    api = config.update_api_url(cfg)
    res = {"ok": False, "msg": "", "has_update": False, "latest_tag": VERSION,
           "asset_url": "", "asset_name": "", "latest_name": ""}
    if not api:
        res["msg"] = "未配置 GitHub 仓库地址"
        return res
    try:
        try:
            rel = _http_get_json(api)
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 404:
                # 尚未发布任何 Release（首次部署常见）
                res["ok"] = True
                res["msg"] = "暂无发布版本（更新尚未发布）"
                return res
            raise
        tag = rel.get("tag_name", "")
        res["latest_tag"] = tag
        res["latest_name"] = rel.get("name") or ""
        if _ver_tuple(tag) <= _ver_tuple(VERSION):
            res["ok"] = True
            res["msg"] = "已是最新版本"
            return res
        for a in rel.get("assets", []):
            name = a.get("name", "")
            if name.endswith(".exe") or name.endswith(".zip"):
                res["asset_url"] = a.get("browser_download_url", "")
                res["asset_name"] = name
                break
        if not res["asset_url"]:
            res["ok"] = True
            res["msg"] = f"发现新版本 {tag}，但 Release 未附带安装包"
            return res
        res["ok"] = True
        res["has_update"] = True
        res["msg"] = f"发现新版本 {tag}"
        return res
    except Exception as e:
        res["msg"] = f"检查更新失败: {e}"
        return res


def download_update(url: str, dest: str, progress=None) -> str:
    import requests
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with requests.get(url, headers={"User-Agent": "NovaForge/2.0"},
                      stream=True, timeout=(10, 120)) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 512):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    if os.path.exists(dest):
        os.remove(dest)
    os.rename(tmp, dest)
    return dest


def apply_update(cfg: dict, new_exe: str, target_exe: str) -> bool:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys.platform == "win32":
        script = os.path.join(root, "update", "updater.bat")
        if not os.path.exists(script):
            return False
        subprocess.Popen([script, new_exe, target_exe],
                         creationflags=subprocess.DETACHED_PROCESS |
                         subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
        return True
    script = os.path.join(root, "update", "updater.sh")
    if not os.path.exists(script):
        return False
    subprocess.Popen(["sh", script, new_exe, target_exe], start_new_session=True,
                     close_fds=True)
    return True
