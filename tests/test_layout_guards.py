"""Content repairs are authored by the model after audit feedback, not regex guards."""
import unittest
from tests import test_report_quality as helper
from tests.test_report_quality import QualityModel
from tests.test_agent import FakeRag,tool,output
from agent.engine import AgentEngine
class LayoutGuardTests(unittest.TestCase):
 setUp=helper.ReportQualityTests.setUp
 tearDown=helper.ReportQualityTests.tearDown
 report=helper.ReportQualityTests.report
 def test_duplicate_pay_items_are_returned_to_author_for_merge(self):
  bad=self.report('无薪试岗');bad['findings'].append(dict(bad['findings'][0],title='零工资低于下限'))
  good=self.report('试岗付酬问题')
  model=QualityModel([tool(),output('report',bad),output('report',good)],[[{'code':'duplicate_risk','detail':'同一付酬义务重复计数，合并两项','finding_indexes':[0,1],'evidence_ids':[]}],[]])
  r=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual([f['title'] for f in r['report']['findings']],['试岗付酬问题'])
  self.assertEqual(r['report']['review_status']['revision_count'],1)
 def test_missing_information_is_moved_by_author_not_program(self):
  bad=self.report();bad['findings'].append(dict(bad['findings'][0],title='许可未知'))
  good=self.report();good['limitations']=['许可情况待核实']
  model=QualityModel([tool(),output('report',bad),output('report',good)],[[{'code':'missing_as_risk','detail':'许可未知不单列异常事实','finding_indexes':[1],'evidence_ids':[]}],[]])
  r=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(r['report']['findings']),1);self.assertIn('许可情况待核实',r['report']['limitations'])
 def test_distinct_rights_are_preserved_when_auditor_accepts(self):
  r=self.report('拒付报酬');r['findings'].append(dict(r['findings'][0],title='解除争议'))
  model=QualityModel([tool(),output('report',r)],[[]])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(reply['report']['findings']),2)
 def test_off_topic_answer_is_corrected_by_author(self):
  import json
  bad=output('answer');d=json.loads(bad['content']);d['message']='人社投诉；另咨询培训贷款';bad['content']=json.dumps(d)
  model=QualityModel([tool(),bad,output('answer')],[[{'code':'off_topic','detail':'未涉及贷款，删除该分支','finding_indexes':[],'evidence_ids':[]}],[]])
  r=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertNotIn('贷款',r['message'])
if __name__=='__main__':unittest.main()
