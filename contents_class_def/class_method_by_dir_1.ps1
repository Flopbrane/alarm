$scriptDir = $PSScriptRoot

# .py が存在する「親の alarm フォルダ」
$baseDir = Resolve-Path (Join-Path $scriptDir "..")

# HTML 出力先（contents_class_def/html_index）
$outDir = Join-Path $scriptDir "html_index"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null


Get-ChildItem $baseDir -Recurse -Filter *.py |
Where-Object {
        $_.FullName -notmatch '\\(.deprecated|.github|.ruff_cache|.vscode|venv-alarm312|venv|.venv|__pycache__|sound|backup)\\'
} |
Group-Object { $_.DirectoryName } |
ForEach-Object {

    $group = $_
    $folderName = Split-Path $group.Name -Leaf
    $outFile = Join-Path $outDir "$folderName.html"

    $items =
    $group.Group |
    Select-String -Pattern '^\s*(class|def)\s+' |
    ForEach-Object {
        $full = (Resolve-Path $_.Path).Path
        $uri  = $full -replace '\\','/'
        $text = [System.Net.WebUtility]::HtmlEncode($_.Line.TrimEnd())

        "<li><a href='vscode://file/${uri}:$($_.LineNumber)'>$($_.Path):$($_.LineNumber)</a> <code>$text</code></li>"
    }

    @"
<!doctype html>
<html lang="ja">
<meta charset="utf-8">
<title>$folderName</title>
<body>
<h1>$folderName</h1>
<ul>
$($items -join "`n")
</ul>
</body>
</html>
"@ | Out-File $outFile -Encoding UTF8
}
