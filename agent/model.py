import json
from urllib.parse import urlsplit
import httpx
from .tasks import check_cancelled,abortable_client,TaskCancelled


class ModelError(RuntimeError): pass


class ChatModel:
    requires_structured_findings=True
    def __init__(self,settings,transport=None): self.settings,self.transport=settings,transport
    def complete(self,messages,tools=None,force_search=False,review_mode=False):
        check_cancelled()
        cfg=self.settings
        if not cfg.api_key: raise ModelError('未配置DeepSeek密钥')
        parsed=urlsplit(cfg.base_url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password: raise ModelError('模型接口地址不合法')
        payload={'model':cfg.model,'messages':messages,'max_tokens':32768 if review_mode else 8192,'thinking':{'type':'enabled' if review_mode else 'disabled'}}
        if review_mode:payload['reasoning_effort']='high'
        if tools:
            payload['tools']=tools
            payload['tool_choice']={'type':'function','function':{'name':'search_knowledge'}} if force_search else 'auto'
        else: payload['response_format']={'type':'json_object'}
        try:
            with httpx.Client(timeout=cfg.timeout,transport=self.transport,follow_redirects=False,trust_env=False) as client, abortable_client(client):
                result=client.post(cfg.base_url.rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+cfg.api_key},json=payload)
            if result.status_code!=200: raise ModelError(f'模型接口HTTP {result.status_code}，本次未生成报告')
            choice=result.json()['choices'][0]
            if choice.get('finish_reason')=='length': raise ModelError('模型输出被截断，本次未生成完整报告')
            message=choice['message']
            return {k:message[k] for k in ['role','content','tool_calls'] if k in message}
        except (ModelError,TaskCancelled): raise
        except Exception:
            check_cancelled()
            raise ModelError('模型接口超时、连接失败或响应格式异常') from None


    def summarize_situation(self,context):
        from .situation import SITUATION_PROMPT, overview_input, valid_overview
        payload=overview_input(context)
        encoded=json.dumps(payload,ensure_ascii=False)
        if len(encoded)>200000:raise ModelError('情况概述材料超过预算')
        message=self.complete([{'role':'system','content':SITUATION_PROMPT},
                               {'role':'user','content':encoded}])
        try:
            value=json.loads(message.get('content') or '')
            if not isinstance(value,dict) or set(value)!={'overview'} or not valid_overview(value['overview']):
                raise ValueError()
            return ' '.join(value['overview'].split())
        except (ValueError,TypeError):raise ModelError('情况概述格式不合要求') from None

    def extract_facts(self,context):
        from .facts import FACT_PROMPT,FactLedger
        messages=[{'role':'system','content':FACT_PROMPT+'\n输出结构：'+json.dumps(FactLedger.model_json_schema(),ensure_ascii=False)},
                  {'role':'user','content':json.dumps(context,ensure_ascii=False)}]
        message=self.complete(messages)
        try:
            return json.loads(message.get('content') or '')
        except ValueError:
            raise ModelError('事实整理格式异常') from None

    def review(self,context,result,sources):
        """One isolated audit request; its memory contains audit records only."""
        from .quality import REVIEW_PROMPT,ContentAudit
        facts={k:context[k] for k in ('materials','history','latest_report','current_message','material_quotes')}
        if 'fact_ledger' in context:facts['fact_ledger']=context['fact_ledger']
        facts['employment_stage']='unknown'  # The auditor judges stage independently from user facts.
        facts['history']=[m for m in facts['history'] if m['role']=='user']
        facts.pop('material_quotes',None)
        fields=('id','kind','title','location','text','boundary','verification_status','related_article_ids')
        draft=result.model_dump()
        if draft.get('report'):
            for finding in draft['report']['findings']:
                for name in ('material_id','page_number','category','fact_basis'):finding.pop(name,None)
        payload={'context':facts,'draft':draft,
                 'review_memory':context.get('review_memory',[]),
                 'sources':[{k:e[k] for k in fields if k in e} for e in sources.values()]}
        messages=[{'role':'system','content':REVIEW_PROMPT+'\n输出结构：'+json.dumps(ContentAudit.model_json_schema(),ensure_ascii=False)},
                  {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
        message=self.complete(messages,review_mode=True)
        try:
            return ContentAudit.model_validate_json(message.get('content') or '').model_dump()
        except ValueError as exc:
            error=ModelError('复核结果格式异常，保留可用报告')
            error.validation_errors=[{'loc':list(e['loc']),'type':e['type']} for e in exc.errors()] if hasattr(exc,'errors') else []
            raise error from None
