import unittest
from agent.tasks import TaskRegistry,TaskCancelled
class DeleteTaskTests(unittest.TestCase):
    def test_delete_cancels_existing_and_late_tasks(self):
        tasks=TaskRegistry();old=tasks.get('S1','old');other=tasks.get('S2','other');cleaned=[]
        old.own(lambda:cleaned.append('upload'))
        tasks.cancel_session('S1')
        self.assertEqual(cleaned,['upload'])
        with self.assertRaises(TaskCancelled):old.commit(lambda:None)
        with self.assertRaises(TaskCancelled):tasks.get('S1','late').check()
        other.check()
    def test_delete_removes_private_material_and_retains_shared_material(self):
        import tempfile
        from pathlib import Path
        from fastapi.testclient import TestClient
        from reader.api import create_app
        from reader.config import Settings
        from agent.memory import SessionStore
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=TestClient(create_app(Settings(data_dir=root)));store=SessionStore(root)
            first=client.post('/api/sessions',json={'title':'删除目标'}).json()
            second=client.post('/api/sessions',json={'title':'保留会话'}).json()
            shared=client.post('/api/materials',data={'text':'共享材料'}).json()['materials'][0]['material_id']
            private=client.post('/api/materials',data={'text':'专属材料'}).json()['materials'][0]['material_id']
            first['material_ids']=[shared,private];first['reports']=[{'version':1}];first['traces']=[{'internal':'test'}];store.save(first)
            second['material_ids']=[shared];store.save(second)
            self.assertEqual(client.delete('/api/sessions/'+first['id']).status_code,200)
            self.assertEqual(client.get('/api/sessions/'+first['id']).status_code,404)
            self.assertEqual(client.get('/api/materials/'+private).status_code,404)
            self.assertEqual(client.get('/api/materials/'+shared).status_code,200)
            self.assertEqual(store.get(second['id'])['material_ids'],[shared])

    def test_delete_stops_generation_before_it_can_write_back(self):
        import tempfile
        from pathlib import Path
        from threading import Event
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from reader.api import create_app
        from reader.config import Settings
        from agent.tasks import check_cancelled
        from tests.test_agent import FakeRag
        entered=Event()
        class Model:
            def complete(self,*args,**kwargs):
                entered.set()
                for _ in range(100):
                    check_cancelled();Event().wait(.02)
                raise AssertionError('删除未停止任务')
        with tempfile.TemporaryDirectory() as temp,patch('agent.routes.ChatModel',return_value=Model()),patch('agent.routes.KnowledgeIndex',return_value=FakeRag()):
            client=TestClient(create_app(Settings(data_dir=Path(temp))))
            sid=client.post('/api/sessions',json={}).json()['id']
            with ThreadPoolExecutor() as pool:
                pending=pool.submit(client.post,f'/api/sessions/{sid}/messages',json={'text':'招聘要求保证金','request_id':'delete-job'})
                self.assertTrue(entered.wait(3))
                self.assertEqual(client.delete('/api/sessions/'+sid).status_code,200)
                self.assertEqual(pending.result(timeout=4).status_code,410)
            self.assertEqual(client.get('/api/sessions/'+sid).status_code,404)
