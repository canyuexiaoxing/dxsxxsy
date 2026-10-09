import tempfile,unittest
from pathlib import Path
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fastapi.testclient import TestClient
from reader.api import create_app
from reader.config import Settings
from agent.memory import SessionStore
from tests.test_agent import FakeRag,tool,output


class StopTaskTests(unittest.TestCase):
    def test_cancelled_task_cannot_commit(self):
        from agent.tasks import TaskRegistry,TaskCancelled
        registry=TaskRegistry();saved=[]
        with registry.scope('S1','job1'):
            token=registry.get('S1','job1')
            token.cancel()
            with self.assertRaises(TaskCancelled):token.commit(lambda:saved.append('report'))
        self.assertEqual(saved,[])

    def test_cancel_before_message_prevents_any_analysis(self):
        with tempfile.TemporaryDirectory() as temp:
            client=TestClient(create_app(Settings(data_dir=Path(temp))))
            sid=client.post('/api/sessions',json={}).json()['id']
            cancelled=client.post(f'/api/sessions/{sid}/tasks/job1/cancel')
            self.assertEqual(cancelled.status_code,200)
            response=client.post(f'/api/sessions/{sid}/messages',json={'text':'公司要求保证金','request_id':'job1'})
            self.assertEqual(response.status_code,410)
            self.assertEqual(SessionStore(Path(temp)).get(sid)['reports'],[])

    def test_stop_during_model_call_does_not_save_report_or_user_message(self):
        entered=Event();release=Event()
        class Model:
            def complete(self,*args,**kwargs):
                entered.set();release.wait(5)
                return tool()
        with tempfile.TemporaryDirectory() as temp,patch('agent.routes.ChatModel',return_value=Model()),patch('agent.routes.KnowledgeIndex',return_value=FakeRag()):
            client=TestClient(create_app(Settings(data_dir=Path(temp))))
            sid=client.post('/api/sessions',json={}).json()['id']
            with ThreadPoolExecutor() as pool:
                pending=pool.submit(client.post,f'/api/sessions/{sid}/messages',json={'text':'公司要求保证金','request_id':'job2'})
                self.assertTrue(entered.wait(3))
                stopped=client.post(f'/api/sessions/{sid}/tasks/job2/cancel')
                self.assertEqual(stopped.status_code,200)
                release.set()
                self.assertEqual(pending.result(timeout=5).status_code,410)
            stored=SessionStore(Path(temp)).get(sid)
            self.assertEqual(stored['messages'],[])
            self.assertEqual(stored['reports'],[])

    def test_stop_cleans_only_this_requests_new_materials(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=TestClient(create_app(Settings(data_dir=root)))
            sid=client.post('/api/sessions',json={}).json()['id']
            original=client.post('/api/materials',data={'text':'原有材料'}).json()['materials'][0]['material_id']
            store=SessionStore(root);session=store.get(sid);session['material_ids']=[original];store.save(session)
            added=client.post('/api/materials',data={'text':'本次新资料','session_id':sid,'request_id':'upload-job'}).json()['materials'][0]['material_id']
            self.assertEqual(client.post(f'/api/sessions/{sid}/tasks/upload-job/cancel').status_code,200)
            self.assertEqual(client.get(f'/api/materials/{added}').status_code,404)
            self.assertEqual(client.get(f'/api/materials/{original}').status_code,200)
            self.assertEqual(store.get(sid)['material_ids'],[original])

    def test_stop_while_reading_upload_does_not_save_late_material(self):
        entered=Event();release=Event()
        from reader.core import MaterialReader
        result=MaterialReader(None).read_text('模拟上传读取结果')
        def read(*args):entered.set();release.wait(5);return result
        with tempfile.TemporaryDirectory() as temp,patch('reader.api.MaterialReader.read_file',side_effect=read):
            root=Path(temp);client=TestClient(create_app(Settings(data_dir=root)))
            sid=client.post('/api/sessions',json={}).json()['id']
            with ThreadPoolExecutor() as pool:
                pending=pool.submit(client.post,'/api/materials',data={'session_id':sid,'request_id':'reading-job'},files={'files':('test.pdf',b'test','application/pdf')})
                self.assertTrue(entered.wait(3))
                stopped=client.post(f'/api/sessions/{sid}/tasks/reading-job/cancel')
                release.set();self.assertEqual(stopped.status_code,200)
                self.assertEqual(pending.result(timeout=5).status_code,410)
            self.assertFalse((root/'materials'/result.material_id).exists())

    def test_completed_task_is_not_rolled_back_by_late_stop(self):
        from agent.tasks import TaskRegistry
        registry=TaskRegistry();saved=[]
        with registry.scope('S2','job3'):
            registry.get('S2','job3').commit(lambda:saved.append('report'))
        self.assertEqual(registry.get('S2','job3').cancel(),'completed')
        self.assertEqual(saved,['report'])


if __name__=='__main__':unittest.main()
