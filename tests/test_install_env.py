import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from reader.config import Settings

class InstallEnvTests(unittest.TestCase):
    def test_installed_env_is_read_from_executable_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            (home/'.env').write_text('DEEPSEEK_API_KEY=sk-synthetic-test\nDEEPSEEK_BASE_URL=https://example.test\nAPI_TIMEOUT_SECONDS=90\n',encoding='utf-8')
            with patch('reader.config.state_root',return_value=home), patch.dict(os.environ,{},clear=True):
                settings=Settings.load()
            self.assertEqual(settings.api_key,'sk-synthetic-test')
            self.assertEqual(settings.base_url,'https://example.test')
            self.assertEqual(settings.timeout,90)
            self.assertEqual(settings.data_dir,(home/'data').resolve())

    def test_environment_overrides_template_and_empty_key_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            (home/'.env').write_text('DEEPSEEK_API_KEY=\nDEEPSEEK_MODEL=template-model\n',encoding='utf-8')
            with patch('reader.config.state_root',return_value=home), patch.dict(os.environ,{'DEEPSEEK_MODEL':'override-model'},clear=True):
                settings=Settings.load()
            self.assertEqual(settings.api_key,'')
            self.assertEqual(settings.model,'override-model')

