import hashlib
import json
import re
from pathlib import Path
from threading import RLock


def tokens(text):
    result=set(re.findall(r'[a-z0-9]+',text.lower()))
    for sequence in re.findall(r'[\u4e00-\u9fff]+',text):
        result.update(sequence[i:i+2] for i in range(len(sequence)-1))
    return result


def select_evidence(ranked_ids,mapping):
    # Each source type has its own budget; a case never replaces a law slot.
    ranked=[mapping[sid] for sid in ranked_ids if sid in mapping]
    chosen=[e for e in ranked if e['kind']=='law'][:3]
    chosen += [e for e in ranked if e['kind'] in {'warning','guide'}][:2]
    cases=[e for e in ranked if e['kind']=='case']
    if cases:
        case=cases[0]
        if case.get('case_id'):
            related=[e for e in mapping.values() if e.get('case_id')==case['case_id']]
            order={'facts':0,'reasoning':1,'outcome':2}
            chosen += sorted(related,key=lambda e:order.get(e.get('chunk_role'),3))[:3]
        else: chosen.append(case)
    return chosen


class KnowledgeIndex:
    def __init__(self,directory:Path,source_path:Path,embedding):
        self.directory,self.source_path,self.embedding=directory,source_path,embedding
        self.lock=RLock()
        self._client=None

    def _entries(self):
        items=json.loads(self.source_path.read_text(encoding='utf-8-sig'))
        seen=set()
        for item in items:
            for field in ['id','title','kind','url','location','published_at','verified_at','text','scope','boundary','tags']:
                if field not in item: raise ValueError('知识条目缺少必需字段')
            if item['id'] in seen or not item['text'].strip(): raise ValueError('知识条目重复或为空')
            seen.add(item['id'])
        return items

    def _collection(self):
        if self._client is None:
            import chromadb
            from chromadb.config import Settings
            self._client=chromadb.PersistentClient(path=str(self.directory),settings=Settings(anonymized_telemetry=False))
        return self._client.get_or_create_collection('job_safety',metadata={'hnsw:space':'cosine'},embedding_function=None)

    def _fingerprint(self): return hashlib.sha256(self.source_path.read_bytes()).hexdigest()

    def build(self):
        with self.lock:
            entries=self._entries()
            if not entries: raise ValueError('知识库为空')
            vectors=[]
            for index in range(0,len(entries),4):
                vectors.extend(self.embedding.encode([e['title']+' '+e['location']+' '+e['text']+' '+' '.join(e['tags']) for e in entries[index:index+4]]))
            collection=self._collection()
            existing=collection.get()['ids']
            if existing: collection.delete(ids=existing)
            collection.upsert(ids=[e['id'] for e in entries],embeddings=vectors,documents=[e['text'] for e in entries],metadatas=[{'kind':e['kind'],'case_id':e.get('case_id',''),'chunk_role':e.get('chunk_role','')} for e in entries])
            collection.modify(metadata={'source_hash':self._fingerprint(),'embedding_model':self.embedding.model})
            return {'count':len(entries),'dimensions':len(vectors[0]),'model':self.embedding.model}

    def search(self,query):
        if not isinstance(query,str) or not query.strip() or len(query)>1500: raise ValueError('检索问题应为1至1500字符')
        with self.lock:
            collection=self._collection()
            metadata=collection.metadata or {}
            if metadata.get('source_hash')!=self._fingerprint() or metadata.get('embedding_model')!=self.embedding.model:
                raise ValueError('知识库尚未建立或资料/模型已变化，请重新运行build-knowledge.ps1')
            entries=self._entries(); mapping={e['id']:e for e in entries}
            vector=self.embedding.encode([query])
            semantic=[]
            for kinds in [('law',),('warning','guide'),('case',)]:
                count=sum(e['kind'] in kinds for e in entries)
                if not count: continue
                condition={'kind':kinds[0]} if len(kinds)==1 else {'kind':{'$in':list(kinds)}}
                result=collection.query(query_embeddings=vector,n_results=min(8,count),where=condition,include=['distances'])
                semantic.extend(sid for sid,d in zip(result['ids'][0],result['distances'][0]) if d<0.75)
            query_tokens=tokens(query)
            ranked=sorted(entries,key=lambda e:len(query_tokens & tokens(e['title']+' '+e['text']+' '+' '.join(e['tags']))),reverse=True)
            keyword=[e['id'] for e in ranked if len(query_tokens & tokens(e['title']+' '+e['text']+' '+' '.join(e['tags'])))>=2][:8]
            scores={}
            for ranking in [semantic,keyword]:
                for rank,sid in enumerate(ranking): scores[sid]=scores.get(sid,0)+1/(60+rank+1)
            return select_evidence(sorted(scores,key=scores.get,reverse=True),mapping)

    def get(self,source_id):
        for entry in self._entries():
            if entry['id']==source_id: return entry
        raise ValueError('未找到依据编号')
