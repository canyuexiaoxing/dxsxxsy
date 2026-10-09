from urllib.parse import urlsplit
import httpx
from agent.tasks import check_cancelled,abortable_client


class OllamaEmbedding:
    def __init__(self,model='qwen3-embedding:4b',base_url='http://127.0.0.1:11434'):
        self.model,self.base_url=model,base_url.rstrip('/')
        parsed=urlsplit(base_url)
        if parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.scheme not in {'http','https'}:
            raise ValueError('本地Embedding地址必须指向本机')

    def encode(self,texts):
        try:
            with httpx.Client(timeout=120,trust_env=False) as client, abortable_client(client):
                response=client.post(self.base_url+'/api/embed',json={'model':self.model,'input':texts,'truncate':False,'options':{'num_ctx':2048}})
                response.raise_for_status()
                vectors=response.json()['embeddings']
            if len(vectors)!=len(texts) or not vectors or not vectors[0]: raise ValueError()
            return vectors
        except Exception:
            check_cancelled()
            raise ValueError('本地Embedding不可用，请先运行start-embedding.ps1') from None
