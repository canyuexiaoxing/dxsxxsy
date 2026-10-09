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
    def test_report_opening_preserves_full_input_instead_of_truncated_session_title(self):
        original='我是大四学生，还未入职、签约或付款。招聘广告月薪6000—8000元。HR要求两个月培训，费用9800元，可以分期但贷款性质未知。'
        report=example();report['report_context']={'user_statements':[original]};report['situation_overview']='大四学生尚未入职，求职过程中被要求参加收费培训，分期性质未知。'
        with ZipFile(BytesIO(render_report_docx(report,original[:22]))) as archive:
            root=ElementTree.fromstring(archive.read('word/document.xml'))
            paragraphs=[''.join(p.itertext()) for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')]
            self.assertNotIn(original,paragraphs)
            self.assertIn(report['situation_overview'],paragraphs)
            self.assertNotIn(original[:22],paragraphs)
            self.assertIn('本次求职情况概述',''.join(paragraphs))

    def test_links_are_styled_encoded_and_distinguish_law_maker_from_site(self):
        report=example();report['sources'][0].update(url='https://example.gov.cn/劳动法/',source_publisher='全国人民代表大会常务委员会',source_site='国家法律法规数据库',source_role='法律制定机关',legal_database_status='specific_record_checked')
        with ZipFile(BytesIO(render_report_docx(report))) as archive:
            xml=archive.read('word/document.xml').decode();rels=archive.read('word/_rels/document.xml.rels').decode()
            self.assertIn('Hyperlink',xml)
            self.assertIn('%E5%8A%B3%E5%8A%A8',rels)
            self.assertIn('法律制定机关',xml)
            self.assertIn('国家法律法规数据库',xml)

    def test_download_old_version_does_not_include_later_user_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);session=store.create('我是大四学生，正在找第一份工作，还没有入职、')
            first='广告月薪6000—8000元，HR说培训费9800元。'
            session['reports']=[example()]
            session['messages']=[{'role':'user','text':first,'material_ids':[]},{'role':'assistant','result':{'report':{'version':1}}},{'role':'user','text':'后来我付了9800元。','material_ids':[]}]
            store.save(session);client=TestClient(create_app(Settings(data_dir=root)))
            response=client.get(f'/api/sessions/{session["id"]}/reports/1/download?format=docx')
            with ZipFile(BytesIO(response.content)) as archive:
                xml=archive.read('word/document.xml').decode()
                self.assertIn('本次求职情况概述',xml)
                self.assertNotIn(first,xml)
                self.assertNotIn('后来我付了9800元。',xml)

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
    def test_download_refreshes_source_links_without_replacing_historical_text(self):
        import json
        entries=json.loads((Path(__file__).resolve().parents[1]/'knowledge/entries.json').read_text(encoding='utf-8'))
        law=next(e for e in entries if e['id']=='K001')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=SessionStore(root);session=store.create('测试会话');report=example()
            report['sources']=[{**law,'url':'https://example.gov.cn/old-link','source_publisher':'旧转载网站'}]
            session['reports']=[report];store.save(session);client=TestClient(create_app(Settings(data_dir=root)))
            data=client.get(f'/api/sessions/{session["id"]}/reports/1/download?format=docx').content
            with ZipFile(BytesIO(data)) as archive:
                self.assertIn('flk.npc.gov.cn',archive.read('word/_rels/document.xml.rels').decode())
                self.assertIn(law['text'],archive.read('word/document.xml').decode())
            self.assertEqual(store.get(session['id'])['reports'][0]['sources'][0]['url'],'https://example.gov.cn/old-link')

    def test_shared_document_source_metadata_is_not_repeated_for_each_chunk(self):
        report=example();source=report['sources'][0];source['source_publisher']='全国人民代表大会常务委员会'
        report['sources'].append({**source,'id':'LCL-022','location':'第二十二条','text':'第二十二条完整测试原文。'})
        report['findings'][0]['evidence_ids'].append('LCL-022')
        document=__import__('docx').Document(BytesIO(render_report_docx(report)))
        texts=[p.text for p in document.paragraphs]
        self.assertEqual(sum('全国人民代表大会常务委员会' in t for t in texts),1)
        self.assertTrue(any('LCL-022' in t for t in texts))
        self.assertIn('第二十二条完整测试原文。',texts)

    def test_empty_report_and_unverified_case_keep_limits(self):
        report=example(); report['findings']=[]
        report['sources'][0].update(kind='case',url='',verification_status='local_document_checked_official_pending',source_document='判决书原文.docx',source_paragraphs='P1–P20')
        with ZipFile(BytesIO(render_report_docx(report))) as archive:
            xml=archive.read('word/document.xml').decode()
            self.assertIn('未列出具体风险点',xml)
            self.assertIn('官方真实性与完整性待核验',xml)
            self.assertIn('判决书原文.docx',xml)

if __name__=='__main__': unittest.main()
