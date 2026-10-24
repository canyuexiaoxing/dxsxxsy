import json,tempfile,unittest
from pathlib import Path
from agent.engine import AgentEngine
from agent.memory import SessionStore
from reader.store import MaterialStore
from tests.test_agent import FakeModel,FakeRag,tool,output

class FollowupDialogueTests(unittest.TestCase):
 def run_turn(self,outputs,text='有家公司让我先培训，费用不清楚，帮我看看。'):
  class Model(FakeModel):
   def classify_report_request(self,text):return False
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);store=SessionStore(root);sid=store.create('test')['id']
   result=AgentEngine(store,MaterialStore(root),FakeRag(),Model(outputs)).turn(sid,text)
   self.assertEqual(store.get(sid)['reports'],[])
   return result
 def test_report_like_long_answer_is_repaired_to_questions_and_brief_advice(self):
  long=output('answer');value=json.loads(long['content']);value['message']='风险分析和建议。'*100;long['content']=json.dumps(value)
  short=output('ask');value=json.loads(short['content']);value['message']='根据现有信息，先暂缓签约付款，核实培训和岗位的关系。';value['questions']=['目前是否已经签约或付款？','培训由谁提供、费用付给谁？'];short['content']=json.dumps(value)
  result=self.run_turn([tool(),long,short])
  self.assertEqual(result['action'],'ask')
  self.assertEqual(len(result['questions']),2)
  self.assertLess(len(result['message']),600)
 def test_missing_questions_do_not_count_as_a_followup(self):
  invalid=output('ask');value=json.loads(invalid['content']);value['questions']=[];invalid['content']=json.dumps(value)
  result=self.run_turn([tool(),invalid,output('ask')])
  self.assertEqual(result['action'],'ask')
  self.assertTrue(result['questions'])
