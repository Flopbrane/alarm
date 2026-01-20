# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
# 関数やクラスの検索
#########################
Add-Type -AssemblyName System.Web

# 1) class/def 一覧を抽出（今の確定版）
$items =
Get-ChildItem -Recurse -Filter *.py |
Select-String -Pattern '^\s*(class|def)\s+' |
ForEach-Object {
    [PSCustomObject]@{
        Path = $_.Path
        Line = $_.LineNumber
        Text = $_.Line.TrimEnd()
    }
}

# 2) HTML化（vscode://file/ で開く）
$rows = $items | ForEach-Object {
    $full = (Resolve-Path $_.Path).Path
    $uriPath = $full -replace '\\','/'          # C:\a\b.py -> C:/a/b.py
    $textEsc = [System.Net.WebUtility]::HtmlEncode($_.Text)
    $fileEsc = [System.Net.WebUtility]::HtmlEncode($full)


    "<li><a href='vscode://file/${uriPath}:$($_.Line)'>${fileEsc}:$($_.Line)</a> <code>$textEsc</code></li>"
}

$html = @"
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>Python class/def index</title>
<style>
body { font-family: sans-serif; }
code { background: #f5f5f5; padding: 0.1em 0.3em; border-radius: 4px; }
li { margin: 0.25em 0; }
</style>
</head>
<body>
<h1>Python class/def index</h1>
<ul>
$($rows -join "`r`n")
</ul>
</body>
</html>
"@

$html | Out-File classes_and_methods_list.html -Encoding UTF8
