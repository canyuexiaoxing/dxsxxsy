from .timing import event
from pathlib import Path
from uuid import uuid4
from .tasks import TaskRegistry,TaskCancelled
from threading import Lock
from typing import Annotated,Literal
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field
from reader.config import configuration_values
import os
from reader.store import MaterialStore
from reader.models import InputError
from .memory import SessionStore
from .model import ChatModel,ModelError
from .engine import AgentEngine,AgentError
from .word_export import render_report_docx
from .presentation import public_report, public_reply, public_session
from rag.embedding import OllamaEmbedding
from rag.index import KnowledgeIndex


class NewSession(BaseModel): title:str=Field(default='新会话',max_length=80)
class Message(BaseModel):
    request_id:str=Field(default="",max_length=64,pattern=r"^[A-Za-z0-9_-]*$")
    text:str=Field(default='',max_length=100000)
    material_ids:list[str]=Field(default_factory=list,max_length=20)


def make_router(settings,tasks=None):
    tasks=tasks or TaskRegistry()
    root=Path(__file__).resolve().parent.parent
    values=configuration_values()
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
        try: return public_session(sessions.get(sid))
        except KeyError: raise HTTPException(404,'会话不存在') from None

    @router.post('/api/sessions/{sid}/messages')
    def send_message(sid:str,body:Message):
        with lock_for(sid):
            try:
                with tasks.scope(sid,body.request_id or uuid4().hex):
                    return public_reply(engine.turn(sid,body.text,body.material_ids))
            except TaskCancelled as exc:raise HTTPException(410,str(exc)) from None
            except KeyError: raise HTTPException(404,'会话不存在') from None
            except InputError as exc: raise HTTPException(400,str(exc)) from None
            except (AgentError,ModelError,ValueError) as exc: raise HTTPException(422,str(exc)) from None

    @router.post('/api/sessions/{sid}/tasks/{request_id}/cancel')
    def cancel_task(sid:str,request_id:str):
        try:sessions.get(sid)
        except KeyError:raise HTTPException(404,'会话不存在') from None
        if not request_id or len(request_id)>64 or not all(c.isalnum() or c in '_-' for c in request_id):
            raise HTTPException(422,'任务编号无效')
        status=tasks.get(sid,request_id).cancel()
        event('cancel_request','received',session_id=sid,request_id=request_id,status=status)
        return {'status':status}
    @router.delete('/api/sessions/{sid}')
    def delete_session(sid:str):
        try:sessions.get(sid)
        except KeyError:raise HTTPException(404,'会话不存在') from None
        tasks.cancel_session(sid)
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
            return public_report(session['reports'][version-1])
        except KeyError: raise HTTPException(404,'报告不存在') from None

    @router.get('/api/sessions/{sid}/reports/{version}/download')
    def download(sid:str,version:int,format:Literal['md','docx']='md'):
        item=report(sid,version)
        if format=='docx':
            # Refresh link metadata only when the original evidence text is identical.
            sources=[]
            metadata_keys=('url','source_publisher','source_role','source_site','source_relation','source_access_note','alternate_urls','legal_database_url','legal_database_status','verified_at')
            for source in item.get('sources',[]):
                try:current=rag.get(source['id'])
                except ValueError:current={}
                if current.get('text')==source.get('text'):
                    source={**source,**{key:current[key] for key in metadata_keys if key in current}}
                sources.append(source)
            item={**item,'sources':sources}
            names={}
            for finding in item['findings']:
                mid=finding.get('material_id')
                if mid and mid!='user':
                    try: names[mid]=materials.load(mid).filename
                    except (InputError,FileNotFoundError,ValueError): pass
            session=sessions.get(sid)
            if 'report_context' not in item:
                statements=[];found=False
                for message in session['messages']:
                    if message['role']=='user':statements.append(message['text'])
                    elif (message.get('result',{}).get('report') or {}).get('version')==version:
                        found=True;break
                item={**item,'report_context':{'user_statements':statements if found else []}}
            if not item.get('situation_overview') and settings.api_key:
                context=item.get('report_context',{})
                mids=[m['material_id'] for m in context.get('materials',[]) if m.get('material_id')]
                if not mids:
                    # Legacy reports: only material IDs submitted before this version.
                    for message in session['messages']:
                        if message['role']=='user':mids.extend(message.get('material_ids',[]))
                        elif (message.get('result',{}).get('report') or {}).get('version')==version:break
                extracted=[]
                for mid in dict.fromkeys(mids):
                    try:extracted.append(materials.load(mid).model_dump())
                    except (InputError,FileNotFoundError,ValueError):pass
                try:
                    item={**item,'situation_overview':engine.model.summarize_situation(
                        {**context,'materials':extracted})}
                except ModelError:pass  # Never substitute the transcript on failure.
            data=render_report_docx(item,session['title'],names)
            return Response(data,media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':f'attachment; filename="report-{version}.docx"'})
        lines=[f'# 求职风险自查报告 · 第{version}版','',item['summary'],'']
        if item.get('prevention'):
            prevention=item['prevention']
            lines.extend(['## 签约与入职前，建议先做',prevention['label'],*['- '+s for s in prevention['steps']],prevention['note'],''])
        for f in item['findings']:
            lines.extend([f'## {f["title"]}（{f["level"]}）',f'原句：{f["quote"]}',f'位置：{f["material_id"]} 第{f["page_number"]}页',f['explanation'],'依据：'+', '.join(f['evidence_ids']),*['- '+s for s in f['suggestions']],''])
        lines.extend(['## 局限',*['- '+s for s in item['limitations']],'','## 依据来源'])
        for source in item['sources']: lines.append(f'- {source["id"]}：{source["title"]}，{source["location"]}，{source["url"]}')
        if version>1 and item['change_reason']: lines.extend(['','修改原因：'+item['change_reason']])
        return Response('\n'.join(lines),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="report-{version}.md"'})

    @router.get('/api/knowledge')
    def knowledge(): return rag._entries()

    return router
