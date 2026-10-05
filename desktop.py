"""Local Windows desktop shell. Reuses existing localhost services when available."""
import ctypes
import subprocess
import sys
import time
from pathlib import Path
import httpx
import webview

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8000'

def check_service():
    try:
        with httpx.Client(timeout=2,trust_env=False) as client:
            response=client.get(URL+'/api/health')
            if response.status_code==200 and response.json().get('stage')=='rag-agent': return True
    except (httpx.HTTPError,ValueError): pass
    return False

def main():
    if not (ROOT/'frontend/dist/client/index.html').is_file():
        raise RuntimeError('前端尚未构建，请在frontend目录执行npm run build。')
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('JobMirror.LocalDesktop')
    (ROOT/'logs').mkdir(exist_ok=True)
    hidden=subprocess.STARTUPINFO(); hidden.dwFlags|=subprocess.STARTF_USESHOWWINDOW;hidden.wShowWindow=0
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'start-embedding.ps1')],cwd=ROOT,startupinfo=hidden,capture_output=True,timeout=90)
    if result.returncode: raise RuntimeError('本地Embedding启动失败，请查看本地Embedding说明。')
    server=None; handles=[]
    try:
        if not check_service():
            for name in ['desktop-server.stdout.log','desktop-server.stderr.log']:handles.append(open(ROOT/'logs'/name,'a',encoding='utf-8'))
            server=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,startupinfo=hidden,stdout=handles[0],stderr=handles[1])
            for _ in range(80):
                if server.poll() is not None: raise RuntimeError('服务未能启动。8000端口可能被占用，请查看logs中的服务日志。')
                if check_service():break
                time.sleep(.25)
            else:raise RuntimeError('本地服务启动超时。')
        webview.settings['ALLOW_DOWNLOADS']=True
        webview.settings['ALLOW_FILE_URLS']=False
        window=webview.create_window('求职避坑镜',URL,width=1380,height=950,min_size=(850,600),background_color='#FFFFFF',text_select=True)
        window.events.loaded += lambda: (ROOT/'logs/desktop-loaded.txt').write_text('Desktop WebView loaded localhost frontend.',encoding='utf-8')
        webview.start(gui='edgechromium',private_mode=False,storage_path=str(ROOT/'data/webview'),icon=str(ROOT/'assets/app-icon.ico'))
    finally:
        if server is not None:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill()
        for handle in handles:handle.close()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        (ROOT/'logs').mkdir(exist_ok=True)
        (ROOT/'logs/desktop-launch-error.log').write_text(str(exc),encoding='utf-8')
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,str(exc),'求职避坑镜：启动提示',0x10)
