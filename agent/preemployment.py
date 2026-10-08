"""Stage-aware prevention guidance; retrieved cases never establish user facts."""
import re

PRE=re.compile(r'尚未(?:实际)?(?:入职|到岗|用工)|未(?:实际)?入职|还没(?:有)?(?:入职|到岗)|未报到|找实习|找工作|求职中|正在面试|还在面试|招聘(?:启事|信息|广告)|拟签|准备签|签约前|面试通知|录用通知|offer|准备入职|接受录用|参加面试',re.I)
POST=re.compile(r'(?:我|本人|员工|劳动者)?(?:已经|已实际|已)(?:到岗|入职|开始工作)|实际提供了劳动|工作了.{0,8}(?:月|年)|被辞退|被解雇|解除劳动关系|离职后')

def asserted_post(text):
    """Ignore denied, prohibited and hypothetical work facts, not actual history."""
    for sentence in re.split(r'[。！？；;\n]',text):
        for match in POST.finditer(sentence):
            prefix=sentence[:match.start()]
            local=re.split(r'[,，]|但是|不过|然而|但',prefix)[-1]
            if re.search(r'(?:不要|不能|不得|不应|请勿|避免|禁止|并非|不是|未曾|没有).{0,12}$',local):continue
            if re.search(r'如果|假如|假设|一旦|(?:^|[,，])若|入职后|录用后|合同(?:说|约定)|协议(?:说|约定)',prefix):continue
            if re.match(r'(?:了)?吗',sentence[match.end():]):continue
            return True
    return False

def detect_stage(context):
    # Most recent explicit user description wins over earlier messages/materials.
    texts=[context.get('current_message','')]+[m.get('text','') for m in reversed(context.get('history',[])) if m.get('role')=='user']
    for text in texts:
        if asserted_post(text):return 'employed'
        if PRE.search(text):return 'preemployment'
    material='\n'.join(p['text'] for m in context.get('materials',[]) for p in m.get('pages',[]))
    if PRE.search(material):return 'preemployment'
    if asserted_post(material):return 'employed'
    return 'unknown'

def prepare_prevention(report,stage):
    report['employment_stage']=stage
    if stage!='preemployment':return report
    findings=report.get('findings',[])
    high=any(f.get('level')=='high' for f in findings)
    steps=list(dict.fromkeys(s for f in findings for s in f.get('suggestions',[])))
    report['prevention']={
        'decision':'pause' if high else 'verify',
        'label':'先暂缓相关付款、贷款或签约，核查后再决定' if high else '先核查再决定；未检出风险不等于安全',
        'steps':steps[:8] or ['向招聘方取得岗位、薪资、费用及签约主体的书面说明，再据具体信息评估。'],
        'note':'这是签约与入职前的风险提示，不是对企业真实性、违法性质或岗位安全的认证。'}
    return report

def prevention_issues(result,stage):
    """Reject default employment remedies in pre-hire suggestions, not explanations."""
    if stage!='preemployment' or not result.report:return []
    issues=[]
    for i,f in enumerate(result.report.findings):
        for suggestion in f.suggestions:
            if re.search(r'申请劳动仲裁|主张.{0,10}(?:双倍工资|二倍工资|2N|经济补偿)|补缴社保',suggestion) and not re.search(r'不建议|不要|不能|不适用|若已|如果已|实际用工后|实际入职后|如果实际|尚不',suggestion):
                issues.append({'type':'pre_hire_remedy_mismatch','field':['report','findings',i,'suggestions'],'detail':'用户尚未实际用工，默认建议应是付款、贷款、签约前核查与规避；不直接推荐劳动仲裁、双倍工资、2N或补缴社保。若有实际用工或已发生损害，先说明并核对适用条件。'})
    return issues

def normalize_preemployment(result,context):
    if context.get('employment_stage')!='preemployment' or not result.report:return []
    from .report_layout import facts_text
    facts=facts_text(context);report=result.report;kept=[];groups={};changes=[];check_ids=[]
    multi=bool(re.search(r'两家公司|多个岗位|分别比较|A公司.*B公司',facts,re.I|re.S))
    training=bool(re.search(r'培训',facts) and re.search(r'付费|学费|培训费|自费',facts))
    for f in report.findings:
        if re.search(r'不收.{0,50}(?:费|押金|保证金)',f.quote) and re.search(r'不扣.{0,12}(?:证|原件)',f.quote) and not re.search(r'但|仍|另行|却|实际收|需支付|必须',f.quote) and not re.search(r'实际收|违反承诺|变相收|拒绝退',f.title):
            report.limitations.append('正常承诺待核对（不计为风险）：'+f.quote+'；核查建议：'+'；'.join(f.suggestions))
            check_ids.extend(f.evidence_ids);changes.append('正常承诺移出风险：'+f.title);continue
        family=None
        if re.search(r'刷单|充值.*任务|垫付|垫资',facts) and re.search(r'充值|垫付|垫资|先付款',f.quote) and re.search(r'刷单|垫资|充值|返利|任务.*先付款',f.title):family='task_payment'
        if re.search(r'保证金|押金',f.quote) and re.search(r'保证金|押金|退款|担保|违约金',f.title):family='deposit'
        if training and re.search(r'培训|招转培|推荐|录用保障|招聘.*(?:条件|信息|描述)|岗位真实性',f.title):
            family='training'
            if re.search(r'贷款|分期|借款',f.quote) and re.search(r'培训贷|还款|借款|授信|征信|贷款.*(?:责任|义务|风险|签约)',f.title):family='loan'
        if family and not multi and family in groups:
            a=groups[family];a.explanation+='\n\n'+f.explanation
            a.suggestions=list(dict.fromkeys(a.suggestions+f.suggestions))
            a.evidence_ids=list(dict.fromkeys(a.evidence_ids+f.evidence_ids))
            a.legal_claims += [c for c in f.legal_claims if c not in a.legal_claims]
            weights={'uncertain':0,'attention':1,'high':2};a.level=max([a.level,f.level],key=weights.get)
            a.title={'deposit':'招聘保证金及其退款、履约条件风险','training':'招聘转付费培训、岗位承诺与费用风险','loan':'培训贷款及还款责任风险','task_payment':'兼职充值垫资与返佣任务风险'}[family]
            changes.append('合并同一求职前风险：'+f.title);continue
        if family:groups[family]=f
        kept.append(f)
    report.findings=kept
    if changes:
        result.evidence_ids=list(dict.fromkeys(result.evidence_ids+check_ids+[sid for f in kept for sid in f.evidence_ids]))
        report.summary=('求职前需重点核查：'+'；'.join(f.title for f in kept)+'。先核实相关费用、签约主体和条款，再决定是否继续；这不是违法认定。') if kept else '现有材料未显示明确的异常条款或行为。先核验招聘主体、岗位真实性及书面条件；未检出风险不等于岗位已被证明安全。'
        if result.action=='revise':report.change_reason='结合新增求职事实更新判断，并完成最终风险组织复核：'+'；'.join(changes)+'。相关条件及论据保留在说明中。'
    return changes

PREEMPLOYMENT_RULES='''本产品核心目标：帮助大学生在找实习、找工作、面试、接受录用和签约之前识别坑并规避，不默认以已入职劳动争议为主线。就业阶段由模型依据用户当前真实经历判断，context的unknown仅表示尚未判断；合同中的未来条件不等于已实际就业，最新明确事实优先。
招聘方明确不收费、不扣证等正常承诺不是异常事实，只列核验与预防建议，不因尚未独立核验就标为risk。一次招转培中的高额学费、只推荐面试、不保障录用、招聘条件不一致是同一交易风险的不同论据，合并说明；实际提出贷款还款安排可以作为独立金融义务风险。保证金收取、退款限制和变相担保是同一笔费用问题，除非已明确另设独立违约金，否则不重复计数。
尚未入职时，优先分析招聘与岗位真实性线索、招聘转付费培训、贷款分期、押金担保、扣证、收费用途和主体、薪资构成与工作内容矛盾、付费试岗、录用承诺与拟签条款。未披露或薪资面议本身只列核查事项，不自动判骗局。
每项建议以预防行动为先：先暂缓什么付款/贷款/签字或交证件，向招聘方书面确认什么，通过具体官方依据/核查入口查什么，出现哪些拒绝核实、要求付款或承诺矛盾时应退出。核查结果只能减少特定疑点，不能把主体登记、对公账户、持牌机构或书面承诺当成继续付费求职的充分条件；独立培训需求应与求职分开评估。不得声称已核验公司或“可以放心入职”，不因没有风险点就给绿灯安全保证。
拟签合同中明确不合理的条款可以作为签约前风险，解释将来适用条件，但不能把计划、承诺或模板条款说成已经发生的扣薪、欠薪、辞退或用工。未实际用工时，未签劳动合同不是已发生违法用工，不主动推荐双倍工资、经济补偿、2N、补缴社保或劳动仲裁作为默认下一步。
先看主体和行为：用人单位招聘保证金与独立培训交易不同；有偿中介服务不当然等于用人单位违法收费。官方风险提示可支持求职风险判断，不能自动认定诈骗。若已付款/受威胁或实际入职，依据具体事实提供退款、投诉或相应救济，不能机械要求用户只有预防建议。
实习须区分在校教学实习、独立应聘实习与实际劳动关系，按实际主体和履行确定规则；不因岗位叫“实习”就自动套用普通员工全部待遇，也不因学生身份就断定没有劳动保护。
关键信息不足时追问尚未入职还是已实际用工、谁收费且钱给谁、签什么与谁签、岗位是否只是培训后推荐。只问会改变避坑判断的问题，先提示已明确的付款或贷款风险，不要求等待材料齐全才提醒暂缓危险操作。用户无法补充时给有限报告。
法律与案例只是规范和类比，不填补用户事实。对照结论重在是否识别风险和提出有效避坑步骤，不预测判决或保证赔偿。报告summary先写求职前最应注意的事项，suggestions给具体预防步骤；普通追问仍answer，新事实改变判断才revise。
'''
