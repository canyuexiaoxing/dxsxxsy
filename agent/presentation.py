"""Public report views: keep diagnostics in storage, expose actionable advice."""
from copy import deepcopy
import re

URL_PATTERN = r'https?://[^\s<>"\u3000-\u303f\u3400-\u9fff\uff00-\uffef]+'
INTERNAL = re.compile(r'上轮复核|审核上限|修改未再复核|内容复核未完成|复核修改未通过|草稿第?\s*\d|review_status|review_notes|\bfinding\b|\bagent\b', re.I)
CHANNELS = (
    (r'企业信用|企业登记|企业工商|工商登记|工商资质|工商信息|国家企业信用信息公示系统',
     'www.gsxt.gov.cn', '核查入口：https://www.gsxt.gov.cn/（国家企业信用信息公示系统）。'),
    (r'人社|人力资源和社会保障|12333',
     'www.12333.gov.cn', '人社办事入口：https://www.12333.gov.cn/；咨询热线：12333。可选择所在地，具体许可查询和受理渠道请向属地人社部门确认。'),
    (r'公共法律服务|法律援助|12348',
     'www.12348.gov.cn', '公共法律服务入口：https://www.12348.gov.cn/；咨询热线：12348。具体服务以所在地受理范围为准。'),
)
USER_LIMIT = '请结合原始材料核实关键事实；尚未确认的内容仅作风险提示，可补充材料后再更新结论。'


def actionable(text):
    """Enrich an already recommended channel; never infer new risk or a local number."""
    original=str(text); result=original
    for pattern,host,detail in CHANNELS:
        if re.search(pattern,original):
            if host not in result:
                result+=' '+detail
            elif host=='www.12333.gov.cn' and not re.search(r'热线[：:]?\s*12333|电话[：:]?\s*12333',result):
                result+=' 咨询热线：12333。'
            elif host=='www.12348.gov.cn' and not re.search(r'热线[：:]?\s*12348|电话[：:]?\s*12348',result):
                result+=' 咨询热线：12348。'
    if re.search(r'报警|向公安|拨打110',original) and '110' not in result:
        result+=' 遇到人身危险或紧急情况，请拨打110。'
    return result


def public_report(report):
    result=deepcopy(report)
    status=result.pop('review_status',{}) or {}
    notes=result.pop('review_notes',[]) or []
    limitations=result.get('limitations',[])
    filtered=[s for s in limitations if not INTERNAL.search(str(s))]
    if notes or len(filtered)!=len(limitations) or status.get('status') not in (None,'passed','not_requested'):
        if USER_LIMIT not in filtered:filtered.append(USER_LIMIT)
    result['limitations']=filtered
    if INTERNAL.search(str(result.get('change_reason',''))):result['change_reason']='根据补充材料更新风险说明与建议。'
    if result.get('prevention'):
        result['prevention']['steps']=[actionable(s) for s in result['prevention'].get('steps',[])]
    for finding in result.get('findings',[]):
        finding['suggestions']=[actionable(s) for s in finding.get('suggestions',[])]
    return result


def public_reply(reply):
    result=deepcopy(reply)
    if result.get('report'):result['report']=public_report(result['report'])
    if isinstance(result.get('message'),str):
        result['message']='\n'.join(line for line in result['message'].splitlines() if not INTERNAL.search(line))
    return result


def public_session(session):
    result=deepcopy(session)
    result.pop('traces',None);result.pop('fact_ledgers',None)
    result['reports']=[public_report(r) for r in result.get('reports',[])]
    for message in result.get('messages',[]):
        if message.get('role')=='assistant':
            if message.get('result'):message['result']=public_reply(message['result'])
            if isinstance(message.get('text'),str):
                message['text']='\n'.join(s for s in message['text'].splitlines() if not INTERNAL.search(s))
    return result
