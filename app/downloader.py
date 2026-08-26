# -*- coding: utf-8 -*-
"""下载引擎 v2：
  - 解析 HuggingFace / ModelScope 仓库文件清单（支持任意仓库全量下载）
  - 智能多源下载：实时测速，速度持续过低时自动切换到国内镜像源（hf-mirror.com）并断点续传
  - 支持直链 / 网盘分享页（网盘仅提供打开/复制，见 store.is_netdisk）
"""
import json
import os
import re
import time
from urllib import request

from . import config

TIMEOUT = 30
CHUNK = 1024 * 256


class SpeedMonitor:
    def __init__(self, window: float = 5.0):
        self.window = window
        self.samples = []
        self.last_t = None
        self.last_done = 0

    def update(self, done: int, now: float = None):
        t = now or time.time()
        if self.last_t is not None:
            dt = t - self.last_t
            if dt > 0 and done >= self.last_done:
                self.samples.append((t, done - self.last_done))
        self.last_t = t
        self.last_done = done
        cutoff = t - self.window
        self.samples = [s for s in self.samples if s[0] >= cutoff]

    def speed(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        dt = self.samples[-1][0] - self.samples[0][0]
        if dt <= 0:
            return 0.0
        return sum(b for _, b in self.samples) / dt


def hf_bases(cfg: dict) -> list:
    bases = ["https://huggingface.co"]
    if cfg.get("auto_mirror", True):
        m = (cfg.get("hf_mirror") or "https://hf-mirror.com").strip().rstrip("/")
        if m and m not in bases:
            bases.append(m)
    return bases


def ms_bases(cfg: dict) -> list:
    return ["https://modelscope.cn"]


def _source_label(url: str) -> str:
    if "hf-mirror.com" in url:
        return "国内镜像 hf-mirror.com"
    if "huggingface.co" in url:
        return "主源 huggingface.co"
    if "modelscope.cn" in url:
        return "ModelScope"
    host = re.sub(r"^https?://", "", url).split("/")[0]
    return host


def _http_get_json(url: str, timeout: int = TIMEOUT):
    req = request.Request(url, headers={"User-Agent": "NovaForge/2.0"})
    with request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_get_json_try(urls, timeout: int = 12):
    last = None
    for u in urls:
        try:
            return _http_get_json(u, timeout)
        except Exception as e:
            last = e
    raise last or Exception("所有 API 源均不可达")


def resolve_hf(cfg: dict, repo: str, patterns=None):
    bases = hf_bases(cfg)
    api_urls = [f"{b}/api/models/{repo}" for b in bases]
    data = _http_get_json_try(api_urls)
    files = []
    for s in data.get("siblings", []):
        fn = s.get("rfilename", "")
        if not fn or fn == ".gitattributes":
            continue
        urls = [f"{b}/{repo}/resolve/main/{fn}" for b in bases]
        files.append((urls, fn))
    return _filter_patterns(files, patterns)


def resolve_modelscope(cfg: dict, repo: str, patterns=None):
    bases = ms_bases(cfg)
    api_urls = [f"{b}/api/v1/models/{repo}/repo/files?Recursive=true" for b in bases]
    data = _http_get_json_try(api_urls)
    files = []
    for f in data.get("Data", {}).get("Files", []):
        path = f.get("Path")
        if not path or path == ".gitattributes":
            continue
        urls = [f"{b}/models/{repo}/resolve/master/{path}" for b in bases]
        files.append((urls, path))
    return _filter_patterns(files, patterns)


def _glob_to_regex(pat: str) -> str:
    i, n = 0, len(pat)
    out = ""
    while i < n:
        c = pat[i]
        if c == "*":
            out += ".*"
        elif c == "?":
            out += "."
        elif c in ".^$+()[]{}|\\":
            out += "\\" + c
        else:
            out += c
        i += 1
    return out


def _filter_patterns(files, patterns):
    if not patterns:
        return files
    pats = [p for p in patterns if p]
    if not pats:
        return files
    rxs = [re.compile(_glob_to_regex(p)) for p in pats]
    return [(u, n) for u, n in files if any(rx.search(n) for rx in rxs)]


def resolve_entry(cfg: dict, entry: dict) -> list:
    src = (entry.get("source") or "direct").lower()
    if src in ("huggingface", "hf"):
        return resolve_hf(cfg, entry.get("repo", ""), entry.get("files"))
    if src in ("modelscope", "ms"):
        return resolve_modelscope(cfg, entry.get("repo", ""), entry.get("files"))
    urls = entry.get("urls") or ([entry["url"]] if entry.get("url") else [])
    return [([u], os.path.basename(u.split("?")[0])) for u in urls]


def _download_one(cfg: dict, url: str, dest_dir: str, filename: str,
                  progress=None, log=None, monitor: SpeedMonitor = None,
                  pause_event=None, cancel_event=None) -> tuple:
    """下载单个文件（带断点续传 + 慢速检测 + 暂停/取消）。
    返回 ("ok", path) / ("slow", part_path) / ("cancelled", part_path) / ("error", msg)。"""
    import requests
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, filename)
    part = dest + ".part"
    headers = {"User-Agent": "NovaForge/2.0"}
    resume = os.path.getsize(part) if os.path.exists(part) else 0
    if resume:
        headers["Range"] = f"bytes={resume}-"
    threshold = float(cfg.get("speed_threshold_kb", 200)) * 1024
    slow_seconds = float(cfg.get("slow_seconds", 8))
    try:
        with requests.get(url, headers=headers, stream=True, timeout=(10, 60)) as r:
            if r.status_code in (416,):
                resume = 0
                if os.path.exists(part):
                    os.remove(part)
                return _download_one(cfg, url, dest_dir, filename, progress, log, monitor,
                                     pause_event, cancel_event)
            if r.status_code == 200 and resume:
                resume = 0
                open(part, "wb").close()
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0)) + resume
            done = resume
            slow_since = None
            mode = "ab" if resume else "wb"
            with open(part, mode) as f:
                for chunk in r.iter_content(chunk_size=CHUNK):
                    if cancel_event and cancel_event.is_set():
                        return ("cancelled", part)
                    if pause_event and pause_event.is_set():
                        while pause_event.is_set():
                            if cancel_event and cancel_event.is_set():
                                return ("cancelled", part)
                            time.sleep(0.2)
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if monitor:
                        monitor.update(done)
                    speed = monitor.speed() if monitor else 0.0
                    if progress:
                        progress(done, total, speed, _source_label(url))
                    if threshold > 0 and done < total:
                        if speed < threshold:
                            if slow_since is None:
                                slow_since = time.time()
                            elif time.time() - slow_since >= slow_seconds:
                                if log:
                                    log(f"速度过低（{speed / 1024:.0f} KB/s），准备切换镜像源…")
                                return ("slow", part)
                        else:
                            slow_since = None
            if os.path.exists(dest):
                os.remove(dest)
            os.rename(part, dest)
            return ("ok", dest)
    except requests.HTTPError as e:
        return ("error", f"HTTP {e.response.status_code} {url.split('/')[2]}")
    except Exception as e:
        return ("error", str(e)[:200])


def smart_download(cfg: dict, url_list: list, dest_dir: str, filename: str,
                   progress=None, log=None, pause_event=None, cancel_event=None) -> tuple:
    monitor = SpeedMonitor(cfg.get("speed_monitor_window", 5.0))
    for idx, url in enumerate(url_list):
        if idx > 0:
            if log:
                log(f"↺ 自动切换下载源 → {_source_label(url)}（断点续传）")
        res, extra = _download_one(cfg, url, dest_dir, filename, progress, log, monitor,
                                   pause_event, cancel_event)
        if res == "ok":
            return (True, extra)
        if res == "slow":
            continue
        if res == "cancelled":
            return (False, "已取消")
        if log:
            log(f"✗ 源失败（{_source_label(url)}）：{extra}")
    return (False, f"所有下载源均失败：{filename}")


def download_entry(cfg: dict, entry: dict, dest_dir: str,
                   progress=None, log=None, pause_event=None, cancel_event=None) -> dict:
    result = {"ok": 0, "fail": 0, "files": [], "errors": []}
    try:
        file_list = resolve_entry(cfg, entry)
    except Exception as e:
        result["errors"].append(f"解析文件清单失败: {e}")
        result["fail"] = 1
        return result
    if not file_list:
        result["errors"].append("未找到可下载文件（可能为限权模型或清单为空）")
        result["fail"] = 1
        return result
    if log:
        log(f"共 {len(file_list)} 个文件，开始全自动下载")
    for i, (urls, fn) in enumerate(file_list, 1):
        if cancel_event and cancel_event.is_set():
            if log:
                log("已停止下载")
            break
        if log:
            log(f"[{i}/{len(file_list)}] {fn}")
        ok, extra = smart_download(cfg, urls, dest_dir, fn, progress, log,
                                   pause_event, cancel_event)
        if ok:
            result["ok"] += 1
            result["files"].append(os.path.join(dest_dir, fn))
        else:
            result["fail"] += 1
            result["errors"].append(f"{fn}: {extra}")
        if log:
            log(f"  已完成 {result['ok']} 个，失败 {result['fail']} 个")
    return result
