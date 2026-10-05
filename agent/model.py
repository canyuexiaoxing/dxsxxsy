from urllib.parse import urlsplit
import httpx


class ModelError(RuntimeError): pass


class ChatModel:
    def __init__(self,settings,transport=None): self.settings,self.transport=settings,transport
    def complete(self,messages,tools=None,force_search=False):
        cfg=self.settings
        if not cfg.api_key: raise ModelError('未配置DeepSeek密钥')
        parsed=urlsplit(cfg.base_url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password: raise ModelError('模型接口地址不合法')
        payload={'model':cfg.model,'messages':messages,'max_tokens':8192,'thinking':{'type':'disabled'}}
        if tools:
            payload['tools']=tools
            payload['tool_choice']={'type':'function','function':{'name':'search_knowledge'}} if force_search else 'auto'
        else: payload['response_format']={'type':'json_object'}
        try:
            with httpx.Client(timeout=cfg.timeout,transport=self.transport,follow_redirects=False,trust_env=False) as client:
                result=client.post(cfg.base_url.rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+cfg.api_key},json=payload)
            if result.status_code!=200: raise ModelError(f'模型接口HTTP {result.status_code}，本次未生成报告')
            choice=result.json()['choices'][0]
            if choice.get('finish_reason')=='length': raise ModelError('模型输出被截断，本次未生成完整报告')
            message=choice['message']
            return {k:message[k] for k in ['role','content','tool_calls'] if k in message}
        except ModelError: raise
        except Exception: raise ModelError('模型接口超时、连接失败或响应格式异常') from None
