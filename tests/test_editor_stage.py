import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests import test_report_quality as helper
from tests.test_report_quality import QualityModel
from agent.engine import AgentEngine,AgentError
from tests.test_agent import FakeRag,tool,output

class EditorStageTests(unittest.TestCase):
 setUp=helper.ReportQualityTests.setUp
 tearDown=helper.ReportQualityTests.tearDown
 report=helper.ReportQualityTests.report
 def test_editor_result_is_validated_and_persisted(self):
  raw=self.report();raw['findings'].append(dict(raw['findings'][0],title='重复收费'))
  clean=json.loads(output('report',self.report())['content'])
  model=QualityModel([tool(),output('report',raw)],[{'corrected_result':clean,'issues':[]}])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(reply['report']['findings']),1)
 def test_editor_cannot_introduce_a_rag_quote(self):
  bad=json.loads(output('report',self.report())['content']);bad['report']['findings'][0]['quote']='资料库里的案情'
  model=QualityModel([tool()]+[output('report',self.report())]*3,[{'corrected_result':bad,'issues':[]}]*3)
  with self.assertRaises(AgentError):AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(self.sessions.get(self.sid)['reports'],[])
 def test_editor_cannot_change_report_into_answer(self):
  clean=json.loads(output('answer')['content'])
  model=QualityModel([tool()]+[output('report',self.report())]*3,[{'corrected_result':clean,'issues':[]}]*3)
  with self.assertRaises(AgentError):AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(self.sessions.get(self.sid)['reports'],[])

 def test_first_report_editor_may_omit_empty_change_reason(self):
  clean=json.loads(output('report',self.report())['content']);clean['report'].pop('change_reason')
  model=QualityModel([tool(),output('report',self.report())],[{'corrected_result':clean,'issues':[]}])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['report']['change_reason'],'')

if __name__=='__main__':unittest.main()
