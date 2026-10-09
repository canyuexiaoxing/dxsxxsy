import json,tempfile,unittest
from pathlib import Path
from agent.engine import AgentEngine,AgentError
from agent.memory import SessionStore
from reader.store import MaterialStore
from tests.test_agent import FakeRag,FakeModel,tool,output
class ValidationLogTests(unittest.TestCase):
    def test_failed_validation_logs_each_attempt_but_keeps_ui_generic(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sessions=SessionStore(root);sid=sessions.create('test')['id']
            broken=output('answer');value=json.loads(broken['content']);value['evidence_ids']=['MISSING'];broken['content']=json.dumps(value)
            engine=AgentEngine(sessions,MaterialStore(root),FakeRag(),FakeModel([tool(),broken,broken,broken]))
            with self.assertLogs('agent.engine',level='WARNING') as captured:
                with self.assertRaises(AgentError) as failure:engine.turn(sid,'用户测试说明')
            logs=[json.loads(line.split('report_validation_failed ',1)[1]) for line in captured.output if 'report_validation_failed ' in line]
            self.assertEqual([item['attempt'] for item in logs],[1,2,3])
            self.assertEqual(logs[-1]['status'],'exhausted')
            self.assertEqual(logs[-1]['issues'][0]['type'],'unretrieved_evidence')
            self.assertEqual(logs[-1]['session_id'],sid)
            self.assertNotIn('用户测试说明',''.join(captured.output))
            self.assertNotIn('unretrieved_evidence',str(failure.exception))
            self.assertNotIn('引用',str(failure.exception))
            self.assertEqual(sessions.get(sid)['reports'],[])
