$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot 'start-embedding.ps1')
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -B tools/build_knowledge.py
if ($LASTEXITCODE -ne 0) { throw 'Knowledge indexing failed.' }
