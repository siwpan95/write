$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dir = 'C:\Users\Administrator\Desktop\小说\第一卷'
$targets = @('第02章-记忆融合，两世为人.txt','第04章-废土格局与力量路线.txt','第05章-金手指登场.txt','第06章-验证机制，锁定工厂.txt')
foreach ($f in $targets) {
  $p = Join-Path $dir $f
  $raw = [System.IO.File]::ReadAllText($p)
  $han = ([regex]::Matches($raw, '[\u4e00-\u9fff]')).Count
  $dash = ([regex]::Matches($raw, '\u2014{2}')).Count
  $nb = ([regex]::Matches($raw, '不是[^。！？\n]{0,30}，而是')).Count
  $weak = ([regex]::Matches($raw, '微微|淡淡|缓缓|轻轻|悄然|默默|隐隐')).Count
  $fw = ([regex]::Matches($raw, '仿佛|宛如|似乎')).Count
  $ft = ([regex]::Matches($raw, '废土')).Count
  $fs = ([regex]::Matches($raw, '辐射')).Count
  $cm = ([regex]::Matches($raw, '沉默')).Count
  $sm = ([regex]::Matches($raw, '这就是|终于明白|从这一刻起')).Count
  $cmax = [math]::Ceiling($han / 1000.0 * 3)
  $fmax = [math]::Ceiling($han / 1000.0 * 2)
  $b = [System.IO.File]::ReadAllBytes($p)
  Write-Output ('=== ' + $f)
  Write-Output ('  han=' + $han + '  dash=' + $dash + '  notbut=' + $nb)
  Write-Output ('  weak=' + $weak + '/' + $cmax + '  fowang=' + $fw + '/' + $fmax + '  feitu=' + $ft + '  fushe=' + $fs + '  chenmo=' + $cm + '  summary=' + $sm)
  Write-Output ('  CRLF=' + ([regex]::Matches($raw, "\r\n")).Count + '  BOM=' + ($b[0] -eq 239))
  $panels = [regex]::Matches($raw, '\u3010[^\u3011]*\u3011') | ForEach-Object { $_.Value }
  if ($panels.Count -gt 0) { Write-Output ('  panels: ' + ($panels -join ' | ')) }
  $first = (@(Get-Content $p -Encoding UTF8))[0]
  Write-Output ('  title: ' + $first)
}
