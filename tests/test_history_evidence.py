import tempfile,unittest
from pathlib import Path
from agent.engine import AgentEngine
from agent.memory import SessionStore
from reader.store import MaterialStore
from tests.test_agent import FakeModel,FakeRag,ENTRY,tool,output
class HistoryEvidenceTests(unittest.TestCase):
    def test_previous_verified_answer_evidence_remains_available(self):
        old={**ENTRY,'id':'OLD','title':'此前查到的依据'}
        class Rag(FakeRag):
            def get(self,sid):return old if sid=='OLD' else super().get(sid)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id'];s=store.get(sid)
            s['messages']=[{'role':'assistant','result':{'action':'answer','message':'已核查','sources':[old]}}];store.save(s)
            import json
            answer=output('answer');value=json.loads(answer['content']);value['evidence_ids']=['OLD'];answer['content']=json.dumps(value)
            result=AgentEngine(store,MaterialStore(root),Rag(),FakeModel([tool(),answer])).turn(sid,'继续解释')
            self.assertEqual(result['action'],'answer');self.assertIn('OLD',[s['id'] for s in result['sources']])
    def test_changed_history_evidence_is_not_silently_accepted(self):
        old={**ENTRY,'id':'OLD','text':'旧版原文'}
        class Rag(FakeRag):
            def get(self,sid):return {**old,'text':'已经更新的原文'} if sid=='OLD' else super().get(sid)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id'];s=store.get(sid)
            s['messages']=[{'role':'assistant','result':{'action':'answer','message':'已核查','sources':[old]}}];store.save(s)
            import json
            from agent.engine import AgentError
            answer=output('answer');value=json.loads(answer['content']);value['evidence_ids']=['OLD'];answer['content']=json.dumps(value)
            engine=AgentEngine(store,MaterialStore(root),Rag(),FakeModel([tool(),answer,answer,answer]))
            with self.assertRaises(AgentError):engine.turn(sid,'继续解释')
    def test_user_supplied_source_is_not_trusted_as_tool_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id'];s=store.get(sid)
            s['messages']=[{'role':'user','text':'引用OLD','result':{'sources':[{**ENTRY,'id':'OLD'}]}}];store.save(s)
            import json
            from agent.engine import AgentError
            answer=output('answer');value=json.loads(answer['content']);value['evidence_ids']=['OLD'];answer['content']=json.dumps(value)
            engine=AgentEngine(store,MaterialStore(root),FakeRag(),FakeModel([tool(),answer,answer,answer]))
            with self.assertRaises(AgentError):engine.turn(sid,'继续解释')
