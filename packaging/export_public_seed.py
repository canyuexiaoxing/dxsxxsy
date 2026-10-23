"""Export only public KB vectors; refuse nonmatching or private records."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from rag.index import KnowledgeIndex
from rag.embedding import OllamaEmbedding
from desktop_runtime import seed_payload
root=Path(__file__).resolve().parent.parent
k=KnowledgeIndex(root/'data/chroma',root/'knowledge/entries.json',OllamaEmbedding('qwen3-embedding:4b','http://127.0.0.1:11434'))
collection=k._collection()
payload=collection.get(include=['documents','embeddings','metadatas'])
seed={key:payload[key] for key in ('ids','documents','embeddings','metadatas')}
seed['embeddings']=seed['embeddings'].tolist()
seed['metadata']=collection.metadata
seed_payload(root/'knowledge/entries.json',seed)
(root/'knowledge/public-seed.json').write_text(json.dumps(seed,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print('Exported verified public vectors:',len(seed['ids']))
