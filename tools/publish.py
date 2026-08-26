# -*- coding: utf-8 -*-
"""内容上传向导（管理员端）：把“大模型 / 上传链接”发布进商城。
按“应用商城”标准要求必填：图标、介绍等，缺一项就无法完成上传。
输出一段 JSON，粘贴到仓库根目录 manifest.json 的 content 数组即可。

用法:
  python tools/publish.py                     # 交互式向导
  python tools/publish.py --out entry.json    # 结果写入文件
"""
import argparse
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import store

REQUIRED = {
    "id": "内容唯一ID（英文小写，如 qwen-7b 或 my-nd-01）",
    "name": "英文名称（商城展示名，如 Qwen 2.5 · 7B）",
    "category": "分类（model / app / game / tool）",
    "title": "中文标题（如 通义千问 2.5 7B 指令模型）",
    "desc": "详细介绍（应用商城风格，可多行）",
    "icon": "图标：@icons/xxx.png（上传到仓库icons/）或绝对URL",
    "source": "来源（huggingface / modelscope / direct / netdisk）",
}


def ask(prompt, default=""):
    v = input(f"  {prompt}" + (f"  [{default}]" if default else "") + ": ").strip()
    return v or default


def build():
    print("=" * 56)
    print("NovaForge 内容上传向导（图标与介绍为必填）")
    print("=" * 56)
    data = {}
    for k, hint in REQUIRED.items():
        data[k] = ask(hint)
    src = data["source"].lower()
    if src in ("huggingface", "hf", "modelscope", "ms"):
        data["source"] = "huggingface" if src in ("huggingface", "hf") else "modelscope"
        data["repo"] = ask("仓库ID（如 Qwen/Qwen2.5-7B-Instruct）")
        fl = ask("文件过滤（留空=全部，如 *.safetensors,*.json）")
        data["files"] = [x.strip() for x in fl.split(",") if x.strip()] if fl else []
    elif src == "direct":
        data["source"] = "direct"
        data["url"] = ask("直链URL（或网盘解析后的直链）")
        data["files"] = []
    elif src == "netdisk":
        data["source"] = "netdisk"
        data["provider"] = ask("网盘类型（baidu/quark/ali/other）", "other")
        data["url"] = ask("分享链接（https://pan.baidu.com/s/...）")
    else:
        print("!! 来源不合法，无法上传。")
        sys.exit(1)

    extra = ask("体积GB（可空）")
    if extra:
        data["size_gb"] = float(extra)
    ver = ask("版本号（可空）")
    if ver:
        data["version"] = ver
    tags = ask("标签（逗号分隔，可空）")
    if tags:
        data["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if not data.get("id"):
        data["id"] = f"item-{uuid.uuid4().hex[:6]}"

    ok, missing = store.is_complete(data)
    if not ok:
        print("\n!! 上传未完成，以下字段缺失或非法：")
        for m in missing:
            print("   -", m)
        print("请补齐后重新运行。")
        sys.exit(1)

    print("\n" + "=" * 56)
    print("校验通过！请把以下 JSON 粘贴到 manifest.json 的 content 数组中：")
    print("=" * 56)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("=" * 56)
    print("上传图标：把图标 PNG 放入仓库 icons/ 目录并推送 GitHub，即可生效。")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    data = build()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"已写入: {args.out}")


if __name__ == "__main__":
    main()
