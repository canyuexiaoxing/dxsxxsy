"""Curated retrieval labels; never infer the user's facts from knowledge labels."""
import re

TOPICS = {
 'fees':r'押金|保证金|建档费|服装费|体检费|报名费|收费|交钱',
 'agency':r'黑中介|职业中介|人力资源服务许可|中介费',
 'paid_offer':r'内推|保offer|保录|直签|保证录取',
 'training_loan':r'培训|招转培|培训贷|贷款|分期',
 'task_fraud':r'刷单|点赞|垫资|垫付|返佣|返现|充值任务',
 'job_truth':r'虚假招聘|虚假岗位|岗位职责|工作内容|薪资|高薪|招聘承诺',
 'contract':r'合同|协议|签约|空白|阴阳|违约金',
 'trial_intern':r'试用期|实习|试岗|转正',
 'identity':r'证件|身份证|银行卡|密码|验证码|个人信息|手机卡',
 'personal_safety':r'传销|境外|出境|下线|拉人头|入门费|人身安全',
 'fake_intern':r'实习生套娃|虚假实习|有偿实习|实习证明|招聘授权|免费劳动',
}

def detect_topics(text):
    return [name for name,pattern in TOPICS.items() if re.search(pattern,text,re.I)]

def label_entry(entry):
    """Conservative labels for retrieval, preserving original text/provenance."""
    e=dict(entry); sid=e['id']; title=e['title']; group=e.get('case_id','')
    stage='both';reason='规范及预防类比可用于拟签材料，不能认定实际用工'
    if e['kind']=='case':
        if group in {'C001','C004','O001','O002','O003','O004','O027'}:
            stage='pre';reason='案情涉及录用、求职收费或招聘阶段'
        elif re.search(r'协议|招聘公司|竞业|合作|服务期',title):
            stage='both';reason='已用工案件可作拟签条款类比，仍须区分实际履行'
        else:
            stage='post';reason='主要案情为已用工后的履行、解除或救济争议'
    elif sid.startswith('LCL-') and (38<=int(sid[4:])<=50 or 80<=int(sid[4:])<=92):
        stage='post';reason='主要为实际用工后的解除或责任规则；原文仍可按编号读取'
    elif sid in {'SUP-L-arbitration-21','SUP-L-arbitration-27','LAB-J1-001','LAB-J1-035','LAB-J2-007','SUP-C09','SUP-C14','SUP-A02','SUP-A03'}:
        stage='post';reason='实际用工后的争议、待遇或救济渠道'
    elif e['kind']=='support' and re.search(r'超过一个月未签|拖欠或克扣|辞退|离职|工伤|口头加班|996与未付',title):
        stage='post';reason='辅助卡主要针对已发生的用工争议'
    elif e['kind'] in {'warning','guide'} or sid in {'K001','K002'}:
        stage='pre';reason='招聘告知、收费扣证或官方求职预防提示'
    e.update(stage_scope=stage,employment_stages={'pre':['preemployment'],'post':['employed'],'both':['preemployment','employed']}[stage],
        risk_topics=detect_topics(title+' '+e['scope']+' '+' '.join(e['tags'])),classification_reason=reason,classified_at='2026-10-07')
    return e

def eligible_entries(entries,stage):
    if stage=='preemployment':
        return [e for e in entries if e.get('stage_scope','both')!='post']
    return entries

def boost_topic_scores(scores,mapping,query):
    topics=set(detect_topics(query))
    return {sid:score*(1+0.15*min(3,len(topics & set(mapping[sid].get('risk_topics',[]))))) for sid,score in scores.items()}
