#!/usr/bin/env bash
# ==============================================================================
# bootstrap.sh —— `write` 工作区 · 换机一键部署
# ==============================================================================
# 目标：**在新机器上从零到可用，只跑这一条命令。**
#
#   git clone <repo> && cd write && bash tools/bootstrap.sh
#
# 做七件事：
#   1. 环境自检（Node / Python / git）
#   2. 装 Node 依赖（cordis 等；node_modules 不入库）
#   3. 装 Python 依赖（requirements.txt；闸门增强层用）
#   4. 重建 PKM 索引 + 图谱 + MOC（派生产物，10 秒）
#   5. 跑一遍闸门（npm run check），确认放行
#   6. 尽力而为地同步远端（Gitee + GitHub，重试 3 次）
#   7. 产物失配检测（入库产物 vs 实际状态）
#
# 纪律：
#   · **幂等** —— 重复跑安全，不会破坏已有内容。
#   · **只读源文件** —— 不修改任何 Markdown（PKM 内核只读）。
#   · **零硬编码路径** —— 不写死盘符/用户名，一切相对仓根。
#   · **失败可见** —— 任一步失败即中止并报出原因，不静默跳过。
#
# 关于 Python 依赖（2026-11-21 增补）
# ----------------------------------
# `requirements.txt` 声明**闸门增强层**的依赖（当前只有 dse-core）。
# 核心内核（doc_review / pkm / metrics / rules / prose-style）仍是
# 纯标准库 —— 缺依赖只影响增强层检查器，不影响核心闸门。
# 依赖缺失时 dse 检查器**报 ERROR 并给出安装指引**，不静默跳过
# （廓者未名夜的教训：不在扫描视角内的「通过」等于闸门失效）。
#
# 退出码：0 部署成功 ／ 1 环境不满足 ／ 2 某一步失败
#
# 作者：WorkBuddy ｜ 2026-11-13
# ==============================================================================
set -euo pipefail

# --- 定位仓根（本脚本在 tools/ 下） -------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# --- 输出helpers -------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'
  C_INFO=$'\033[36m'; C_DIM=$'\033[2m'; C_END=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_ERR=""; C_INFO=""; C_DIM=""; C_END=""
fi

step() { printf "\n%s▸ %s%s\n" "$C_INFO" "$1" "$C_END"; }
ok()   { printf "  %s✓%s %s\n" "$C_OK" "$C_END" "$1"; }
warn() { printf "  %s!%s %s\n" "$C_WARN" "$C_END" "$1"; }
die()  { printf "\n%s✗ %s%s\n" "$C_ERR" "$1" "$C_END" >&2; exit "${2:-1}"; }
hint() { printf "    %s%s%s\n" "$C_DIM" "$1" "$C_END"; }

printf "%s\n" "╔══════════════════════════════════════════════════════════════╗"
printf "%s\n" "║  write 工作区 · 换机部署                                      ║"
printf "%s\n" "╚══════════════════════════════════════════════════════════════╝"
printf "  仓根：%s\n" "$REPO_ROOT"

# ==============================================================================
# 1. 环境自检
# ==============================================================================
step "1/7 环境自检"

# --- Node ---
NODE_OK=0
if command -v node >/dev/null 2>&1; then
  NODE_VER="$(node -v)"
  NODE_MAJOR="$(printf '%s' "$NODE_VER" | sed 's/^v//' | cut -d. -f1)"
  if [ "$NODE_MAJOR" -ge 22 ] 2>/dev/null; then
    ok "Node $NODE_VER"
    NODE_OK=1
  else
    warn "Node $NODE_VER 版本过低（需要 >= 22，engines 字段要求）"
  fi
else
  warn "未找到 node —— Node 依赖（cordis）无法安装"
  hint "装 Node 22+：https://nodejs.org/  或  winget install OpenJS.NodeJS"
fi

# --- Python ---
# 关键：**必须与工具链实际使用的解释器一致**。
# 各自探测会装错地方 —— 本机实测：PATH 上的 python 指向 E 盘 Python314，
# 而 Cordis 的 findPython 选的是 WorkBuddy 托管的 envs/default。
# 依赖装到 A、闸门用 B ⇒ 增强层检查器（dse）在闸门侧静默降级。
# 故先问 Cordis（单一真理源），问不到再退回本地探测。
PYTHON=""
# 路径走 stderr（cordis logger 写 stdout，混在一起会拿到多行垃圾）
CORDIS_PY="$(node tools/host.mjs python 2>&1 >/dev/null | tail -1 || true)"
if [ -n "$CORDIS_PY" ] && [ -x "$CORDIS_PY" ]; then
  PYTHON="$CORDIS_PY"
  ok "Python $("$PYTHON" -V 2>&1) （工具链实际使用：$PYTHON）"
else
  for cand in \
    "${PYTHON:-}" "${WRITE_PYTHON:-}" \
    "$(command -v python3 2>/dev/null || true)" \
    "$(command -v python 2>/dev/null || true)" \
    "$(command -v py 2>/dev/null || true)"
  do
    [ -n "$cand" ] || continue
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" 2>/dev/null; then
        PYTHON="$cand"
        break
      fi
    fi
  done
  # Windows 常见安装位置（不写死具体用户名/版本）
  if [ -z "$PYTHON" ]; then
    for cand in "$LOCALAPPDATA/Programs/Python/Python3"*/python.exe \
                "$LOCALAPPDATA/Programs/Python/Python3"*/python3.exe \
                "/c/Program Files/Python3"*/python.exe; do
      if [ -x "$cand" ]; then PYTHON="$cand"; break; fi
    done
  fi
  if [ -n "$PYTHON" ]; then
    ok "Python $("$PYTHON" -V 2>&1) （$PYTHON）"
    warn "未取到工具链实际使用的解释器（node tools/host.mjs python 失败）"
    hint "依赖可能装到与闸门不同的解释器 —— 装完请用 `npm run doctor` 复核"
  else
    warn "未找到 Python 3.9+ —— PKM 内核与检查器无法运行"
    hint "装 Python：https://www.python.org/downloads/  （勾选 Add to PATH）"
  fi
fi

# --- git ---
if command -v git >/dev/null 2>&1; then
  ok "git $(git --version | awk '{print $3}')"
else
  warn "未找到 git —— 本脚本不强制要求，但版本同步会失效"
fi

[ "$NODE_OK" -eq 1 ] || die "Node 22+ 是硬依赖（cordis 编排层）。装好后重跑本脚本。" 1
[ -n "$PYTHON" ]     || die "Python 3.9+ 是硬依赖（PKM 内核 + 检查器）。装好后重跑本脚本。" 1

# 记录 Python 路径，供 npm 脚本复用（不写死，只在本机环境变量里）
export WRITE_PYTHON="$PYTHON"

# ==============================================================================
# 2. 装 Node 依赖
# ==============================================================================
step "2/7 安装 Node 依赖（cordis 等；node_modules 不入库）"
if [ -d node_modules ] && [ -d node_modules/cordis ]; then
  ok "node_modules 已存在且含 cordis —— 跳过安装（幂等）"
else
  if command -v npm >/dev/null 2>&1; then
    npm install --no-audit --no-fund 2>&1 | sed 's/^/    /'
    ok "依赖安装完成"
  else
    die "未找到 npm —— 无法安装 cordis。装 Node 22+（自带 npm）后重跑。" 1
  fi
fi

# ==============================================================================
# 3. 装 Python 依赖
# ==============================================================================
step "3/7 安装 Python 依赖（requirements.txt · 闸门增强层）"
if [ ! -f requirements.txt ]; then
  warn "无 requirements.txt —— 跳过（核心内核不依赖三方包，仍可运行）"
else
  # 幂等：已装的跳过。--disable-pip-version-check 避免刷屏。
  PIP_ARGS="--disable-pip-version-check --no-input"
  if "$PYTHON" -m pip --version >/dev/null 2>&1; then
    # 先探测是否已满足（避免每次都联网）
    NEED_PIP=0
    if ! "$PYTHON" -c "import dse_core" >/dev/null 2>&1; then
      NEED_PIP=1
    fi
    if [ "$NEED_PIP" -eq 0 ]; then
      ok "Python 依赖已就绪（dse_core 可导入）—— 跳过安装（幂等）"
    else
      if "$PYTHON" -m pip install $PIP_ARGS -r requirements.txt 2>&1 | sed 's/^/    /'; then
        ok "Python 依赖安装完成"
      else
        warn "Python 依赖安装失败 —— 增强层检查器（dse）将报 ERROR"
        hint "手动重试：$PYTHON -m pip install -r requirements.txt"
        hint "不影响核心闸门（doc_review / pkm / metrics 等仍可运行）"
      fi
    fi
  else
    warn "pip 不可用 —— 跳过 Python 依赖安装"
    hint "装 pip：$PYTHON -m ensurepip --upgrade"
  fi
fi

# ==============================================================================
# 4. 重建 PKM 索引 + 图谱 + MOC
# ==============================================================================
step "4/7 重建 PKM 索引 / 图谱 / MOC（派生产物，10 秒）"
"$PYTHON" tools/pkm/pkm_cli.py build --root "$REPO_ROOT" 2>&1 | sed 's/^/    /'
ok "PKM 产物已生成"

# ==============================================================================
# 5. 跑闸门
# ==============================================================================
step "5/7 跑闸门（npm run check）"
if node tools/host.mjs check >/tmp/write-check.log 2>&1; then
  ok "闸门通过 —— ERROR 0，可放行"
else
  EXIT=$?
  tail -20 /tmp/write-check.log | sed 's/^/    /'
  if [ "$EXIT" -eq 1 ]; then
    warn "闸门有 ERROR —— 见上方报告（审校报告/工具链自检报告-*.md）"
    hint "这不阻塞部署：PKM 部署已完成，只是仓内内容有待处理的问题"
    hint "若 ERROR 来自 sync 检查器（远端落后），执行 git push <远端> master"
  else
    die "闸门执行失败（退出码 $EXIT）" 2
  fi
fi

# ==============================================================================
# 5. 双端同步（可选 · 尽力而为）
# ==============================================================================
step "6/7 同步远端（Gitee + GitHub · 尽力而为）"
CUR_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo master)"
for remote in origin github; do
  if ! git -C "$REPO_ROOT" remote get-url "$remote" >/dev/null 2>&1; then
    warn "远端 $remote 未配置 —— 跳过"
    continue
  fi
  # GitHub 直连在部分网络下被阻断，且**间歇性抖动**（实测：失败后重试即通）。
  # 故重试 3 次，每次间隔 3 秒；仍失败则降级为警告，不阻断部署。
  PUSHED=0
  for attempt in 1 2 3; do
    # `-C "$REPO_ROOT"` —— 不依赖调用者的当前目录
    if GIT_TERMINAL_PROMPT=0 git -C "$REPO_ROOT" push "$remote" "$CUR_BRANCH" >/dev/null 2>&1; then
      ok "$remote 已同步"
      PUSHED=1
      break
    fi
    [ "$attempt" -lt 3 ] && sleep 3
  done

  if [ "$PUSHED" -eq 0 ]; then
    # 区分两种失败：**网络不可达** vs **历史分叉**。
    # 分叉时普通 push 会被拒（need to pull），但内容可能已在新提交里
    # （rebase 重写 hash 的典型症状）—— 这时该强推，而不是盲目 pull。
    if git -C "$REPO_ROOT" ls-remote "$remote" >/dev/null 2>&1; then
      REMOTE_SHA="$(git -C "$REPO_ROOT" ls-remote "$remote" "refs/heads/$CUR_BRANCH" | cut -f1)"
      LOCAL_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
      if [ -n "$REMOTE_SHA" ] && [ "$REMOTE_SHA" != "$LOCAL_SHA" ]; then
        # 远端可达但 sha 不同 → 是分叉，不是网络问题
        if git -C "$REPO_ROOT" merge-base --is-ancestor "$REMOTE_SHA" HEAD 2>/dev/null; then
          warn "$remote 远端领先本地（本地含远端提交，但尚未推送）"
          hint "直接推送即可：git push $remote $CUR_BRANCH"
        else
          warn "$remote 与本地**历史分叉**（本地已 rebase/重写过 hash）"
          hint "先备份远端旧历史，再安全强推："
          hint "  git branch backup/pre-push-$remote $remote/master"
          hint "  git push --force-with-lease $remote $CUR_BRANCH"
          hint "（--force-with-lease 比 --force 安全：远端若又有新提交会拒绝）"
        fi
      else
        warn "$remote 推送失败（已重试 3 次）"
        hint "恢复网络后手动补推：git push $remote $CUR_BRANCH"
      fi
    else
      warn "$remote 推送失败（已重试 3 次）—— 常见于 GitHub 直连被阻断"
      hint "恢复网络后手动补推：git push $remote $CUR_BRANCH"
    fi
  fi
done

# ==============================================================================
# 6. 产物失配检测（入库产物是否与实际状态同步）
# ==============================================================================
step "7/7 产物失配检测（入库产物 vs 实际状态）"
# 新增笔记/改设定后，连接图谱会变，而入库产物（graph.json / MOC）不会自动跟着变。
# 若不失配检测，指标（如「孤立率 0.0%」）会悄悄失真 —— 且没人会发现。
if git -C "$REPO_ROOT" diff --quiet -- PKM/ 2>/dev/null; then
  ok "入库产物与工作区一致"
else
  warn "入库产物已失配 —— PKM/ 下有未提交的重建结果"
  hint "原因：新增笔记或改动设定后，连接图谱变了"
  hint "处理：npm run pkm:build && git add PKM/ && git commit -m 'chore(PKM): 重建入库产物'"
fi

# ==============================================================================
# 完成
# ==============================================================================
cat <<EOF

$(printf "%s" "$C_OK")╔══════════════════════════════════════════════════════════════╗
║  部署完成                                                       ║
╚══════════════════════════════════════════════════════════════╝$(printf "%s" "$C_END")

  常用命令：
    npm run pkm:search <关键词>      全仓检索（中文分词，零依赖）
    npm run pkm:links <文档路径>     查某文档的出链 / 入链
    npm run pkm:build                重建索引 + 图谱 + MOC
    npm run check                    跑全闸门（含 PKM 连接层体检）
    npm run pkm:doctor               环境自检

  文档入口：
    PKM/MOC-全库.md                  全库内容地图
    PKM/01-MOC/MOC-跨项目知识网络.md 跨项目导航
    PKM/00-原子笔记/guide-0001-PKM连接层使用指南.md   使用指南

  可选：装 Obsidian 后「Open folder as vault」指向本仓根目录，
        即可获得图形化双链与图谱视图（Markdown 原生，无需迁移）。

EOF

exit 0
