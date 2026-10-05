import json
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from reader.api import create_app
from reader.config import Settings
from pathlib import Path
from agent.engine import AgentEngine, AgentError
from agent.memory import SessionStore
from reader.store import MaterialStore
from reader.core import MaterialReader
from rag.index import KnowledgeIndex

ENTRY={'id':'K001','title':'依据','kind':'law','url':'https://example.gov.cn/law','location':'第九条','published_at':'2012-12-28','verified_at':'2026-10-03','text':'用人单位不得要求劳动者提供担保或者收取财物。','scope':'用人单位招用劳动者','boundary':'先核实主体和用途','tags':['保证金','押金']}

class FakeEmbed:
    model='test-embedding'
    def encode(self,texts): return [[1.0,0.1] for _ in texts]

class FakeRag:
    def search(self,query): return [ENTRY]
    def get(self,source_id):
        if source_id!='K001': raise ValueError('unknown source')
        return ENTRY

def tool(query='入职保证金'):
    return {'role':'assistant','content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':'search_knowledge','arguments':json.dumps({'query':query})}}]}

def output(action='ask',report=None):
    return {'role':'assistant','content':json.dumps({'action':action,'message':'请核实收费主体和用途。','questions':['谁收钱？'] if action=='ask' else [],'evidence_ids':['K001'],'report':report},ensure_ascii=False)}

class FakeModel:
    def __init__(self,outputs): self.outputs=list(outputs)
    def complete(self,messages,tools=None,force_search=False): return self.outputs.pop(0)

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.sessions=SessionStore(self.root); self.materials=MaterialStore(self.root)
        self.material=MaterialReader(None).read_text('公司要求入职交2000元保证金。')
        self.materials.save(self.material,b'test')
        self.sid=self.sessions.create('测试')['id']
    def tearDown(self): self.temp.cleanup()
    def engine(self,outputs): return AgentEngine(self.sessions,self.materials,FakeRag(),FakeModel(outputs))
    def report(self):
        return {'summary':'发现收费风险信号','findings':[{'title':'入职收费','level':'high','quote':'公司要求入职交2000元保证金。','material_id':self.material.material_id,'page_number':1,'explanation':'需核实是否符合适用条件','evidence_ids':['K001'],'suggestions':['核实收费主体']}],'limitations':['尚未核实主体资质'],'change_reason':''}
    def test_ask_then_report_and_restart(self):
        self.engine([tool(),output()]).turn(self.sid,'帮我分析',[self.material.material_id])
        self.assertEqual(self.sessions.get(self.sid)['state'],'awaiting_info')
        self.engine([tool(),output('report',self.report())]).turn(self.sid,'是用人单位收保证金')
        restored=SessionStore(self.root).get(self.sid)
        self.assertEqual(len(restored['reports']),1)
        self.assertEqual(len(restored['messages']),4)
    def test_answer_does_not_rewrite_report(self):
        self.engine([tool(),output('report',self.report())]).turn(self.sid,'分析',[self.material.material_id])
        self.engine([tool(),output('answer')]).turn(self.sid,'这是什么意思？')
        self.assertEqual(len(self.sessions.get(self.sid)['reports']),1)
    def test_http_report_download_restart_and_delete(self):
        with patch('agent.routes.KnowledgeIndex',return_value=FakeRag()),patch('agent.routes.ChatModel',return_value=FakeModel([tool(),output('report',self.report())])):
            client=TestClient(create_app(Settings(data_dir=self.root)))
            response=client.post(f'/api/sessions/{self.sid}/messages',json={'text':'分析','material_ids':[self.material.material_id]})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['report']['version'],1)
            downloaded=client.get(f'/api/sessions/{self.sid}/reports/1/download')
            self.assertEqual(downloaded.status_code,200)
            self.assertIn('https://example.gov.cn/law',downloaded.text)
            restarted=TestClient(create_app(Settings(data_dir=self.root)))
            self.assertEqual(len(restarted.get(f'/api/sessions/{self.sid}').json()['reports']),1)
            self.assertEqual(restarted.get(f'/api/sessions/{self.sid}/reports/99').status_code,404)
            self.assertEqual(restarted.delete(f'/api/sessions/{self.sid}').status_code,200)
            self.assertEqual(restarted.get(f'/api/sessions/{self.sid}').status_code,404)
            self.assertFalse((self.root/'materials'/self.material.material_id).exists())
    def test_structure_repair_still_checks_citations(self):
        broken={'role':'assistant','content':'{'}
        report=self.report(); report['findings'][0]['evidence_ids']=['FAKE']
        with self.assertRaises(AgentError):
            self.engine([tool(),broken,output('report',report)]).turn(self.sid,'分析',[self.material.material_id])
        self.assertEqual(len(self.sessions.get(self.sid)['reports']),0)
    def test_structure_repair_succeeds(self):
        result=self.engine([tool(),{'role':'assistant','content':'{'},output()]).turn(self.sid,'分析',[self.material.material_id])
        self.assertEqual(result['action'],'ask')
    def test_revision_preserves_versions(self):
        self.engine([tool(),output('report',self.report())]).turn(self.sid,'分析',[self.material.material_id])
        revised=self.report(); revised['change_reason']='新增收费主体信息'; revised['summary']='需重新核实'
        self.engine([tool(),output('revise',revised)]).turn(self.sid,'纠正：收钱的是培训机构')
        self.assertEqual([r['version'] for r in self.sessions.get(self.sid)['reports']],[1,2])
    def test_invalid_citation_and_quote_are_rejected(self):
        for field in ['citation','quote']:
            report=self.report()
            if field=='citation': report['findings'][0]['evidence_ids']=['FAKE']
            else: report['findings'][0]['quote']='不存在的原文'
            with self.assertRaises(AgentError): self.engine([tool(),output('report',report)]).turn(self.sid,'分析',[self.material.material_id])
        self.assertEqual(len(self.sessions.get(self.sid)['reports']),0)
    def test_session_isolation_and_delete(self):
        self.engine([tool(),output()]).turn(self.sid,'分析',[self.material.material_id])
        second=self.sessions.create('另一个')['id']
        self.assertEqual(self.sessions.get(second)['material_ids'],[])
        self.sessions.delete(self.sid)
        with self.assertRaises(KeyError): self.sessions.get(self.sid)
    def test_repeated_questions_are_rejected(self):
        self.engine([tool(),output()]).turn(self.sid,'分析',[self.material.material_id])
        with self.assertRaises(AgentError): self.engine([tool(),output()]).turn(self.sid,'不知道')
    def test_tool_loop_limit(self):
        with self.assertRaises(AgentError): self.engine([tool() for _ in range(8)]).turn(self.sid,'分析',[self.material.material_id])
    def test_no_report_replacement_without_revision(self):
        self.engine([tool(),output('report',self.report())]).turn(self.sid,'分析',[self.material.material_id])
        with self.assertRaises(AgentError): self.engine([tool(),output('report',self.report())]).turn(self.sid,'补充信息')

    def test_null_optional_fields_in_report_are_normalized(self):
        report=self.report(); report['change_reason']=None
        reply=output('report',report)
        body=json.loads(reply['content']); body['message']=None; body['questions']=None
        reply['content']=json.dumps(body)
        result=self.engine([tool(),reply]).turn(self.sid,'分析',[self.material.material_id])
        self.assertEqual(result['questions'],[])
        self.assertEqual(result['report']['change_reason'],'')

class RagTests(unittest.TestCase):
    def test_persistent_index_and_sources(self):
        # Chroma's native index retains Windows handles until process exit.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            root=Path(root); source=root/'entries.json'; source.write_text(json.dumps([ENTRY]),encoding='utf-8')
            index=KnowledgeIndex(root/'index',source,FakeEmbed())
            index.build()
            self.assertEqual(index.search('入职保证金')[0]['id'],'K001')
            again=KnowledgeIndex(root/'index',source,FakeEmbed())
            self.assertEqual(again.get('K001')['url'],ENTRY['url'])
            source.write_text(json.dumps([{**ENTRY,'text':'已修改'}]),encoding='utf-8')
            with self.assertRaises(ValueError): again.search('入职保证金')

if __name__=='__main__': unittest.main()
