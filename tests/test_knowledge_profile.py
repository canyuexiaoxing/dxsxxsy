import unittest
from rag.profile import label_entry,eligible_entries,detect_topics,boost_topic_scores

def entry(sid,kind='law',title='规范',**kw):
 return dict(id=sid,kind=kind,title=title,scope='',tags=[],**kw)

class ProfileTests(unittest.TestCase):
 def test_pre_hire_excludes_remedy_but_keeps_trial(self):
  es=[label_entry(entry('LCL-082')),label_entry(entry('LCL-019',title='试用期'))]
  self.assertEqual([e['id'] for e in eligible_entries(es,'preemployment')],['LCL-019'])
  self.assertEqual(len(eligible_entries(es,'employed')),2)
 def test_case_group_stage_consistent(self):
  for role in ['facts','reasoning','outcome']:
   self.assertEqual(label_entry(entry('O003-'+role,'case','招转培',case_id='O003'))['stage_scope'],'pre')
 def test_unknown_legacy_entries_remain_available(self):
  self.assertEqual(len(eligible_entries([entry('legacy')],'preemployment')),1)
 def test_topic_boost_preserves_retrieval_score(self):
  es={'a':dict(risk_topics=['task_fraud']),'b':dict(risk_topics=[])}
  result=boost_topic_scores({'a':1,'b':1},es,'刷单垫付')
  self.assertGreater(result['a'],result['b'])
  self.assertIn('identity',detect_topics('需要我提供银行卡验证码'))
 def test_labels_do_not_change_original_text(self):
  e=entry('x',title='拟签合同');e['text']='原文';e['verified_at']='2026-10-01'
  result=label_entry(e)
  self.assertEqual(result['text'],'原文');self.assertEqual(result['verified_at'],e['verified_at'])

 def test_trial_direct_rule_uses_existing_catalogue_id(self):
  import json
  from pathlib import Path
  from agent.quality import context_sources
  es=json.loads((Path(__file__).resolve().parents[1]/'knowledge/entries.json').read_text(encoding='utf-8-sig'))
  mapping={e['id']:e for e in es}
  def get(sid):
   if sid not in mapping:raise ValueError(sid)
   return mapping[sid]
  ids=[e['id'] for e in context_sources('拟签一年合同，试用期三个月。',[],get,stage='preemployment')]
  self.assertIn('K004',ids)
  self.assertNotIn('LCL-039',ids)
 def test_internship_facts_supply_direct_official_warning(self):
  from agent.quality import context_sources
  def get(sid):return dict(id=sid,kind='warning' if sid.startswith('PRE-W') else 'law')
  ids=[e['id'] for e in context_sources('个人以公司名义招远程实习，收实习证明费，分派私人任务，拒绝招聘授权。',[],get,stage='preemployment')]
  self.assertIn('PRE-W-intern',ids)
 def test_task_payment_advice_does_not_duplicate_the_same_risk(self):
  from agent.preemployment import normalize_preemployment
  from tests.test_content_layout import result
  r=result(['小额返利后要求充值垫资才能领佣金','做任务先付款可以直接拒绝'])
  for f in r.report.findings:f.quote='先返5元，再充值500元，垫付2000元才能领取佣金。'
  normalize_preemployment(r,{'employment_stage':'preemployment','current_message':'兼职点赞充值任务，先返5元再要求垫付。'})
  self.assertEqual(len(r.report.findings),1)
if __name__=='__main__':unittest.main()
