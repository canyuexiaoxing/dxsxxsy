import json, unittest
from unittest.mock import patch
from agent.engine import AgentEngine, AgentError
from tests import test_report_quality as helper
from tests.test_agent import FakeRag, tool, output
from tests.test_report_quality import QualityModel

class LedgerModel(QualityModel):
 def __init__(self, outputs, reviews, bad=False):
  super().__init__(outputs,reviews); self.bad=bad; self.extract_contexts=[];self.analysis_contexts=[];self.audit_contexts=[]
 def extract_facts(self,context):
  self.extract_contexts.append(context)
  q=context['material_quotes'][0]['quote_id']
  return {'items':[{'status':'known','statement':'公司要求保证金','quote_ids':['Qinvented' if self.bad else q],'rationale':''},{'status':'unknown','statement':'收款账户尚不明确','quote_ids':[],'rationale':''}]}
 def complete(self,messages,**kwargs):
  self.analysis_contexts.append(json.loads(messages[1]['content']))
  return super().complete(messages,**kwargs)
 def review(self,context,*args):
  self.audit_contexts.append(context)
  return super().review(context,*args)

class FactLedgerTests(unittest.TestCase):
 setUp=helper.ReportQualityTests.setUp
 tearDown=helper.ReportQualityTests.tearDown
 report=helper.ReportQualityTests.report
 def test_quote_ids_are_short_unique_and_preserve_originals(self):
  from agent.engine import material_quotes
  text='尚未付款。费用9800元。可以分期。'
  quotes=material_quotes({'messages':[]},[],text)
  self.assertEqual([q['quote_id'] for q in quotes],['Q0001','Q0002','Q0003'])
  self.assertEqual(''.join(q['quote'] for q in quotes),text)
 def test_retry_receives_exact_reference_error_and_recovers(self):
  class Repairing(LedgerModel):
   def extract_facts(self,context):
    self.extract_contexts.append(context)
    if len(self.extract_contexts)==1:return {'items':[{'status':'known','statement':'公司要求保证金','quote_ids':['Q000'],'rationale':''}]}
    feedback=context['repair_feedback']
    self_feedback=feedback['errors'][0]
    assert self_feedback['type']=='unknown_quote_id'
    assert feedback['allowed_quote_ids']==['Q0001']
    return {'items':[{'status':'known','statement':'公司要求保证金','quote_ids':['Q0001'],'rationale':''}]}
  model=Repairing([tool(),output('report',self.report())],[[]])
  with self.assertLogs('agent.engine',level='WARNING') as logs:
   result=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(result['action'],'report')
  self.assertIn('unknown_quote_id',' '.join(logs.output))
  self.assertNotIn('公司要求保证金',' '.join(logs.output))
 def test_interface_error_is_not_disguised_as_reference_error(self):
  from agent.model import ModelError
  class Unavailable(LedgerModel):
   def extract_facts(self,context):
    self.extract_contexts.append(context)
    raise ModelError('模型接口HTTP 429，本次未生成报告')
  model=Unavailable([],[])
  with self.assertRaisesRegex(AgentError,'HTTP 429'):
   AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(model.extract_contexts),2)

 def test_fact_extraction_retry_has_a_fixed_limit(self):
  model=LedgerModel([tool(),output('report',self.report())],[[]],bad=True)
  with self.assertRaises(AgentError):AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(model.extract_contexts),2)
  self.assertEqual(self.sessions.get(self.sid)['messages'],[])
 def test_fact_extraction_api_uses_only_supplied_user_evidence(self):
  from agent.model import ChatModel
  from reader.config import Settings
  model=ChatModel(Settings(api_key='test'))
  original={'current_message':'未付款','material_quotes':[{'quote_id':'Q1','quote':'未付款'}]}
  response={'items':[{'status':'known','statement':'未付款','quote_ids':['Q1'],'rationale':''}]}
  with patch.object(model,'complete',return_value={'content':json.dumps(response)}) as complete:
   self.assertEqual(model.extract_facts(original),response)
  self.assertEqual(json.loads(complete.call_args.args[0][1]['content']),original)
 def test_shared_ledger_is_persisted_and_raw_inputs_remain(self):
  model=LedgerModel([tool(),output('report',self.report())],[[]])
  AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  ledger=model.analysis_contexts[0]['fact_ledger']
  self.assertEqual(ledger,model.audit_contexts[0]['fact_ledger'])
  self.assertEqual(ledger['items'][0]['evidence'][0]['quote'],'公司要求保证金')
  self.assertEqual(model.audit_contexts[0]['current_message'],'公司要求保证金')
  self.assertEqual(self.sessions.get(self.sid)['fact_ledgers'][-1]['ledger'],ledger)
 def test_invalid_fact_origin_blocks_analysis_and_persistence(self):
  model=LedgerModel([tool(),output('report',self.report())],[[]],bad=True)
  with self.assertRaisesRegex(AgentError,'事实'):
   AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(model.analysis_contexts,[])
  self.assertEqual(self.sessions.get(self.sid)['reports'],[])
 def test_extraction_never_receives_assistant_or_rag_facts(self):
  old=self.sessions.get(self.sid);old['messages']=[{'role':'assistant','result':{'message':'凭空贷款案例'}}];self.sessions.save(old)
  model=LedgerModel([tool(),output('report',self.report())],[[]])
  AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(model.extract_contexts),1)
  self.assertNotIn('凭空贷款案例',json.dumps(model.extract_contexts))
  self.assertNotIn('K001',json.dumps(model.extract_contexts))
 def test_first_report_change_reason_cleared_before_review(self):
  report=self.report();report['change_reason']='原报告有三条，现在合并'
  model=QualityModel([tool(),output('report',report)],[[]])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(model.checked[0]['report']['change_reason'],'')
  self.assertEqual(reply['report']['change_reason'],'')
 def test_old_first_version_word_hides_internal_edit_reason(self):
  from agent.word_export import render_report_docx
  from tests.test_word_export import example
  from zipfile import ZipFile
  from io import BytesIO
  report=example();report['change_reason']='内部草稿合并记录'
  with ZipFile(BytesIO(render_report_docx(report))) as archive:
   self.assertNotIn('内部草稿合并记录',archive.read('word/document.xml').decode())
  report['version']=2
  with ZipFile(BytesIO(render_report_docx(report))) as archive:
   self.assertIn('内部草稿合并记录',archive.read('word/document.xml').decode())
 def test_known_without_evidence_and_inferred_without_reason_rejected(self):
  from agent.facts import resolve_ledger
  for item in [{'status':'known','statement':'已贷款','quote_ids':[]}, {'status':'inferred','statement':'可能贷款','quote_ids':['Q1'],'rationale':''}]:
   with self.assertRaises(ValueError):resolve_ledger({'items':[item]},[{'quote_id':'Q1','quote':'分期'}])
 def test_audit_allows_check_labels_but_still_requires_complete_verdicts(self):
  from agent.quality import ContentAudit
  from tests.audit_fixture import audit
  good=audit()
  for check in good['checks']:check['title']='检查标题'
  ContentAudit.model_validate(good)
  good['checks'][0].pop('verdict')
  with self.assertRaises(ValueError):ContentAudit.model_validate(good)
 def test_production_model_cannot_silently_omit_stage_fields(self):
  class Production(QualityModel):requires_structured_findings=True
  body=json.loads(output('report',self.report())['content'])
  repaired={**body,'employment_stage':'preemployment','stage_reason':'用户未入职'}
  model=Production([tool(),{'content':json.dumps(body)},{'content':json.dumps(repaired)}],[[]])
  AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(model.checked[0]['employment_stage'],'preemployment')
  self.assertTrue(any(t['tool']=='citation_repair' for t in self.sessions.get(self.sid)['traces'][-1]))
 def test_audit_diagnostic_labels_do_not_discard_concrete_feedback(self):
  from agent.quality import ContentAudit
  from tests.audit_fixture import audit
  data=audit([{'code':'unsafe_advice','detail':'对公账户不能作为安全保证','finding_indexes':[],'evidence_ids':[]}])
  data['checks'][0].update(finding_indexes=[],evidence_ids=[])
  result=ContentAudit.model_validate(data)
  self.assertEqual(result.issues[0].detail,'对公账户不能作为安全保证')
  data['issues'][0]['detail']=''
  with self.assertRaises(ValueError):ContentAudit.model_validate(data)
 def test_new_user_turn_rebuilds_ledger_without_creating_another_report(self):
  class Updated(LedgerModel):
   def extract_facts(self,context):
    self.extract_contexts.append(context)
    q=next(q for q in context['material_quotes'] if q['quote']==context['current_message'])
    return {'items':[{'status':'known','statement':context['current_message'],'quote_ids':[q['quote_id']],'rationale':''}]}
  model=Updated([tool(),output('report',self.report()),tool(),output('answer')],[[],[]])
  engine=AgentEngine(self.sessions,self.materials,FakeRag(),model)
  engine.turn(self.sid,'公司要求保证金')
  engine.turn(self.sid,'只解释如何保存聊天记录')
  saved=self.sessions.get(self.sid)
  self.assertEqual(len(saved['reports']),1)
  self.assertEqual(len(saved['fact_ledgers']),2)
  self.assertEqual(saved['fact_ledgers'][-1]['ledger']['items'][0]['statement'],'只解释如何保存聊天记录')
  self.assertEqual(model.audit_contexts[-1]['fact_ledger'],saved['fact_ledgers'][-1]['ledger'])
 def test_real_reviewer_receives_ledger_and_originals(self):
  from agent.model import ChatModel
  from agent.schema import parse_turn
  from reader.config import Settings
  from tests.audit_fixture import audit
  context={'materials':[],'history':[],'latest_report':None,'current_message':'公司要求保证金','material_quotes':[], 'fact_ledger':{'items':[{'status':'unknown','statement':'贷款性质未明确'}]}}
  model=ChatModel(Settings(api_key='test'))
  with patch.object(model,'complete',return_value={'content':json.dumps(audit())}) as complete:
   model.review(context,parse_turn(output('answer')['content']),{})
  payload=json.loads(complete.call_args.args[0][1]['content'])
  self.assertEqual(payload['context']['fact_ledger'],context['fact_ledger'])
  self.assertEqual(payload['context']['current_message'],context['current_message'])

if __name__=='__main__':unittest.main()
