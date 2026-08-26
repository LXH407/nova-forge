# -*- coding: utf-8 -*-
"""NovaForge 入口。
  - 无参数：启动图形界面
  - 带 --cli：控制台下载模式（打包成单文件 EXE 后，GUI 通过该模式拉起独立控制台做全自动下载）
  - 带 --publish：内容上传引导工具（管理员）
"""
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _write_crash(e):
    """窗口版无控制台，把启动异常写到日志，便于排查。"""
    try:
        from app import config
        p = os.path.join(config.logs_dir(), "startup.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n=== 启动异常 %s ===\n%s\n" % (__import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                                                     traceback.format_exc()))
    except Exception:
        pass


def _dispatch():
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--cli":
            from cli.download_cli import main as cli_main
            sys.exit(cli_main(sys.argv[2:]))
        if len(sys.argv) > 1 and sys.argv[1] == "--publish":
            from tools.publish import main as pub_main
            sys.exit(pub_main(sys.argv[2:]))
        from app.ui import main
        main()
    except Exception:
        _write_crash(sys.exc_info()[1])
        raise


if __name__ == "__main__":
    _dispatch()
