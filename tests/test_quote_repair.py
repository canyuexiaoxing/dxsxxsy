import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,r'E:\workp\dxsxxsy')
from agent.engine import AgentEngine,AgentError
from agent.memory import SessionStore
from reader.store import MaterialStore
from reader.core import MaterialReader

SOURCE={'id':'K007','kind':'guide','text':'建议投诉举报','title':'指南'}
class Rag:
    def search(self,query):return [SOURCE]
class Model:
    def __init__(self,responses):self.responses=responses;self.contexts=[]
    def complete(self,messages,**kwargs):
        self.contexts.append(json.loads(json.dumps(messages)))
        value=self.responses.pop(0)
        return value(messages) if callable(value) else value
def search():return {'role':'assistant','tool_calls':[{'id':'c1','function':{'name':'search_knowledge','arguments':'{"query":"加班"}'}}]}
def report(finding):
    return {'role':'assistant','content':json.dumps({'action':'report','message':'','questions':[],'evidence_ids':['K007'],'report':{'summary':'需核查','findings':[finding],'limitations':['未核验'],'change_reason':''}},ensure_ascii=False)}
def finding(**changes):return {'title':'工时风险','level':'attention','quote':'工作时间为早9时至晚9时。','material_id':'user','page_number':0,'explanation':'核查考勤','evidence_ids':['K007'],'suggestions':['保存证据'],**changes}
def selected(messages,source='user'):
    ctx=json.loads(messages[1]['content']);c=next(c for c in ctx['material_quotes'] if c['material_id']==source)
    return report({'title':'工时风险','level':'attention','quote_id':c['quote_id'],'explanation':'核查考勤','evidence_ids':['K007'],'suggestions':['保存证据']})
class QuoteRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.sessions=SessionStore(self.root);self.materials=MaterialStore(self.root);self.sid=self.sessions.create('测试')['id']
    def tearDown(self):self.tmp.cleanup()
    def run_turn(self,responses,text='工作时间为早9时至晚9时。',mids=None):
        self.model=Model(responses);return AgentEngine(self.sessions,self.materials,Rag(),self.model).turn(self.sid,text,mids)
    def test_quote_id_resolves_user_original(self):
        result=self.run_turn([search(),selected])
        f=result['report']['findings'][0];self.assertEqual(f['quote'],'工作时间为早9时至晚9时。');self.assertEqual(f['material_id'],'user');self.assertNotIn('quote_id',f)
    def test_quote_id_resolves_uploaded_material_page(self):
        m=MaterialReader(None).read_text('公司要求每周工作6天。');self.materials.save(m,b'test')
        result=self.run_turn([search(),lambda messages:selected(messages,m.material_id)],'请分析',[m.material_id])
        f=result['report']['findings'][0];self.assertEqual(f['quote'],'公司要求每周工作6天。');self.assertEqual(f['material_id'],m.material_id);self.assertEqual(f['page_number'],1)
    def test_rag_quote_is_repaired_not_accepted(self):
        invalid=report(finding(quote='建议投诉举报',material_id='K007'))
        result=self.run_turn([search(),invalid,selected]);self.assertEqual(result['action'],'report');self.assertEqual(len(self.sessions.get(self.sid)['reports']),1)
        trace=self.sessions.get(self.sid)['traces'][-1];self.assertTrue(any(t['tool']=='citation_repair' for t in trace))
    def test_persistently_bad_quote_never_writes_report(self):
        invalid=report(finding(quote='建议投诉举报',material_id='K007'))
        with self.assertRaisesRegex(AgentError,'本次未能完成分析'):
            self.run_turn([search(),invalid,invalid,invalid])
        self.assertEqual(len(self.sessions.get(self.sid)['reports']),0);self.assertEqual(len(self.model.contexts),4)
    def test_unknown_quote_id_cannot_fall_back_to_free_text(self):
        invalid=report(finding(quote_id='FAKE'))
        with self.assertRaisesRegex(AgentError,'本次未能完成分析'):self.run_turn([search(),invalid,invalid,invalid])
        self.assertEqual(self.sessions.get(self.sid)['reports'],[])
    def test_quote_cannot_join_two_user_messages(self):
        s=self.sessions.get(self.sid);s['messages']=[{'role':'user','text':'公司要求','material_ids':[]}];self.sessions.save(s)
        invalid=report(finding(quote='公司要求每周工作6天。'))
        with self.assertRaisesRegex(AgentError,'本次未能完成分析'):self.run_turn([search(),invalid,invalid,invalid],'每周工作6天。')
    def test_repair_cannot_introduce_unretrieved_evidence(self):
        invalid=report(finding(quote='建议投诉举报',material_id='K007'))
        def repaired(messages):
            response=selected(messages);data=json.loads(response['content']);data['report']['findings'][0]['evidence_ids']=['FAKE'];response['content']=json.dumps(data);return response
        with self.assertRaisesRegex(AgentError,'本次未能完成分析'):self.run_turn([search(),invalid,repaired,repaired])
        self.assertEqual(self.sessions.get(self.sid)['reports'],[])
if __name__=='__main__':unittest.main()
