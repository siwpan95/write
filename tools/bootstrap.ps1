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
Write-Step "1/4 环境自检"

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
    $env:Path = "$(Split-Path -Parent $gitExe);$env:Path"
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
Write-Step "2/4 安装 Node 依赖（cordis 等；node_modules 不入库）"
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
Write-Step "3/4 重建 PKM 索引 / 图谱 / MOC（派生产物，10 秒）"
& $pythonExe tools/pkm/pkm_cli.py build --root $RepoRoot 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
if ($LASTEXITCODE -ne 0) { Write-Die "PKM 构建失败（退出码 $LASTEXITCODE）" 2 }
Write-Ok "PKM 产物已生成"

# ==============================================================================
# 4. 跑闸门
# ==============================================================================
Write-Step "4/4 跑闸门（npm run check）"
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
        } else {
            Write-Die "闸门执行失败（退出码 $exitCode）" 2
        }
    }
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
