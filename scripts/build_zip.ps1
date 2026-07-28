# Build dist\naksha-<version>.zip for plugins.qgis.org
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
$version = (Select-String -Path "$root\naksha\metadata.txt" -Pattern '^version=(.+)$').Matches[0].Groups[1].Value.Trim()
$stage = Join-Path $env:TEMP "naksha_zip_stage"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory "$stage\naksha" | Out-Null
Copy-Item "$root\naksha\*" "$stage\naksha" -Recurse -Exclude "__pycache__"
Get-ChildItem $stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force "$root\dist" | Out-Null
$zip = "$root\dist\naksha-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "$stage\naksha" -DestinationPath $zip
Remove-Item -Recurse -Force $stage
Write-Output "built $zip"
