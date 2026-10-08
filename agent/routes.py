from pathlib import Path
from threading import Lock
from typing import Annotated,Literal
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field
from dotenv import dotenv_values
import os
from reader.store import MaterialStore
from reader.models import InputError
from .memory import SessionStore
from .model import ChatModel,ModelError
from .engine import AgentEngine,AgentError
from .word_export import render_report_docx
from rag.embedding import OllamaEmbedding
from rag.index import KnowledgeIndex


class NewSession(BaseModel): title:str=Field(default='新会话',max_length=80)
class Message(BaseModel):
    text:str=Field(default='',max_length=100000)
    material_ids:list[str]=Field(default_factory=list,max_length=20)


def make_router(settings):
    root=Path(__file__).resolve().parent.parent
    values={**dotenv_values(root/'.env'),**os.environ}
    rag=KnowledgeIndex(settings.data_dir/'chroma',root/'knowledge'/'entries.json',OllamaEmbedding(values.get('EMBEDDING_MODEL') or 'qwen3-embedding:4b',values.get('EMBEDDING_BASE_URL') or 'http://127.0.0.1:11434'))
    sessions=SessionStore(settings.data_dir)
    materials=MaterialStore(settings.data_dir)
    engine=AgentEngine(sessions,materials,rag,ChatModel(settings))
    locks={}; locks_guard=Lock()
    router=APIRouter()

    def lock_for(sid):
        with locks_guard: return locks.setdefault(sid,Lock())

    @router.post('/api/sessions')
    def create_session(body:NewSession): return sessions.create(body.title)

    @router.get('/api/sessions')
    def list_sessions(): return sessions.list()

    @router.get('/api/sessions/{sid}')
    def get_session(sid:str):
        try: return sessions.get(sid)
        except KeyError: raise HTTPException(404,'会话不存在') from None

    @router.post('/api/sessions/{sid}/messages')
    def send_message(sid:str,body:Message):
        with lock_for(sid):
            try: return engine.turn(sid,body.text,body.material_ids)
            except KeyError: raise HTTPException(404,'会话不存在') from None
            except InputError as exc: raise HTTPException(400,str(exc)) from None
            except (AgentError,ModelError,ValueError) as exc: raise HTTPException(422,str(exc)) from None

    @router.delete('/api/sessions/{sid}')
    def delete_session(sid:str):
        with lock_for(sid):
            try:
                session=sessions.get(sid)
                sessions.delete(sid)
                used=set()
                for other in sessions.list(): used.update(sessions.get(other['id'])['material_ids'])
                for mid in session['material_ids']:
                    if mid in used: continue
                    folder=materials._directory(mid)
                    for filename in ['original','result.json']:
                        (folder/filename).unlink(missing_ok=True)
                    if folder.is_dir() and not any(folder.iterdir()): folder.rmdir()
                return {'deleted':sid}
            except KeyError: raise HTTPException(404,'会话不存在') from None

    @router.get('/api/sessions/{sid}/reports/{version}')
    def report(sid:str,version:int):
        try:
            session=sessions.get(sid)
            if version<1 or version>len(session['reports']): raise KeyError()
            return session['reports'][version-1]
        except KeyError: raise HTTPException(404,'报告不存在') from None

    @router.get('/api/sessions/{sid}/reports/{version}/download')
    def download(sid:str,version:int,format:Literal['md','docx']='md'):
        item=report(sid,version)
        if format=='docx':
            names={}
            for finding in item['findings']:
                mid=finding.get('material_id')
                if mid and mid!='user':
                    try: names[mid]=materials.load(mid).filename
                    except (InputError,FileNotFoundError,ValueError): pass
            data=render_report_docx(item,sessions.get(sid)['title'],names)
            return Response(data,media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':f'attachment; filename="report-{version}.docx"'})
        lines=[f'# 求职风险自查报告 · 第{version}版','',item['summary'],'']
        for f in item['findings']:
            lines.extend([f'## {f["title"]}（{f["level"]}）',f'原句：{f["quote"]}',f'位置：{f["material_id"]} 第{f["page_number"]}页',f['explanation'],'依据：'+', '.join(f['evidence_ids']),*['- '+s for s in f['suggestions']],''])
        lines.extend(['## 局限',*['- '+s for s in item['limitations']],'','## 依据来源'])
        for source in item['sources']: lines.append(f'- {source["id"]}：{source["title"]}，{source["location"]}，{source["url"]}')
        if version>1 and item['change_reason']: lines.extend(['','修改原因：'+item['change_reason']])
        return Response('\n'.join(lines),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="report-{version}.md"'})

    @router.get('/api/knowledge')
    def knowledge(): return rag._entries()

    return router
