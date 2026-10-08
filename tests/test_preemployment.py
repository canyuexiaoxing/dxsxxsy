import unittest,json
from agent.preemployment import detect_stage,prepare_prevention

def context(text,material='',history=None):return {'current_message':text,'history':history or [],'materials':[{'pages':[{'text':material}]}] if material else []}
class PreemploymentTests(unittest.TestCase):
 def test_normal_recruiting_promise_is_not_a_risk(self):
  from agent.preemployment import normalize_preemployment
  from tests.test_content_layout import result
  r=result(['不收费承诺仍需预防']);f=r.report.findings[0]
  f.quote='招聘方明确不收押金、培训费或其他费用，不扣留身份证原件。'
  f.category='risk';f.fact_basis='abnormal_clause'
  normalize_preemployment(r,{'employment_stage':'preemployment','current_message':f.quote})
  self.assertEqual(len(r.report.findings),0)
 def test_deposit_and_its_refund_are_one_risk(self):
  from agent.preemployment import normalize_preemployment
  from tests.test_content_layout import result
  r=result(['履约保证金收费','保证金变相违约金','超长试用期'])
  for f in r.report.findings[:2]:f.quote='入职前向招聘公司支付2000元保证金，办完交接后退还。'
  normalize_preemployment(r,{'employment_stage':'preemployment','current_message':'尚未入职'})
  self.assertEqual(len(r.report.findings),2)
 def test_training_arguments_merge_but_loan_stays_separate(self):
  from agent.preemployment import normalize_preemployment
  from tests.test_content_layout import result
  r=result(['招转培高额培训费','招聘条件与付费培训不一致','只推荐面试不保证录用','培训贷还款义务'])
  for f in r.report.findings:f.quote='先支付培训费，贷款分12期，结业推荐面试。'
  normalize_preemployment(r,{'employment_stage':'preemployment','current_message':'招聘方让先付费培训，可贷款。'})
  self.assertEqual(len(r.report.findings),2)
 def test_default_post_hire_remedy_is_rejected_before_employment(self):
  from agent.preemployment import prevention_issues
  from agent.schema import TurnResult
  from tests.test_content_layout import result
  r=result(['招聘保证金风险']);r.report.findings[0].suggestions=['建议申请劳动仲裁并主张双倍工资。']
  self.assertTrue(prevention_issues(r,'preemployment'))
  self.assertEqual(prevention_issues(r,'employed'),[])
 def test_pre_hire_sources_do_not_inject_post_hire_double_wages(self):
  from agent.quality import context_sources
  ids=[]
  def get(sid):ids.append(sid);return {'id':sid,'kind':'law' if sid!='K005' else 'warning'}
  results=context_sources('还没入职，未签合同，对方要求付费培训。',[],get,stage='preemployment')
  self.assertNotIn('LCL-082',ids)
  self.assertIn('K001',ids)
  self.assertIn('K005',[r['id'] for r in results])
 def test_explicit_started_fact_beats_general_pre_hire_question(self):
  self.assertEqual(detect_stage(context('我已经入职了，现在回头看签约前应该核查什么？')),'employed')
 def test_unstarted_offer_is_preemployment(self):
  self.assertEqual(detect_stage(context('我还没有入职，HR让我贷款培训。')),'preemployment')
 def test_offer_review_is_preemployment(self):
  self.assertEqual(detect_stage(context('我拿到了OFFER，准备入职，想看看有没有坑。')),'preemployment')
 def test_unsigned_draft_is_not_existing_employment(self):
  self.assertEqual(detect_stage(context('帮我看拟签协议','入职后试用期两个月。')),'preemployment')
 def test_later_actual_work_overrides_history(self):
  self.assertEqual(detect_stage(context('我已经到岗工作一个月了。',history=[{'role':'user','text':'我还没入职。'}])),'employed')
 def test_quote_future_clause_does_not_prove_started(self):
  self.assertEqual(detect_stage(context('这是招聘信息，请分析。','录用后员工已经入职的，按公司制度执行。')),'preemployment')
 def test_unknown_stage_is_not_assumed(self):
  self.assertEqual(detect_stage(context('这个协议有什么问题？')),'unknown')
 def test_unstarted_high_risk_has_pause_decision_not_compensation(self):
  r={'findings':[{'level':'high','suggestions':['暂缓付款，核对收费主体。']}],'limitations':[]}
  prepare_prevention(r,'preemployment')
  self.assertEqual(r['prevention']['decision'],'pause')
  self.assertIn('暂缓',r['prevention']['label'])
 def test_zero_findings_never_promises_safe(self):
  r={'findings':[],'limitations':['企业主体未知']};prepare_prevention(r,'preemployment')
  self.assertEqual(r['prevention']['decision'],'verify')
  self.assertIn('不等于安全',r['prevention']['label'])
 def test_employed_does_not_get_pre_hire_decision(self):
  r={'findings':[]};prepare_prevention(r,'employed');self.assertNotIn('prevention',r)
if __name__=='__main__':unittest.main()
