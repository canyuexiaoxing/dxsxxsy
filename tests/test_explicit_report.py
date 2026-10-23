import tempfile,unittest
from pathlib import Path
from agent.engine import AgentEngine,AgentError
from agent.memory import SessionStore
from reader.store import MaterialStore
from tests.test_agent import FakeModel,FakeRag,tool,output
class ExplicitReportTests(unittest.TestCase):
    def test_model_cannot_create_report_without_user_request(self):
        class Model(FakeModel):
            def classify_report_request(self,text):return False
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id']
            report={'summary':'测试','findings':[],'limitations':['主体未核实'],'change_reason':''}
            model=Model([tool(),output('report',report),output('answer')])
            result=AgentEngine(store,MaterialStore(root),FakeRag(),model).turn(sid,'对方让我交押金，你帮我看看。')
            self.assertEqual(result['action'],'answer');self.assertEqual(store.get(sid)['reports'],[])
    def test_explicit_request_can_generate(self):
        class Model(FakeModel):
            def classify_report_request(self,text):return True
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id']
            report={'summary':'测试','findings':[],'limitations':['主体未核实'],'change_reason':''}
            result=AgentEngine(store,MaterialStore(root),FakeRag(),Model([tool(),output('report',report)])).turn(sid,'对方让我交押金，请生成报告。')
            self.assertEqual(result['action'],'report');self.assertEqual(len(store.get(sid)['reports']),1)
    def test_permission_does_not_carry_to_later_turn(self):
        class Model(FakeModel):
            def classify_report_request(self,text):return '请生成报告' in text
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id']
            report={'summary':'测试','findings':[],'limitations':['主体未核实'],'change_reason':''}
            model=Model([tool(),output('report',report),tool(),output('revise',{**report,'change_reason':'补充'}),output('answer')])
            engine=AgentEngine(store,MaterialStore(root),FakeRag(),model)
            engine.turn(sid,'对方让我交押金，请生成报告。')
            result=engine.turn(sid,'收款的是个人，现在我应该怎么办？')
            self.assertEqual(result['action'],'answer');self.assertEqual(len(store.get(sid)['reports']),1)
    def test_persistent_unrequested_report_never_saves(self):
        class Model(FakeModel):
            def classify_report_request(self,text):return False
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id']
            report={'summary':'测试','findings':[],'limitations':['主体未核实'],'change_reason':''}
            engine=AgentEngine(store,MaterialStore(root),FakeRag(),Model([tool(),output('report',report),output('report',report),output('report',report)]))
            with self.assertRaises(AgentError):engine.turn(sid,'资料都给了，不需要再问，但先别生成报告。')
            self.assertEqual(store.get(sid)['reports'],[])
    def test_model_classifier_uses_only_current_message_and_strict_bool(self):
        import json
        from agent.model import ChatModel,ModelError
        from reader.config import Settings
        from unittest.mock import patch
        model=ChatModel(Settings());message='别生成报告，简单告诉我怎么办。'
        with patch.object(model,'complete',return_value={'content':'{"requested":false}'}) as call:
            self.assertFalse(model.classify_report_request(message))
            payload=json.loads(call.call_args.args[0][1]['content'])
            self.assertEqual(payload,{'current_user_message':message})
        for content in ('{"requested":"true"}','{"requested":true,"other":1}','{}'):
            with patch.object(model,'complete',return_value={'content':content}):
                with self.assertRaises(ModelError):model.classify_report_request('请生成报告')
    def test_no_request_can_ask_for_missing_facts(self):
        class Model(FakeModel):
            def classify_report_request(self,text):return False
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);sid=store.create('test')['id']
            result=AgentEngine(store,MaterialStore(root),FakeRag(),Model([tool(),output('ask')])).turn(sid,'我只知道要交钱。')
            self.assertEqual(result['action'],'ask');self.assertIsNone(result['report'])
