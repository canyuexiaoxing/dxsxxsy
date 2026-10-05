import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit
from fastapi import APIRouter,HTTPException,Request

FILENAME='api-settings.json'

def stored_api_key(directory):
    path=Path(directory)/FILENAME
    if not path.exists(): return None
    try:
        value=json.loads(path.read_text(encoding='utf-8')).get('api_key')
        return value if isinstance(value,str) and value else None
    except (OSError,ValueError,TypeError): return None

def make_settings_router(settings):
    router=APIRouter(); lock=Lock()
    def status():
        return {'configured':bool(settings.api_key),'provider':'DeepSeek','model':settings.model}
    def check_origin(request):
        origin=request.headers.get('origin')
        if origin and (urlsplit(origin).scheme not in {'http','https'} or urlsplit(origin).netloc!=request.headers.get('host')):
            raise HTTPException(403,'请在本机软件页面中修改设置')

    @router.get('/api/settings/api-key')
    def get_settings(): return status()

    @router.post('/api/settings/api-key')
    async def set_settings(request:Request):
        check_origin(request)
        try: body=await request.json()
        except ValueError: raise HTTPException(400,'请输入有效的 API Key') from None
        key=body.get('api_key') if isinstance(body,dict) else None
        if not isinstance(key,str): raise HTTPException(400,'请输入有效的 API Key')
        key=key.strip()
        if not key or len(key)>512 or not key.isascii() or any(c.isspace() for c in key):
            raise HTTPException(400,'API Key 不能为空，且不能包含空格或换行')
        with lock:
            directory=Path(settings.data_dir); directory.mkdir(parents=True,exist_ok=True)
            temporary=None
            try:
                fd,temporary=tempfile.mkstemp(prefix='.api-settings-',suffix='.tmp',dir=directory)
                with os.fdopen(fd,'w',encoding='utf-8') as file:
                    json.dump({'api_key':key},file); file.flush(); os.fsync(file.fileno())
                os.replace(temporary,directory/FILENAME)
                settings.api_key=key
            except OSError:
                raise HTTPException(500,'本地设置保存失败，请检查目录写入权限') from None
            finally:
                if temporary: Path(temporary).unlink(missing_ok=True)
        return {**status(),'message':'已保存，下次分析直接使用新 Key'}
    return router
