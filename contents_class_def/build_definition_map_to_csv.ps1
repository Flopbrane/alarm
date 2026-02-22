# ===============================
# ★ 設定項目
# ===============================
# このファイルの概要：
# プロジェクト内の Python ファイルを再帰的に走査し、
# class 定義と def 定義を抽出して CSV に保存する。
# 出力される CSV は以下のカラムを持つ。
# - file_key: ファイルの相対パス（プロジェクトルートからの）
# - kind: 'class' または 'def'
# - name: 定義名（クラス名または関数名）
# - lineno: 定義が現れる行番号
# - indent: 行のインデント量（スペース数）
# - is_method: クラス内メソッドである可能性が高いかどうか（bool）
# - raw_line: 定義行の生テキスト
# 生成された CSV は各ファイルのクラスや関数などの情報を情報ベースとして
# 他のスクリプトで利用して、再帰的に*.pyファイルを解析し、
# 参照先、参照元、未使用定義の検出などに活用できる。
# ===============================
param(
    [string]$ProjectRoot = ""
)

# この .ps1 が置かれているフォルダ
$scriptDir = $PSScriptRoot

if ($ProjectRoot -eq "") {
    $projectRoot = Resolve-Path (Join-Path $scriptDir "..")
}
else {
    $projectRoot = Resolve-Path $ProjectRoot
}


# プロジェクトルート（通常は scriptDir の1つ上）
# 他プロジェクトで使う場合は、絶対パスに変更可能
# 例:
# $projectRoot = "D:\PC\Python\another_project"
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")   # D:\PC\Python\alarm

# ===============================
# 出力先
# ===============================

$outDir = Join-Path $scriptDir "definition_map"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outCsv = Join-Path $outDir "definition_map.csv"

$rows = @()

Get-ChildItem $projectRoot -Recurse -Filter *.py |
    Where-Object {
        $_.FullName -notmatch '\\(\.deprecated|\.github|\.ruff_cache|\.vscode|venv-alarm312|venv|\.venv|__pycache__|sound|backup)\\'
    } |
        ForEach-Object {
            $file = $_
            # プロジェクトルートを除去して相対パス化
            $relPath = $file.FullName.Substring($projectRoot.Path.Length).TrimStart('\')
            $relPath = $relPath -replace '\\', '/'
            # class / def の行を拾う
            Select-String -Path $file.FullName -Pattern '^\s*(class|def)\s+' |
                ForEach-Object {
                    $lineText = $_.Line

                    # 名前の抽出（class Foo / def bar）
                    if ($lineText -match '^\s*(class|def)\s+([A-Za-z_][A-Za-z0-9_]*)') {
                        $kind = $matches[1]
                        $name = $matches[2]

                        # クラス内メソッドかどうか（ざっくり推定）
                        # インデントがある def は class 内である可能性が高い
                        # インデント量を取得（PS 5.1 対応）
                        $indent = 0
                        if ($lineText -match '^\s+') {
                            $indent = $Matches[0].Length
                        }
                        $maybeMethod = ($kind -eq 'def' -and $indent -ge 4)

                        $rows += [PSCustomObject]@{
                            file_key  = $relPath
                            kind      = $kind            # class / def
                            name      = $name            # def名 / class名
                            lineno    = $_.LineNumber
                            indent    = $indent
                            is_method = $maybeMethod
                            raw_line  = $lineText.TrimEnd()
                        }
                    }
                }
            }

$rows |
    ConvertTo-Csv -NoTypeInformation |
        Set-Content -Path $outCsv -Encoding utf8
Write-Host "Definition map CSV generated at: $outCsv"
# ===============================