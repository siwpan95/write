# ==============================================================================
# bootstrap.ps1 —— `write` 工作区 · 换机一键部署（Windows 原生）
# ==============================================================================
# 目标：**在新机器上从零到可用，只跑这一条命令。**
#
#   git clone <repo>; cd write; powershell -ExecutionPolicy Bypass -File tools\bootstrap.ps1
#
# 与 bootstrap.sh 等价（同一套纪律、同一套步骤），供 Windows PowerShell /
# PowerShell 7 使用。若在 Git Bash 里，直接 `bash tools/bootstrap.sh` 即可。
#
# 纪律：幂等 / 只读源文件 / 零硬编码路径 / 失败可见
#
# 退出码：0 部署成功 ／ 1 环境不满足 ／ 2 某一步失败
#
# 作者：WorkBuddy ｜ 2026-11-13
# ==============================================================================
[CmdletBinding()]
param(
    # 跳过 npm install（node_modules 已就位时）
    [switch]$SkipInstall,
    # 跳过闸门（只做环境与索引重建）
    [switch]$SkipCheck
)

$ErrorActionPreference = 'Stop'

# --- 定位仓根（本脚本在 tools\ 下） -------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

function Write-Step { param($m) Write-Host ""; Write-Host "▸ $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "  ✓ $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "  ! $m" -ForegroundColor Yellow }
function Write-Die  { param($m, $code = 1) Write-Host ""; Write-Host "✗ $m" -ForegroundColor Red; exit $code }
function Write-Hint { param($m) Write-Host "    $m" -ForegroundColor DarkGray }

Write-Host "╔══════════════════════════════════════════════════════════════╗"
Write-Host "║  write 工作区 · 换机部署（Windows）                          ║"
Write-Host "╚══════════════════════════════════════════════════════════════╝"
Write-Host "  仓根：$RepoRoot"

# ==============================================================================
# 1. 环境自检
# ==============================================================================
Write-Step "1/6 环境自检"

# --- Node ---
$nodeOk = $false
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVer = (node -v).TrimStart('v')
    $nodeMajor = [int]($nodeVer -split '\.')[0]
    if ($nodeMajor -ge 22) {
        Write-Ok "Node $nodeVer"
        $nodeOk = $true
    } else {
        Write-Warn "Node $nodeVer 版本过低（需要 >= 22）"
    }
} else {
    Write-Warn "未找到 node —— Node 依赖（cordis）无法安装"
    Write-Hint "装 Node 22+：https://nodejs.org/  或  winget install OpenJS.NodeJS"
}

# --- Python ---
$pythonExe = $null
$pyCandidates = @()
if ($env:PYTHON)    { $pyCandidates += $env:PYTHON }
if ($env:WRITE_PYTHON) { $pyCandidates += $env:WRITE_PYTHON }
foreach ($cmd in @('python', 'python3', 'py')) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($c) { $pyCandidates += $c.Source }
}
# Windows 常见安装位置（用通配而非写死版本）
$pyCandidates += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
$pyCandidates += Get-ChildItem -Path "C:\Program Files\Python3*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }

foreach ($cand in $pyCandidates) {
    if (-not $cand) { continue }
    try {
        & $cand -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonExe = $cand; break }
    } catch { }
}
if ($pythonExe) {
    $pyVer = (& $pythonExe -V 2>&1) -join ' '
    Write-Ok "Python $pyVer （$pythonExe）"
} else {
    Write-Warn "未找到 Python 3.9+ —— PKM 内核与检查器无法运行"
    Write-Hint "装 Python：https://www.python.org/downloads/  （勾选 Add to PATH）"
}

# --- git ---
$gitExe = $null
$g = Get-Command git -ErrorAction SilentlyContinue
if ($g) { $gitExe = $g.Source }
if (-not $gitExe) {
    # 常见安装位置（PortableGit / Git for Windows / Scoop / winget）
    $gitCandidates = @(
        "$env:ProgramFiles\Git\cmd\git.exe",
        "${env:ProgramFiles(x86)}\Git\cmd\git.exe",
        "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe",
        "$env:USERPROFILE\scoop\apps\git\current\cmd\git.exe",
        "C:\PortableGit\cmd\git.exe",
        # Git Bash 自带的 mingw64（WorkBuddy 内置 PortableGit 即此形态）
        "C:\Program Files\Git\mingw64\bin\git.exe",
        "$env:USERPROFILE\.workbuddy\binaries\git\mingw64\bin\git.exe"
    )
    # WorkBuddy 内置 PortableGit（apps/<App>/resources/vendor/PortableGit）
    $gitCandidates += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs" -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName 'resources\vendor\PortableGit\mingw64\bin\git.exe' }
    foreach ($cand in $gitCandidates) {
        if (Test-Path $cand) { $gitExe = $cand; break }
    }
}
if (-not $gitExe) {
    # 兜底：在常见根目录浅层搜索（不无限递归，避免慢）
    foreach ($base in @("$env:LOCALAPPDATA\Programs", "$env:ProgramFiles", "${env:ProgramFiles(x86)}")) {
        if (-not (Test-Path $base)) { continue }
        $hit = Get-ChildItem -Path $base -Filter 'git.exe' -Recurse -Depth 3 -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -match '\\cmd\\git\.exe$|\\bin\\git\.exe$' } |
               Select-Object -First 1
        if ($hit) { $gitExe = $hit.FullName; break }
    }
}
if ($gitExe) {
    $gitVer = (& $gitExe --version) -replace '^git version ', ''
    Write-Ok "git $gitVer"

    # ⚠️ PortableGit 布局陷阱（本机实测踩过）：
    #   辅助程序 git-remote-https.exe 实际位于 `<PortableGit>/mingw64/bin/`，
    #   而 git 默认推导的 exec-path 是 `<PortableGit>/mingw64/libexec/git-core/`。
    #   两者不一致 → 任何 https 远端操作报
    #   「git: 'remote-https' is not a git command」。
    # 修法：把 cmd 目录加进 PATH（供命令名调用），并显式设 GIT_EXEC_PATH
    # 指向辅助程序真实所在处。
    $gitBinDir = Split-Path -Parent $gitExe
    $portableRoot = Split-Path -Parent (Split-Path -Parent $gitBinDir)
    $gitCmdDir = Join-Path $portableRoot 'cmd'
    if (Test-Path $gitCmdDir) { $env:Path = "$gitCmdDir;$env:Path" }
    $env:Path = "$gitBinDir;$env:Path"
    if (Test-Path (Join-Path $gitBinDir 'git-remote-https.exe')) {
        $env:GIT_EXEC_PATH = $gitBinDir
    }
} else {
    Write-Warn "未找到 git —— 版本同步会失效"
    Write-Hint "装 Git：https://git-scm.com/download/win  或  winget install Git.Git"
}

if (-not $nodeOk)   { Write-Die "Node 22+ 是硬依赖（cordis 编排层）。装好后重跑本脚本。" 1 }
if (-not $pythonExe) { Write-Die "Python 3.9+ 是硬依赖（PKM 内核 + 检查器）。装好后重跑本脚本。" 1 }

$env:WRITE_PYTHON = $pythonExe

# ==============================================================================
# 2. 装 Node 依赖
# ==============================================================================
Write-Step "2/6 安装 Node 依赖（cordis 等；node_modules 不入库）"
if ($SkipInstall) {
    Write-Ok "已指定 -SkipInstall —— 跳过"
} elseif ((Test-Path 'node_modules\cordis')) {
    Write-Ok "node_modules 已存在且含 cordis —— 跳过安装（幂等）"
} elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    npm install --no-audit --no-fund 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Write-Ok "依赖安装完成"
} else {
    Write-Die "未找到 npm —— 无法安装 cordis。装 Node 22+（自带 npm）后重跑。" 1
}

# ==============================================================================
# 3. 重建 PKM 索引 + 图谱 + MOC
# ==============================================================================
Write-Step "3/6 重建 PKM 索引 / 图谱 / MOC（派生产物，10 秒）"
& $pythonExe tools/pkm/pkm_cli.py build --root $RepoRoot 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
if ($LASTEXITCODE -ne 0) { Write-Die "PKM 构建失败（退出码 $LASTEXITCODE）" 2 }
Write-Ok "PKM 产物已生成"

# ==============================================================================
# 4. 跑闸门
# ==============================================================================
Write-Step "4/6 跑闸门（npm run check）"
if ($SkipCheck) {
    Write-Ok "已指定 -SkipCheck —— 跳过"
} else {
    node tools/host.mjs check 2>&1 | Out-File -Encoding utf8 "$env:TEMP\write-check.log"
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Ok "闸门通过 —— ERROR 0，可放行"
    } else {
        Get-Content "$env:TEMP\write-check.log" -Tail 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        if ($exitCode -eq 1) {
            Write-Warn "闸门有 ERROR —— 见 审校报告\工具链自检报告-*.md"
            Write-Hint "这不阻塞部署：PKM 部署已完成，只是仓内内容有待处理的问题"
            Write-Hint "若 ERROR 来自 sync 检查器（远端落后），执行 git push <远端> master"
        } else {
            Write-Die "闸门执行失败（退出码 $exitCode）" 2
        }
    }
}

# ==============================================================================
# 5. 双端同步（可选 · 尽力而为）
# ==============================================================================
Write-Step "5/6 同步远端（Gitee + GitHub · 尽力而为）"
$branch = (git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null)
if (-not $branch) { $branch = 'master' }
foreach ($remote in @('origin', 'github')) {
    git -C $RepoRoot remote get-url $remote *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "远端 $remote 未配置 —— 跳过"
        continue
    }
    # GitHub 直连在部分网络下被阻断，且**间歇性抖动**（实测：失败后重试即通）。
    # 故重试 3 次，每次间隔 3 秒；仍失败则降级为警告，不阻断部署。
    $pushed = $false
    for ($i = 1; $i -le 3; $i++) {
        $env:GIT_TERMINAL_PROMPT = '0'
        # 用**命令名** `git` 调用（PATH 已在上文加入 PortableGit 的 cmd 目录）——
        # 用绝对路径调 git.exe 会丢 exec-path，导致「remote-https is not a git command」。
        # 同时用 `-C $RepoRoot` 显式指定仓库，不依赖调用者的当前目录。
        git -C $RepoRoot push $remote $branch *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "$remote 已同步"
            $pushed = $true
            break
        }
        if ($i -lt 3) { Start-Sleep -Seconds 3 }
    }
    if (-not $pushed) {
        # 区分两种失败：**网络不可达** vs **历史分叉**。
        # 分叉时普通 push 会被拒（need to pull），但内容可能已在新提交里
        # （rebase 重写 hash 的典型症状）—— 这时该强推，而不是盲目 pull。
        $remoteLine = & $gitExe -C $RepoRoot ls-remote $remote "refs/heads/$branch" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $remoteSha = ($remoteLine -split '\s+')[0]
            $localSha = (& $gitExe -C $RepoRoot rev-parse HEAD).Trim()
            if ($remoteSha -and $remoteSha -ne $localSha) {
                & $gitExe -C $RepoRoot merge-base --is-ancestor $remoteSha HEAD 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-Warn "$remote 远端领先本地（本地含远端提交，但尚未推送）"
                    Write-Hint "直接推送即可：git push $remote $branch"
                } else {
                    Write-Warn "$remote 与本地**历史分叉**（本地已 rebase/重写过 hash）"
                    Write-Hint "先备份远端旧历史，再安全强推："
                    Write-Hint "  git branch backup/pre-push-$remote $remote/master"
                    Write-Hint "  git push --force-with-lease $remote $branch"
                    Write-Hint "（--force-with-lease 比 --force 安全：远端若又有新提交会拒绝）"
                }
            } else {
                Write-Warn "$remote 推送失败（已重试 3 次）"
                Write-Hint "恢复网络后手动补推：git push $remote $branch"
            }
        } else {
            Write-Warn "$remote 推送失败（已重试 3 次）—— 常见于 GitHub 直连被阻断"
            Write-Hint "恢复网络后手动补推：git push $remote $branch"
        }
    }
}

# ==============================================================================
# 6. 产物失配检测（入库产物是否与实际状态同步）
# ==============================================================================
Write-Step "6/6 产物失配检测（入库产物 vs 实际状态）"
# 新增笔记/改设定后，连接图谱会变，而入库产物（graph.json / MOC）不会自动跟着变。
# 若不失配检测，指标（如「孤立率 0.0%」）会悄悄失真 —— 且没人会发现。
& $gitExe -C $RepoRoot diff --quiet -- PKM/ 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "入库产物与工作区一致"
} else {
    Write-Warn "入库产物已失配 —— PKM/ 下有未提交的重建结果"
    Write-Hint "原因：新增笔记或改动设定后，连接图谱变了"
    Write-Hint "处理：npm run pkm:build && git add PKM/ && git commit -m 'chore(PKM): 重建入库产物'"
}

# ==============================================================================
# 完成
# ==============================================================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  部署完成                                                       ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  常用命令："
Write-Host "    npm run pkm:search <关键词>      全仓检索（中文分词，零依赖）"
Write-Host "    npm run pkm:links <文档路径>     查某文档的出链 / 入链"
Write-Host "    npm run pkm:build                重建索引 + 图谱 + MOC"
Write-Host "    npm run check                    跑全闸门（含 PKM 连接层体检）"
Write-Host "    npm run pkm:doctor               环境自检"
Write-Host ""
Write-Host "  文档入口："
Write-Host "    PKM\MOC-全库.md                          全库内容地图"
Write-Host "    PKM\01-MOC\MOC-跨项目知识网络.md          跨项目导航"
Write-Host "    PKM\00-原子笔记\guide-0001-PKM连接层使用指南.md   使用指南"
Write-Host ""
Write-Host "  可选：装 Obsidian 后「Open folder as vault」指向本仓根目录，"
Write-Host "        即可获得图形化双链与图谱视图（Markdown 原生，无需迁移）。"
Write-Host ""

exit 0
