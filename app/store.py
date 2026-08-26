# -*- coding: utf-8 -*-
"""内容商城（store）：对 manifest 内容做分类、校验、图标加载。

内容条目（content）必备字段（上传时必须填写，缺一项即视为“未完善”）：
  id / name(英文名) / category(model|app|game|tool) / title(中文标题)
  desc(介绍) / icon(图标URL或 @路径) / source(huggingface|modelscope|direct|netdisk)
  - huggingface/modelscope: 需 repo（可加 files 通配过滤）
  - direct: 需 url（可多个 urls）
  - netdisk: 需 url(分享链接) + provider(baidu|quark|ali|other)
"""
import os
import re

from . import config, manifest

CATEGORIES = {
    "model": {"cn": "模型中心", "en": "MODELS", "color": "#22D3EE", "glyph": "◆"},
    "app":   {"cn": "应用商店", "en": "APPS",   "color": "#8B5CF6", "glyph": "⬢"},
    "game":  {"cn": "游戏中心", "en": "GAMES",  "color": "#F97316", "glyph": "▶"},
    "tool":  {"cn": "工具集",   "en": "TOOLS",  "color": "#34D399", "glyph": "⚙"},
}

REQUIRED_FIELDS = ("id", "name", "category", "title", "desc", "icon", "source")


def category_meta(cat: str) -> dict:
    return CATEGORIES.get(cat, {"cn": cat, "en": cat.upper(), "color": "#22D3EE", "glyph": "•"})


def load_content(cfg: dict) -> list:
    return manifest.load_merged(cfg).get("content", [])


def shop(cfg: dict) -> dict:
    """商城经营配置（积分/会员/支付方式），来自远端清单。"""
    m = manifest.load_merged(cfg)
    return m.get("shop") or {}


def content_price(item: dict) -> int:
    try:
        return max(1, int(item.get("points", 1)))
    except Exception:
        return 1


def payment_image_path(cfg: dict, pid: str) -> str:
    """支付方式图片本地缓存路径（存在才返回）。"""
    p = os.path.join(config.cache_dir(), "payments", f"{pid}.png")
    return p if os.path.exists(p) else ""


def ensure_payment_image(cfg: dict, pay: dict) -> str:
    """确保支付方式收款码已缓存到本地，返回本地路径。"""
    pid = pay.get("id", "pay")
    local = payment_image_path(cfg, pid)
    if local:
        return local
    url = resolve_icon_url(cfg, pay.get("image", ""))
    if url:
        try:
            from urllib import request as ur
            req = ur.Request(url, headers={"User-Agent": "NovaForge/2.1"})
            with ur.urlopen(req, timeout=15) as r:
                data = r.read()
            if data and len(data) > 100:
                d = os.path.dirname(local)
                os.makedirs(d, exist_ok=True)
                with open(local, "wb") as f:
                    f.write(data)
                return local
        except Exception:
            pass
    return ""


def by_category(cfg: dict, cat: str) -> list:
    return [c for c in load_content(cfg) if c.get("category") == cat]


def get_content(cfg: dict, content_id: str):
    for c in load_content(cfg):
        if c.get("id") == content_id:
            return c
    return None


def is_complete(item: dict) -> tuple:
    """返回 (是否完整, 缺失字段列表)。上传必须满足：必填字段齐全 + 源信息完整。"""
    missing = [f for f in REQUIRED_FIELDS if not item.get(f)]
    if item.get("category") not in CATEGORIES:
        missing.append("category(合法值)")
    src = (item.get("source") or "").lower()
    if src in ("huggingface", "hf", "modelscope", "ms"):
        if not item.get("repo"):
            missing.append("repo")
    elif src == "direct":
        if not item.get("url") and not item.get("urls"):
            missing.append("url")
    elif src == "netdisk":
        if not item.get("url"):
            missing.append("url")
        if not item.get("provider"):
            missing.append("provider")
    else:
        missing.append("source")
    return (not missing, missing)


def resolve_icon_url(cfg: dict, icon: str) -> str:
    """把 @仓库内路径 解析为 GitHub raw 直链；绝对 URL 原样返回。"""
    if not icon:
        return ""
    icon = icon.strip()
    if icon.startswith("@"):
        rel = icon[1:].lstrip("/")
        owner = cfg.get("github_owner", "").strip()
        repo = cfg.get("github_repo", "").strip()
        if owner and repo and owner != "YOUR_GITHUB_USERNAME":
            return f"https://raw.githubusercontent.com/{owner}/{repo}/main/{rel}"
        return ""
    if icon.startswith(("http://", "https://")):
        return icon
    return ""


def icon_local_path(cfg: dict, content_id: str) -> str:
    """图标本地缓存路径（存在才返回）。"""
    p = os.path.join(config.icons_dir(), f"{content_id}.png")
    return p if os.path.exists(p) else ""


def ensure_icon(cfg: dict, item: dict) -> str:
    """确保内容图标已缓存到本地，返回本地路径（无则生成占位图）。"""
    cid = item.get("id", "unknown")
    local = icon_local_path(cfg, cid)
    if local:
        return local
    url = resolve_icon_url(cfg, item.get("icon", ""))
    if url:
        try:
            from urllib import request as ur
            req = ur.Request(url, headers={"User-Agent": "NovaForge/2.0"})
            with ur.urlopen(req, timeout=15) as r:
                data = r.read()
            if data and len(data) > 100:
                with open(local, "wb") as f:
                    f.write(data)
                return local
        except Exception:
            pass
    return _make_placeholder(item, local)


def _make_placeholder(item: dict, local: str) -> str:
    try:
        from PIL import Image, ImageDraw, ImageFont
        color = category_meta(item.get("category", "")).get("color", "#22D3EE")
        letter = (item.get("name") or item.get("title") or "?").strip()[0].upper()
        im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([4, 4, 251, 251], radius=56, fill=(16, 24, 38, 255),
                            outline=_hex(color), width=6)
        d.ellipse([68, 68, 188, 188], outline=_hex(color), width=4)
        try:
            f = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 96)
        except Exception:
            f = ImageFont.load_default()
        d.text((128, 126), letter, anchor="mm", font=f, fill=_hex(color))
        im.save(local)
    except Exception:
        pass
    return local if os.path.exists(local) else ""


def _hex(c: str):
    try:
        return tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    except Exception:
        return (34, 211, 238, 255)


def provider_label(provider: str) -> str:
    return {"baidu": "百度网盘", "quark": "夸克网盘", "ali": "阿里云盘",
            "other": "其他网盘"}.get(provider, provider or "网盘")


def size_label(size_gb) -> str:
    if not size_gb:
        return "—"
    return f"约 {size_gb:g} GB"


def is_netdisk(item: dict) -> bool:
    return (item.get("source") or "").lower() == "netdisk"
