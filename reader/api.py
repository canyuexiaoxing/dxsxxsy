import mimetypes
from pathlib import Path
from agent.tasks import TaskRegistry,TaskCancelled,active_task,check_cancelled
from fastapi.staticfiles import StaticFiles
from typing import Annotated
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from .config import Settings
from .core import MaterialReader, MAX_FILE_BYTES, safe_filename
from .models import InputError
from .store import MaterialStore
from .vision import VisionClient
from .api_key_settings import make_settings_router


def create_app(settings=None,vision=None):
    settings = settings or Settings.load()
    tasks=TaskRegistry()
    reader = MaterialReader(vision or VisionClient(settings))
    store = MaterialStore(settings.data_dir)
    app = FastAPI(title='求职避坑镜：本地RAG Agent',version='0.2.0',description='支持材料读取、RAG检索、追问和风险报告；相关材料发送至DeepSeek。')

    @app.get('/api/health')
    def health(): return {'status':'ok','stage':'rag-agent','vision_configured':bool(settings.api_key)}

    def discard_new(mid):
        from agent.memory import SessionStore
        sessions=SessionStore(settings.data_dir)
        if any(mid in sessions.get(s['id'])['material_ids'] for s in sessions.list()):return
        folder=store._directory(mid)
        for filename in ('original','result.json'):(folder/filename).unlink(missing_ok=True)
        if folder.is_dir() and not any(folder.iterdir()):folder.rmdir()
    @app.post('/api/materials')
    async def ingest(text: Annotated[str,Form()]='',files: Annotated[list[UploadFile] | None,File()]=None,
                     session_id:Annotated[str,Form()]='',request_id:Annotated[str,Form()]=''):
        token=None;binding=None
        if session_id and request_id:
            from agent.memory import SessionStore
            try:SessionStore(settings.data_dir).get(session_id)
            except KeyError:raise HTTPException(404,'会话不存在') from None
            if len(request_id)>64 or not all(c.isalnum() or c in '_-' for c in request_id):raise HTTPException(422,'任务编号无效')
            token=tasks.get(session_id,request_id);binding=active_task.set(token)
        try:
            files = files or []
            if len(files) > 5: raise HTTPException(400,'一次最多上传5个文件')
            if not text.strip() and not files: raise HTTPException(400,'请输入文字或上传材料')
            results,errors = [],[]
            if text.strip():
                try:
                    check_cancelled()
                    result = reader.read_text(text)
                    check_cancelled()
                    await run_in_threadpool(store.save,result,text.encode('utf-8'))
                    if token:token.own(lambda mid=result.material_id:discard_new(mid))
                    check_cancelled()
                    results.append(result)
                except InputError as exc: raise HTTPException(400,str(exc)) from None
            for upload in files:
                try:
                    check_cancelled()
                    buffer = bytearray()
                    while block := await upload.read(64*1024):
                        buffer.extend(block)
                        if len(buffer) > MAX_FILE_BYTES: raise InputError('单文件超过20MiB，请拆分提交')
                    data = bytes(buffer)
                    result = await run_in_threadpool(reader.read_file,upload.filename or 'material',data)
                    check_cancelled()
                    await run_in_threadpool(store.save,result,data)
                    if token:token.own(lambda mid=result.material_id:discard_new(mid))
                    check_cancelled()
                    results.append(result)
                except InputError as exc:
                    errors.append({'filename':safe_filename(upload.filename or 'material'),'error':str(exc)})
                finally: await upload.close()
            return {'materials':results,'errors':errors,'notice':'结果为提取内容，未经人工核验；尚未进行风险分析。'}

        except TaskCancelled as exc:raise HTTPException(410,str(exc)) from None
        finally:
            if binding is not None:active_task.reset(binding)

    @app.get('/api/materials/{material_id}')
    def get_material(material_id: str):
        try: return store.load(material_id)
        except InputError as exc: raise HTTPException(404,str(exc)) from None

    @app.get('/api/materials/{material_id}/original')
    def original(material_id: str):
        try:
            result = store.load(material_id)
            mime = mimetypes.guess_type(result.filename)[0] or 'application/octet-stream'
            return FileResponse(store.original_path(material_id),media_type=mime,filename=result.filename)
        except InputError as exc: raise HTTPException(404,str(exc)) from None

    app.include_router(make_settings_router(settings))

    from agent.routes import make_router
    app.include_router(make_router(settings,tasks))
    frontend=Path(__file__).resolve().parent.parent/'frontend/dist/client'
    if frontend.is_dir():
        app.mount('/assets',StaticFiles(directory=frontend/'assets'),name='frontend-assets')
        @app.get('/',include_in_schema=False)
        def frontend_page(): return FileResponse(frontend/'index.html')
        @app.get('/mint-sidebar.png',include_in_schema=False)
        def sidebar_asset(): return FileResponse(frontend/'mint-sidebar.png')
    return app
