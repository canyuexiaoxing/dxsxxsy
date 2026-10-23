import json
import unittest
from unittest.mock import patch
from agent.timing import timed_turn, measured

class TimingTests(unittest.TestCase):
 def test_correlated_safe_events_and_failure(self):
  records=[]
  class Sink:
   def info(self,line): records.append(json.loads(line))
  @timed_turn
  def turn(self,sid,text):
   return measured('analysis',lambda: 'ok')
  with patch('agent.timing._logger',return_value=Sink()):
   self.assertEqual(turn(None,'session-test','PRIVATE_SECRET'),'ok')
  self.assertEqual([r['event'] for r in records],['start','start','end','end'])
  self.assertEqual(len({r['request_id'] for r in records}),1)
  self.assertTrue(all(r['session_id']=='session-test' for r in records))
  self.assertNotIn('PRIVATE_SECRET',json.dumps(records))
  self.assertGreaterEqual(records[-1]['elapsed_ms'],0)
  records.clear()
  with patch('agent.timing._logger',return_value=Sink()):
   with self.assertRaises(ValueError): measured('validation',lambda: (_ for _ in ()).throw(ValueError('PRIVATE_SECRET')))
  self.assertEqual(records[-1]['status'],'error')
  self.assertEqual(records[-1]['error_type'],'ValueError')
  self.assertNotIn('PRIVATE_SECRET',json.dumps(records))

class KeywordForwardingTests(unittest.TestCase):
 def test_business_stage_is_forwarded(self):
  def search(query,stage): return (query,stage)
  self.assertEqual(measured('rag_search',search,'test',stage='preemployment'),('test','preemployment'))
