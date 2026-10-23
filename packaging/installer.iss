[Setup]
AppId={{A41D740F-0A79-456D-953C-68F806CE4D6A}
AppName=求职避坑镜
AppVersion=0.3.1
AppPublisher=求职避坑镜项目组
DefaultDirName={localappdata}\Programs\JobMirror
DefaultGroupName=求职避坑镜
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release
#ifdef OfflineBundle
OutputBaseFilename=JobMirror-Setup-0.3.1-Offline
#else
OutputBaseFilename=JobMirror-Setup-0.3.1
#endif
SetupIconFile=..\assets\app-icon.ico
UninstallDisplayIcon={app}\JobMirror.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "..\dist\JobMirror\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installer.env"; DestDir: "{app}"; DestName: ".env"; Flags: onlyifdoesntexist uninsneveruninstall
#ifdef OfflineBundle
Source: "离线版使用说明.txt"; DestDir: "{app}"; DestName: "安装版使用说明.txt"; Flags: ignoreversion
Source: "Qwen-LICENSE.txt"; DestDir: "{app}\models"; Flags: ignoreversion uninsneveruninstall
Source: "MODEL-NOTICE.txt"; DestDir: "{app}\models"; Flags: ignoreversion uninsneveruninstall
Source: "..\models\ollama\manifests\registry.ollama.ai\library\qwen3-embedding\4b"; DestDir: "{app}\models\ollama\manifests\registry.ollama.ai\library\qwen3-embedding"; Flags: ignoreversion uninsneveruninstall
Source: "..\models\ollama\blobs\sha256-2ca34c70bbf2dc85cb69688daf0b423bdc361504ea29d7f5a35c19f739d8ee0d"; DestDir: "{app}\models\ollama\blobs"; Flags: ignoreversion uninsneveruninstall
Source: "..\models\ollama\blobs\sha256-2b0cf8f17b4c723c27303015383c27ec4bf2d8314bb677d05e920dd70bb0f16b"; DestDir: "{app}\models\ollama\blobs"; Flags: ignoreversion nocompression uninsneveruninstall
#else
Source: "安装版使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion
#endif
Source: "MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\求职避坑镜"; Filename: "{app}\JobMirror.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\求职避坑镜"; Filename: "{app}\JobMirror.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\JobMirror.exe"; Description: "启动求职避坑镜"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\desktop.lock"

[Code]
var
  RemoveProjectData: Boolean;

function InitializeUninstall: Boolean;
var
  I: Integer;
begin
  Result := True;
  RemoveProjectData := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/PURGEUSERDATA=1') = 0 then
      RemoveProjectData := True;
  if not UninstallSilent then
    RemoveProjectData := MsgBox('是否同时删除本安装目录中的模型、聊天记录、上传材料、报告数据、设置和日志？' + #13#10 + '选择“是”将永久删除这些数据；选择“否”会保留它们。', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Root: String;
begin
  if (CurUninstallStep = usPostUninstall) and RemoveProjectData then begin
    Root := AddBackslash(ExpandFileName(ExpandConstant('{app}')));
    if Length(Root) <= 3 then begin
      Log('Refusing project data cleanup at a drive root.');
      Exit;
    end;
    { All recursive targets are fixed child folders of the exact installation directory. }
    Log('Removing project data under installation directory: ' + Root);
    DelTree(Root + 'data', True, True, True);
    DelTree(Root + 'models', True, True, True);
    DelTree(Root + 'logs', True, True, True);
    DeleteFile(Root + '.env');
    RemoveDir(Root);
  end;
end;

function WebView2Present: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := ((RegQueryStringValue(HKLM32, Key, 'pv', Version)) and (Version <> '') and (Version <> '0.0.0.0'));
  if not Result then
    Result := ((RegQueryStringValue(HKCU, Key, 'pv', Version)) and (Version <> '') and (Version <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  if not WebView2Present then begin
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
      Result := '无法启动微软 WebView2 安装程序，请检查后重试。';
      Exit;
    end;
    if not WebView2Present then
      Result := 'WebView2 未能安装。请保持联网，或先从微软官网安装 WebView2 Runtime 后再重试。https://developer.microsoft.com/microsoft-edge/webview2/';
  end;
end;
