import json,unittest,httpx
from agent.engine import AgentEngine
from agent.model import ChatModel,ModelError
from reader.config import Settings
from tests import test_report_quality as helper
from tests.test_report_quality import QualityModel
from tests.test_agent import FakeRag,tool,output
from agent.schema import parse_turn

ISSUE=[{'code':'unsupported_fact','detail':'草稿将收费意图直接认定为诈骗，材料不足以支持。','finding_indexes':[0],'evidence_ids':[]}]
class BoundedReviewTests(unittest.TestCase):
 setUp=helper.ReportQualityTests.setUp
 tearDown=helper.ReportQualityTests.tearDown
 report=helper.ReportQualityTests.report
 def test_two_reviews_two_modifications_deliver_even_if_not_passed(self):
  model=QualityModel([tool()]+[output('report',self.report())]*3,[ISSUE]*3)
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(len(model.checked),2)
  self.assertEqual(len(self.sessions.get(self.sid)['reports']),1)
  self.assertEqual(reply['report']['review_status']['audit_count'],2)
  self.assertEqual(reply['report']['review_status']['revision_count'],2)
  self.assertEqual(reply['report']['review_status']['status'],'final_revision_unreviewed')
  self.assertTrue(any('复核' in s for s in reply['report']['review_notes']))
 def test_failed_first_audit_does_not_claim_two_revisions(self):
  class Retry(QualityModel):
   def __init__(self,*a):super().__init__(*a);self.first=True
   def review(self,*a):
    if self.first:self.first=False;raise ModelError('暂不可用')
    return super().review(*a)
  model=Retry([tool(),output('report',self.report()),output('report',self.report())],[ISSUE])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['report']['review_status']['audit_count'],2)
  self.assertEqual(reply['report']['review_status']['revision_count'],1)
  self.assertNotIn('两轮修改上限',reply['report']['review_notes'][0])
 def test_passed_initial_draft_needs_no_modification(self):
  model=QualityModel([tool(),output('report',self.report())],[[]])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['report']['review_status']['status'],'passed')
  self.assertEqual(len(model.checked),1)
 def test_failed_revision_keeps_last_valid_report(self):
  bad=self.report();bad['findings'][0]['quote']='RAG案例中别人的话'
  model=QualityModel([tool(),output('report',self.report()),output('report',bad)],[ISSUE])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['report']['findings'][0]['quote'],'公司要求保证金')
  self.assertEqual(reply['report']['review_status']['status'],'revision_failed')
 def test_review_service_failure_still_delivers(self):
  class Offline(QualityModel):
   def review(self,*args):raise ModelError('复核接口暂时不可用')
  model=Offline([tool(),output('report',self.report())],[])
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(reply['report']['review_status']['status'],'unavailable')
 def test_review_notes_do_not_become_user_history(self):
  model=QualityModel([tool(),output('report',self.report()),output('report',self.report())],[ISSUE,[]])
  AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  users=[m['text'] for m in self.sessions.get(self.sid)['messages'] if m['role']=='user']
  self.assertEqual(users,['公司要求保证金'])
  traces=self.sessions.get(self.sid)['traces'][-1]
  self.assertEqual(len([t for t in traces if t['tool']=='quality_review']),2)

 def test_second_audit_receives_audit_memory_only(self):
  class Remember(QualityModel):
   def __init__(self,*args):super().__init__(*args);self.memory=[]
   def review(self,context,*args):
    self.memory.append(context['review_memory'].copy())
    return super().review(context,*args)
  model=Remember([tool(),output('report',self.report()),output('report',self.report())],[ISSUE,[]])
  AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
  self.assertEqual(model.memory[0],[])
  self.assertEqual(model.memory[1],[{'round':1,'issues':ISSUE}])
 def test_unavailable_review_note_survives_word_download(self):
  from agent.word_export import render_report_docx
  from io import BytesIO
  from zipfile import ZipFile
  class Offline(QualityModel):
   def review(self,*args):raise ModelError('不可用')
  reply=AgentEngine(self.sessions,self.materials,FakeRag(),Offline([tool(),output('report',self.report())],[])).turn(self.sid,'公司要求保证金')
  with ZipFile(BytesIO(render_report_docx(reply['report']))) as doc:
   self.assertIn('内容复核未完成',doc.read('word/document.xml').decode())

class ReviewerIsolationTests(unittest.TestCase):
 def test_reviewer_returns_issues_with_separate_memory_and_no_assistant_history(self):
  requests=[]
  def handler(request):
   requests.append(json.loads(request.content))
   return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(__import__('tests.audit_fixture',fromlist=['audit']).audit(ISSUE))}}]})
  model=ChatModel(Settings(api_key='test'),httpx.MockTransport(handler))
  context={'materials':[],'history':[{'role':'user','text':'公司要求保证金'},{'role':'assistant','result':{'message':'旧的分析思路'}}],'latest_report':None,'current_message':'请分析','material_quotes':[],'employment_stage':'preemployment','review_memory':[{'round':1,'issues':ISSUE}]}
  draft=parse_turn(output('report',helper.ReportQualityTests.report(self))['content'])
  issues=model.review(context,draft,{})
  self.assertEqual(issues['issues'],ISSUE)
  payload=json.loads(requests[0]['messages'][1]['content'])
  self.assertEqual(payload['review_memory'],context['review_memory'])
  self.assertNotIn('旧的分析思路',json.dumps(payload,ensure_ascii=False))
  self.assertNotIn('tools',requests[0])
  self.assertEqual(len(requests),1)
if __name__=='__main__':unittest.main()
