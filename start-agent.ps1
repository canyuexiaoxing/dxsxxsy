$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot 'start-embedding.ps1')
& (Join-Path $PSScriptRoot 'start-reader.ps1')
