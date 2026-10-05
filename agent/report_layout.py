"""Conservative layout guards: do not count checks and advice as material risks."""
import re

TOPICS=[(r'培训贷|贷款|借贷',r'贷款|借款|借贷|分期'),(r'婚育|性别歧视|女性歧视|妇联|12338',r'婚育|性别|歧视|女性|妇女|男|女'),(r'境外|使领馆',r'境外|海外|出国|外国|使领馆'),(r'诈骗|报案|公安|报警',r'诈骗|骗钱|欺骗|骗局|骗子|报案|公安|报警|威胁|限制人身自由|失联|被困')]

def facts_text(context):
    parts=[context.get('current_message','')]
    parts += [m.get('text','') for m in context.get('history',[]) if m['role']=='user']
    parts += [p['text'] for m in context.get('materials',[]) for p in m['pages']]
    return '\n'.join(parts)

def focused_lines(text,facts):
    lines=text.splitlines();kept=[]
    for line in lines:
        if any(re.search(topic,line) and not re.search(trigger,facts) for topic,trigger in TOPICS):continue
        kept.append(line)
    return '\n'.join(kept).strip()

def normalize_layout(result,context):
    facts=facts_text(context);changes=[]
    if result.action=='answer':
        focused=focused_lines(result.message,facts)
        if focused and focused!=result.message:
            result.message=focused;changes.append('删除未涉及事实领域的建议段落')
        return changes
    if not result.report:return changes
    report=result.report;kept=[];groups={}
    no_salary=bool(re.search(r'无薪试岗|试岗.*(?:不支付|拒付)',facts))
    external=bool(re.search(r'外包|派遣',facts))
    abnormal_pay=bool(re.search(r'欠薪|欠付|拖欠|拒付|不支付|漏缴|断缴|不缴|不交|未缴|未足额',facts))
    for finding in report.findings:
        title=finding.title
        check=None
        if re.search(r'证据留存|举证成本|证据准备|维权时效准备',title):
            check='需准备实际用工、报酬及相关沟通证据；证据准备不另计为风险。'
            if kept:kept[0].suggestions=list(dict.fromkeys(kept[0].suggestions+finding.suggestions))[:5]
        elif (re.search(r'核查',title) and not re.search(r'发现|证实|查实',title)) or re.search(r'^(?:尚缺少|尚缺|信息不足)|(?:是否|能否).*(?:適用|适用|成立|合规).*(?:待核实|待确认|未知)|(?:需|待|有待)(?:进一步)?核(?:实|查)|待确认',title):
            check='适用条件或材料信息未明，需进一步核实：'+title
        elif re.search(r'重复试用|变相试用',title) and not re.search(r'重复|反复|第二次|再次|又.*试用|另行.*试用',facts):
            check='材料未披露另行或重复约定试用期，需核对合同期限和实际约定，不认定已存在重复试用。'
        elif re.search(r'主体定位|责任主体|主体身份|付酬责任',title) and re.search(r'需.*核实|待核实|需明确|需核实',title):
            check='需核实签约、实际管理与发薪主体，不因缺少主体材料独立计为风险。'
        elif re.search(r'主体.*不清|主体.*不明|(?:合同|劳动关系)归属不(?:明|清)',title) and not re.search(r'拒绝.*(?:告知|明确).*(?:主体|单位)|冒用|伪造|合同.*(?:互相矛盾|不一致)',facts):
            check='需核实合同及用人单位主体；材料未披露签约情况，不据此认定主体安排已损害权益。'
        elif re.search(r'告知不明确|未履行.*告知|招聘阶段.*告知',title) and not re.search(r'未告知|隐瞒|拒绝告知|虚假宣传|虚假招聘|欺骗|没有说明',facts):
            check='材料未披露招聘沟通和告知过程，需核查书面说明，不认定已发生未履行告知义务。'
        elif re.search(r'收费培训|培训收费|培训费|变相收费',title) and not re.search(r'培训费|学费|缴费|交费|付费|培训.*收费|收费.*培训|垫付',facts):
            changes.append('删除无收费事实支撑的风险：'+title);continue
        elif re.search(r'派遣岗位|用工比例|派遣比例|三性',title) and not re.search(r'比例|临时性|辅助性|替代性|主营|派遣.*[0-9一二三四五六七八九十]+人',facts):
            check='未提供岗位性质和派遣人员数量、用工总量，需核实，不认定已违反岗位或比例限制。'
        elif re.search(r'代发|代缴|结算链|支付链|发薪链|工资.*链条',title) and not abnormal_pay:
            check='可核对工资到账、社保缴费及责任主体；正常发薪缴社保本身不另计为风险。'
        elif re.search(r'职业发展|岗位稳定|工龄.*(?:衔接|变动)|反复.*试岗',title) and not re.search(r'职业发展|岗位稳定|工龄|反复|多次',facts):
            check='材料未披露反复操作、工龄或职业发展受损等事实，不作额外风险判断。'
        elif any(re.search(topic,title) and not re.search(trigger,facts) for topic,trigger in TOPICS):
            changes.append('删除无当前事实支撑的主题：'+title);continue
        if check:
            report.limitations.append(check);changes.append('核查事项移出风险：'+title);continue
        family=None
        if no_salary and re.search(r'无薪|拒付|不支付|工资下限|试用期工资|最低工资',title) and not re.search(r'辞退|解除|解聘',title):family='trial_payment'
        if external and re.search(r'外包|实际管理|控制权|管理权|现场管理',title) and not re.search(r'欠薪|拖欠|工资|社保|工伤',title):family='employment_form'
        key=(family,finding.material_id) if family else None
        if key and key in groups:
            primary=groups[key]
            primary.evidence_ids=list(dict.fromkeys(primary.evidence_ids+finding.evidence_ids))
            primary.suggestions=list(dict.fromkeys(primary.suggestions+finding.suggestions))[:5]
            changes.append('合并同一义务的风险：'+title);continue
        if key:groups[key]=finding
        finding.suggestions=[focused_lines(s,facts) for s in finding.suggestions]
        finding.suggestions=[s for s in finding.suggestions if s]
        kept.append(finding)
    report.findings=kept
    report.limitations=list(dict.fromkeys(report.limitations))
    if changes:
        report.summary=('根据已提供事实，主要风险信号为：'+ '；'.join(f.title for f in kept)+'。相关判断须核对适用条件，不构成违法认定。') if kept else '现有材料不足以支持独立风险结论；需核实事项见分析局限。'
        result.evidence_ids=list(dict.fromkeys(sid for f in kept for sid in f.evidence_ids))
    return changes
