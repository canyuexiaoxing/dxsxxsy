import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree
from fastapi.testclient import TestClient
from agent.word_export import render_report_docx
from agent.memory import SessionStore
from reader.config import Settings
from reader.api import create_app

def example():
    return {'summary':'发现收费风险，需核实主体与用途。','version':1,'created_at':'2026-10-04T02:00:00+00:00','change_reason':'',
        'findings':[{'title':'入职保证金','level':'high','quote':'入职前交2000元保证金。','material_id':'user','page_number':0,'explanation':'需要核实是否属于用人单位收取财物。','evidence_ids':['K001'],'suggestions':['保留收费通知和转账凭证。']}],
        'limitations':['尚未核实收费主体。'],'sources':[{'id':'K001','title':'中华人民共和国劳动合同法','kind':'law','location':'第九条','text':'不得要求劳动者提供担保或者以其他名义向劳动者收取财物。','boundary':'核实收费主体与用途。','url':'https://example.gov.cn/law','verified_at':'2026-10-04'}]}

class WordExportTests(unittest.TestCase):
    def test_editable_docx_has_chart_sources_and_original_quote(self):
        data=render_report_docx(example(),'测试报告')
        with ZipFile(BytesIO(data)) as archive:
            xml=archive.read('word/document.xml').decode()
            root=ElementTree.fromstring(xml)
            text=''.join(root.itertext())
            for value in ['入职前交2000元保证金。','尚未核实收费主体。','第九条','结论与风险概览','待核实事项与分析局限']:
                self.assertIn(value,text)
            self.assertTrue(any(name.startswith('word/media/') for name in archive.namelist()))
            self.assertIn('https://example.gov.cn/law',archive.read('word/_rels/document.xml.rels').decode())
    def test_download_content_type_format_validation_and_missing_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); store=SessionStore(root); session=store.create('测试会话')
            session['reports']=[example()]; store.save(session)
            client=TestClient(create_app(Settings(data_dir=root)))
            path=f'/api/sessions/{session["id"]}/reports/1/download'
            response=client.get(path+'?format=docx')
            self.assertEqual(response.status_code,200)
            self.assertIn('wordprocessingml.document',response.headers['content-type'])
            self.assertTrue(response.content.startswith(b'PK'))
            self.assertIn('.docx',response.headers['content-disposition'])
            self.assertEqual(client.get(path+'?format=exe').status_code,422)
            self.assertEqual(client.get(path.replace('/1/','/2/')+'?format=docx').status_code,404)
    def test_empty_report_and_unverified_case_keep_limits(self):
        report=example(); report['findings']=[]
        report['sources'][0].update(kind='case',url='',verification_status='local_document_checked_official_pending',source_document='判决书原文.docx',source_paragraphs='P1–P20')
        with ZipFile(BytesIO(render_report_docx(report))) as archive:
            xml=archive.read('word/document.xml').decode()
            self.assertIn('未列出具体风险点',xml)
            self.assertIn('官方真实性与完整性待核验',xml)
            self.assertIn('判决书原文.docx',xml)

if __name__=='__main__': unittest.main()
