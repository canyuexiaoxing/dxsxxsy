"""Desktop entry point and frozen backend subprocess entry."""
import json
import multiprocessing
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from desktop_runtime import resource_root,state_root,ModelRuntime,prepare_knowledge,MODEL_URL

SETUP_HTML='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>
body{margin:0;background:#f3f8f6;color:#23483f;font:17px "Microsoft YaHei",sans-serif;display:grid;place-items:center;height:100vh}.card{max-width:620px;background:white;padding:48px;border-radius:24px;box-shadow:0 16px 50px #184e3612}h1{font-size:30px}p{line-height:1.8}#status{white-space:pre-wrap;color:#47675e}.dot{width:28px;height:28px;border:3px solid #dfece6;border-top-color:#27816b;border-radius:50%;animation:spin 1s linear infinite}button{border:0;background:#27816b;color:white;padding:12px 24px;border-radius:10px;cursor:pointer}@keyframes spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.dot{animation:none}}
</style><div class="card"><div class="dot" id="spinner"></div><h1>求职避坑镜</h1><p>正在准备你的本地工作空间。正在检查本地检索模型，缺少时才会下载。完成后即可打开应用，并在设置中填写自己的 API Key。</p><p id="status">正在初始化…</p><button id="retry" hidden onclick="this.hidden=true;pywebview.api.retry()">重试</button><p style="font-size:13px;color:#7b938a">资料与会话保存在本机。关闭窗口会停止本次启动。</p></div></html>'''

def serve(port):
    import uvicorn
    from reader.api import create_app
    uvicorn.run(create_app(),host='127.0.0.1',port=port,log_config=None)

def self_test(output):
    from reader.config import Settings
    from reader.api import create_app
    from fastapi.testclient import TestClient
    from rag.index import KnowledgeIndex
    from rag.embedding import OllamaEmbedding
    from agent.word_export import render_report_docx
    from PIL import Image
    import pymupdf
    root=resource_root();home=state_root();data=home/'data';data.mkdir(parents=True,exist_ok=True)
    os.environ['DATA_DIR']=str(data)
    prepare_knowledge(root,data,lambda _:None)
    settings=Settings.load()
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/health').status_code==200
        assert client.get('/').status_code==200
        assert not settings.api_key,'发行测试不得包含API Key'
    k=KnowledgeIndex(data/'chroma',root/'knowledge/entries.json',OllamaEmbedding('qwen3-embedding:4b',os.environ.get('EMBEDDING_BASE_URL',MODEL_URL)))
    assert k._collection().count()==398
    result={'ok':True,'knowledge_count':398,'data_dir':str(data),'frontend':True,'api_key_configured':False}
    report={'summary':'这是安装版导出功能验证。','version':1,'findings':[],'limitations':['测试材料不代表真实求职经历。'],'sources':[]}
    document=render_report_docx(report,'安装版测试')
    assert document.startswith(b'PK');result['word_export']=True
    pdf=pymupdf.open();page=pdf.new_page();page.insert_text((72,72),'JobMirror PDF smoke test')
    with pymupdf.open(stream=pdf.tobytes(),filetype='pdf') as reopened:assert 'JobMirror' in reopened[0].get_text()
    result['pdf_reader']=True
    if os.environ.get('JOBMIRROR_TEST_RETRIEVAL')=='1':
        found=k.search('招聘要求交押金，扣留身份证',stage='preemployment')
        assert found;result['retrieved_ids']=[e['id'] for e in found]
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    import ctypes
    import httpx
    import webview
    root=resource_root();home=state_root();data=home/'data'
    (home/'logs').mkdir(parents=True,exist_ok=True);data.mkdir(parents=True,exist_ok=True)
    import msvcrt
    instance=open(home/'desktop.lock','a+b')
    instance.seek(0)
    try:msvcrt.locking(instance.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        instance.close()
        ctypes.windll.user32.MessageBoxW(None,'求职避坑镜已经运行，请打开已有窗口。','求职避坑镜',0x40)
        return
    os.environ['DATA_DIR']=str(data)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));model_url=f'http://127.0.0.1:{sock.getsockname()[1]}'
    os.environ['EMBEDDING_BASE_URL']=model_url
    os.environ['EMBEDDING_MODEL']='qwen3-embedding:4b'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('JobMirror.LocalDesktop')
    stop=threading.Event();lock=threading.Lock();lifecycle=threading.Lock();model=ModelRuntime(root,home,stop,model_url);server=None;handles=[]
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    url=f'http://127.0.0.1:{port}'
    def status(message,error=False):
        if stop.is_set():return
        try:window.evaluate_js('document.getElementById("status").textContent='+json.dumps(message)+';document.getElementById("retry").hidden='+('false' if error else 'true')+';document.getElementById("spinner").style.display='+json.dumps('none' if error else 'block'))
        except Exception:pass
    def bootstrap():
        nonlocal server
        if not lock.acquire(blocking=False):return
        try:
            prepare_knowledge(root,data,status)
            if stop.is_set():return
            model.prepare(status)
            if stop.is_set():return
            status('正在打开应用…')
            args=[sys.executable,'--serve',str(port)] if getattr(sys,'frozen',False) else [sys.executable,str(root/'desktop.py'),'--serve',str(port)]
            with lifecycle:
                if stop.is_set():return
                for name in ('desktop-server.stdout.log','desktop-server.stderr.log'):handles.append(open(home/'logs'/name,'a',encoding='utf-8'))
                server=subprocess.Popen(args,env=os.environ.copy(),stdout=handles[-2],stderr=handles[-1],creationflags=subprocess.CREATE_NO_WINDOW)
            with httpx.Client(timeout=2,trust_env=False) as client:
                for _ in range(160):
                    if stop.is_set():return
                    if server.poll() is not None:raise RuntimeError('应用服务启动失败，请查看用户数据目录中的服务日志。')
                    try:
                        if client.get(url+'/api/health').status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.25)
                else:raise RuntimeError('应用服务启动超时，请重试。')
            window.load_url(url)
        except Exception as exc:
            (home/'logs/desktop-launch-error.log').write_text(str(exc),encoding='utf-8')
            if server and server.poll() is None:server.terminate();server.wait(timeout=10)
            model.close()
            status('启动未完成：'+str(exc)+'\n请检查网络后重试。',True)
        finally:lock.release()
    class Bridge:
        def retry(self):threading.Thread(target=bootstrap,daemon=True).start()
    def closing():stop.set()
    webview.settings['ALLOW_DOWNLOADS']=True
    webview.settings['ALLOW_FILE_URLS']=False
    window=webview.create_window('求职避坑镜',html=SETUP_HTML,js_api=Bridge(),width=1280,height=800,min_size=(850,600),background_color='#F3F8F6',text_select=True)
    window.events.closing+=closing
    try:webview.start(lambda:threading.Thread(target=bootstrap,daemon=True).start(),gui='edgechromium',private_mode=False,storage_path=str(data/'webview'),icon=str(root/'assets/app-icon.ico'))
    finally:
        stop.set()
        with lifecycle:
            if server and server.poll() is None:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill()
            for handle in handles:handle.close()
        model.close()
        instance.close()

if __name__=='__main__':
    multiprocessing.freeze_support()
    if getattr(sys,'frozen',False):
        home=state_root();(home/'logs').mkdir(parents=True,exist_ok=True)
        if sys.stdout is None:sys.stdout=open(home/'logs/process.stdout.log','a',encoding='utf-8')
        if sys.stderr is None:sys.stderr=open(home/'logs/process.stderr.log','a',encoding='utf-8')
    try:
        if len(sys.argv)>2 and sys.argv[1]=='--serve':serve(int(sys.argv[2]))
        elif len(sys.argv)>2 and sys.argv[1]=='--self-test':self_test(sys.argv[2])
        else:main()
    except Exception as exc:
        import traceback
        home=state_root();(home/'logs').mkdir(parents=True,exist_ok=True)
        (home/'logs/desktop-launch-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        if len(sys.argv)==1:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'启动失败：'+str(exc)+'\n日志：'+str(home/'logs'),'求职避坑镜',0x10)
        sys.exit(1)
