import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.engine import AgentEngine,AgentError
from agent.memory import SessionStore
from reader.store import MaterialStore
from tests.test_agent import FakeModel,FakeRag,tool,output
from agent.schema import TurnResult

class QualityModel(FakeModel):
 def __init__(self,outputs,reviews):super().__init__(outputs);self.reviews=list(reviews);self.checked=[]
 def review(self,context,result,sources):self.checked.append(result.model_dump());return self.reviews.pop(0)

class ReportQualityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.sessions=SessionStore(self.root);self.sid=self.sessions.create('测试')['id'];self.materials=MaterialStore(self.root)
 def tearDown(self):self.temp.cleanup()
 def report(self,title='入职收费'):
  return {'summary':'收费风险','findings':[{'title':title,'level':'high','quote':'公司要求保证金','explanation':'核实收费','evidence_ids':['K001'],'suggestions':['核实主体']}],'limitations':[],'change_reason':''}
 def test_missing_information_is_not_a_separate_finding(self):
  result=TurnResult.model_validate(json.loads(output('report',self.report('尚缺少合同和许可证信息'))['content']))
  with self.assertRaises(AgentError):AgentEngine(None,None,None,None)._validate(result,{'messages':[],'reports':[]},[],'公司要求保证金',{'K001':{'kind':'law'}})
 def test_duplicate_review_triggers_repair_and_is_checked_again(self):
  bad=self.report();bad['findings'].append(dict(bad['findings'][0],title='收费主体收取保证金'))
  good=self.report()
  model=QualityModel([tool(),output('report',bad),output('report',good)],[[{'code':'duplicate_risk','detail':'同一保证金风险应合并','finding_indexes':[0,1],'evidence_ids':[]}],[]])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(reply['report']['findings']),1);self.assertEqual(len(model.checked),2)
  self.assertTrue(any(t['tool']=='quality_review' for t in self.sessions.get(self.sid)['traces'][-1]))
 def test_bad_citation_after_review_repair_cannot_be_saved(self):
  bad=self.report();bad['findings'][0]['quote']='知识库里的案情'
  model=QualityModel([tool(),output('report',self.report()),output('report',bad),output('report',bad)],[[{'code':'insufficient_citation','detail':'法条不足','finding_indexes':[0],'evidence_ids':['K001']}]])
  with self.assertRaises(AgentError):AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(self.sessions.get(self.sid)['reports'],[])
 def test_off_topic_answer_is_repaired_without_modifying_report(self):
  reply=output('answer');reply['content']=reply['content'].replace('请核实收费主体和用途。','可以联系妇联处理歧视')
  model=QualityModel([tool(),reply,output('answer')],[[{'code':'off_topic','detail':'当前仅问收费，不涉及歧视','finding_indexes':[],'evidence_ids':[]}],[]])
  result=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'入职保证金该找谁核实？')
  self.assertNotIn('妇联',result['message']);self.assertEqual(self.sessions.get(self.sid)['reports'],[])
 def test_persistent_quality_failure_is_not_saved(self):
  issue=[{'code':'unsupported_fact','detail':'反复辞退无证据','finding_indexes':[0],'evidence_ids':[]}]
  model=QualityModel([tool()]+[output('report',self.report())]*3,[issue]*3)
  with self.assertRaises(AgentError):AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(self.sessions.get(self.sid)['reports'],[])

 def test_related_laws_are_expanded_once_with_bounded_budget(self):
  from agent.quality import related_sources
  source={'id':'S','kind':'support','related_article_ids':['L1','L1','L2','C','L3']}
  mapping={**{sid:{'id':sid,'kind':'law'} for sid in ['L1','L2','L3']},'C':{'id':'C','kind':'case'}}
  self.assertEqual([e['id'] for e in related_sources([source],mapping.__getitem__,limit=2)],['L1','L2'])
 def test_actual_refusal_is_not_moved_to_missing_information(self):
  result=TurnResult.model_validate(json.loads(output('report',self.report('拒绝签订劳动合同'))['content']))
  AgentEngine(None,None,None,None)._validate(result,{'messages':[],'reports':[]},[],'公司要求保证金',{'K001':{'kind':'law'}})

 def test_applicability_unknown_is_a_limitation_not_a_risk(self):
  result=TurnResult.model_validate(json.loads(output('report',self.report('试用期工资下限规则是否适用尚待核实'))['content']))
  with self.assertRaises(AgentError):AgentEngine(None,None,None,None)._validate(result,{'messages':[],'reports':[]},[],'公司要求保证金',{'K001':{'kind':'law'}})
 def test_repair_cannot_switch_report_to_answer(self):
  issue=[{'code':'unsupported_fact','detail':'发现未提供事实','finding_indexes':[0],'evidence_ids':[]}]
  model=QualityModel([tool(),output('report',self.report()),output('answer'),output('answer')],[issue,[],[]])
  with self.assertRaises(AgentError):AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(self.sessions.get(self.sid)['messages'],[])

 def test_multiple_rules_inside_one_finding_are_not_duplicate_counts(self):
  from agent.quality import concrete_review_issues
  issue={'code':'duplicate_risk','detail':'同一条里引用多个规则','finding_indexes':[0],'evidence_ids':[]}
  result=TurnResult.model_validate(json.loads(output('report',self.report())['content']))
  self.assertEqual(concrete_review_issues([issue],result),[])

if __name__=='__main__':unittest.main()
