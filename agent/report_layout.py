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

def assistant_voice(text):
    """Keep quoted judicial language intact; the assistant itself is not a court."""
    parts=re.split(r'(“[^”]*”|「[^」]*」|『[^』]*』)',text)
    for i,part in enumerate(parts):
        if i%2 and re.search(r'法院|判决|裁判|文书', ''.join(parts[:i])[-35:]):continue
        parts[i]=re.sub(r'本院|本法庭|本庭','本报告',part)
    return ''.join(parts)

def normalize_voice(result):
    changed=False
    def clean(text):
        nonlocal changed
        value=assistant_voice(text)
        changed=changed or value!=text
        return value
    result.message=clean(result.message)
    result.questions=[clean(s) for s in result.questions]
    if result.report:
        report=result.report
        report.summary=clean(report.summary);report.change_reason=clean(report.change_reason)
        report.limitations=[clean(s) for s in report.limitations]
        for finding in report.findings:
            finding.title=clean(finding.title);finding.explanation=clean(finding.explanation)
            finding.suggestions=[clean(s) for s in finding.suggestions]
            # Never rewrite the verified quotation from uploaded/user material.
    return ['纠正智能体自称法院的措辞'] if changed else []

def sanitize_display(result,sources):
    """Presentation boundary: never alter source quotations or evidence IDs."""
    labels={sid:'《'+entry.get('title','官方依据')+'》'+entry.get('location','') for sid,entry in sources.items()}
    def clean(text):
        text=re.sub(r'Q[a-fA-F0-9]{20}(?![a-fA-F0-9])','材料原句',text)
        for sid in sorted(labels,key=len,reverse=True):
            text=re.sub(r'(?<![A-Za-z0-9_-])'+re.escape(sid)+r'(?![A-Za-z0-9_-])',lambda _:labels[sid],text)
        return text
    result.message=clean(result.message);result.questions=[clean(q) for q in result.questions]
    if result.report:
        r=result.report;r.summary=clean(r.summary);r.change_reason=clean(r.change_reason)
        r.limitations=[clean(s) for s in r.limitations]
        for f in r.findings:
            f.title=clean(f.title);f.explanation=clean(f.explanation)
            f.suggestions=[clean(s) for s in f.suggestions]
            for c in f.legal_claims:c.statement=clean(c.statement)

def normalize_layout(result,context):
    facts=facts_text(context);changes=[]
    if result.action=='answer':
        focused=focused_lines(result.message,facts)
        if focused and focused!=result.message:
            result.message=focused;changes.append('删除未涉及事实领域的建议段落')
        return changes+normalize_voice(result)
    if not result.report:return changes+normalize_voice(result)
    report=result.report;kept=[];groups={};advice=[];check_ids=[]
    no_salary=bool(re.search(r'无薪试岗|试岗.*(?:不支付|拒付)',facts))
    external=bool(re.search(r'外包|派遣',facts))
    abnormal_pay=bool(re.search(r'欠薪|欠付|拖欠|拒付|不支付|漏缴|断缴|不缴|不交|未缴|未足额',facts))
    training_service=bool(re.search(r'培训',facts) and re.search(r'服务期|服务年限',facts))
    cancelled_offer=bool(re.search(r'录用',facts) and re.search(r'取消录用|无法安排入职|尚未实际入职|没有.*实际入职',facts))
    no_work_registration=bool(re.search(r'求职登记|登记求职',facts) and re.search(r'未安排[^。\n]*有报酬|尚未实际用工',facts))
    noncompete=bool(re.search(r'保密协议|竞业限制|不得从事同类',facts))
    for finding in report.findings:
        finding.evidence_ids=list(dict.fromkeys(finding.evidence_ids+[sid for claim in finding.legal_claims for sid in claim.basis_ids]))
        title=finding.title
        structured_risk=finding.category=='risk' and finding.fact_basis in {'abnormal_clause','abnormal_behavior'}
        check=None
        if finding.category=='advice':
            advice.append(finding);changes.append('结构化行动建议移出风险：'+title);continue
        elif finding.category=='check' or finding.fact_basis in {'missing_information','normal_fact','user_request'}:
            check='核查与条件分析（不计为风险）：'+title+'。'+finding.explanation+'；建议：'+'；'.join(finding.suggestions)
        elif re.search(r'解除.{0,12}性质.*(?:不明|未知)|解除.*(?:理由|原因|责任).*不明',title) and not re.search(r'违法|拒付|拖欠|未签|未订立|歧视|报复|怀孕|病假|拒绝',title):
            check='解除的适用条件尚未明确（不计为风险）：'+title+'。'+finding.explanation+'；建议：'+'；'.join(finding.suggestions)
        elif no_work_registration and re.search(r'劳动关系|工伤',title) and re.search(r'求职登记|登记求职|未安排|了解工作环境|参观|食堂',finding.quote):
            check='登记与参观的判断条件（不计为风险）：'+title+'。'+finding.explanation+'；建议：'+'；'.join(finding.suggestions)
        elif re.search(r'^(?:求职者|劳动者|员工|您|你)?(?:可|可以|应|应当)(?:通过|向|申请|寻求|保存|保留)|^(?:维权|救济|处理)(?:途径|渠道|建议)',title) and not re.search(r'拒绝|阻碍|禁止',title):
            advice.append(finding)
            changes.append('救济与行动建议移出风险：'+title);continue
        elif re.search(r'(?:不足以|难以|无法)认定|缺乏.{0,12}(?:基础|依据)|(?:是否|能否).*(?:不明|未知|需个案判断)|(?:未载|未见|未提供).*(?:地域|范围|支付记录|补偿记录)',title):
            check='判断条件或材料缺口（不计为风险）：'+title+'。'+finding.explanation+'；核查建议：'+'；'.join(finding.suggestions)
        elif re.search(r'(?:材料|信息|证据).*(?:缺口|不足|未披露)|材料性质.*(?:限制|结论)|证据.*(?:部分保全|举证强度)',title):
            check='材料或证据局限：'+title+'。'+finding.explanation
        elif re.search(r'证据留存|举证成本|证据准备|维权时效准备',title):
            check='需准备实际用工、报酬及相关沟通证据；证据准备不另计为风险。'
            if kept:kept[0].suggestions=list(dict.fromkeys(kept[0].suggestions+finding.suggestions))[:5]
        elif not structured_risk and ((re.search(r'核查',title) and not re.search(r'发现|证实|查实',title)) or re.search(r'^(?:尚缺少|尚缺|信息不足)|(?:是否|能否).*(?:適用|适用|成立|合规).*(?:待核实|待确认|未知)|(?:需|待|有待)(?:进一步)?核(?:实|查)|待确认',title)):
            check='适用条件或材料信息未明，需进一步核实：'+title
        elif re.search(r'重复试用|变相试用',title) and not re.search(r'重复|反复|第二次|再次|又.*试用|另行.*试用',facts):
            check='材料未披露另行或重复约定试用期，需核对合同期限和实际约定，不认定已存在重复试用。'
        elif re.search(r'主体定位|责任主体|主体身份|付酬责任',title) and re.search(r'需.*核实|待核实|需明确|需核实',title):
            check='需核实签约、实际管理与发薪主体，不因缺少主体材料独立计为风险。'
        elif re.search(r'(?:就业协议|入职安排).*(?:不明|缺少|未提供)',title) and not re.search(r'拒(?:绝)?签.{0,8}(?:书面)?劳动合同|已(?:入职|到岗|用工).{0,12}(?:两|二|三|[2-9])个月.{0,15}未签',facts):
            check='就业协议内容及实际用工情况需进一步核实；未提供协议文本不等于未签合同或已经违法，不单列风险。'
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
            check_ids.extend(finding.evidence_ids)
            report.limitations.append(check);changes.append('核查事项移出风险：'+title);continue
        family=None
        if noncompete and re.search(r'竞业|保密义务|违约金',title) and not re.search(r'扣薪|扣发|欠薪|证件|泄露|培训',title):family='noncompete_obligation'
        if cancelled_offer and re.search(r'录用承诺|取消录用|缔约过失|信赖利益|录用后.*损失',title) and not re.search(r'扣押|扣留|欠薪|歧视|保证金|押金',title):family='offer_reliance'
        if no_salary and re.search(r'无薪|拒付|不支付|工资下限|试用期工资|最低工资',title) and not re.search(r'辞退|解除|解聘',title):family='trial_payment'
        if external and re.search(r'外包|实际管理|控制权|管理权|现场管理',title) and not re.search(r'欠薪|拖欠|工资|社保|工伤',title):family='employment_form'
        if training_service and re.search(r'服务期.*(?:违约|赔偿)|培训.*(?:违约|赔偿)|赔偿.*培训|培训费.*(?:上限|赔偿)|限制正常离职',title) and not re.search(r'工资|欠薪|扣发|扣除|扣留|扣押|证件|社保|贷款',title):family='training_service_payment'
        if re.search(r'辞职|离职',facts) and re.search(r'拒.{0,5}(?:交接|办理.{0,3}交接)|拒不办理工作交接',facts) and re.search(r'离职|交接|预告|通知|補救|补救|补位|损失|成本|违约责任',title) and not re.search(r'工资|扣薪|欠薪|社保|证件|经济补偿|竞业|保密|培训',title):family='resignation_damage'
        key=(family,None if family=='resignation_damage' else finding.material_id) if family else None
        if key and key in groups:
            primary=groups[key]
            primary.legal_claims += [c for c in finding.legal_claims if c not in primary.legal_claims]
            if family in {'training_service_payment','offer_reliance','noncompete_obligation','resignation_damage'}:
                primary.explanation+='\n\n'+finding.explanation
                primary.title={'training_service_payment':'培训服务期及培训费赔偿条款风险','offer_reliance':'取消录用造成信赖利益损失的风险','noncompete_obligation':'竞业限制条款及违约金请求的适用风险','resignation_damage':'未依法预告离职、拒绝交接所涉损失赔偿风险'}[family]
                levels={'uncertain':0,'attention':1,'high':2}
                primary.level=max((primary.level,finding.level),key=levels.get)
            primary.evidence_ids=list(dict.fromkeys(primary.evidence_ids+finding.evidence_ids))
            primary.suggestions=list(dict.fromkeys(primary.suggestions+finding.suggestions))
            changes.append('合并同一义务的风险：'+title);continue
        if key:groups[key]=finding
        finding.suggestions=[focused_lines(s,facts) for s in finding.suggestions]
        finding.suggestions=[s for s in finding.suggestions if s]
        kept.append(finding)
    for item in advice:
        if kept:
            kept[0].suggestions=list(dict.fromkeys(kept[0].suggestions+[item.explanation]+item.suggestions))
            kept[0].evidence_ids=list(dict.fromkeys(kept[0].evidence_ids+item.evidence_ids))
        else:
            report.limitations.append('行动建议（不计为风险）：'+item.explanation+'；'+'；'.join(item.suggestions))
    report.findings=kept
    report.limitations=list(dict.fromkeys(report.limitations))
    if changes:
        report.summary=('根据已提供事实，主要风险信号为：'+ '；'.join(f.title for f in kept)+'。相关判断须核对适用条件，不构成违法认定。') if kept else '现有材料未显示可确认的独立异常条款或行为；具体判断和待核实事项见分析局限。'
        result.evidence_ids=list(dict.fromkeys([sid for f in kept for sid in f.evidence_ids]+check_ids))
        merged=[c for c in changes if c.startswith('合并同一义务的风险：')]
        if result.action=='revise' and merged:
            report.change_reason='结合本轮新增信息更新判断，并完成最终结构复核：'+'；'.join(merged)+'。多个事实论据归入同一风险，说明、建议及直接依据均保留；具体判断变化与适用条件见本版报告。'
    return changes+normalize_voice(result)
