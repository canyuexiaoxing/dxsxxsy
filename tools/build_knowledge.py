import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from reader.config import Settings
from rag.embedding import OllamaEmbedding
from rag.index import KnowledgeIndex

if __name__=='__main__':
    cfg=Settings.load(); values={**dotenv_values(ROOT/'.env'),**os.environ}
    index=KnowledgeIndex(cfg.data_dir/'chroma',ROOT/'knowledge/entries.json',OllamaEmbedding(values.get('EMBEDDING_MODEL') or 'qwen3-embedding:4b',values.get('EMBEDDING_BASE_URL') or 'http://127.0.0.1:11434'))
    print(json.dumps(index.build(),ensure_ascii=False))
