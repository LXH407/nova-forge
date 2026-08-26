# -*- coding: utf-8 -*-
"""清单（manifest）管理：商城内容 + 更新信息。

数据源：
  1. 内置清单（打包进程序，仓库根目录 manifest.json 为单一真源）
  2. GitHub raw 远端清单（管理员维护，用户点“同步”拉取）
  3. 本地缓存（最近一次同步结果）
合并规则：远端条目按 id 覆盖内置条目。
"""
import json
import os
import sys
import time
from urllib import request

from . import config

TIMEOUT = 30


def bundled_manifest_path() -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", "manifest.json")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(base, "manifest.json"),
                 os.path.join(base, "assets", "manifest.json")):
        if os.path.exists(cand):
            return cand
    return os.path.join(base, "manifest.json")


def load_bundled() -> dict:
    p = bundled_manifest_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": config.VERSION, "content": []}


def load_local() -> dict:
    """读取仓库根目录 manifest.json（后端管理程序直接读写此单一真源）。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "manifest.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": config.VERSION, "content": []}


def cache_path() -> str:
    return os.path.join(config.cache_dir(), "manifest_cache.json")


def load_cached() -> dict:
    p = cache_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cached(data: dict) -> None:
    try:
        with open(cache_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _http_get_json(url: str, timeout: int = TIMEOUT):
    req = request.Request(url, headers={"User-Agent": "NovaForge/2.0"})
    with request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def sync_remote(cfg: dict, quiet: bool = False) -> dict:
    """拉取远端清单并合并。失败回退已有数据。"""
    url = config.default_manifest_url(cfg)
    result = {"ok": False, "msg": "", "manifest": None}
    if not url:
        result["msg"] = "未配置 GitHub 仓库地址（请在设置中填写 owner/repo）"
        if not quiet:
            print("[manifest]", result["msg"])
        return result
    try:
        remote = _http_get_json(url)
        if not isinstance(remote, dict) or "content" not in remote:
            result["msg"] = "远端清单格式异常（缺少 content 字段）"
            return result
        save_cached(remote)
        cfg["last_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
        config.save_config(cfg)
        result["ok"] = True
        result["manifest"] = merge_manifest(load_bundled(), remote)
        result["msg"] = f"同步成功（{time.strftime('%H:%M:%S')}）"
        if not quiet:
            print("[manifest]", result["msg"])
        return result
    except Exception as e:
        result["msg"] = f"同步失败: {e}"
        if not quiet:
            print("[manifest]", result["msg"])
        return result


def merge_manifest(local: dict, remote: dict) -> dict:
    content = {}
    for it in local.get("content", []):
        if it.get("id"):
            content[it["id"]] = it
    for it in remote.get("content", []):
        if it.get("id"):
            content[it["id"]] = it
    merged = {
        "version": remote.get("version", local.get("version", config.VERSION)),
        "update": remote.get("update", local.get("update", {})),
        "shop": remote.get("shop") or local.get("shop") or {},
        "content": sorted(content.values(), key=lambda x: x.get("name", "")),
    }
    return merged


def load_merged(cfg: dict, include_cached: bool = True) -> dict:
    bundled = load_bundled()
    cached = load_cached() if include_cached else {}
    return merge_manifest(bundled, cached)


def find_content(manifest: dict, content_id: str):
    for it in manifest.get("content", []):
        if it.get("id") == content_id:
            return it
    return None
