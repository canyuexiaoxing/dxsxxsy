import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from desktop_runtime import state_root, seed_payload, model_available

class DesktopRuntimeTests(unittest.TestCase):
    def test_frozen_state_follows_executable_install_directory(self):
        with patch('desktop_runtime.sys.frozen', True, create=True), patch('desktop_runtime.sys.executable', 'D:/Apps/JobMirror/JobMirror.exe'), patch.dict('os.environ', {'LOCALAPPDATA': 'C:/Users/test/AppData/Local'}, clear=True):
            self.assertEqual(state_root(), Path('D:/Apps/JobMirror'))

    def test_data_override_is_preserved(self):
        with patch.dict('os.environ', {'JOBMIRROR_HOME': 'E:/test/profile'}):
            self.assertEqual(state_root(), Path('E:/test/profile'))

    def test_seed_does_not_accept_stale_or_extra_private_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'entries.json'
            source.write_text(json.dumps([{'id':'K001','text':'公开法条'}]),encoding='utf-8')
            import hashlib
            seed={'metadata':{'source_hash':hashlib.sha256(source.read_bytes()).hexdigest(),'embedding_model':'qwen3-embedding:4b'},'ids':['K001'],'documents':['私人聊天'],'embeddings':[[1.0]],'metadatas':[{'kind':'law'}]}
            with self.assertRaises(ValueError):seed_payload(source,seed)
            seed['documents']=['公开法条']
            self.assertEqual(seed_payload(source,seed)['ids'],['K001'])
            seed['metadata']['source_hash']='old'
            with self.assertRaises(ValueError):seed_payload(source,seed)

    def test_model_tag_requires_correct_model(self):
        self.assertFalse(model_available({'models':[{'name':'other:latest'}]}))
        self.assertTrue(model_available({'models':[{'name':'qwen3-embedding:4b'}]}))

    def test_seed_import_uses_same_cosine_metric_as_retrieval(self):
        from desktop_runtime import prepare_knowledge
        from unittest.mock import MagicMock
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'knowledge').mkdir()
            source=root/'knowledge/entries.json'
            source.write_text(json.dumps([{'id':'K001','text':'公开法条'}]),encoding='utf-8')
            seed={'metadata':{'source_hash':hashlib.sha256(source.read_bytes()).hexdigest(),'embedding_model':'qwen3-embedding:4b'},'ids':['K001'],'documents':['公开法条'],'embeddings':[[1.0]],'metadatas':[{'kind':'law'}]}
            (root/'knowledge/public-seed.json').write_text(json.dumps(seed),encoding='utf-8')
            client=MagicMock();collection=client.get_or_create_collection.return_value
            collection.metadata={};collection.get.return_value={'ids':[]}
            with patch('chromadb.PersistentClient',return_value=client):prepare_knowledge(root,root/'data',lambda _:None)
            self.assertEqual(client.get_or_create_collection.call_args.kwargs['metadata']['hnsw:space'],'cosine')
            collection.upsert.assert_called_once()

    def test_cancelled_setup_never_starts_model_process(self):
        from desktop_runtime import ModelRuntime
        import threading
        stop=threading.Event();stop.set()
        with patch('desktop_runtime.subprocess.Popen') as spawn, patch('desktop_runtime.httpx.Client') as client:
            ModelRuntime(Path('resources'),Path('profile'),stop).prepare(lambda _:None)
        spawn.assert_not_called();client.assert_not_called()

    def test_each_instance_can_use_its_own_model_endpoint(self):
        from desktop_runtime import ModelRuntime
        import threading
        from unittest.mock import MagicMock
        client=MagicMock();client.get.return_value.json.return_value={'models':[{'name':'qwen3-embedding:4b'}]}
        with patch('desktop_runtime.httpx.Client') as factory:
            factory.return_value.__enter__.return_value=client
            ModelRuntime(Path('resources'),Path('profile'),threading.Event(),'http://127.0.0.1:12345').prepare(lambda _:None)
        client.get.assert_called_once_with('http://127.0.0.1:12345/api/tags')

    def test_close_during_probe_prevents_a_late_process_spawn(self):
        from desktop_runtime import ModelRuntime
        from unittest.mock import MagicMock
        import threading
        import httpx
        stop=threading.Event();client=MagicMock()
        def cancel(*args,**kwargs):
            stop.set();raise httpx.ConnectError('not running')
        client.get.side_effect=cancel
        with tempfile.TemporaryDirectory() as folder, patch('desktop_runtime.httpx.Client') as factory, patch('desktop_runtime.subprocess.Popen') as spawn:
            factory.return_value.__enter__.return_value=client
            ModelRuntime(Path('resources'),Path(folder),stop).prepare(lambda _:None)
            spawn.assert_not_called()
