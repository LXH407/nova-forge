# -*- coding: utf-8 -*-
"""NovaForge 主界面（tkinter，白色系 · 微软商店式布局）。
布局：顶部栏 + 左侧分类导航（首页/模型/应用/游戏/工具）+ 内容卡片网格。
页面：首页 / 分类商城 / 内容详情 / 卡密 / 设置 / 更新
"""
import os
import queue
import sys
import threading
import time
import traceback

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import config, license as lic, manifest, machine, netdisk, store, updater, downloader
from .config import APP_DISPLAY, APP_TAGLINE, VERSION


def machine_id() -> str:
    return machine.get_machine_id()

# ---------- 主题（白色系，微软商店风） ----------
BG = "#F5F6FA"            # 页面背景
PANEL = "#FFFFFF"         # 卡片 / 面板
PANEL2 = "#F1F3F7"        # 输入框 / 次级底色
BORDER = "#E5E8EF"
ACCENT = "#0EA5E9"        # 主色（清爽蓝）
ACCENT2 = "#7C3AED"       # 副色（紫）
TEXT = "#0F172A"
SUB = "#64748B"
OK = "#16A34A"
WARN = "#D97706"
RED = "#DC2626"

F = "Microsoft YaHei UI"
F_EN = "Segoe UI"

NAV_ITEMS = [
    ("home", "⌂", "首页"),
    ("model", "◆", "模型中心"),
    ("app", "⬢", "应用商店"),
    ("game", "▶", "游戏中心"),
    ("tool", "⚙", "工具集"),
    ("wallet", "₿", "钱包"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_DISPLAY}  {APP_TAGLINE}  ·  v{VERSION}")
        self.geometry("1120x720")
        self.minsize(960, 620)
        self.configure(bg=BG)

        self.cfg = config.load_config()
        self.q = queue.Queue()
        self._images = {}
        self._back_stack = []
        self._download_run = False
        self._dl_ctx = None
        self._cur_nav = "home"

        self._build_style()
        self._build_header()
        self._build_sidebar()
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)
        self._status = tk.Label(self, text=f"v{VERSION} · 本地运行 · 全自动下载",
                                bg=PANEL, fg=SUB, anchor="w", font=(F, 9), padx=14)
        self._status.pack(fill="x", side="bottom")

        self.after(300, self._refresh_badge)
        self.after(500, self._poll)
        self.show_home()

    def report_callback_exception(self, exc, val, tb):
        """窗口版无控制台：把 UI 回调异常写入日志，避免静默退出。"""
        try:
            p = os.path.join(config.logs_dir(), "ui.log")
            with open(p, "a", encoding="utf-8") as f:
                f.write("\n[%s] UI 回调异常\n%s\n" % (
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    "".join(traceback.format_exception(exc, val, tb))))
        except Exception:
            pass
        try:
            super().report_callback_exception(exc, val, tb)
        except Exception:
            pass

    # ---------------- 基础 ----------------
    def _build_style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
            s.configure("Vertical.TScrollbar", background=BORDER, troughcolor=BG,
                        arrowcolor=SUB, bordercolor=BG)
        except Exception:
            pass

    def _poll(self):
        try:
            while True:
                fn = self.q.get_nowait()
                try:
                    fn()
                except Exception as e:
                    print("[ui]", e)
        except queue.Empty:
            pass
        self.after(200, self._poll)

    def _run_async(self, fn, on_done=None, on_err=None):
        def w():
            try:
                r = fn()
                if on_done:
                    self.q.put(lambda: on_done(r))
            except Exception as e:
                if on_err:
                    self.q.put(lambda: on_err(e))
                else:
                    print("[async]", e)
        threading.Thread(target=w, daemon=True).start()

    def _refresh_badge(self):
        pts = lic.points(self.cfg)
        if lic.is_member(self.cfg):
            self._lic_badge.configure(text=f"● 永久会员 · 积分 {pts}", fg=OK)
        elif self.cfg.get("activated"):
            self._lic_badge.configure(text=f"● 积分卡已兑换 · 积分 {pts}", fg=ACCENT2)
        else:
            self._lic_badge.configure(text=f"● 未激活 · 积分 {pts}", fg=WARN)

    def clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _back(self):
        if self._back_stack:
            self._back_stack.pop()()
        else:
            self.show_home()

    def _pill(self, parent, text, cmd, color=ACCENT, bg=PANEL2, padx=14, pady=6):
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=color,
                      activebackground=BORDER, activeforeground=color, relief="flat",
                      bd=0, padx=padx, pady=pady, cursor="hand2", font=(F, 10))
        return b

    # ---------------- 顶部栏 ----------------
    def _build_header(self):
        h = tk.Frame(self, bg=PANEL, height=64)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Frame(self, bg="#DCE4F0", height=1).pack(fill="x")

        self._logo_img = self._load_img("assets/logo_main.png", 40)
        if self._logo_img:
            tk.Label(h, image=self._logo_img, bg=PANEL).pack(side="left", padx=(16, 10))
        brand = tk.Frame(h, bg=PANEL)
        brand.pack(side="left")
        tk.Label(brand, text=APP_DISPLAY, bg=PANEL, fg=TEXT, font=(F_EN, 15, "bold")).pack(anchor="w")
        tk.Label(brand, text=APP_TAGLINE, bg=PANEL, fg=ACCENT, font=(F_EN, 8)).pack(anchor="w")

        right = tk.Frame(h, bg=PANEL)
        right.pack(side="right", padx=12)
        self._lic_badge = tk.Label(h, text="● 未激活", bg=PANEL, fg=WARN, font=(F, 10, "bold"))
        self._lic_badge.pack(side="right", padx=16)
        for t, c, col in (("🔑 卡密", self.show_license, ACCENT2), ("⚙ 设置", self.show_settings, SUB),
                          ("🔄 更新", self.show_update, ACCENT)):
            self._pill(right, t, c, col).pack(side="left", padx=3)

    def _load_img(self, path, size):
        try:
            from PIL import Image, ImageTk
            p = path
            if not os.path.isabs(p):
                root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                p = os.path.join(root, p)
            if not os.path.exists(p):
                return None
            im = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
            ph = ImageTk.PhotoImage(im)
            self._images[id(ph)] = ph
            return ph
        except Exception:
            return None

    # ---------------- 左侧导航 ----------------
    def _build_sidebar(self):
        sb = tk.Frame(self, bg=PANEL, width=196)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        tk.Frame(sb, bg=BORDER, width=1).pack(side="right", fill="y")
        self._nav_btns = {}
        for key, glyph, cn in NAV_ITEMS:
            b = tk.Button(sb, text=f"  {glyph}  {cn}", command=lambda k=key: self._nav(k),
                          bg=PANEL, fg=SUB, activebackground=PANEL2, activeforeground=TEXT,
                          relief="flat", bd=0, anchor="w", padx=18, pady=11,
                          font=(F, 11), cursor="hand2")
            b.pack(fill="x", padx=10, pady=2)
            self._nav_btns[key] = b

    def _nav(self, key):
        self._cur_nav = key
        for k, b in self._nav_btns.items():
            if k == key:
                b.configure(bg=PANEL2, fg=ACCENT, font=(F, 11, "bold"))
            else:
                b.configure(bg=PANEL, fg=SUB, font=(F, 11))
        if key == "home":
            self.show_home()
        elif key == "wallet":
            self.show_wallet()
        else:
            self.show_store(key)

    # ================= 首页（微软商店式） =================
    def show_home(self):
        self.clear_content()
        self._back_stack = []
        self._cur_nav = "home"
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        hero = tk.Frame(p, bg="#E8F4FE", padx=24, pady=18)
        hero.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hero, text="欢迎使用 NovaForge", bg="#E8F4FE", fg=TEXT,
                 font=(F, 18, "bold")).pack(anchor="w")
        tk.Label(hero, text="把模型、应用、游戏、工具统统装进你的设备 · 全自动下载，速度过慢自动切换国内镜像源",
                 bg="#E8F4FE", fg=SUB, font=(F, 10)).pack(anchor="w", pady=(2, 8))
        self._pill(hero, "🚀 同步商城清单", self._do_sync, ACCENT, "#FFFFFF").pack(anchor="w")

        grid = tk.Frame(p, bg=BG)
        grid.pack(fill="x", padx=20, pady=8)
        cats = [n for n in NAV_ITEMS[1:] if n[0] != "wallet"]
        for i, (key, glyph, cn) in enumerate(cats, start=1):
            meta = store.category_meta(key)
            count = len(store.by_category(self.cfg, key))
            tile = tk.Frame(grid, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                            padx=12, pady=12, cursor="hand2")
            tile.grid(row=0, column=i, padx=6, sticky="nsew")
            tile.bind("<Button-1>", lambda e, k=key: self.show_store(k))
            tk.Label(tile, text=glyph, bg=PANEL, fg=meta["color"], font=(F, 16, "bold")).pack(anchor="w")
            tk.Label(tile, text=cn, bg=PANEL, fg=TEXT, font=(F, 11, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(tile, text=f"{count} 个内容", bg=PANEL, fg=SUB, font=(F, 9)).pack(anchor="w")
        for c in range(1, 5):
            grid.grid_columnconfigure(c, weight=1, uniform="tile")

        tk.Label(p, text="全部内容", bg=BG, fg=TEXT, font=(F, 13, "bold")).pack(anchor="w", padx=20, pady=(10, 2))
        items = store.load_content(self.cfg)
        if items:
            self._card_scroll(p, items)
        else:
            tk.Label(p, text="暂无内容，请点击「同步商城清单」刷新，或联系管理员。",
                     bg=BG, fg=SUB, font=(F, 11)).pack(pady=30)

        self._refresh_badge()

    def _mark_nav(self, key):
        for k, b in self._nav_btns.items():
            if k == key:
                b.configure(bg=PANEL2, fg=ACCENT, font=(F, 11, "bold"))
            else:
                b.configure(bg=PANEL, fg=SUB, font=(F, 11))

    def _do_sync(self):
        self._status.config(text="正在同步商城清单…")
        self._run_async(lambda: manifest.sync_remote(self.cfg),
                        lambda r: (self._status.config(text=f"同步：{r['msg']}"),
                                   self._toast(r["msg"]),
                                   self._sync_banlist(quiet=True)))

    def _sync_banlist(self, quiet=False):
        if not quiet:
            self._status.config(text="正在同步封禁名单…")
        self._run_async(lambda: lic.sync_banlist(self.cfg),
                        lambda r: (config.save_config(self.cfg),
                                   self._status.config(text=f"封禁名单：{r['msg']}"),
                                   self._refresh_lic_page()))

    def _toast(self, msg):
        try:
            self._status.config(text=msg)
        except Exception:
            pass

    # ================= 分类商城 =================
    def show_store(self, cat):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._cur_nav = cat
        self._mark_nav(cat)
        meta = store.category_meta(cat)
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        top = tk.Frame(p, bg=BG)
        top.pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(top, text=f"{meta['glyph']}  {meta['cn']}", bg=BG,
                 fg=TEXT, font=(F, 16, "bold")).pack(side="left")
        tk.Label(top, text=f" · {meta['en']}", bg=BG, fg=SUB, font=(F_EN, 11)).pack(side="left")
        self._pill(top, "🔄 同步", self._do_sync, ACCENT).pack(side="right")

        items = store.by_category(self.cfg, cat)
        if not items:
            tk.Label(p, text="该分类暂时没有内容，可在后端管理台添加。",
                     bg=BG, fg=SUB, font=(F, 11)).pack(pady=40)
            return
        self._card_scroll(p, items)

    def _card_scroll(self, parent, items):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(wid, width=e.width))

        cols = 4
        for i, item in enumerate(items):
            row, col = divmod(i, cols)
            self._make_card(inner, item).grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        for c in range(cols):
            inner.grid_columnconfigure(c, weight=1, uniform="card")

    def _make_card(self, parent, item):
        cid = item.get("id", "")
        card = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                        padx=14, pady=14, cursor="hand2")
        card.bind("<Button-1>", lambda e: self.show_detail(cid))
        card.bind("<Enter>", lambda e: card.configure(highlightbackground=ACCENT))
        card.bind("<Leave>", lambda e: card.configure(highlightbackground=BORDER))

        meta = store.category_meta(item.get("category", ""))
        icon = self._icon_for(item, 88)
        if icon:
            lab = tk.Label(card, image=icon, bg=PANEL)
            lab.image = icon
            lab.pack()
            lab.bind("<Button-1>", lambda e: self.show_detail(cid))
        tk.Label(card, text=item.get("name", "?"), bg=PANEL, fg=TEXT,
                 font=(F_EN, 12, "bold")).pack(anchor="w", pady=(8, 0))
        tk.Label(card, text=item.get("title", ""), bg=PANEL, fg=SUB,
                 font=(F, 9), wraplength=180, justify="left").pack(anchor="w")
        tags = item.get("tags") or []
        if tags:
            tk.Label(card, text="  ".join(tags[:3]), bg=PANEL, fg=meta["color"],
                     font=(F, 8)).pack(anchor="w", pady=(2, 0))
        info = tk.Frame(card, bg=PANEL)
        info.pack(fill="x", pady=(6, 0))
        src = {"huggingface": "HF", "modelscope": "MS", "direct": "直链",
               "netdisk": store.provider_label(item.get("provider"))}.get(
            (item.get("source") or "direct").lower(), "直链")
        tk.Label(info, text=src, bg=PANEL, fg=ACCENT2, font=(F, 8, "bold")).pack(side="left")
        tk.Label(info, text="   " + store.size_label(item.get("size_gb")), bg=PANEL,
                 fg=SUB, font=(F, 8)).pack(side="left")

        if not store.is_complete(item)[0]:
            missing = store.is_complete(item)[1]
            tk.Label(card, text="⚠ 信息未完善（缺少: " + "、".join(missing[:3]) + "）",
                     bg=PANEL, fg=RED, font=(F, 8)).pack(anchor="w", pady=(4, 0))
        action = tk.Button(card, text="🚀 下载" if store.is_netdisk(item) is False else "🌐 打开",
                           bg=meta["color"], fg="#FFFFFF", activebackground=ACCENT,
                           activeforeground="#FFFFFF", relief="flat", cursor="hand2",
                           font=(F, 9, "bold"), command=lambda: self.show_detail(cid))
        action.pack(fill="x", pady=(10, 0))
        return card

    def _icon_for(self, item, size):
        cid = item.get("id", "unknown")
        key = f"{cid}_{size}"
        if key in self._images:
            return self._images[key]
        path = store.ensure_icon(self.cfg, item)
        ph = None
        if path:
            ph = self._load_img(path, size)
        if not ph:
            ph = self._load_img("assets/icon.png", size)
        if ph:
            self._images[key] = ph
        return ph

    # ================= 内容详情 =================
    def show_detail(self, cid):
        item = store.get_content(self.cfg, cid)
        if not item:
            return
        self.clear_content()
        self._back_stack.append(lambda: self.show_store(item.get("category", "model")))
        self._mark_nav(item.get("category", "home"))
        meta = store.category_meta(item.get("category", ""))
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        top = tk.Frame(p, bg=BG)
        top.pack(fill="x", padx=20, pady=(14, 8))
        self._pill(top, "‹ 返回", self._back, TEXT).pack(side="left")

        body = tk.Frame(p, bg=BG)
        body.pack(fill="both", expand=True, padx=20)
        lf = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                      padx=20, pady=20, width=250)
        lf.pack(side="left", fill="y", padx=(0, 16))
        lf.pack_propagate(False)
        icon = self._icon_for(item, 130)
        if icon:
            lab = tk.Label(lf, image=icon, bg=PANEL)
            lab.image = icon
            lab.pack()
        tk.Label(lf, text=item.get("name", ""), bg=PANEL, fg=TEXT,
                 font=(F_EN, 12, "bold"), wraplength=200).pack(pady=(10, 2))
        tk.Label(lf, text=item.get("title", ""), bg=PANEL, fg=SUB, font=(F, 10),
                 wraplength=200).pack()

        self._dl_status = tk.Label(lf, text="", bg=PANEL, fg=ACCENT, font=(F, 9),
                                   wraplength=200, justify="left")
        self._dl_status.pack(pady=(8, 4))

        is_nd = store.is_netdisk(item)
        if is_nd:
            tk.Label(lf, text=f"来源：{store.provider_label(item.get('provider'))}",
                     bg=PANEL, fg=ACCENT2, font=(F, 9)).pack()
            self._pill(lf, "🌐 打开链接", lambda: self._open_nd(item), ACCENT, "#E0F2FE").pack(fill="x", pady=(10, 4))
            self._pill(lf, "📋 复制链接", lambda: self._copy_nd(item), SUB).pack(fill="x")
        else:
            self._pill(lf, "🚀 开始全自动下载", self._start_dl_click, "#FFFFFF", ACCENT).pack(fill="x", pady=(10, 4))

        rf = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=20)
        rf.pack(side="left", fill="both", expand=True)
        tk.Label(rf, text=f"{meta['glyph']} {item.get('title', '')}", bg=PANEL, fg=TEXT,
                 font=(F, 15, "bold")).pack(anchor="w")
        row = tk.Frame(rf, bg=PANEL)
        row.pack(anchor="w", pady=4)
        price = store.content_price(item)
        price_txt = "会员免费" if lic.is_member(self.cfg) else f"{price} 积分"
        for k, v in (("类别", meta["cn"]), ("体积", store.size_label(item.get("size_gb"))),
                     ("版本", item.get("version", "-")), ("价格", price_txt)):
            tk.Label(row, text=f"{k}：{v}   ", bg=PANEL, fg=SUB, font=(F, 9)).pack(side="left")
        if item.get("tags"):
            tk.Label(rf, text="标签：" + "  ".join(item.get("tags") or []), bg=PANEL,
                     fg=meta["color"], font=(F, 9)).pack(anchor="w", pady=(0, 8))
        tk.Label(rf, text="介绍", bg=PANEL, fg=ACCENT, font=(F, 10, "bold")).pack(anchor="w")
        desc = tk.Text(rf, bg="#FBFCFE", fg=TEXT, wrap="word", relief="flat", height=8,
                       font=(F, 10), padx=8, pady=8, highlightbackground=BORDER, highlightthickness=1)
        desc.insert("1.0", item.get("desc", ""))
        desc.configure(state="disabled")
        desc.pack(fill="both", expand=True, pady=(4, 8))
        repo = item.get("repo") or item.get("url") or ""
        tk.Label(rf, text=f"来源地址：{repo}", bg=PANEL, fg=SUB, font=(F, 8),
                 wraplength=560, justify="left").pack(anchor="w")

        tk.Label(rf, text="下载日志", bg=PANEL, fg=ACCENT, font=(F, 10, "bold")).pack(anchor="w", pady=(8, 2))
        self._dl_log = tk.Text(rf, bg="#FBFCFE", fg=SUB, height=6, relief="flat",
                               font=("Consolas", 9), padx=8, pady=8, state="disabled",
                               highlightbackground=BORDER, highlightthickness=1)
        self._dl_log.pack(fill="both", expand=True)
        self._dl_ctx = {"item": item, "cid": cid}

    def _append_log(self, text):
        try:
            self._dl_log.configure(state="normal")
            self._dl_log.insert("end", text + "\n")
            self._dl_log.see("end")
            self._dl_log.configure(state="disabled")
        except Exception:
            pass

    def _open_nd(self, item):
        price = store.content_price(item)
        ok, msg = self._gate(item.get("id", ""), price)
        if not ok:
            return
        lic.consume_download(self.cfg, price)
        config.save_config(self.cfg)
        self._refresh_badge()
        netdisk.open_link(item.get("url", ""))

    def _copy_nd(self, item):
        netdisk.copy_link(item.get("url", ""))

    def _gate(self, cid, price=1):
        ok, msg = lic.can_download(self.cfg, cid, price)
        if not ok:
            messagebox.showwarning("积分不足", msg + "\n\n请到「钱包」兑换积分或输入会员卡开通永久会员。")
            self.show_wallet()
            return False, msg
        return True, msg

    def _start_dl_click(self):
        if self._download_run:
            return
        item = self._dl_ctx["item"]
        cid = self._dl_ctx["cid"]
        price = store.content_price(item)
        ok, msg = self._gate(cid, price)
        if not ok:
            return
        dest = self.cfg.get("default_download_dir") or ""
        if not dest or not os.path.isdir(dest):
            dest = filedialog.askdirectory(initialdir=dest or os.path.expanduser("~"),
                                           title="选择保存目录")
            if not dest:
                return
            self.cfg["default_download_dir"] = dest
            config.save_config(self.cfg)
        lic.consume_download(self.cfg, price)
        config.save_config(self.cfg)
        self._refresh_badge()
        self._download_run = True
        self._dl_status.config(text="准备解析文件清单…")
        self._append_log(f"授权：{msg}")

        def prog(done, total, speed, src):
            self.q.put(lambda: self._show_progress(done, total, speed, src))

        self._run_async(lambda: downloader.download_entry(self.cfg, item, dest,
                                                          progress=prog, log=self._append_log),
                        self._dl_done)

    def _show_progress(self, done, total, speed, src):
        try:
            pct = (done / total * 100) if total else 0
            speed_s = self._fmt_speed(speed)
            self._dl_status.config(text=f"下载中 {pct:.1f}%  ·  {speed_s}\n源：{src}")
        except Exception:
            pass

    @staticmethod
    def _fmt_speed(bps):
        if bps >= 1024 * 1024:
            return f"{bps / 1024 / 1024:.2f} MB/s"
        if bps >= 1024:
            return f"{bps / 1024:.0f} KB/s"
        return f"{bps:.0f} B/s"

    def _dl_done(self, r):
        self._download_run = False
        self._append_log(f"下载结束：成功 {r['ok']}，失败 {r['fail']}")
        if r["errors"]:
            self._append_log("失败：" + "；".join(r["errors"][:3]))
        self._dl_status.config(text=f"完成：成功 {r['ok']} / 失败 {r['fail']}",
                               fg=OK if r["fail"] == 0 else RED)

    # ================= 卡密 =================
    def show_license(self):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        tk.Label(p, text="🔑  卡密中心", bg=BG, fg=TEXT, font=(F, 17, "bold")).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(p, text="会员卡 → 输入后自动绑定本机，开通永久会员（下载全部内容免积分）；积分卡 → 兑换积分（1 积分下载 1 个商品）。离线验签，无需联网授权。",
                 bg=BG, fg=SUB, font=(F, 10), wraplength=760, justify="left").pack(anchor="w", padx=24)

        box = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=18)
        box.pack(fill="x", padx=24, pady=16)
        tk.Label(box, text="卡密", bg=PANEL, fg=TEXT, font=(F, 11, "bold")).pack(anchor="w")
        self._key_var = tk.StringVar()
        tk.Entry(box, textvariable=self._key_var, font=("Consolas", 12), bg=PANEL2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", highlightbackground=BORDER,
                 highlightthickness=1).pack(fill="x", pady=(6, 10))
        btns = tk.Frame(box, bg=PANEL)
        btns.pack(fill="x")
        self._pill(btns, "🔓 激活", self._activate, "#FFFFFF", ACCENT).pack(side="left")
        self._pill(btns, "🔄 同步封禁名单", self._sync_banlist, SUB).pack(side="left", padx=(10, 0))

        self._lic_info = tk.Label(p, text="", bg=BG, fg=TEXT, justify="left", font=(F, 11))
        self._lic_info.pack(anchor="w", padx=24)
        self._refresh_lic_page()

    def _activate(self):
        key = self._key_var.get().strip()
        if not key:
            messagebox.showwarning("提示", "请输入卡密")
            return
        try:
            info = lic.activate(self.cfg, key)
            config.save_config(self.cfg)
            self._refresh_lic_page()
            self._refresh_badge()
            if info["type"] == "vip":
                messagebox.showinfo("开通成功",
                                    "已开通永久会员（自动绑定本机）\n下载全部内容免积分")
            else:
                messagebox.showinfo("兑换成功",
                                    f"已兑换 {info['pts']} 点积分\n当前积分：{lic.points(self.cfg)}")
        except lic.LicenseError as e:
            messagebox.showerror("激活失败", str(e))

    def _refresh_lic_page(self):
        st = lic.license_status(self.cfg)
        pts = lic.points(self.cfg)
        if lic.is_member(self.cfg):
            i = st["info"]
            self._lic_info.config(text=(
                f"状态：✅ 永久会员（已绑定本机）\n"
                f"会员卡号：{i['uid']}    开通时间：{self.cfg.get('member_since', '-')}\n"
                f"积分余额：{pts} 点（会员下载全部内容免积分）\n\n"
                f"本机指纹：{st['machine']}"))
        elif st["activated"]:
            i = st["info"]
            self._lic_info.config(text=(
                f"状态：✅ 已兑换积分卡\n"
                f"卡号：{i['uid']}    类型：{lic.card_description(i)}\n"
                f"积分余额：{pts} 点（1 积分下载 1 个商品）\n\n"
                f"本机指纹：{st['machine']}\n"
                "如需开通永久会员，请输入会员卡，或到「钱包」页购买。"))
        else:
            self._lic_info.config(text=(
                f"状态：⚠ 未激活\n"
                f"积分余额：{pts} 点\n\n"
                f"本机指纹：{st['machine']}\n"
                "购买卡密时请提供本机指纹给管理员：\n"
                "会员卡 = 永久会员（绑定本机）；积分卡 = 1 积分可下载 1 个商品。"))

    # ================= 钱包 / 充值 =================
    def show_wallet(self):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._mark_nav("wallet")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        tk.Label(p, text="₿  钱包", bg=BG, fg=TEXT, font=(F, 17, "bold")).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(p, text="下载内容消耗积分；会员卡开通后为永久会员，下载全部内容免积分。",
                 bg=BG, fg=SUB, font=(F, 10)).pack(anchor="w", padx=24)

        shop = store.shop(self.cfg)
        pt_price = shop.get("point_price", 1.0)
        mb_price = shop.get("member_price", 19.9)
        mb_days = shop.get("member_days", 365)

        bal = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=16)
        bal.pack(fill="x", padx=24, pady=12)
        lr = tk.Frame(bal, bg=PANEL)
        lr.pack(fill="x")
        tk.Label(lr, text="积分余额", bg=PANEL, fg=SUB, font=(F, 10)).pack(side="left")
        tk.Label(lr, text=f"{lic.points(self.cfg)} 点", bg=PANEL, fg=ACCENT,
                 font=(F_EN, 24, "bold")).pack(side="left", padx=12)
        st = lic.license_status(self.cfg)
        if lic.is_member(self.cfg):
            tk.Label(lr, text="● 永久会员（已绑定本机）", bg=PANEL, fg=OK,
                     font=(F, 11, "bold")).pack(side="right")
        else:
            tk.Label(lr, text="● 未开通会员", bg=PANEL, fg=WARN,
                     font=(F, 11, "bold")).pack(side="right")

        info = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=16)
        info.pack(fill="x", padx=24, pady=(0, 12))
        tk.Label(info, text="价格与会员权益", bg=PANEL, fg=TEXT, font=(F, 12, "bold")).pack(anchor="w")
        tk.Label(info, text=f"积分单价：1 积分 = {pt_price:g} 元    ·    会员卡：{mb_price:g} 元（开通即永久，自动绑定本机）",
                 bg=PANEL, fg=SUB, font=(F, 10)).pack(anchor="w", pady=(6, 2))
        for b in (shop.get("member_benefits") or []):
            tk.Label(info, text="· " + str(b), bg=PANEL, fg=SUB, font=(F, 10)).pack(anchor="w")

        tk.Label(p, text="在线支付方式", bg=BG, fg=TEXT, font=(F, 13, "bold")).pack(anchor="w", padx=24, pady=(4, 4))
        pays = shop.get("payments") or []
        if pays:
            wrap = tk.Frame(p, bg=BG)
            wrap.pack(fill="x", padx=24)
            for i, pay in enumerate(pays):
                card = tk.Frame(wrap, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                                padx=14, pady=12)
                card.grid(row=0, column=i, padx=6, sticky="nsew")
                wrap.grid_columnconfigure(i, weight=1, uniform="pay")
                tk.Label(card, text=pay.get("name", "支付"), bg=PANEL, fg=ACCENT,
                         font=(F, 12, "bold")).pack(anchor="w")
                img = self._pay_image(pay)
                if img:
                    lab = tk.Label(card, image=img, bg=PANEL, cursor="hand2")
                    lab.image = img
                    lab.pack(pady=6)
                    lab.bind("<Button-1>", lambda e, x=pay.get("note", ""): self._copy_text(
                        f"收款码说明：{x}"))
                else:
                    tk.Label(card, text="（管理员尚未上传收款码）", bg=PANEL, fg=SUB,
                             font=(F, 9)).pack(pady=10)
                tk.Label(card, text=pay.get("note", ""), bg=PANEL, fg=SUB, font=(F, 9),
                         wraplength=220, justify="left").pack(anchor="w")
        else:
            tk.Label(p, text="（管理员尚未配置支付方式）", bg=BG, fg=SUB, font=(F, 10)).pack(anchor="w", padx=24)

        tk.Label(p, text="充值登记（支付后填写，便于管理员发放）", bg=BG, fg=TEXT,
                 font=(F, 13, "bold")).pack(anchor="w", padx=24, pady=(12, 4))
        box = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=16)
        box.pack(fill="x", padx=24)
        tk.Label(box, text="本机指纹（发送给管理员用于发放积分/会员）", bg=PANEL, fg=SUB,
                 font=(F, 9)).pack(anchor="w")
        fp = tk.Frame(box, bg=PANEL)
        fp.pack(fill="x", pady=4)
        tk.Label(fp, text=machine_id(), bg=PANEL2, fg=TEXT, font=("Consolas", 11),
                 padx=10, pady=4).pack(side="left")
        self._pill(fp, "📋 复制指纹", lambda: self._copy_text(machine_id()), SUB).pack(side="left", padx=8)
        tk.Label(box, text="支付单号 / 说明（选填）", bg=PANEL, fg=SUB, font=(F, 9)).pack(anchor="w", pady=(8, 4))
        self._order_var = tk.StringVar()
        tk.Entry(box, textvariable=self._order_var, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                 relief="flat", highlightbackground=BORDER, highlightthickness=1).pack(fill="x")
        bt = tk.Frame(box, bg=PANEL)
        bt.pack(fill="x", pady=(8, 0))
        self._pill(bt, "📝 登记订单", self._save_order, "#FFFFFF", ACCENT).pack(side="left")
        self._pill(bt, "📋 复制全部（含指纹）", self._copy_order_info, SUB).pack(side="left", padx=(10, 0))
        self._order_info = tk.Label(p, text="", bg=BG, fg=SUB, justify="left", font=(F, 9))
        self._order_info.pack(anchor="w", padx=24, pady=6)
        self._refresh_orders()

        tk.Label(p, text="流程：扫码支付 → 复制「本机指纹 + 支付单号」发送给管理员 → 管理员发放积分卡或会员卡 → 在「卡密」页输入激活。",
                 bg=BG, fg=SUB, font=(F, 9), wraplength=760, justify="left").pack(anchor="w", padx=24, pady=(8, 0))
        self._refresh_badge()

    def _pay_image(self, pay):
        key = "pay_" + pay.get("id", "x")
        if key in self._images:
            return self._images[key]
        path = store.ensure_payment_image(self.cfg, pay)
        if not path:
            return None
        ph = self._load_img(path, 150)
        if ph:
            self._images[key] = ph
        return ph

    def _copy_text(self, txt):
        try:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self._toast("已复制到剪贴板")
        except Exception:
            pass

    def _save_order(self):
        note = self._order_var.get().strip()
        if not note:
            messagebox.showwarning("提示", "请填写支付单号或说明")
            return
        orders = list(self.cfg.get("wallet_orders") or [])
        orders.append({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "machine": machine_id(),
            "note": note,
        })
        self.cfg["wallet_orders"] = orders
        config.save_config(self.cfg)
        self._order_var.set("")
        self._refresh_orders()
        self._copy_order_info()
        messagebox.showinfo("已登记", "订单已登记并复制，请粘贴发送给管理员。")

    def _refresh_orders(self):
        try:
            orders = list(self.cfg.get("wallet_orders") or [])
            if not orders:
                self._order_info.config(text="暂无登记记录")
                return
            lines = [f"{o['time']}  {o['machine']}  {o['note']}" for o in orders[-5:]]
            self._order_info.config(text="最近登记：\n" + "\n".join(lines))
        except Exception:
            pass

    def _copy_order_info(self):
        orders = list(self.cfg.get("wallet_orders") or [])
        txt = f"【NovaForge 充值登记】\n本机指纹：{machine_id()}"
        if orders:
            txt += "\n" + "\n".join(f"{o['time']} {o['note']}" for o in orders[-5:])
        self._copy_text(txt)

    # ================= 设置 =================
    def show_settings(self):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)
        tk.Label(p, text="⚙  设置", bg=BG, fg=TEXT, font=(F, 17, "bold")).pack(anchor="w", padx=24, pady=(20, 12))

        form = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=16)
        form.pack(fill="x", padx=24)
        self._s_dir = self._row(form, "默认下载目录", self.cfg.get("default_download_dir", ""))
        self._s_mirror = self._row(form, "国内镜像(hf-mirror)", self.cfg.get("hf_mirror", "https://hf-mirror.com"))
        self._s_thr = self._row(form, "慢速阈值 KB/s", str(self.cfg.get("speed_threshold_kb", 200)))
        self._s_secs = self._row(form, "慢速持续秒数", str(self.cfg.get("slow_seconds", 8)))

        r = tk.Frame(form, bg=PANEL)
        r.pack(fill="x", pady=5)
        tk.Label(r, text="慢速自动切换镜像", bg=PANEL, fg=TEXT, width=22, anchor="w").pack(side="left")
        self._s_auto = tk.BooleanVar(value=bool(self.cfg.get("auto_mirror", True)))
        tk.Checkbutton(r, variable=self._s_auto, bg=PANEL, fg=TEXT, selectcolor=PANEL2,
                       activebackground=PANEL).pack(side="left")

        self._pill(form, "💾 保存设置", self._save_settings, "#FFFFFF", ACCENT).pack(anchor="w", pady=(12, 0))
        tk.Label(p, text="下载时速度过慢会自动切换国内镜像源；商城清单与更新由软件自动同步。",
                 bg=BG, fg=SUB, font=(F, 9)).pack(anchor="w", padx=24, pady=8)

    def _row(self, parent, label, value):
        r = tk.Frame(parent, bg=PANEL)
        r.pack(fill="x", pady=4)
        tk.Label(r, text=label, bg=PANEL, fg=TEXT, width=22, anchor="w").pack(side="left")
        v = tk.StringVar(value=value)
        tk.Entry(r, textvariable=v, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightbackground=BORDER, highlightthickness=1).pack(side="left", fill="x", expand=True)
        return v

    def _save_settings(self):
        self.cfg["default_download_dir"] = self._s_dir.get().strip()
        self.cfg["hf_mirror"] = self._s_mirror.get().strip() or "https://hf-mirror.com"
        try:
            self.cfg["speed_threshold_kb"] = max(50, int(self._s_thr.get()))
        except Exception:
            pass
        try:
            self.cfg["slow_seconds"] = max(2, int(self._s_secs.get()))
        except Exception:
            pass
        self.cfg["auto_mirror"] = bool(self._s_auto.get())
        config.save_config(self.cfg)
        messagebox.showinfo("设置", "已保存。")
        self._status.config(text="设置已保存")

    # ================= 更新 =================
    def show_update(self):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)
        tk.Label(p, text="🔄  关于与更新", bg=BG, fg=TEXT, font=(F, 17, "bold")).pack(anchor="w", padx=24, pady=(20, 8))
        self._up_info = tk.Label(p, text=f"当前版本：v{VERSION}\n积分制 + 永久会员 · 自动更新",
                                 bg=BG, fg=TEXT, justify="left", font=(F, 11))
        self._up_info.pack(anchor="w", padx=24)
        self._pill(p, "🔎 检查更新", self._check_update, "#FFFFFF", ACCENT).pack(anchor="w", padx=24, pady=14)
        self._up_result = tk.Label(p, text="", bg=BG, fg=SUB, justify="left", font=(F, 10))
        self._up_result.pack(anchor="w", padx=24)
        self._update_plan = {}
        self._install_btn = self._pill(p, "⬇ 下载并安装新版本", self._install_update, OK)
        self._up_install_hidden = True

    def _check_update(self):
        self._up_result.config(text="正在检查更新……")
        self._run_async(lambda: updater.check_update(self.cfg), self._on_checked)

    def _on_checked(self, r):
        self._up_result.config(text=r["msg"])
        if r["has_update"]:
            self._update_plan = r
            self._install_btn.pack(anchor="w", padx=24, pady=(4, 0))

    def _install_update(self):
        r = self._update_plan
        if not r or not r.get("asset_url"):
            return
        self._up_result.config(text="正在下载新版本……")
        new_path = os.path.join(config.cache_dir(), r.get("asset_name") or "update.exe")
        self._run_async(lambda: updater.download_update(r["asset_url"], new_path),
                        lambda p: self._finish_install(p, new_path),
                        lambda e: self._up_result.config(text=f"下载失败：{e}"))

    def _finish_install(self, _p, new_path):
        target = os.path.abspath(sys.argv[0])
        if not target.lower().endswith(".exe") and not os.path.exists(target):
            target = os.path.join(os.path.dirname(target), config.APP_EXE)
        if updater.apply_update(self.cfg, new_path, target):
            self._up_result.config(text=f"新版本已下载，正在替换并重启…\n{new_path}")
            self.after(600, self.destroy)
        else:
            self._up_result.config(text="更新脚本缺失，请手动替换程序文件。")


def main():
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            messagebox.showerror("启动失败", str(e))
        except Exception:
            pass


if __name__ == "__main__":
    main()
