# -*- coding: utf-8 -*-
"""离线卡密系统 v3（积分制 + 永久会员 · 无服务器）。

卡密 = MG.<base64url(payload)>.<base64url(RSA-PKCS1v15-SHA256 签名)>
  payload = {
    "uid":  卡号,
    "plan": 方案名,
    "exp":  有效期 YYYY-MM-DD 或 "0"(永久)（会员卡绑定后按永久会员处理）
    "bind": "*"(不限机) 或 <机器ID>(绑定机)
    "type": "vip" 或 "normal"
    "pts":  积分数量（normal/积分卡生效，默认 1）
  }

会员（vip/会员卡）：
  - 激活后自动绑定当前电脑机器码，实现永久会员（下载全部内容免积分）
积分（normal/积分卡）：
  - 每张积分卡兑换 1 点积分（可后端配置），1 积分 = 下载 1 个商品
未激活 / 无积分 -> 提示前往「钱包」充值
"""
import base64
import json
import os
import sys
import time
from datetime import date

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from . import machine

# 由 tools/gen_keypair.py 生成。更换密钥对后把新公钥粘贴到这里再重新打包。
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqE2YU9iQ3uLps9a2tQVM
Crk2wTp8FJRAnhC5wxrj/L7LuJCxgKkOr2HTACHgf8Hz/PMLsnmArB0CsCa7y5kG
jKXLj+/x7YePkaJZM24+PDOGtoKCmXxqXfgJWmUuu6P5crjFnP1Jmf0NC4Mp2bta
cAMQclD7Pqjo3OQnWI0MTvNZyKVTq5QjTl5Hc6pM5QyVzXY3lrFIGvwz5Ed42RRa
y2IwpDqWRlhAi+jagUeMkfOD/V/yRJfugEyVyxkS5avsVJn6+hAfKgTQINQoNukt
m9vsxXmpfkpx5WeP36bCM9l+QMXXoHamTtDRM0VlH8YDCzOSFkEPOF8gE9bZswXG
KwIDAQAB
-----END PUBLIC KEY-----"""

_PUB_CACHE = None

PERMANENT = "9999-12-31"


def _get_pub():
    global _PUB_CACHE
    if _PUB_CACHE is None:
        _PUB_CACHE = load_pem_public_key(PUBLIC_KEY.encode("utf-8"))
    return _PUB_CACHE


def b64url_decode(s: str) -> bytes:
    s = s.strip().replace("-", "+").replace("_", "/")
    pad = "=" * (-len(s) % 4)
    return base64.b64decode(s + pad)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_key(priv_key, uid: str, plan: str, exp: str, bind: str,
             typ: str = "vip", pts: int = 1) -> str:
    """用私钥签发一张卡密（管理员端 / 后端管理程序）。
    payload = {uid, plan, exp, bind, type(vip|normal), pts}"""
    payload = json.dumps(
        {"uid": uid, "plan": plan, "exp": exp, "bind": bind,
         "type": typ, "pts": int(pts)},
        ensure_ascii=False, separators=(",", ":"),
    )
    p_b64 = b64url_encode(payload.encode("utf-8"))
    sig = priv_key.sign(p_b64.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"MG.{p_b64}.{b64url_encode(sig)}"


def banlist_path() -> str:
    from . import config
    return os.path.join(config.cache_dir(), "banlist.json")


def bundled_banlist() -> dict:
    try:
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        for cand in (os.path.join(base, "assets", "banlist.json"),
                     os.path.join(base, "banlist.json")):
            if os.path.exists(cand):
                with open(cand, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass
    return {"banned": []}


def load_banlist() -> dict:
    banned = set(bundled_banlist().get("banned", []))
    p = banlist_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                banned.update(json.load(f).get("banned", []))
        except Exception:
            pass
    return {"banned": sorted(banned), "count": len(banned)}


def sync_banlist(cfg: dict) -> dict:
    from urllib import request
    owner = (cfg.get("github_owner") or "").strip()
    repo = (cfg.get("github_repo") or "").strip()
    if not (owner and repo and owner != "YOUR_GITHUB_USERNAME"):
        return {"ok": False, "msg": "未配置远端仓库，无法同步封禁名单"}
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/banlist.json"
    try:
        req = request.Request(url, headers={"User-Agent": "NovaForge/2.1"})
        with request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        p = banlist_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        n = len(data.get("banned", []))
        cfg["last_ban_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return {"ok": True, "msg": f"封禁名单已同步（{n} 条）", "count": n}
    except Exception as e:
        return {"ok": False, "msg": f"同步失败：{e}"}


def is_banned(uid: str) -> bool:
    try:
        return uid in load_banlist().get("banned", [])
    except Exception:
        return False


class LicenseError(Exception):
    pass


def verify_key(key: str) -> dict:
    key = (key or "").strip()
    parts = key.split(".")
    if len(parts) != 3 or parts[0] != "MG":
        raise LicenseError("卡密格式不正确")
    p_b64, s_b64 = parts[1], parts[2]
    try:
        sig = b64url_decode(s_b64)
        _get_pub().verify(sig, p_b64.encode("ascii"),
                          padding.PKCS1v15(), hashes.SHA256())
    except Exception:
        raise LicenseError("卡密校验失败（签名不匹配）")
    try:
        payload = json.loads(b64url_decode(p_b64).decode("utf-8"))
    except Exception:
        raise LicenseError("卡密内容解析失败")
    for k in ("uid", "plan", "exp", "bind"):
        if k not in payload:
            raise LicenseError("卡密字段缺失")
    payload.setdefault("type", "vip")
    payload.setdefault("pts", 1)
    return payload


def check_expired(payload: dict) -> bool:
    exp = str(payload.get("exp", "0"))
    if exp in ("0", "", "*"):
        return False
    try:
        return date.fromisoformat(exp) < date.today()
    except Exception:
        return False


def check_bind(payload: dict) -> tuple:
    mid = machine.get_machine_id()
    bind = payload.get("bind", "*")
    if bind == "*":
        return True, mid
    return str(bind).upper() == mid, mid


def points(cfg: dict) -> int:
    try:
        return int(cfg.get("points", 0))
    except Exception:
        return 0


def add_points(cfg: dict, n: int, note: str = "") -> int:
    cfg["points"] = points(cfg) + int(n)
    return cfg["points"]


def spend_points(cfg: dict, n: int, note: str = "") -> bool:
    if points(cfg) < n:
        return False
    cfg["points"] = points(cfg) - int(n)
    return True


def member_machine(cfg: dict) -> str:
    return str(cfg.get("member_machine", "") or "").upper()


def is_member(cfg: dict) -> bool:
    act = cfg.get("activated")
    if not act or act.get("type", "vip") != "vip":
        return False
    if is_banned(act.get("uid", "")):
        return False
    mm = member_machine(cfg)
    if mm and mm != machine.get_machine_id():
        return False
    exp = str(cfg.get("member_expire", ""))
    if exp and exp != "0":
        try:
            if date.fromisoformat(exp) < date.today():
                return False
        except Exception:
            pass
    return True


def member_expire_label(cfg: dict) -> str:
    exp = str(cfg.get("member_expire", ""))
    if exp in ("", "0"):
        return "永久" if cfg.get("activated") else "-"
    if exp == PERMANENT:
        return "永久"
    return exp


def card_description(info: dict) -> str:
    t = info.get("type", "vip")
    if t == "vip":
        return "会员卡 · 永久会员（已绑定本机）"
    return f"积分卡 · 兑换 {int(info.get('pts', 1))} 点积分"


def _mark_redeemed(cfg: dict, uid: str):
    redeemed = list(cfg.get("redeemed") or [])
    if uid not in redeemed:
        redeemed.append(uid)
    cfg["redeemed"] = redeemed


def activate(cfg: dict, key: str) -> dict:
    payload = verify_key(key)
    uid = payload["uid"]
    if is_banned(uid):
        raise LicenseError("该卡密已被封禁，请联系管理员解封")
    if check_expired(payload):
        raise LicenseError("卡密已过期")
    ok, mid = check_bind(payload)
    if not ok:
        raise LicenseError("卡密已绑定其他机器，本机无法使用")
    redeemed = list(cfg.get("redeemed") or [])
    if uid in redeemed:
        raise LicenseError("该卡密已在本机使用过，不能重复兑换")

    typ = payload.get("type", "vip")
    info = {
        "key": key,
        "uid": uid,
        "plan": payload["plan"],
        "exp": payload["exp"],
        "bind": payload["bind"],
        "type": typ,
        "pts": int(payload.get("pts", 1)),
        "machine": mid,
        "activated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if typ == "vip":
        cfg["activated"] = info
        cfg["member_expire"] = PERMANENT
        cfg["member_machine"] = machine.get_machine_id()
        cfg["member_since"] = time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        cfg["points"] = points(cfg) + int(payload.get("pts", 1))
        cfg["activated"] = cfg.get("activated") or info
    _mark_redeemed(cfg, uid)
    return info


def license_status(cfg: dict) -> dict:
    act = cfg.get("activated")
    if act:
        if is_banned(act.get("uid", "")):
            return {"activated": False, "reason": "卡密已被封禁", "info": act}
        if act.get("type", "vip") == "vip":
            if member_machine(cfg) and member_machine(cfg) != machine.get_machine_id():
                return {"activated": False, "reason": "会员已绑定其他机器", "info": act}
            return {"activated": True, "info": act, "machine": machine.get_machine_id(),
                    "member": True, "points": points(cfg)}
        return {"activated": True, "info": act, "machine": machine.get_machine_id(),
                "member": False, "points": points(cfg)}
    return {
        "activated": False,
        "reason": "未激活",
        "machine": machine.get_machine_id(),
        "points": points(cfg),
        "member": False,
    }


def can_download(cfg: dict, content_id: str = None, price: int = 1) -> tuple:
    """返回 (是否允许, 说明)。price 为商品积分价格。"""
    if is_member(cfg):
        return True, "会员 · 全部内容免费下载"
    if points(cfg) >= int(price):
        return True, f"将消耗 {int(price)} 点积分"
    return False, (f"积分不足（当前 {points(cfg)}，需要 {int(price)}）。"
                   "请前往「钱包」兑换积分或输入会员卡升级为永久会员。")


def consume_download(cfg: dict, price: int = 1) -> None:
    """下载时扣减积分（会员免扣）。"""
    if not is_member(cfg):
        spend_points(cfg, int(price), "下载商品")


if __name__ == "__main__":
    from . import config
    c = config.load_config()
    print("机器ID:", machine.get_machine_id())
    print(license_status(c))
    print("积分:", points(c), "会员:", is_member(c))
