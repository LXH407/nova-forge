# -*- coding: utf-8 -*-
"""网盘链接操作：打开 / 复制。百度/夸克等分享页受登录态限制，由用户浏览器跳转。"""
import webbrowser


def open_link(url: str) -> None:
    if url:
        webbrowser.open(url)


def copy_link(url: str) -> bool:
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(url)
        r.update()
        r.destroy()
        return True
    except Exception:
        try:
            import subprocess
            subprocess.run("clip", input=url.encode(), shell=True)
            return True
        except Exception:
            return False
