import unittest,json
import httpx
from reader.vision import VisionClient,VisionError
from reader.config import Settings
from agent.schema import TurnResult
from agent.report_layout import normalize_layout
from agent.engine import AgentEngine,CitationError

def turn(category='check',basis='missing_information'):
 return TurnResult.model_validate(dict(action='report',message='',questions=[],evidence_ids=['L'],report=dict(summary='摘要',limitations=[],findings=[dict(title='赔偿请求成立条件',level='uncertain',quote='合同总期限未披露。',material_id='user',page_number=0,explanation='条件未知。',evidence_ids=['L'],suggestions=['核对合同。'],category=category,fact_basis=basis,legal_claims=[dict(statement='按合同期限核对试用期上限。',basis_ids=['L'])])],change_reason='')))

class SystemicRepairs(unittest.TestCase):
 def test_resignation_loss_arguments_are_one_damage_risk(self):
  from tests.test_content_layout import result
  r=result(['未提前通知离职可能赔偿','拒不办理交接的赔偿风险','单位补救成本与损失赔偿风险'],['未预告。','未交接。','补位费用须证明因果关系。'])
  r.report.findings[1].material_id='another-upload'
  normalize_layout(r,dict(current_message='员工辞职即走，拒绝交接，公司采取补救并承担损失。',materials=[],history=[]))
  self.assertEqual(len(r.report.findings),1)
  self.assertIn('因果关系',r.report.findings[0].explanation)
 def test_program_leaves_article_90_applicability_to_auditor(self):
  r=turn('risk','abnormal_behavior');r.evidence_ids=['LCL-090'];f=r.report.findings[0];f.evidence_ids=['LCL-090']
  f.legal_claims[0].statement='劳动者违反劳动合同约定给单位造成损失的，应承担赔偿责任。';f.legal_claims[0].basis_ids=['LCL-090']
  AgentEngine(None,None,None,None)._validate(r,dict(reports=[],messages=[]),[],f.quote,{'LCL-090':{'kind':'law'}})
 def test_program_leaves_penalty_reduction_to_auditor(self):
  r=turn('risk','abnormal_clause');r.evidence_ids=['LCL-023'];f=r.report.findings[0];f.evidence_ids=['LCL-023'];f.suggestions=['可以请求酌减违约金。'];f.legal_claims[0].basis_ids=['LCL-023']
  AgentEngine(None,None,None,None)._validate(r,dict(reports=[],messages=[]),[],f.quote,{'LCL-023':{'kind':'law','text':'可以约定竞业限制条款。'}})
 def test_limited_article_90_claim_is_accepted(self):
  r=turn('risk','abnormal_behavior');r.evidence_ids=['LCL-090'];f=r.report.findings[0];f.evidence_ids=['LCL-090']
  f.legal_claims[0].statement='违反本法规定解除劳动合同给单位造成损失，应当赔偿。';f.legal_claims[0].basis_ids=['LCL-090']
  AgentEngine(None,None,None,None)._validate(r,dict(reports=[],messages=[]),[],f.quote,{'LCL-090':{'kind':'law'}})
 def test_ocr_digit_spacing_is_formatting_not_two_counts(self):
  r=self.vision([dict(text='迟到1 5 次。1、5两项。共1.5小时。',issues=[],unreadable=False)]).extract(b'test','image/png')
  self.assertEqual(r.text,'迟到15 次。1、5两项。共1.5小时。')
 def test_actual_unsigned_contract_kept_despite_conditional_title(self):
  r=turn('risk','abnormal_behavior');f=r.report.findings[0]
  f.title='用工九个月未订立书面合同，金额需核查';f.quote='公司未与员工订立书面劳动合同。'
  normalize_layout(r,dict(current_message=f.quote,materials=[],history=[]))
  self.assertEqual(len(r.report.findings),1)
 def test_bare_unknown_dismissal_is_check_even_if_model_labels_risk(self):
  for title in ['解除性质与责任不明：解除理由、主体和程序材料缺失','解除劳动关系的性质与原因不明，影响补偿请求方向']:
   with self.subTest(title=title):
    r=turn('risk','abnormal_behavior');f=r.report.findings[0]
    f.title=title;f.quote='2022年8月2日解除劳动关系。'
    normalize_layout(r,dict(current_message=f.quote,materials=[],history=[]))
    self.assertEqual(len(r.report.findings),0)
 def test_misplaced_change_reason_is_relocated_without_loss(self):
  from agent.schema import parse_turn
  value=turn().model_dump();value['change_reason']='新增事实改变依据';value['report'].pop('change_reason')
  r=parse_turn(json.dumps(value));self.assertEqual(r.report.change_reason,'新增事实改变依据')
 def test_conflicting_change_reasons_are_not_silently_rewritten(self):
  from agent.schema import parse_turn
  from pydantic import ValidationError
  value=turn().model_dump();value['change_reason']='甲';value['report']['change_reason']='乙'
  with self.assertRaises(ValidationError):parse_turn(json.dumps(value))
 def test_reviewer_accepts_issue_schema_in_one_request(self):
  from agent.model import ChatModel
  class Stub(ChatModel):
   def __init__(self):self.calls=0
   def complete(self,*args,**kwargs):self.calls+=1;return {'content':json.dumps(__import__('tests.audit_fixture',fromlist=['audit']).audit())}
  model=Stub();context=dict(materials=[],history=[],latest_report=None,current_message='',material_quotes=[])
  self.assertEqual(model.review(context,turn(),{})['issues'],[])
  self.assertEqual(model.calls,1)
 def test_reviewer_invalid_schema_does_not_add_audit_calls(self):
  from agent.model import ChatModel,ModelError
  class Stub(ChatModel):
   def __init__(self):self.calls=0
   def complete(self,*args,**kwargs):self.calls+=1;return {'content':json.dumps(turn().model_dump())}
  model=Stub();context=dict(materials=[],history=[],latest_report=None,current_message='',material_quotes=[])
  with self.assertRaises(ModelError):model.review(context,turn(),{})
  self.assertEqual(model.calls,1)
 def vision(self,contents):
  answers=iter(contents)
  def handle(request):
   return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(next(answers),ensure_ascii=False)}}]})
  return VisionClient(Settings(api_key='test',model='test'),httpx.MockTransport(handle))
 def test_harmless_extra_field_does_not_lose_ocr(self):
  r=self.vision([dict(type='json_object',text='迟到15次。',issues=[],unreadable=False)]).extract(b'test','image/png')
  self.assertEqual(r.text,'迟到15次。')
 def test_wrong_type_is_repaired_once(self):
  r=self.vision([dict(text=15,issues=[],unreadable=False),dict(text='15次',issues=[],unreadable=False)]).extract(b'test','image/png')
  self.assertEqual(r.text,'15次')
 def test_persistent_missing_text_fails(self):
  with self.assertRaises(VisionError):self.vision([dict(issues=[],unreadable=False)]*2).extract(b'test','image/png')
 def test_structured_checks_do_not_depend_on_title(self):
  r=turn();normalize_layout(r,{'current_message':'合同总期限未披露。','materials':[],'history':[]})
  self.assertEqual(len(r.report.findings),0)
  self.assertIn('核对合同',r.report.limitations[0])
 def test_missing_fact_cannot_be_counted_as_risk(self):
  r=turn('risk','missing_information');normalize_layout(r,{'current_message':'合同总期限未披露。','materials':[],'history':[]})
  self.assertEqual(len(r.report.findings),0)
 def test_program_checks_case_id_exists_without_deciding_applicability(self):
  r=turn('risk','abnormal_clause');r.report.findings[0].level='attention'
  r.report.findings[0].evidence_ids=['L','C'];r.report.findings[0].legal_claims[0].basis_ids=['C']
  AgentEngine(None,None,None,None)._validate(r,{'reports':[],'messages':[]},[],'合同总期限未披露。',{'L':{'kind':'law'},'C':{'kind':'case'}})
 def test_display_hides_internal_ids_without_rewriting_quote(self):
  from agent.report_layout import sanitize_display
  r=turn('risk','abnormal_clause');q='Q'+'a'*20
  r.message='根据'+q+'以及LCL-039处理。';r.report.findings[0].quote=q
  sanitize_display(r,{'LCL-039':{'title':'劳动合同法','location':'第三十九条'}})
  self.assertNotIn(q,r.message);self.assertNotIn('LCL-039',r.message)
  self.assertIn('第三十九条',r.message);self.assertEqual(r.report.findings[0].quote,q)
if __name__=='__main__':unittest.main()
