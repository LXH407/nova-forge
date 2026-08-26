# -*- coding: utf-8 -*-
"""NovaForge 主界面（tkinter，Bandcamp 风格）。
布局：顶部品牌栏 + 搜索 + 左侧固定导航 + 紫色横幅首页 + 内容分区列表 + 底部全局下载进度条。
页面：首页 / 分类商城 / 内容详情 / 搜索 / 卡密 / 钱包 / 设置 / 更新
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

# ---------- 主题（Bandcamp 风格，紫色主调） ----------
BG = "#F6F7F9"            # 页面背景
PANEL = "#FFFFFF"         # 卡片 / 面板
PANEL2 = "#F2F4F7"        # 输入框 / 次级底色
BORDER = "#E7E9EE"
TEXT = "#101828"
SUB = "#667085"
PURPLE = "#7C3AED"        # 主色（紫）
PURPLE_D = "#5B21B6"      # 深紫
PURPLE_L = "#A78BFA"      # 浅紫
BLUE = "#0EA5E9"
OK = "#16A34A"
WARN = "#D97706"
RED = "#DC2626"
ORANGE = "#F97316"

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

CAT_COLORS = {"model": PURPLE, "app": BLUE, "game": ORANGE, "tool": OK}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_DISPLAY}  {APP_TAGLINE}  ·  v{VERSION}")
        self.geometry("1200x780")
        self.minsize(1024, 680)
        self.configure(bg=BG)

        self.cfg = config.load_config()
        self.q = queue.Queue()
        self._images = {}
        self._back_stack = []
        self._cur_nav = "home"
        self._cur_view = None

        # 全局下载状态（底部进度条）
        self._dl_running = False
        self._dl_meta = None
        self._dl_pause = threading.Event()
        self._dl_cancel = threading.Event()

        self._build_style()
        self._build_header()
        self._build_dlbar()
        self._body = tk.Frame(self, bg=BG)
        self._body.pack(fill="both", expand=True)
        self._build_sidebar()
        self._content = tk.Frame(self._body, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)

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
            self._lic_badge.configure(text=f"● 永久会员 · {pts} 积分", fg=OK)
        elif self.cfg.get("activated"):
            self._lic_badge.configure(text=f"● 积分卡 · {pts} 积分", fg=PURPLE)
        else:
            self._lic_badge.configure(text=f"● 未激活 · {pts} 积分", fg=WARN)

    def clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _back(self):
        if self._back_stack:
            self._back_stack.pop()()
        else:
            self.show_home()

    def _pill(self, parent, text, cmd, fg=PURPLE, bg="#FFFFFF", padx=16, pady=7, bd=1, font=None):
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                      activebackground=PANEL2, activeforeground=fg, relief="flat",
                      bd=bd, highlightbackground=BORDER, highlightthickness=bd,
                      padx=padx, pady=pady, cursor="hand2",
                      font=font or (F, 10, "bold"))
        return b

    def _icon_img(self, path, size):
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

    # ---------------- 顶部栏（品牌 + 搜索 + 操作） ----------------
    def _build_header(self):
        h = tk.Frame(self, bg=PANEL, height=58)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        self._logo_img = self._icon_img("assets/logo_main.png", 34)
        if self._logo_img:
            tk.Label(h, image=self._logo_img, bg=PANEL).pack(side="left", padx=(18, 10))
        brand = tk.Frame(h, bg=PANEL)
        brand.pack(side="left")
        tk.Label(brand, text=APP_DISPLAY, bg=PANEL, fg=TEXT, font=(F_EN, 15, "bold")).pack(anchor="w")
        tk.Label(brand, text=APP_TAGLINE, bg=PANEL, fg=PURPLE, font=(F_EN, 8)).pack(anchor="w")

        # 搜索框
        sr = tk.Frame(h, bg=PANEL2, highlightbackground=BORDER, highlightthickness=1)
        sr.pack(side="left", padx=26, ipady=2)
        tk.Label(sr, text="⌕", bg=PANEL2, fg=SUB, font=(F, 12)).pack(side="left", padx=(10, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._maybe_search())
        tk.Entry(sr, textvariable=self._search_var, bg=PANEL2, fg=TEXT, relief="flat",
                 width=30, insertbackground=TEXT, font=(F, 10)).pack(side="left", ipady=3)

        right = tk.Frame(h, bg=PANEL)
        right.pack(side="right", padx=14)
        self._lic_badge = tk.Label(h, text="● 未激活", bg=PANEL, fg=WARN, font=(F, 10, "bold"))
        self._lic_badge.pack(side="right", padx=14)
        for t, c, col in (("🔑 卡密", self.show_license, PURPLE), ("⚙ 设置", self.show_settings, SUB),
                          ("🔄 更新", self.show_update, BLUE)):
            self._pill(right, t, c, col, bg=PANEL, bd=0).pack(side="left", padx=3)

    def _maybe_search(self):
        q = self._search_var.get().strip()
        if len(q) >= 2:
            self._do_search(q)

    # ---------------- 左侧导航 ----------------
    def _build_sidebar(self):
        sb = tk.Frame(self._body, bg=PANEL, width=208)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        tk.Frame(sb, bg=BORDER, width=1).pack(side="right", fill="y")
        tk.Label(sb, text="浏览", bg=PANEL, fg=SUB, font=(F, 9, "bold")).pack(anchor="w", padx=22, pady=(16, 6))
        self._nav_btns = {}
        for key, glyph, cn in NAV_ITEMS:
            b = tk.Button(sb, text=f"  {glyph}  {cn}", command=lambda k=key: self._nav(k),
                          bg=PANEL, fg=SUB, activebackground=PANEL2, activeforeground=PURPLE,
                          relief="flat", bd=0, anchor="w", padx=18, pady=9,
                          font=(F, 11), cursor="hand2")
            b.pack(fill="x", padx=8, pady=1)
            self._nav_btns[key] = b
        ver = tk.Label(sb, text=f"v{VERSION} · 本地运行", bg=PANEL, fg=SUB, font=(F, 8))
        ver.pack(side="bottom", pady=10)

    def _mark_nav(self, key):
        for k, b in self._nav_btns.items():
            if k == key:
                b.configure(bg=PANEL2, fg=PURPLE, font=(F, 11, "bold"))
            else:
                b.configure(bg=PANEL, fg=SUB, font=(F, 11))

    def _nav(self, key):
        self._cur_nav = key
        self._mark_nav(key)
        if key == "home":
            self.show_home()
        elif key == "wallet":
            self.show_wallet()
        else:
            self.show_store(key)

    # ---------------- 底部全局下载进度条（替代音乐播放器） ----------------
    def _build_dlbar(self):
        bar = tk.Frame(self, bg=PANEL, height=76)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="bottom", before=bar)
        self._dlbar = bar

        # 左：图标 + 名称 + 来源
        left = tk.Frame(bar, bg=PANEL, width=250)
        left.pack(side="left", fill="y", padx=(16, 8))
        left.pack_propagate(False)
        self._dl_icon = tk.Label(left, text="⬡", bg=PANEL, fg=PURPLE_L, font=(F, 26))
        self._dl_icon.pack(side="left", padx=(0, 10))
        ltxt = tk.Frame(left, bg=PANEL)
        ltxt.pack(side="left", fill="y")
        self._dl_name = tk.Label(ltxt, text="暂无下载任务", bg=PANEL, fg=TEXT,
                                 font=(F, 11, "bold"), anchor="w")
        self._dl_name.pack(anchor="w")
        self._dl_sub = tk.Label(ltxt, text="在内容详情页点击「全自动下载」开始", bg=PANEL,
                                fg=SUB, font=(F, 9), anchor="w")
        self._dl_sub.pack(anchor="w")

        # 中：进度条 + 状态
        mid = tk.Frame(bar, bg=PANEL)
        mid.pack(side="left", fill="both", expand=True, padx=12)
        self._dl_canvas = tk.Canvas(mid, bg=PANEL, highlightthickness=0, height=10)
        self._dl_canvas.pack(fill="x", pady=(8, 2))
        self._dl_status = tk.Label(mid, text="空闲 · 随时可以开始下载", bg=PANEL, fg=SUB,
                                   font=(F, 9), anchor="w")
        self._dl_status.pack(anchor="w")
        self._draw_bar(0.0)

        # 右：暂停 / 停止
        right = tk.Frame(bar, bg=PANEL)
        right.pack(side="right", padx=14)
        self._dl_pause_btn = self._pill(right, "⏸ 暂停", self._toggle_pause, TEXT,
                                        bg=PANEL, bd=0, padx=12)
        self._dl_pause_btn.pack(side="left", padx=3)
        self._dl_pause_btn.configure(state="disabled")
        self._dl_stop_btn = self._pill(right, "✕ 停止", self._stop_dl, RED,
                                       bg=PANEL, bd=0, padx=12)
        self._dl_stop_btn.pack(side="left", padx=3)
        self._dl_stop_btn.configure(state="disabled")

    def _draw_bar(self, frac):
        try:
            c = self._dl_canvas
            c.delete("bar")
            w = c.winfo_width() or 200
            h = 10
            c.create_oval(0, 0, h, h, fill=BORDER, outline="")
            c.create_oval(w - h, 0, w, h, fill=BORDER, outline="")
            c.create_rectangle(h / 2, 0, w - h / 2, h, fill=BORDER, outline="")
            fw = max(h, int((w - h) * max(0.0, min(1.0, frac))))
            if fw > h:
                c.create_oval(0, 0, h, h, fill=PURPLE, outline="")
                c.create_rectangle(h / 2, 0, fw - h / 2, h, fill=PURPLE, outline="")
                if fw > h:
                    c.create_oval(fw - h, 0, fw, h, fill=PURPLE, outline="")
        except Exception:
            pass

    def _set_dlbar_active(self, item, dest):
        self._dl_running = True
        self._dl_pause.clear()
        self._dl_cancel.clear()
        self._dl_meta = {"item": item, "dest": dest}
        self._dl_icon.configure(text="⭳", fg=PURPLE)
        self._dl_name.configure(text=item.get("name") or item.get("title") or "下载中")
        src = store.provider_label(item.get("provider")) if store.is_netdisk(item) else {
            "huggingface": "HuggingFace", "modelscope": "ModelScope", "direct": "直链"}.get(
            (item.get("source") or "direct").lower(), "下载")
        self._dl_sub.configure(text=f"{src} · {dest}")
        self._dl_status.configure(text="正在解析文件清单…", fg=PURPLE)
        self._dl_pause_btn.configure(state="normal", text="⏸ 暂停")
        self._dl_stop_btn.configure(state="normal")
        self._draw_bar(0.0)

    def _set_dlbar_idle(self, msg=""):
        self._dl_running = False
        self._dl_meta = None
        self._dl_icon.configure(text="⬡", fg=PURPLE_L)
        self._dl_name.configure(text="暂无下载任务")
        self._dl_sub.configure(text=msg or "在内容详情页点击「全自动下载」开始")
        self._dl_status.configure(text="空闲 · 随时可以开始下载", fg=SUB)
        self._dl_pause_btn.configure(state="disabled", text="⏸ 暂停")
        self._dl_stop_btn.configure(state="disabled")
        self._draw_bar(0.0)

    def _update_dlbar_progress(self, done, total, speed, src):
        pct = (done / total * 100) if total else 0
        self._draw_bar(pct / 100.0)
        spd = self._fmt_speed(speed)
        self._dl_status.configure(
            text=f"{pct:5.1f}%   ·   {spd}   ·   源：{src}", fg=TEXT)

    def _toggle_pause(self):
        if not self._dl_running:
            return
        if self._dl_pause.is_set():
            self._dl_pause.clear()
            self._dl_pause_btn.configure(text="⏸ 暂停")
            self._dl_status.configure(text="已恢复下载", fg=OK)
        else:
            self._dl_pause.set()
            self._dl_pause_btn.configure(text="▶ 继续")
            self._dl_status.configure(text="已暂停 · 点击「继续」恢复", fg=WARN)

    def _stop_dl(self):
        if not self._dl_running:
            return
        self._dl_cancel.set()
        self._dl_pause.clear()
        self._dl_stop_btn.configure(state="disabled")
        self._dl_status.configure(text="正在停止…", fg=RED)

    # ================= 首页（紫色横幅 + 分区） =================
    def show_home(self):
        self.clear_content()
        self._back_stack = []
        self._cur_nav = "home"
        self._cur_view = self.show_home
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        # 紫色横幅
        hero = tk.Canvas(p, bg=PURPLE, highlightthickness=0, height=176)
        hero.pack(fill="x", padx=20, pady=(16, 4))
        hero.bind("<Configure>", lambda e: self._draw_hero(hero))

        # 分区：热门内容
        sec = self._section(p, "热门内容", "POPULAR", lambda: self.show_store("model"))
        items = store.load_content(self.cfg)
        if items:
            self._card_scroll(sec, items[:8], cols=4)
        else:
            tk.Label(sec, text="暂无内容，请点击「同步商城清单」刷新。", bg=BG, fg=SUB,
                     font=(F, 11)).pack(pady=24)

        self._refresh_badge()

    def _draw_hero(self, c):
        try:
            c.delete("all")
            w = c.winfo_width() or 1000
            h = c.winfo_height() or 176
            # 垂直渐变 深紫 -> 紫 -> 浅紫
            for y in range(h):
                t = y / max(1, h - 1)
                if t < 0.5:
                    k = t * 2
                    r = int(0x5B + (0x7C - 0x5B) * k); g = int(0x21 + (0x3A - 0x21) * k); b = int(0xB6 + (0xED - 0xB6) * k)
                else:
                    k = (t - 0.5) * 2
                    r = int(0x7C + (0xA8 - 0x7C) * k); g = int(0x3A + (0x5B - 0x3A) * k); b = int(0xED + (0xFA - 0xED) * k)
                c.create_line(0, y, w, y, fill="#%02x%02x%02x" % (r, g, b))
            c.create_text(28, 40, text="欢迎使用 NOVA FORGE", anchor="w", fill="#FFFFFF",
                          font=(F_EN, 22, "bold"))
            c.create_text(28, 78, text="把模型 · 应用 · 游戏 · 工具统统装进你的设备", anchor="w",
                          fill="#EDE9FE", font=(F, 12))
            c.create_text(28, 104, text="全自动下载 · 速度过慢自动切换国内镜像源 · 积分/永久会员", anchor="w",
                          fill="#DDD6FE", font=(F, 10))
            # 右侧按钮
            c.create_rectangle(w - 200, 102, w - 30, 140, fill="#FFFFFF", outline="", tags="syncbox")
            c.create_text(w - 115, 121, text="🚀 同步商城清单", fill=PURPLE_D,
                          font=(F, 10, "bold"), tags="synclink")
            c.tag_bind("synclink", "<Button-1>", lambda e: self._do_sync())
            c.tag_bind("synclink", "<Enter>", lambda e: c.itemconfigure("synclink", fill=PURPLE))
            c.tag_bind("synclink", "<Leave>", lambda e: c.itemconfigure("synclink", fill=PURPLE_D))
            c.tag_bind("syncbox", "<Button-1>", lambda e: self._do_sync())
        except Exception:
            pass

    def _section(self, parent, title, en, more_cmd=None):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="x", padx=20, pady=(10, 4))
        head = tk.Frame(wrap, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=title, bg=BG, fg=TEXT, font=(F, 15, "bold")).pack(side="left")
        tk.Label(head, text=f"  ·  {en}", bg=BG, fg=SUB, font=(F_EN, 9)).pack(side="left")
        if more_cmd:
            self._pill(head, "查看全部 →", more_cmd, PURPLE, bg=BG, bd=0, padx=6, pady=2,
                       font=(F, 9, "bold")).pack(side="right")
        body = tk.Frame(wrap, bg=BG)
        body.pack(fill="x", pady=(2, 0))
        return body

    # ================= 分类商城 =================
    def show_store(self, cat):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._cur_nav = cat
        self._cur_view = lambda: self.show_store(cat)
        self._mark_nav(cat)
        meta = store.category_meta(cat)
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        top = tk.Frame(p, bg=BG)
        top.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(top, text=f"{meta['glyph']}  {meta['cn']}", bg=BG, fg=TEXT,
                 font=(F, 18, "bold")).pack(side="left")
        tk.Label(top, text=f"  ·  {meta['en']}", bg=BG, fg=SUB, font=(F_EN, 10)).pack(side="left")
        self._pill(top, "🔄 同步", self._do_sync, PURPLE, bg=BG, bd=0).pack(side="right")

        items = store.by_category(self.cfg, cat)
        if not items:
            tk.Label(p, text="该分类暂时没有内容，可在后端管理台添加。", bg=BG, fg=SUB,
                     font=(F, 11)).pack(pady=40)
            return
        self._card_scroll(p, items)

    # ================= 搜索结果页 =================
    def _do_search(self, q):
        q = (q or "").strip().lower()
        if not q:
            return
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._cur_view = lambda: self._do_search(q)
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)
        tk.Label(p, text=f"⌕  “{self._search_var.get().strip()}” 的搜索结果", bg=BG, fg=TEXT,
                 font=(F, 15, "bold")).pack(anchor="w", padx=20, pady=(16, 6))
        results = []
        for it in store.load_content(self.cfg):
            hay = " ".join([str(it.get("name", "")), str(it.get("title", "")),
                            " ".join(it.get("tags") or []), str(it.get("desc", ""))]).lower()
            if q in hay:
                results.append(it)
        if results:
            self._card_scroll(p, results)
        else:
            tk.Label(p, text="没有找到相关内容，换个关键词试试。", bg=BG, fg=SUB,
                     font=(F, 11)).pack(pady=30)

    # ---------------- 卡片网格 ----------------
    def _card_scroll(self, parent, items, cols=4):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(wid, width=e.width))

        for i, item in enumerate(items):
            row, col = divmod(i, cols)
            self._make_card(inner, item).grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        for c in range(cols):
            inner.grid_columnconfigure(c, weight=1, uniform="card")

    def _make_card(self, parent, item):
        cid = item.get("id", "")
        card = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                        padx=14, pady=14, cursor="hand2")
        card.bind("<Button-1>", lambda e: self.show_detail(cid))
        card.bind("<Enter>", lambda e: card.configure(highlightbackground=PURPLE))
        card.bind("<Leave>", lambda e: card.configure(highlightbackground=BORDER))

        meta = store.category_meta(item.get("category", ""))
        color = CAT_COLORS.get(item.get("category", ""), PURPLE)
        icon = self._icon_for(item, 84)
        if icon:
            lab = tk.Label(card, image=icon, bg=PANEL)
            lab.image = icon
            lab.pack()
            lab.bind("<Button-1>", lambda e: self.show_detail(cid))
        tk.Label(card, text=item.get("name", "?"), bg=PANEL, fg=TEXT,
                 font=(F_EN, 12, "bold")).pack(anchor="w", pady=(8, 0))
        tk.Label(card, text=item.get("title", ""), bg=PANEL, fg=SUB, font=(F, 9),
                 wraplength=180, justify="left").pack(anchor="w")
        tags = item.get("tags") or []
        if tags:
            tk.Label(card, text="  ".join(tags[:3]), bg=PANEL, fg=color,
                     font=(F, 8)).pack(anchor="w", pady=(2, 0))
        info = tk.Frame(card, bg=PANEL)
        info.pack(fill="x", pady=(6, 0))
        src = {"huggingface": "HF", "modelscope": "MS", "direct": "直链",
               "netdisk": store.provider_label(item.get("provider"))}.get(
            (item.get("source") or "direct").lower(), "直链")
        tk.Label(info, text=src, bg=PANEL, fg=PURPLE, font=(F, 8, "bold")).pack(side="left")
        tk.Label(info, text="   " + store.size_label(item.get("size_gb")), bg=PANEL,
                 fg=SUB, font=(F, 8)).pack(side="left")
        if not store.is_complete(item)[0]:
            missing = store.is_complete(item)[1]
            tk.Label(card, text="⚠ 缺少: " + "、".join(missing[:3]), bg=PANEL, fg=RED,
                     font=(F, 8)).pack(anchor="w", pady=(4, 0))
        price = store.content_price(item)
        price_txt = "会员免费" if lic.is_member(self.cfg) else f"{price} 积分"
        tk.Button(card, text="🚀 下载" if not store.is_netdisk(item) else "🌐 打开",
                  bg=color, fg="#FFFFFF", activebackground=color, activeforeground="#FFFFFF",
                  relief="flat", cursor="hand2", font=(F, 9, "bold"),
                  command=lambda: self.show_detail(cid)).pack(fill="x", pady=(10, 0))
        return card

    def _icon_for(self, item, size):
        cid = item.get("id", "unknown")
        key = f"{cid}_{size}"
        if key in self._images:
            return self._images[key]
        path = store.icon_local_path(self.cfg, cid)
        ph = None
        if path:
            ph = self._icon_img(path, size)
        if not ph:
            ph = self._icon_img("assets/icon.png", size)
        if ph:
            self._images[key] = ph
        # 本地还没有真实图标：立即返回占位图，后台下载完成后刷新当前页
        if not path:
            self._ensure_icon_async(item, size)
        return ph

    def _ensure_icon_async(self, item, size):
        def work():
            try:
                path = store.ensure_icon(self.cfg, item)
                if path:
                    self.q.put(lambda: self._apply_icon(item, size))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _apply_icon(self, item, size):
        key = f"{item.get('id', 'unknown')}_{size}"
        self._images.pop(key, None)
        if self._cur_view:
            try:
                self._cur_view()
            except Exception:
                pass

    # ================= 内容详情 =================
    def show_detail(self, cid):
        item = store.get_content(self.cfg, cid)
        if not item:
            return
        self.clear_content()
        self._back_stack.append(lambda: self.show_store(item.get("category", "model")))
        self._mark_nav(item.get("category", "home"))
        self._cur_view = lambda: self.show_detail(cid)
        meta = store.category_meta(item.get("category", ""))
        color = CAT_COLORS.get(item.get("category", ""), PURPLE)
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        top = tk.Frame(p, bg=BG)
        top.pack(fill="x", padx=20, pady=(14, 8))
        self._pill(top, "‹ 返回", self._back, TEXT, bg=BG, bd=0).pack(side="left")

        body = tk.Frame(p, bg=BG)
        body.pack(fill="both", expand=True, padx=20)
        lf = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                      padx=20, pady=20, width=252)
        lf.pack(side="left", fill="y", padx=(0, 16))
        lf.pack_propagate(False)
        icon = self._icon_for(item, 128)
        if icon:
            lab = tk.Label(lf, image=icon, bg=PANEL)
            lab.image = icon
            lab.pack()
        tk.Label(lf, text=item.get("name", ""), bg=PANEL, fg=TEXT, font=(F_EN, 12, "bold"),
                 wraplength=200).pack(pady=(10, 2))
        tk.Label(lf, text=item.get("title", ""), bg=PANEL, fg=SUB, font=(F, 10),
                 wraplength=200).pack()

        is_nd = store.is_netdisk(item)
        if is_nd:
            tk.Label(lf, text=f"来源：{store.provider_label(item.get('provider'))}",
                     bg=PANEL, fg=PURPLE, font=(F, 9)).pack(pady=(6, 0))
            self._pill(lf, "🌐 打开链接", lambda: self._open_nd(item), PURPLE, "#F3EEFF").pack(fill="x", pady=(10, 4))
            self._pill(lf, "📋 复制链接", lambda: self._copy_nd(item), SUB).pack(fill="x")
        else:
            self._pill(lf, "🚀 开始全自动下载", self._start_dl_click, "#FFFFFF", PURPLE).pack(fill="x", pady=(10, 4))

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
                     fg=color, font=(F, 9)).pack(anchor="w", pady=(0, 8))
        tk.Label(rf, text="介绍", bg=PANEL, fg=PURPLE, font=(F, 10, "bold")).pack(anchor="w")
        desc = tk.Text(rf, bg="#FBFBFF", fg=TEXT, wrap="word", relief="flat", height=8,
                       font=(F, 10), padx=8, pady=8, highlightbackground=BORDER, highlightthickness=1)
        desc.insert("1.0", item.get("desc", ""))
        desc.configure(state="disabled")
        desc.pack(fill="both", expand=True, pady=(4, 8))
        repo = item.get("repo") or item.get("url") or ""
        tk.Label(rf, text=f"来源地址：{repo}", bg=PANEL, fg=SUB, font=(F, 8),
                 wraplength=560, justify="left").pack(anchor="w")

        tk.Label(rf, text="下载日志（底部进度条实时显示）", bg=PANEL, fg=PURPLE,
                 font=(F, 10, "bold")).pack(anchor="w", pady=(8, 2))
        self._dl_log = tk.Text(rf, bg="#FBFBFF", fg=SUB, height=6, relief="flat",
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
        if self._dl_running:
            messagebox.showinfo("正在下载", "已有任务在进行中，请先在底部停止或等待完成。")
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

        self._set_dlbar_active(item, dest)
        self._append_log(f"授权：{msg}")
        self._append_log(f"保存目录：{dest}")

        def prog(done, total, speed, src):
            self.q.put(lambda: self._update_dlbar_progress(done, total, speed, src))

        self._run_async(lambda: downloader.download_entry(
                            self.cfg, item, dest, progress=prog, log=self._append_log,
                            pause_event=self._dl_pause, cancel_event=self._dl_cancel),
                        self._dl_done)

    @staticmethod
    def _fmt_speed(bps):
        if bps >= 1024 * 1024:
            return f"{bps / 1024 / 1024:.2f} MB/s"
        if bps >= 1024:
            return f"{bps / 1024:.0f} KB/s"
        return f"{bps:.0f} B/s"

    def _dl_done(self, r):
        cancelled = self._dl_cancel.is_set()
        self._dl_pause.clear()
        self._dl_cancel.clear()
        if cancelled:
            self._set_dlbar_idle("已停止下载")
        else:
            ok_n, fail_n = r.get("ok", 0), r.get("fail", 0)
            if fail_n == 0:
                self._set_dlbar_idle(f"完成：成功 {ok_n} 个 · 已保存到下载目录")
            else:
                self._set_dlbar_idle(f"完成：成功 {ok_n} / 失败 {fail_n}（见日志）")
        self._append_log(f"下载结束：成功 {r.get('ok', 0)}，失败 {r.get('fail', 0)}")
        if r.get("errors"):
            self._append_log("失败：" + "；".join(r["errors"][:3]))

    # ================= 卡密 =================
    def show_license(self):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._cur_view = self.show_license
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        tk.Label(p, text="🔑  卡密中心", bg=BG, fg=TEXT, font=(F, 18, "bold")).pack(anchor="w", padx=28, pady=(22, 4))
        tk.Label(p, text="会员卡 → 输入后自动绑定本机，开通永久会员（下载全部内容免积分）；积分卡 → 兑换积分（1 积分下载 1 个商品）。离线验签，无需联网授权。",
                 bg=BG, fg=SUB, font=(F, 10), wraplength=780, justify="left").pack(anchor="w", padx=28)

        box = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=22, pady=18)
        box.pack(fill="x", padx=28, pady=16)
        tk.Label(box, text="卡密", bg=PANEL, fg=TEXT, font=(F, 11, "bold")).pack(anchor="w")
        self._key_var = tk.StringVar()
        tk.Entry(box, textvariable=self._key_var, font=("Consolas", 12), bg=PANEL2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", highlightbackground=BORDER,
                 highlightthickness=1).pack(fill="x", pady=(6, 10))
        btns = tk.Frame(box, bg=PANEL)
        btns.pack(fill="x")
        self._pill(btns, "🔓 激活", self._activate, "#FFFFFF", PURPLE).pack(side="left")
        self._pill(btns, "🔄 同步封禁名单", self._sync_banlist, SUB).pack(side="left", padx=(10, 0))

        self._lic_info = tk.Label(p, text="", bg=BG, fg=TEXT, justify="left", font=(F, 11))
        self._lic_info.pack(anchor="w", padx=28)
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
        self._cur_view = self.show_wallet
        self._mark_nav("wallet")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)

        tk.Label(p, text="₿  钱包", bg=BG, fg=TEXT, font=(F, 18, "bold")).pack(anchor="w", padx=28, pady=(22, 4))
        tk.Label(p, text="下载内容消耗积分；会员卡开通后为永久会员，下载全部内容免积分。",
                 bg=BG, fg=SUB, font=(F, 10)).pack(anchor="w", padx=28)

        shop = store.shop(self.cfg)
        pt_price = shop.get("point_price", 1.0)
        mb_price = shop.get("member_price", 19.9)

        bal = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=22, pady=16)
        bal.pack(fill="x", padx=28, pady=12)
        lr = tk.Frame(bal, bg=PANEL)
        lr.pack(fill="x")
        tk.Label(lr, text="积分余额", bg=PANEL, fg=SUB, font=(F, 10)).pack(side="left")
        tk.Label(lr, text=f"{lic.points(self.cfg)} 点", bg=PANEL, fg=PURPLE,
                 font=(F_EN, 26, "bold")).pack(side="left", padx=12)
        if lic.is_member(self.cfg):
            tk.Label(lr, text="● 永久会员（已绑定本机）", bg=PANEL, fg=OK,
                     font=(F, 11, "bold")).pack(side="right")
        else:
            tk.Label(lr, text="● 未开通会员", bg=PANEL, fg=WARN,
                     font=(F, 11, "bold")).pack(side="right")

        info = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=22, pady=16)
        info.pack(fill="x", padx=28, pady=(0, 12))
        tk.Label(info, text="价格与会员权益", bg=PANEL, fg=TEXT, font=(F, 12, "bold")).pack(anchor="w")
        tk.Label(info, text=f"积分单价：1 积分 = {pt_price:g} 元    ·    会员卡：{mb_price:g} 元（开通即永久，自动绑定本机）",
                 bg=PANEL, fg=SUB, font=(F, 10)).pack(anchor="w", pady=(6, 2))
        for b in (shop.get("member_benefits") or []):
            tk.Label(info, text="· " + str(b), bg=PANEL, fg=SUB, font=(F, 10)).pack(anchor="w")

        tk.Label(p, text="在线支付方式", bg=BG, fg=TEXT, font=(F, 13, "bold")).pack(anchor="w", padx=28, pady=(4, 4))
        pays = shop.get("payments") or []
        if pays:
            wrap = tk.Frame(p, bg=BG)
            wrap.pack(fill="x", padx=28)
            for i, pay in enumerate(pays):
                card = tk.Frame(wrap, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                                padx=14, pady=12)
                card.grid(row=0, column=i, padx=6, sticky="nsew")
                wrap.grid_columnconfigure(i, weight=1, uniform="pay")
                tk.Label(card, text=pay.get("name", "支付"), bg=PANEL, fg=PURPLE,
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
                         wraplength=230, justify="left").pack(anchor="w")
        else:
            tk.Label(p, text="（管理员尚未配置支付方式）", bg=BG, fg=SUB, font=(F, 10)).pack(anchor="w", padx=28)

        tk.Label(p, text="充值登记（支付后填写，便于管理员发放）", bg=BG, fg=TEXT,
                 font=(F, 13, "bold")).pack(anchor="w", padx=28, pady=(12, 4))
        box = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=22, pady=16)
        box.pack(fill="x", padx=28)
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
        self._pill(bt, "📝 登记订单", self._save_order, "#FFFFFF", PURPLE).pack(side="left")
        self._pill(bt, "📋 复制全部（含指纹）", self._copy_order_info, SUB).pack(side="left", padx=(10, 0))
        self._order_info = tk.Label(p, text="", bg=BG, fg=SUB, justify="left", font=(F, 9))
        self._order_info.pack(anchor="w", padx=28, pady=6)
        self._refresh_orders()

        tk.Label(p, text="流程：扫码支付 → 复制「本机指纹 + 支付单号」发送给管理员 → 管理员发放积分卡或会员卡 → 在「卡密」页输入激活。",
                 bg=BG, fg=SUB, font=(F, 9), wraplength=780, justify="left").pack(anchor="w", padx=28, pady=(8, 0))
        self._refresh_badge()

    def _pay_image(self, pay):
        key = "pay_" + pay.get("id", "x")
        if key in self._images:
            return self._images[key]
        path = store.payment_image_path(self.cfg, pay.get("id", "pay"))
        ph = None
        if path:
            ph = self._icon_img(path, 150)
        if not ph:
            return None
        self._images[key] = ph
        if not path:
            self._ensure_pay_async(pay, key)
        return ph

    def _ensure_pay_async(self, pay, key):
        def work():
            try:
                path = store.ensure_payment_image(self.cfg, pay)
                if path:
                    self.q.put(lambda: self._apply_icon_pay(pay, key))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _apply_icon_pay(self, pay, key):
        self._images.pop(key, None)
        if self._cur_view:
            try:
                self._cur_view()
            except Exception:
                pass

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
        self._cur_view = self.show_settings
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)
        tk.Label(p, text="⚙  设置", bg=BG, fg=TEXT, font=(F, 18, "bold")).pack(anchor="w", padx=28, pady=(22, 12))

        form = tk.Frame(p, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=22, pady=16)
        form.pack(fill="x", padx=28)
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

        self._pill(form, "💾 保存设置", self._save_settings, "#FFFFFF", PURPLE).pack(anchor="w", pady=(12, 0))
        tk.Label(p, text="下载时速度过慢会自动切换国内镜像源；商城清单与更新由软件自动同步。",
                 bg=BG, fg=SUB, font=(F, 9)).pack(anchor="w", padx=28, pady=8)

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
        self._toast("设置已保存")

    # ================= 更新 =================
    def show_update(self):
        self.clear_content()
        self._back_stack.append(self.show_home)
        self._cur_view = self.show_update
        self._mark_nav("home")
        p = tk.Frame(self._content, bg=BG)
        p.pack(fill="both", expand=True)
        tk.Label(p, text="🔄  关于与更新", bg=BG, fg=TEXT, font=(F, 18, "bold")).pack(anchor="w", padx=28, pady=(22, 8))
        self._up_info = tk.Label(p, text=f"当前版本：v{VERSION}\n积分制 + 永久会员 · 自动更新",
                                 bg=BG, fg=TEXT, justify="left", font=(F, 11))
        self._up_info.pack(anchor="w", padx=28)
        self._pill(p, "🔎 检查更新", self._check_update, "#FFFFFF", PURPLE).pack(anchor="w", padx=28, pady=14)
        self._up_result = tk.Label(p, text="", bg=BG, fg=SUB, justify="left", font=(F, 10))
        self._up_result.pack(anchor="w", padx=28)
        self._update_plan = {}
        self._install_btn = self._pill(p, "⬇ 下载并安装新版本", self._install_update, "#FFFFFF", OK)
        self._up_install_hidden = True

    def _check_update(self):
        self._up_result.config(text="正在检查更新……")
        self._run_async(lambda: updater.check_update(self.cfg), self._on_checked)

    def _on_checked(self, r):
        self._up_result.config(text=r["msg"])
        if r["has_update"]:
            self._update_plan = r
            self._install_btn.pack(anchor="w", padx=28, pady=(4, 0))

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

    # ================= 同步 =================
    def _do_sync(self):
        self._toast("正在同步商城清单…")
        self._run_async(lambda: manifest.sync_remote(self.cfg),
                        lambda r: (self._toast(f"同步：{r['msg']}"),
                                   self._sync_banlist(quiet=True)))

    def _sync_banlist(self, quiet=False):
        if not quiet:
            self._toast("正在同步封禁名单…")
        self._run_async(lambda: lic.sync_banlist(self.cfg),
                        lambda r: (config.save_config(self.cfg),
                                   self._toast(f"封禁名单：{r['msg']}"),
                                   self._refresh_lic_page()))

    def _toast(self, msg):
        try:
            if self._dl_running:
                return  # 下载中不覆盖底部状态
            self._dl_status.configure(text=msg, fg=PURPLE)
        except Exception:
            pass


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
