$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskExe = Join-Path $taskRoot 'runtime\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $taskExe)) { throw 'Ollama runtime is not ready.' }
$env:OLLAMA_MODELS = Join-Path $taskRoot 'models\ollama'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_CONTEXT_LENGTH = '2048'
$env:OLLAMA_NUM_PARALLEL = '1'
$taskReady = $false
try {
    $taskTags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
    if ($taskTags.models.name -contains 'qwen3-embedding:4b') { $taskReady = $true }
    else { throw 'Port 11434 is occupied by an Ollama instance without the project model.' }
} catch {
    if ($_.Exception.Message -like 'Port 11434*') { throw }
}
if (-not $taskReady) {
    $taskLogDir = Join-Path $taskRoot 'logs'
    New-Item -ItemType Directory -Path $taskLogDir -Force | Out-Null
    $taskProcess = Start-Process -FilePath $taskExe -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskLogDir 'ollama.stdout.log') -RedirectStandardError (Join-Path $taskLogDir 'ollama.stderr.log')
    $taskProcess.Id | Set-Content -LiteralPath (Join-Path $taskLogDir 'ollama.pid')
    for ($taskAttempt = 0; $taskAttempt -lt 40; $taskAttempt++) {
        try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 1 | Out-Null; $taskReady = $true; break } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $taskReady) { throw 'Ollama did not start. Check logs/ollama.stderr.log.' }
}
Write-Output 'Embedding service: http://127.0.0.1:11434'
Write-Output 'Model: qwen3-embedding:4b'