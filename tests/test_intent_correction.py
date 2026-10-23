import sys,unittest
sys.path.insert(0,r'E:\workp\dxsxxsy')
from agent.model import ChatModel
from reader.config import Settings
from unittest.mock import patch
class IntentCorrectionPromptTests(unittest.TestCase):
    def test_latest_explicit_correction_has_priority(self):
        with patch.object(ChatModel,'complete',return_value={'content':'{"requested":true}'}) as call:
            self.assertTrue(ChatModel(Settings()).classify_report_request('刚才说不要生成，现在请生成报告。'))
            self.assertIn('最后明确表达',call.call_args.args[0][0]['content'])
