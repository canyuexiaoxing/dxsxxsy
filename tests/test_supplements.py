import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.index import select_evidence
from agent.engine import AgentEngine,AgentError,check_sensitive_text
from agent.schema import TurnResult
from agent.memory import SessionStore
from reader.store import MaterialStore

class SupplementsTests(unittest.TestCase):
 def test_support_has_separate_budget(self):
  entries=[{'id':f'{k}{i}','kind':k} for k in ['law','warning','support'] for i in range(4)]
  result=select_evidence([e['id'] for e in reversed(entries)],{e['id']:e for e in entries})
  self.assertEqual(sum(e['kind']=='support' for e in result),2)
  self.assertEqual(sum(e['kind']=='law' for e in result),3)
  self.assertEqual(sum(e['kind']=='warning' for e in result),2)
 def test_program_checks_support_reference_exists_auditor_checks_use(self):
  result=TurnResult.model_validate({'action':'report','message':'','questions':[],'evidence_ids':['S'],'report':{'summary':'摘要','findings':[{'title':'风险','level':'high','quote':'公司收费','explanation':'说明','evidence_ids':['S'],'suggestions':['核实']}],'limitations':[],'change_reason':''}})
  engine=AgentEngine(None,None,None,None)
  engine._validate(result,{'messages':[],'reports':[]},[],'公司收费',{'S':{'kind':'support'}})
 def test_sensitive_text_stops_before_model_and_is_not_saved(self):
  with tempfile.TemporaryDirectory() as d:
   sessions=SessionStore(Path(d));sid=sessions.create('测试')['id']
   class NeverModel:
    def complete(self,*args,**kwargs):raise AssertionError('不得发送敏感文本')
   engine=AgentEngine(sessions,MaterialStore(Path(d)),None,NeverModel())
   with self.assertRaisesRegex(AgentError,'脱敏'):engine.turn(sid,'身份证号码：110101199001011234')
   self.assertEqual(sessions.get(sid)['messages'],[])

 def test_masked_fields_are_allowed(self):
  check_sensitive_text('身份证号：【已脱敏】；银行卡号：****************；家庭住址：某省某市')
 def test_bank_and_address_labels_are_blocked(self):
  for text in ['银行卡号：6222021234567890123','家庭住址：浙江省杭州市具体街道123号']:
   with self.assertRaises(AgentError):check_sensitive_text(text)

if __name__=='__main__':unittest.main()
