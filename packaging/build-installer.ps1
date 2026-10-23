param([string]$InnoCompiler, [switch]$OfflineBundle)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
Set-Location $taskRoot
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $taskPython)) { throw '请先准备项目Python环境。' }
if (-not $InnoCompiler) { $InnoCompiler=(Get-Command iscc.exe -ErrorAction SilentlyContinue).Source }
if (-not $InnoCompiler -or -not (Test-Path $InnoCompiler)) { throw '请安装Inno Setup，并用 -InnoCompiler 指定ISCC.exe。' }
$taskBootstrap=Join-Path $PSScriptRoot 'MicrosoftEdgeWebview2Setup.exe'
if (-not (Test-Path $taskBootstrap)) { Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $taskBootstrap }
$taskSignature=Get-AuthenticodeSignature $taskBootstrap
if ($taskSignature.Status -ne 'Valid' -or $taskSignature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'WebView2引导程序签名验证失败。' }
& $taskPython -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw '回归测试失败。' }
& $taskPython packaging/export_public_seed.py
if ($LASTEXITCODE -ne 0) { throw '公开知识库索引导出失败。' }
& $taskPython -m PyInstaller --noconfirm packaging/JobMirror.spec
if ($LASTEXITCODE -ne 0) { throw '独立程序打包失败。' }
if ($OfflineBundle) { & $InnoCompiler /DOfflineBundle packaging/installer.iss } else { & $InnoCompiler packaging/installer.iss }
if ($LASTEXITCODE -ne 0) { throw '安装包编译失败。' }
$taskFilename=if ($OfflineBundle) {'JobMirror-Setup-0.3.1-Offline.exe'} else {'JobMirror-Setup-0.3.1.exe'}
$taskSetup=Join-Path $taskRoot ('release\'+$taskFilename)
Get-FileHash -LiteralPath $taskSetup -Algorithm SHA256 | Format-List
Write-Output "安装包：$taskSetup"
