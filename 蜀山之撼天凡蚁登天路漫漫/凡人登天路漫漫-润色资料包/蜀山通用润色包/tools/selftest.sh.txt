#!/usr/bin/env bash
# 自检：四项全绿再开工
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"
FAIL=0

echo "== 1. Python 与依赖"
python3 -c "import sys;assert sys.version_info>=(3,8);print('  python',sys.version.split()[0])" || FAIL=1
python3 -c "import docx;print('  python-docx',docx.__version__ if hasattr(docx,'__version__') else 'ok')" 2>/dev/null || { echo "  ! 缺 python-docx：pip install python-docx"; FAIL=1; }

echo "== 2. 配置"
python3 - <<'PY'
import json,sys,os
c=json.load(open('config.json',encoding='utf-8'))
need=['book','kb_id','src_dir','draft_dir','out_dir','min_han']
miss=[k for k in need if k not in c]
if miss: print('  ! 缺少字段：',miss); sys.exit(1)
print('  书名：%s' % c['book'])
print('  知识库：%s' % c['kb_id'])
print('  原稿目录：%s %s' % (c['src_dir'], '存在' if os.path.isdir(c['src_dir']) else '不存在!'))
print('  草稿目录：%s %s' % (c['draft_dir'], '存在' if os.path.isdir(c['draft_dir']) else '不存在!'))
print('  下限：%s 汉字' % c['min_han'])
sys.exit(0 if os.path.isdir(c['src_dir']) else 1)
PY
[ $? -ne 0 ] && FAIL=1

echo "== 3. count.py 判定能力"
python3 - <<'PY'
import subprocess,sys,os,tempfile
ok_text = "第1章 试验\n\n" + ("他数了三遍，数出来的数是一样的，一个也没有漏。\n\n"*180)
bad_text = "第1章 试验\n\n（他站着。）\n\n（他等着。）\n"
d=tempfile.mkdtemp()
p1=os.path.join(d,'ch900.md'); p2=os.path.join(d,'ch901.md')
open(p1,'w',encoding='utf-8').write(ok_text)
open(p2,'w',encoding='utf-8').write(bad_text)
r1=subprocess.run([sys.executable,'tools/count.py',p1,'--quiet'],capture_output=True,text=True)
r2=subprocess.run([sys.executable,'tools/count.py',p2,'--quiet'],capture_output=True,text=True)
print('  合格样稿 →', 'PASS' if r1.returncode==0 else 'FAIL（工具判定异常）')
print('  不合格样稿 →', 'PASS（工具漏判）' if r2.returncode==0 else 'FAIL 正确')
sys.exit(0 if r1.returncode==0 and r2.returncode!=0 else 1)
PY
[ $? -ne 0 ] && FAIL=1

echo "== 4. extract.py 取章"
python3 - <<'PY'
import subprocess,sys
r=subprocess.run([sys.executable,'tools/extract.py','--scan'],capture_output=True,text=True)
lines=[l for l in r.stdout.splitlines() if l.strip()]
if lines:
    print('  可识别章节：%d 章（例：%s）' % (len(lines), lines[0].strip()[:40]))
    sys.exit(0)
print('  ! 原稿目录里没有识别到章标题（需 # 第 N 章 或 第N章）')
sys.exit(1)
PY
[ $? -ne 0 ] && FAIL=1

echo
if [ $FAIL -eq 0 ]; then
  echo "全部通过，可以开工。"
else
  echo "有红项，先修再开工。"
fi
exit $FAIL
