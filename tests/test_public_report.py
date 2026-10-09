import unittest
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile
from agent.word_export import render_report_docx


class PublicReportTests(unittest.TestCase):
    def sample(self):
        return dict(summary='培训收费待核实', version=1, sources=[], limitations=['分期是否为贷款尚不明确'],
                    review_status={'status':'final_revision_unreviewed','last_issues':[{'detail':'草稿内部 finding'}]},
                    review_notes=['已达到两次审核上限，最后一次修改未再复核','上轮复核待核实提示：草稿内部 finding'],
                    prevention={'label':'先核查','steps':['通过国家企业信用信息公示系统核查企业','咨询当地人社部门核实招聘服务许可','保存聊天记录'], 'note':'尚未付款'},
                    findings=[dict(title='收费培训',level='attention',quote='培训9800元', material_id='user',page_number=0,
                                   explanation='需明确收费主体',evidence_ids=[],suggestions=['向公共法律服务机构咨询协议'])])

    def test_export_hides_diagnostics_and_links_actions(self):
        raw=self.sample(); before=deepcopy(raw)
        with ZipFile(BytesIO(render_report_docx(raw))) as doc:
            xml=doc.read('word/document.xml').decode()
            self.assertNotIn('两次审核上限',xml)
            self.assertNotIn('草稿内部',xml)
            self.assertIn('分期是否为贷款尚不明确',xml)
            from lxml import etree
            root=etree.fromstring(xml.encode()); ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs=root.findall('.//w:p',ns)
            for token,host,phone in [('核查企业','www.gsxt.gov.cn',''),('招聘服务许可','www.12333.gov.cn','12333'),('咨询协议','www.12348.gov.cn','12348')]:
                p=next(p for p in paragraphs if token in ''.join(p.itertext()))
                if host in ('www.gsxt.gov.cn','www.12333.gov.cn'):
                    self.assertIn('官方核查入口',''.join(p.itertext()))
                    target=next(q for q in paragraphs if host in ''.join(q.itertext()))
                    self.assertTrue(target.findall('w:hyperlink',ns))
                else:
                    self.assertIn(host,''.join(p.itertext()))
                    self.assertTrue(p.findall('w:hyperlink',ns))
                if phone:self.assertIn(phone,''.join(p.itertext()))
        self.assertEqual(raw,before)

    def test_public_view_is_idempotent_and_preserves_saved_diagnostics(self):
        from agent.presentation import public_report,public_session
        raw=self.sample(); result=public_report(raw)
        self.assertEqual(result,public_report(result))
        self.assertNotIn('review_status',result)
        self.assertNotIn('review_notes',result)
        self.assertEqual(result['prevention']['steps'][2],'保存聊天记录')
        session={'reports':[raw],'messages':[{'role':'assistant','result':{'report':raw}}],'traces':['internal']}
        public=public_session(session)
        self.assertNotIn('traces',public)
        self.assertNotIn('review_notes',public['messages'][0]['result']['report'])
        self.assertIn('review_status',session['reports'][0])

    def test_historical_api_and_download_use_public_view(self):
        import tempfile
        from pathlib import Path
        from fastapi.testclient import TestClient
        from reader.api import create_app
        from reader.config import Settings
        from agent.memory import SessionStore
        with tempfile.TemporaryDirectory() as directory:
            store=SessionStore(Path(directory));session=store.create('历史报告')
            report=self.sample();report['change_reason']='';session['reports']=[report]
            session['messages']=[{'role':'assistant','text':'报告已生成','result':{'report':report}}]
            store.save(session)
            client=TestClient(create_app(Settings(data_dir=Path(directory))))
            path=f'/api/sessions/{session["id"]}'
            for url in [path,path+'/reports/1',path+'/reports/1/download?format=md']:
                response=client.get(url);self.assertEqual(response.status_code,200)
                self.assertNotIn('草稿内部',response.text)
                self.assertNotIn('review_status',response.text)
                self.assertIn('www.gsxt.gov.cn',response.text)
                self.assertIn('12348',response.text)
            self.assertIn('review_status',store.get(session['id'])['reports'][0])
