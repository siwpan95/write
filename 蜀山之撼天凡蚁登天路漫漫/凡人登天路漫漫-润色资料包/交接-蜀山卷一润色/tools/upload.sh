#!/usr/bin/env bash
# 上传单个交付件到知识库
# 用法：bash tools/upload.sh "/sandbox/workspace/凡人登天路漫漫-第110至114章-润色稿.docx"
set -e
FILE="$1"
if [ -z "$FILE" ]; then echo "用法: bash tools/upload.sh <docx绝对路径>"; exit 1; fi
cd /sandbox/workspace/skills/ima-knowledge
python3 scripts/upload_file.py \
  --file-path "$FILE" \
  --knowledge-base-id "ima_kb_UDyaN3jL" \
  --rename "$(basename "$FILE")"
