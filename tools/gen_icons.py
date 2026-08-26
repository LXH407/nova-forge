# -*- coding: utf-8 -*-
"""生成 NovaForge 软件图标与商城占位图标（管理员可随时用真实图标替换 icons/ 内文件）。"""
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def font(sz):
    for p in ("C:/Windows/Fonts/arialbd.ttf",
              "C:/Windows/Fonts/seguisb.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def rounded(size, radius, bg):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=bg)
    return im, d


def gen_app_icon():
    S = 512
    im, d = rounded(S, 110, (11, 15, 26, 255))
    cx = cy = S // 2
    d.ellipse([cx - 150, cy - 150, cx + 150, cy + 150], outline=(0, 229, 255, 255), width=14)
    d.ellipse([cx - 172, cy - 172, cx + 172, cy + 172], outline=(139, 92, 246, 120), width=4)
    d.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], outline=(0, 229, 255, 120), width=3)
    core = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dc = ImageDraw.Draw(core)
    dc.ellipse([cx - 58, cy - 58, cx + 58, cy + 58], fill=(0, 229, 255, 255))
    dc.ellipse([cx - 38, cy - 38, cx + 38, cy + 38], fill=(224, 250, 255, 255))
    core = core.filter(ImageFilter.GaussianBlur(6))
    im = Image.alpha_composite(im, core)
    for i in range(4):
        a = math.radians(i * 90)
        nx = cx + 150 * math.cos(a)
        ny = cy + 150 * math.sin(a)
        r = 26 if i % 2 == 0 else 18
        d.ellipse([nx - r, ny - r, nx + r, ny + r],
                  fill=(139, 92, 246, 255) if i % 2 else (255, 255, 255, 255))
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(os.path.join(ROOT, "assets", "icon.png"))
    im.save(os.path.join(ROOT, "assets", "icon.ico"),
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("app icon OK")


def content_icon(fname, letter, color, ring=None):
    ring = ring or (0, 229, 255, 255)
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, 251, 251], radius=56, fill=(16, 24, 38, 255),
                        outline=color, width=5)
    d.rounded_rectangle([20, 20, 235, 235], radius=42, outline=(255, 255, 255, 26), width=2)
    d.ellipse([64, 64, 192, 192], outline=ring, width=4)
    f = font(96)
    d.text((128, 128), letter, anchor="mm", font=f, fill=color)
    for i in range(3):
        d.ellipse([104 + i * 22, 226, 112 + i * 22, 234], fill=color)
    im.save(os.path.join(ROOT, "icons", f"{fname}.png"))


def gen_extra_assets():
    """生成客户端打包所需 logo_main / logo_alt / bg（构建时自动补齐，避免仓库缺二进制资产）。"""
    S = 512
    # logo_main：紫色圆角方块 + 白色 NF 徽标（Header 品牌区）
    im, d = rounded(S, 118, (124, 58, 237, 255))
    d.ellipse([S - 158, 58, S - 30, 186], outline=(255, 255, 255, 80), width=6)
    f = font(180)
    d.text((S // 2, S // 2 + 8), "NF", anchor="mm", font=f, fill=(255, 255, 255, 255))
    im.save(os.path.join(ROOT, "assets", "logo_main.png"))
    # logo_alt：深色底 + 青色描边（备用变体）
    im2, d2 = rounded(S, 118, (11, 15, 26, 255))
    d2.ellipse([S - 158, 58, S - 30, 186], outline=(0, 229, 255, 160), width=6)
    d2.text((S // 2, S // 2 + 8), "NF", anchor="mm", font=f, fill=(0, 229, 255, 255))
    im2.save(os.path.join(ROOT, "assets", "logo_alt.png"))
    # bg：紫色垂直渐变（备用背景）
    W, H = 1200, 780
    grad = Image.new("RGBA", (W, H))
    for y in range(H):
        t = y / max(1, H - 1)
        k = t
        r = int(0x5B + (0xA8 - 0x5B) * k)
        g = int(0x21 + (0x5B - 0x21) * k)
        b = int(0xB6 + (0xFA - 0xB6) * k)
        grad.paste((r, g, b, 255), (0, y, W, y + 1))
    grad.save(os.path.join(ROOT, "assets", "bg.png"))
    print("extra assets OK")


def main():
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "icons"), exist_ok=True)
    gen_app_icon()
    gen_extra_assets()
    content_icon("qwen", "Q", (0, 229, 255, 255))
    content_icon("deepseek", "D", (139, 92, 246, 255))
    content_icon("llama", "L", (52, 211, 153, 255))
    content_icon("app_ollama", "O", (249, 115, 22, 255))
    content_icon("app_stable", "S", (236, 72, 153, 255))
    content_icon("game_cyber", "G", (249, 115, 22, 255), (249, 115, 22, 255))
    content_icon("tool_comfyui", "C", (52, 211, 153, 255), (52, 211, 153, 255))
    print("content icons OK")


if __name__ == "__main__":
    main()
