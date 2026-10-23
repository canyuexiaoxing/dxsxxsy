"""Installed desktop resources, public knowledge seed and local model setup."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import threading
import httpx

MODEL='qwen3-embedding:4b'
MODEL_URL='http://127.0.0.1:11435'

def resource_root():
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))

def state_root():
    if os.environ.get('JOBMIRROR_HOME'):return Path(os.environ['JOBMIRROR_HOME'])
    if getattr(sys,'frozen',False):return Path(sys.executable).resolve().parent
    return resource_root()

def model_available(tags):
    return any(item.get('name')==MODEL for item in tags.get('models',[]))

def seed_payload(source,seed):
    metadata=seed.get('metadata',{})
    entries=json.loads(source.read_text(encoding='utf-8-sig'))
    expected={entry['id']:entry['text'] for entry in entries}
    if metadata.get('source_hash')!=hashlib.sha256(source.read_bytes()).hexdigest() or metadata.get('embedding_model')!=MODEL:
        raise ValueError('公开知识库版本与索引不一致。')
    ids=seed.get('ids',[])
    if len(ids)!=len(expected) or set(ids)!=set(expected) or any(len(seed.get(field,[]))!=len(ids) for field in ('documents','embeddings','metadatas')):
        raise ValueError('公开知识库索引不完整。')
    if any(expected[sid]!=text for sid,text in zip(ids,seed['documents'])):
        raise ValueError('公开知识库索引内容不匹配。')
    return seed

def prepare_knowledge(root,data_dir,status):
    import chromadb
    from chromadb.config import Settings
    payload=seed_payload(root/'knowledge/entries.json',json.loads((root/'knowledge/public-seed.json').read_text(encoding='utf-8')))
    client=chromadb.PersistentClient(path=str(data_dir/'chroma'),settings=Settings(anonymized_telemetry=False))
    collection=client.get_or_create_collection('job_safety',metadata={'hnsw:space':'cosine'},embedding_function=None)
    metadata=collection.metadata or {}
    if metadata.get('source_hash')==payload['metadata']['source_hash'] and metadata.get('embedding_model')==MODEL and collection.count()==len(payload['ids']):return
    status('正在准备公开知识库…')
    old=collection.get()['ids']
    if old:collection.delete(ids=old)
    for offset in range(0,len(payload['ids']),50):
        collection.upsert(**{key:payload[key][offset:offset+50] for key in ('ids','documents','embeddings','metadatas')})
    collection.modify(metadata=payload['metadata'])

class ModelRuntime:
    def __init__(self,root,home,stop,url=MODEL_URL):
        self.root,self.home,self.stop=root,home,stop
        self.url=url
        self.guard=threading.Lock()
        self.process=None;self.log=None
    def prepare(self,status):
        if self.stop.is_set():return
        with httpx.Client(timeout=10,trust_env=False) as client:
            try:
                tags=client.get(self.url+'/api/tags');tags.raise_for_status()
                if not model_available(tags.json()):
                    raise RuntimeError('模型服务端口已被其他服务使用。请关闭该服务后重试。')
                status('本地模型已就绪。');return
            except httpx.ConnectError:pass
        status('正在启动本地模型服务…')
        (self.home/'logs').mkdir(parents=True,exist_ok=True)
        env=os.environ.copy()
        env.update(OLLAMA_MODELS=str(self.home/'models/ollama'),OLLAMA_HOST=self.url.removeprefix('http://'),OLLAMA_CONTEXT_LENGTH='2048',OLLAMA_NUM_PARALLEL='1')
        with self.guard:
            if self.stop.is_set():return
            self.log=open(self.home/'logs/model.log','a',encoding='utf-8')
            self.process=subprocess.Popen([str(self.root/'runtime/ollama/ollama.exe'),'serve'],env=env,stdout=self.log,stderr=self.log,creationflags=subprocess.CREATE_NO_WINDOW)
        with httpx.Client(timeout=30,trust_env=False) as client:
            for _ in range(120):
                if self.stop.is_set():return
                if self.process.poll() is not None:raise RuntimeError('本地模型服务启动失败，请查看用户数据目录中的logs/model.log。')
                try:
                    response=client.get(self.url+'/api/tags');response.raise_for_status();break
                except httpx.ConnectError:time.sleep(.25)
            else:raise RuntimeError('本地模型服务启动超时。')
            if not model_available(response.json()):
                status('首次使用需要下载Qwen3-Embedding-4B（约2.5GB），请保持联网。下载中断后可重试续传。')
                with client.stream('POST',self.url+'/api/pull',json={'model':MODEL,'stream':True},timeout=httpx.Timeout(60,connect=15)) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if self.stop.is_set():return
                        if not line:continue
                        item=json.loads(line)
                        if item.get('error'):raise RuntimeError(item['error'])
                        total=item.get('total',0);done=item.get('completed',0)
                        if total:status(f'正在下载模型：{done/total:.0%}（{done/1024**3:.2f} / {total/1024**3:.2f} GB）')
                        else:status('正在准备模型：'+item.get('status','请稍候'))
                response=client.get(self.url+'/api/tags');response.raise_for_status()
                if not model_available(response.json()):raise RuntimeError('下载未完成，请检查网络后重试。')
        status('本地模型已就绪。')
    def close(self):
        with self.guard:
            if self.process is not None and self.process.poll() is None:
                subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,timeout=10)
                self.process.wait(timeout=10)
            if self.log:self.log.close();self.log=None
