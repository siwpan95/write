#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 motifs.json 注入 template.html，产出单文件工作台 horror_lab.html。

用法：
    python build/build.py            # 构建
    python build/build.py --check    # 构建后用 node 跑一遍逻辑验证

设计：产物是**单文件、零依赖、双击即用**的 HTML——给不装环境的人用。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT.parent
DATA = TOOLS / "generator" / "motifs.json"
TPL = ROOT / "template.html"
OUT = TOOLS / "horror_lab.html"


def build():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    slim = {
        "formula": data["formula"],
        "temperatures": data["temperatures"],
        "motifs": data["motifs"],
    }
    payload = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
    tpl = TPL.read_text(encoding="utf-8")
    if "/*__DATA__*/" not in tpl:
        print("❌ 模板缺少注入点 /*__DATA__*/", file=sys.stderr)
        return 1
    html = tpl.replace("/*__DATA__*/", payload)
    OUT.write_text(html, encoding="utf-8")
    kb = len(html.encode("utf-8")) / 1024
    print(f"✅ {OUT.name}  {kb:.1f} KB  ({len(slim['motifs'])} 母题 / {len(slim['temperatures'])} 温度)")
    return 0


def verify():
    node = shutil.which("node")
    if not node:
        print("⚠ 未找到 node，跳过逻辑验证")
        return 0
    print("\n运行逻辑验证（最小 DOM stub）…")
    r = subprocess.run([node, str(ROOT / "verify_lab.js")], cwd=ROOT)
    return r.returncode


if __name__ == "__main__":
    rc = build()
    if rc == 0 and "--check" in sys.argv:
        rc = verify()
    sys.exit(rc)
