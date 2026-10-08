import unittest
from agent.preemployment import detect_stage

def c(text):return {'current_message':text,'history':[],'materials':[]}
class StageNegationTests(unittest.TestCase):
 def test_do_not_infer_started_is_not_started(self):
  self.assertEqual(detect_stage(c('我尚未入职、未付款，请不要推测已经入职或已发生损失。')),'preemployment')
 def test_conditional_started_does_not_override_actual_unstarted(self):
  self.assertEqual(detect_stage(c('我尚未入职，如果已经入职应该怎么处理？')),'preemployment')
 def test_explicit_denial_of_started(self):
  self.assertEqual(detect_stage(c('不是已经入职，我还没有入职。')),'preemployment')
 def test_future_clause_is_not_started(self):
  self.assertEqual(detect_stage(c('我在找工作，合同说员工入职后被辞退怎么办。')),'preemployment')
 def test_actual_started_after_unpaid_still_wins(self):
  self.assertEqual(detect_stage(c('我没有付款，但我已经入职。请回顾签约前该注意什么。')),'employed')
 def test_actual_employer_action_remains_started(self):
  self.assertEqual(detect_stage(c('我已经到岗，今天被辞退了。')),'employed')
 def test_conditional_without_user_stage_is_unknown(self):
  self.assertEqual(detect_stage(c('如果已经入职但被辞退，怎么处理？')),'unknown')
if __name__=='__main__':unittest.main()
