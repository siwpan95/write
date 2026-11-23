#!/usr/bin/env bash
# 单文件上传：bash tools/upload.sh <docx 绝对路径>
set -e
if [ $# -lt 1 ]; then
  echo "用法：bash tools/upload.sh /abs/path/file.docx"
  exit 3
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
KB=$(python3 -c "import json,sys;print(json.load(open('$ROOT/config.json',encoding='utf-8'))['kb_id'])")
if [ -z "$UP" ]; then echo "未设置 POLISH_UPLOAD_SCRIPT（上传脚本由项目环境提供），已跳过上传。"; exit 0; fi

UP="${POLISH_UPLOAD_SCRIPT:-}"  # 由项目环境提供；未设置则报错退出
if [ ! -f "$UP" ]; then
  echo "未找到上传脚本：$UP"
  exit 3
fi
python3 "$UP" --file-path "$1" --knowledge-base-id "$KB"
