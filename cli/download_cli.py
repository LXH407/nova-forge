# -*- coding: utf-8 -*-
"""控制台全自动下载器（GUI 通过它完成下载，也可命令行独立使用）。
实时打印速度；速度持续过低时自动切换国内镜像源并续传。

用法:
  python cli/download_cli.py --job <job.json>
  python cli/download_cli.py --repo Qwen/Qwen2.5-7B-Instruct --platform hf --dest D:/models
  python cli/download_cli.py --url https://... --dest D:/models
"""
import argparse
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, downloader, license as lic, manifest, store


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(os.path.join(config.logs_dir(), "download.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _speed(bps):
    if bps >= 1024 * 1024:
        return f"{bps / 1024 / 1024:.2f} MB/s"
    return f"{bps / 1024:.0f} KB/s"


def download_entry(cfg, entry, dest, name=""):
    title = name or entry.get("name") or entry.get("title") or "内容"
    log(f"开始下载：{title}（源：{entry.get('source', 'direct')}）")
    log(f"保存目录：{dest}")
    if not os.path.isdir(dest):
        os.makedirs(dest, exist_ok=True)
    last = {"t": 0}

    def prog(done, total, speed, src):
        now = time.time()
        if now - last["t"] > 1.5:
            pct = (done / total * 100) if total else 0
            log(f"  {pct:5.1f}%   {_speed(speed)}   源：{src}")
            last["t"] = now

    r = downloader.download_entry(cfg, entry, dest, progress=prog, log=log)
    log(f"全部结束：成功 {r['ok']}，失败 {r['fail']}；目录：{dest}")
    for e in r["errors"]:
        log(f"  失败项：{e}")
    return 0 if r["fail"] == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="NovaForge 控制台下载器")
    ap.add_argument("--job", default="")
    ap.add_argument("--repo", default="")
    ap.add_argument("--platform", default="hf", choices=["hf", "ms", "huggingface", "modelscope"])
    ap.add_argument("--files", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("--dest", default="")
    ap.add_argument("--name", default="")
    args = ap.parse_args(argv)

    cfg = config.load_config()
    entry = None
    dest = ""

    if args.job and os.path.exists(args.job):
        with open(args.job, "r", encoding="utf-8") as f:
            job = json.load(f)
        entry = job.get("entry")
        dest = job.get("dest") or ""
        if job.get("cfg"):
            cfg.update({k: v for k, v in job["cfg"].items() if v})

    if entry is None and args.repo:
        plat = "huggingface" if args.platform in ("hf", "huggingface") else "modelscope"
        files = [x.strip() for x in args.files.split(",") if x.strip()] or None
        entry = {"id": f"cli-{args.repo}", "name": args.name or args.repo.split("/")[-1],
                 "category": "model", "title": args.repo, "desc": "", "icon": "",
                 "source": plat, "repo": args.repo, "files": files}
        dest = args.dest or cfg.get("default_download_dir") or "."

    if entry is None and args.url:
        entry = {"id": "cli-url", "name": args.name or "直链", "category": "tool",
                 "title": "直链下载", "desc": "", "icon": "", "source": "direct",
                 "url": args.url}
        dest = args.dest or "."

    if entry is None:
        if args.name:
            mf = manifest.load_merged(cfg)
            it = manifest.find_content(mf, args.name)
            if it:
                entry = it
                dest = args.dest or cfg.get("default_download_dir") or "."
    if entry is None:
        log("没有可下载的任务（--job / --repo / --url / --name=内容id）")
        return 1

    # 授权检查（v2.1 积分制：会员免积分，否则按商品积分价扣减）
    price = store.content_price(entry)
    ok, msg = lic.can_download(cfg, entry.get("id"), price)
    if not ok:
        log(f"授权不足：{msg}")
        return 1
    log(f"授权：{msg}")
    lic.consume_download(cfg, price)
    config.save_config(cfg)

    return download_entry(cfg, entry, dest, entry.get("name"))


if __name__ == "__main__":
    sys.exit(main())
