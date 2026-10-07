"""Presentation and conditional self-checks; never add findings or assert benefits."""
import re

LEVEL_NOTE='红灯=高风险；黄灯=需关注；灰色=待核实。未检出风险不等于绿灯安全。'

def ordered_sources(report):
    priority=list(dict.fromkeys(sid for f in report.get('findings',[]) for sid in f.get('evidence_ids',[])))
    ranks={sid:i for i,sid in enumerate(priority)}
    kinds={'law':0,'warning':1,'guide':2,'case':3,'support':4}
    return sorted(report.get('sources',[]),key=lambda e:(kinds.get(e.get('kind'),5),ranks.get(e['id'],len(ranks))))

def overview_ids(report):
    available={s['id'] for s in report.get('sources',[])}
    return list(dict.fromkeys(sid for f in report.get('findings',[]) for sid in f.get('evidence_ids',[]) if sid in available))

def prepare_report(report,facts):
    report['sources']=ordered_sources(report)
    checks=[]
    if '就业协议' in facts:
        not_started=bool(re.search(r'尚未(?:入职|到岗)|未(?:实际)?入职|还没(?:有)?(?:入职|到岗)',facts))
        started=bool(re.search(r'已经(?:实际)?(?:入职|到岗)|已实际到岗|已到岗|实际提供了劳动',facts))
        if not not_started and not started:checks.append('是否已经实际到岗并提供劳动？')
        if not re.search(r'(?:签订|签署|签过|未签|尚未签).{0,8}(?:书面)?劳动合同',facts):
            checks.append('除就业协议外，是否另行签署书面劳动合同？如已实际用工，请说明起始时间。')
    report['self_checks']=checks
    return report
