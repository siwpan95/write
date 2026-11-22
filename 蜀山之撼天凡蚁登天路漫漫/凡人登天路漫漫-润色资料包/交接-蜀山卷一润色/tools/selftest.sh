#!/usr/bin/env bash
# 自检：确认三个工具在本机可用
set -e
cd "$(dirname "$0")/.."
echo "== 1. extract 能否取到原稿（第111章） =="
python3 tools/extract.py 111 --limit 300 | head -8
echo
echo "== 2. count 能否统计样板章 =="
python3 tools/count.py samples/第108章-一页.md samples/第109章-记住.md || true
echo
echo "== 3. build 参数是否正常 =="
python3 tools/build.py --help | head -6
echo
echo "自检结束。若上面三段都有输出，工具可用。"
