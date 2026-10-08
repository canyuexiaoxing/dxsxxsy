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
 def test_audit_feedback_returns_to_author_for_modification(self):
  raw=self.report();raw['findings'].append(dict(raw['findings'][0],title='重复收费'))
  clean=json.loads(output('report',self.report())['content'])
  model=QualityModel([tool(),output('report',raw),{'role':'assistant','content':json.dumps(clean)}],[[{'code':'duplicate_risk','detail':'同一收费重复列出','finding_indexes':[0,1],'evidence_ids':[]}],[]])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(reply['report']['findings']),1)
 def test_reviewer_cannot_replace_report_with_rag_quote(self):
  bad=json.loads(output('report',self.report())['content']);bad['report']['findings'][0]['quote']='资料库里的案情'
  model=QualityModel([tool()]+[output('report',self.report())]*3,[{'corrected_result':bad,'issues':[]}]*3)
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['action'],'report')
  self.assertEqual(reply['report']['findings'][0]['quote'],'公司要求保证金')
  self.assertEqual(reply['report']['review_status']['status'],'unavailable')
 def test_reviewer_cannot_change_report_into_answer(self):
  clean=json.loads(output('answer')['content'])
  model=QualityModel([tool()]+[output('report',self.report())]*3,[{'corrected_result':clean,'issues':[]}]*3)
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['action'],'report')
  self.assertEqual(reply['report']['findings'][0]['quote'],'公司要求保证金')
  self.assertEqual(reply['report']['review_status']['status'],'unavailable')

 def test_first_report_editor_may_omit_empty_change_reason(self):
  clean=json.loads(output('report',self.report())['content']);clean['report'].pop('change_reason')
  model=QualityModel([tool(),output('report',self.report())],[[]])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['report']['change_reason'],'')

if __name__=='__main__':unittest.main()
