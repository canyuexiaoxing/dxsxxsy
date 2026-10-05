import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.engine import AgentEngine
from tests.test_report_quality import QualityModel
from tests import test_editor_stage as helper
from tests.test_agent import FakeRag,tool,output

class LayoutGuardTests(unittest.TestCase):
 setUp=helper.EditorStageTests.setUp
 tearDown=helper.EditorStageTests.tearDown
 report=helper.EditorStageTests.report
 def run_draft(self,titles,facts):
  report=self.report();report['findings']=[dict(report['findings'][0],title=t,quote=facts) for t in titles]
  draft=json.loads(output('report',report)['content'])
  model=QualityModel([tool(),output('report',report)],[{'corrected_result':draft,'issues':[]}])
  return AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,facts)['report']
 def test_zero_trial_salary_is_one_risk_not_two(self):
  report=self.run_draft(['无薪试岗拒付报酬','拒付报酬与试用期工资下限','证据留存与举证成本'],'公司要求无薪试岗后拒不支付劳动报酬')
  self.assertEqual(len(report['findings']),1)
 def test_distinct_pay_and_dismissal_rights_are_kept(self):
  report=self.run_draft(['无薪试岗拒付报酬','以考核不合格辞退'],'公司要求无薪试岗后辞退并拒付报酬')
  self.assertEqual(len(report['findings']),2)
 def test_missing_qualification_and_hypothetical_repeat_trial_are_checks(self):
  report=self.run_draft(['无薪试岗拒付报酬','劳务派遣主体资质与用工关系需核实','试岗期是否构成变相试用期或重复试用期'],'劳务派遣公司安排3至7天无薪试岗后拒付报酬')
  self.assertEqual(len(report['findings']),1)
  self.assertGreaterEqual(len(report['limitations']),2)
 def test_actual_repeated_trial_is_kept(self):
  report=self.run_draft(['重复试用期风险'],'公司在试岗后又另行约定试用期')
  self.assertEqual(len(report['findings']),1)
 def test_unknown_contract_party_and_unmentioned_training_charges_are_checks(self):
  report=self.run_draft(['外包名义与实际管理矛盾','用人单位主体不清、劳动合同归属不明可能影响工资社保与救济路径','培训由实际用工方组织，需关注是否出现收费培训或变相收费'],'公司名义外包，由纺织公司岗前培训并直接管理，服务方收到费用后发薪缴保')
  self.assertEqual(len(report['findings']),1)
 def test_model_calls_checks_gaps_or_checkpoints(self):
  report=self.run_draft(['名为外包实为派遣','派遣经营许可与谁是用人单位的核查缺口','劳动合同与派遣协议必备条款是否落实的核查点'],'名义外包，实际由纺织公司培训管理，服务方发薪缴保')
  self.assertEqual(len(report['findings']),1)
 def test_qualification_check_need_is_not_a_risk(self):
  report=self.run_draft(['无薪试岗拒付报酬','劳务派遣主体与许可信息的核查需要'],'派遣公司安排无薪试岗后拒付报酬')
  self.assertEqual(len(report['findings']),1)
 def test_unknown_relationship_and_unreported_disclosure_are_checks(self):
  report=self.run_draft(['外包名义实际管理','用工主体与劳动关系归属不清，影响维权对象','招聘阶段对用工形式和责任主体告知不明确'],'名义外包，纺织公司直接管理，咨询公司发薪缴保')
  self.assertEqual(len(report['findings']),1)
 def test_unprovided_dispatch_ratio_and_payment_chain_are_not_risks(self):
  report=self.run_draft(['名义外包实际由用工方管理','现场管理控制权高度归集','派遣岗位与用工比例可能违规','工资代发社保代缴链条存在风险'],'公司以业务外包名义合作，由另一公司管理，签约服务方支付工资并缴社保')
  self.assertEqual(len(report['findings']),1)
  self.assertTrue(report['limitations'])
 def test_explicit_dispatch_ratio_and_arrears_are_not_removed(self):
  report=self.run_draft(['派遣人数比例超限','工资代发链条发生欠薪'],'公司派遣人数比例80%，工资已拖欠')
  self.assertEqual(len(report['findings']),2)
 def test_answer_does_not_add_unmentioned_training_loans(self):
  raw=json.loads(output('answer')['content']);raw['message']='1. 可以向人社部门投诉。\n2. 培训贷款问题可联系放款机构。'
  model=QualityModel([tool(),{'role':'assistant','content':json.dumps(raw,ensure_ascii=False)}],[{'corrected_result':raw,'issues':[]}])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'试岗欠薪该找谁处理？')
  self.assertNotIn('贷款',reply['message']);self.assertIn('人社',reply['message'])

if __name__=='__main__':unittest.main()
