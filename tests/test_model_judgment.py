import json,unittest
from unittest.mock import patch
from agent.engine import AgentEngine
from agent.schema import parse_turn
from tests import test_report_quality as helper
from tests.test_report_quality import QualityModel
from tests.test_agent import FakeRag,FakeModel,tool,output

class ModelJudgmentTests(unittest.TestCase):
 setUp=helper.ReportQualityTests.setUp
 tearDown=helper.ReportQualityTests.tearDown
 report=helper.ReportQualityTests.report
 def draft(self,report):
  d=json.loads(output('report',report)['content']);d['employment_stage']='preemployment';d['stage_reason']='用户明确尚未入职，离职后仅为未来合同条件。'
  return {'role':'assistant','content':json.dumps(d,ensure_ascii=False)}
 def test_stage_comes_from_model_not_future_clause_keyword(self):
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),FakeModel([tool(),self.draft(self.report())])).turn(self.sid,'尚未入职，公司要求保证金，合同约定离职后退还。')
  self.assertEqual(reply['report']['employment_stage'],'preemployment')
 def test_program_does_not_merge_model_risks_by_keywords(self):
  r=self.report('保证金收费');r['findings'].append(dict(r['findings'][0],title='保证金退款限制'))
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),FakeModel([tool(),self.draft(r)])).turn(self.sid,'尚未入职，公司要求保证金')
  self.assertEqual(len(reply['report']['findings']),2)
 def test_program_does_not_delete_answer_by_topic_keywords(self):
  o=output('answer');d=json.loads(o['content']);d['message']='若后续受到威胁，可向公安咨询。';o['content']=json.dumps(d)
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),FakeModel([tool(),o])).turn(self.sid,'公司要求保证金')
  self.assertIn('公安',reply['message'])
 def test_empty_answer_is_repaired_without_creating_report(self):
  empty=json.loads(output('answer')['content']);empty['message']=''
  valid=dict(empty,message='保留招聘广告、聊天记录和新旧确认书。')
  model=FakeModel([tool(),{'role':'assistant','content':json.dumps(empty)}, {'role':'assistant','content':json.dumps(valid,ensure_ascii=False)}])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'只给证据保存建议，不生成报告')
  self.assertEqual(reply['action'],'answer')
  self.assertIn('聊天记录',reply['message'])
  self.assertIsNone(reply['report'])
  self.assertEqual(self.sessions.get(self.sid)['reports'],[])
 def test_program_does_not_rule_on_law_applicability(self):
  r=self.report('是否适用需核查');r['findings'][0]['suggestions']=['可以核查是否适用违约金调减规则。']
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),FakeModel([tool(),self.draft(r)])).turn(self.sid,'公司要求保证金')
  self.assertIn('调减',reply['report']['findings'][0]['suggestions'][0])
 def test_review_notes_are_not_model_report_limitations(self):
  class Offline(QualityModel):
   def review(self,*a):raise ValueError('bad review')
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),Offline([tool(),self.draft(self.report())],[])).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['report']['limitations'],[])
  self.assertTrue(reply['report']['review_notes'])
 def test_model_stage_is_used_in_retrieval(self):
  class Rag(FakeRag):
   stage_aware=True
   def search(self,query,stage='unknown'):self.stage=stage;return super().search(query)
  rag=Rag();call=tool();call['tool_calls'][0]['function']['arguments']=json.dumps({'query':'保证金','stage':'preemployment'})
  AgentEngine(self.sessions,self.materials,rag,FakeModel([call,self.draft(self.report())])).turn(self.sid,'公司要求保证金，合同离职后退还。')
  self.assertEqual(rag.stage,'preemployment')

class AuditContractTests(unittest.TestCase):
 def test_every_check_is_required_once(self):
  from agent.quality import ContentAudit
  from tests.audit_fixture import audit
  from pydantic import ValidationError
  good=audit();ContentAudit.model_validate(good)
  good['checks'][-1]=dict(good['checks'][0])
  with self.assertRaises(ValidationError):ContentAudit.model_validate(good)
 def test_issue_verdict_without_concrete_feedback_is_invalid(self):
  from agent.quality import ContentAudit
  from tests.audit_fixture import audit
  from pydantic import ValidationError
  bad=audit();bad['checks'][0]['verdict']='issues'
  with self.assertRaises(ValidationError):ContentAudit.model_validate(bad)
 def test_reviewer_uses_reasoning_and_hides_material_quote_ids(self):
  import httpx
  from agent.model import ChatModel
  from reader.config import Settings
  from tests.audit_fixture import audit
  seen=[]
  def handle(request):
   seen.append(json.loads(request.content))
   return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(audit())}}]})
  context={'materials':[],'history':[],'latest_report':None,'current_message':'拟签合同','material_quotes':[{'quote_id':'Qwrong','quote':'拟签合同'}]}
  draft=parse_turn(output('answer')['content'])
  ChatModel(Settings(api_key='test'),httpx.MockTransport(handle)).review(context,draft,{})
  self.assertEqual(seen[0]['thinking']['type'],'enabled')
  self.assertNotIn('Qwrong',seen[0]['messages'][1]['content'])
  self.assertNotIn('tools',seen[0])
if __name__=='__main__':unittest.main()
