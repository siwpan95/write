#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_package.py —— 一键打包交付物

把整个 kit 目录压成 zip，默认输出到 <workspace>/output/。
自动排除：__pycache__、.DS_Store、旧 zip、临时文件。

用法
    python3 build_package.py
    python3 build_package.py --name 《我给第四天灾发任务》开书工程包.zip
    python3 build_package.py --list        # 只列清单不打包
"""

import argparse
import datetime as dt
import os
import sys
import zipfile
from pathlib import Path

EXCLUDE_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "node_modules"}
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".zip", ".tmp", ".log"}


def iter_files(root: Path, exclude_zip: Path | None = None):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if fn in EXCLUDE_NAMES or p.suffix in EXCLUDE_SUFFIX:
                continue
            if exclude_zip and p.resolve() == exclude_zip.resolve():
                continue
            yield p


def guess_output_dir(kit_root: Path) -> Path:
    """优先 /sandbox/workspace/output，其次 kit 同级 output，最后 kit 内部。"""
    candidates = [Path("/sandbox/workspace/output"), kit_root.parent / "output", kit_root / "output"]
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            return c
        except OSError:
            continue
    raise RuntimeError("找不到可写的输出目录")


def main(argv=None):
    ap = argparse.ArgumentParser(description="打包开书工程包")
    ap.add_argument("--name", default=None, help="zip 文件名")
    ap.add_argument("--list", action="store_true", help="只列清单")
    args = ap.parse_args(argv)

    kit_root = Path(__file__).resolve().parent.parent
    stamp = dt.datetime.now().strftime("%Y%m%d")
    name = args.name or f"虚拟网游开书工程包_{stamp}.zip"
    out_dir = guess_output_dir(kit_root)
    out = out_dir / name

    files = sorted(iter_files(kit_root, exclude_zip=out))
    if not files:
        print("[x] 目录是空的", file=sys.stderr)
        return 1

    if args.list:
        total = 0
        for f in files:
            size = f.stat().st_size
            total += size
            print(f"{size/1024:8.1f} KB  {f.relative_to(kit_root)}")
        print(f"\n共 {len(files)} 个文件，{total/1024/1024:.2f} MB")
        return 0

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            z.write(f, Path(kit_root.name) / f.relative_to(kit_root))

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"[√] 打包完成：{out}")
    print(f"    文件数：{len(files)}｜压缩后：{size_mb:.2f} MB")
    print("\n目录结构：")
    for f in files:
        print("  ", f.relative_to(kit_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
