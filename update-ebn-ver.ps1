# update-ebn-ver.ps1 — 升版時一鍵同步 BUILD 與 ebn-ver.txt
# 用法：.\update-ebn-ver.ps1 2026062016
param([string]$NewVer)
if (-not $NewVer) {
    Write-Host "用法: .\update-ebn-ver.ps1 <新版號，例如 2026062016>"
    exit 1
}
$dir = $PSScriptRoot

Set-Content "$dir\ebn-ver.txt" $NewVer -NoNewline -Encoding utf8

foreach ($f in @("evidence.html","search.html")) {
    $path = "$dir\$f"
    (Get-Content $path -Raw) -replace 'const BUILD="[0-9]+"', "const BUILD=`"$NewVer`"" |
        Set-Content $path -NoNewline -Encoding utf8
}

Write-Host "✅ ebn-ver.txt + evidence.html + search.html BUILD 全部更新到 $NewVer"
Write-Host "   lawyer.html 的 BUILD 由另一個 session 管（對應 ver.txt）"
Write-Host ""
Write-Host "下一步：git add -A && git commit -m '升版 $NewVer' && git push"
