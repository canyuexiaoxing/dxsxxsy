import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from reader.config import Settings
from reader.api import create_app
from agent.model import ChatModel

class KeySettingsTests(unittest.TestCase):
    def test_save_persists_and_changes_live_model_without_returning_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); cfg=Settings(data_dir=root)
            client=TestClient(create_app(cfg))
            self.assertFalse(client.get('/api/settings/api-key').json()['configured'])
            key='sk-test-local-setting'
            response=client.post('/api/settings/api-key',json={'api_key':key})
            self.assertEqual(response.status_code,200)
            self.assertNotIn(key,response.text)
            self.assertNotIn(key,client.get('/api/settings/api-key').text)
            self.assertTrue(client.get('/api/health').json()['vision_configured'])
            self.assertEqual(json.loads((root/'api-settings.json').read_text())['api_key'],key)
            with patch.dict(os.environ,{'DATA_DIR':str(root)},clear=True):
                self.assertEqual(Settings.load().api_key,key)
            observed=[]
            def handler(request):
                observed.append(request.headers['authorization'])
                return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'{}'},'finish_reason':'stop'}]})
            ChatModel(cfg,httpx.MockTransport(handler)).complete([])
            self.assertEqual(observed,['Bearer '+key])
    def test_invalid_values_are_rejected_without_echo_and_cross_origin_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg=Settings(data_dir=Path(temp)); client=TestClient(create_app(cfg))
            for value in ['',None,123,'sk-secret\nINJECT','sk-secret withspace']:
                response=client.post('/api/settings/api-key',json={'api_key':value})
                self.assertEqual(response.status_code,400)
                self.assertNotIn('sk-secret',response.text)
            response=client.post('/api/settings/api-key',json={'api_key':'sk-test'},headers={'origin':'https://other.example'})
            self.assertEqual(response.status_code,403)
            self.assertEqual(cfg.api_key,'')

if __name__=='__main__': unittest.main()
