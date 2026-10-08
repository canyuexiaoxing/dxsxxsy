"""One-time verified migration: reuse unchanged vectors, embed only added text."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if not (ROOT/'rag').exists():ROOT=Path(r'E:\workp\dxsxxsy')
sys.path.insert(0,str(ROOT))
from rag.index import KnowledgeIndex
from rag.embedding import OllamaEmbedding
from reader.config import Settings

def embedding_text(e):return e['title']+' '+e['location']+' '+e['text']+' '+' '.join(e['tags'])
def metadata(e):return dict(kind=e['kind'],case_id=e.get('case_id',''),chunk_role=e.get('chunk_role',''),stage_scope=e.get('stage_scope','both'),risk_topics=','.join(e.get('risk_topics',[])))

if __name__=='__main__':
 out=ROOT/'knowledge/evaluations/profile-20261007'
 old_raw=(out/'entries-before.json').read_bytes();old=json.loads(old_raw.decode('utf-8-sig'));old_map={e['id']:e for e in old}
 cfg=Settings.load();index=KnowledgeIndex(cfg.data_dir/'chroma',ROOT/'knowledge/entries.json',OllamaEmbedding());new=index._entries();collection=index._collection();info=collection.metadata or {}
 if info.get('source_hash')==index._fingerprint():
  print('Current index already matches; no mutation');sys.exit(0)
 assert info.get('source_hash')==hashlib.sha256(old_raw).hexdigest(),'旧库摘要不匹配，停止迁移'
 assert info.get('embedding_model')==index.embedding.model,'模型变化，不能复用向量'
 assert set(collection.get()['ids'])==set(old_map),'数据库与旧快照不一致'
 unchanged=[e for e in new if e['id'] in old_map and embedding_text(e)==embedding_text(old_map[e['id']])]
 changed=[e for e in new if e not in unchanged]
 assert len(unchanged)==len(old) and len(changed)==4,'本轮只允许新增四条提示与修改标签'
 print('Embedding four new official warning summaries',flush=True)
 vectors=index.embedding.encode([embedding_text(e) for e in changed])
 collection.update(ids=[e['id'] for e in unchanged],metadatas=[metadata(e) for e in unchanged])
 collection.upsert(ids=[e['id'] for e in changed],embeddings=vectors,documents=[e['text'] for e in changed],metadatas=[metadata(e) for e in changed])
 collection.modify(metadata={**info,'source_hash':index._fingerprint(),'profile_version':'preemployment-20261007'})
 assert collection.count()==len(new)
 result=dict(count=len(new),vectors_reused=len(unchanged),vectors_added=len(changed),model=index.embedding.model)
 (out/'index-refresh.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
