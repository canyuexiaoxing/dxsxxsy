import unittest
from agent.engine import material_quotes, resolve_quotes, CitationError
from agent.schema import TurnResult


class UploadedQuoteRecoveryTests(unittest.TestCase):
    def result(self, **changes):
        return TurnResult.model_validate({'action': 'report', 'message': '', 'questions': [],
            'evidence_ids': [], 'report': {'summary': '检查合同', 'limitations': [],
            'findings': [{'title': '违约金', 'level': 'attention', 'quote_id': 'incorrect-id',
                'quote': '30000元离职违约金。', 'material_id': 'Mtest', 'page_number': 2,
                'explanation': '核查条款', 'evidence_ids': [], 'suggestions': [], **changes}]}})

    def catalogue(self, text='30000元离职违约金。'):
        return material_quotes({'messages': []}, [{'material_id': 'Mtest', 'pages': [
            {'page_number': 1, 'text': '合同期限一年。'},
            {'page_number': 2, 'text': text}]}], '请检查')

    def test_recovers_saved_contract_failure_with_exact_uploaded_quote(self):
        result = self.result()
        catalogue = self.catalogue('乙方辞职须支付\n30000元离职违约金。\n双方未约定专项培训服务期。')
        resolve_quotes(result, catalogue)
        finding = result.report.findings[0]
        self.assertIn(finding.quote_id, {q['quote_id'] for q in catalogue})
        self.assertEqual(finding.quote, '30000元离职违约金。')
        self.assertEqual((finding.material_id, finding.page_number), ('Mtest', 2))

    def test_whitespace_only_difference_is_recovered_and_original_restored(self):
        result = self.result(quote='30000 元离职违约金。')
        resolve_quotes(result, self.catalogue())
        self.assertEqual(result.report.findings[0].quote, '30000元离职违约金。')

    def test_substring_restores_complete_original_segment(self):
        result = self.result()
        resolve_quotes(result, self.catalogue('离职需支付30000元离职违约金。'))
        self.assertEqual(result.report.findings[0].quote, '离职需支付30000元离职违约金。')

    def test_wrong_source_page_edited_text_and_missing_text_are_rejected(self):
        for change in [{'material_id': 'user'}, {'material_id': 'K007'},
                       {'page_number': 1}, {'quote': ''}, {'quote': '50000元离职违约金。'},
                       {'quote': '违约金。'}]:
            with self.subTest(change=change), self.assertRaises(CitationError):
                resolve_quotes(self.result(**change), self.catalogue())

    def test_repeated_quote_is_ambiguous_and_rejected(self):
        with self.assertRaises(CitationError):
            resolve_quotes(self.result(), self.catalogue('30000元离职违约金。\n30000元离职违约金。'))

    def test_repeated_substring_in_single_segment_is_rejected(self):
        with self.assertRaises(CitationError):
            resolve_quotes(self.result(quote='30000元离职违约金'),
                self.catalogue('30000元离职违约金和30000元离职违约金。'))

    def test_duplicate_segment_cannot_be_ignored_for_unique_candidate(self):
        with self.assertRaises(CitationError):
            resolve_quotes(self.result(quote='30000元离职违约金'),
                self.catalogue('30000元离职违约金和30000元离职违约金。\n30000元离职违约金。'))

    def test_engine_persists_verified_quote_and_recovery_trace(self):
        import tempfile
        from pathlib import Path
        from agent.engine import AgentEngine
        from agent.memory import SessionStore
        from reader.store import MaterialStore
        from reader.core import MaterialReader
        from test_quote_repair import Model, Rag, search, report, finding
        with tempfile.TemporaryDirectory() as tmp:
            sessions = SessionStore(Path(tmp))
            materials = MaterialStore(Path(tmp))
            sid = sessions.create('合同引用回归')['id']
            material = MaterialReader(None).read_text('30000元离职违约金。')
            materials.save(material, b'test')
            model = Model([search(), report(finding(quote_id='incorrect-id',
                quote='30000元离职违约金。', material_id=material.material_id, page_number=1))])
            result = AgentEngine(sessions, materials, Rag(), model).turn(sid, '请检查', [material.material_id])
            self.assertEqual(result['report']['findings'][0]['quote'], '30000元离职违约金。')
            stored = sessions.get(sid)
            self.assertEqual(len(stored['reports']), 1)
            self.assertTrue(any(t['tool']=='quote_id_recovery' for t in stored['traces'][-1]))

    def test_rag_text_not_in_uploaded_catalogue_is_rejected(self):
        with self.assertRaises(CitationError):
            resolve_quotes(self.result(quote='不得与劳动者约定由劳动者承担违约金。'), self.catalogue())

    def test_valid_id_remains_authoritative(self):
        catalogue = self.catalogue()
        selected = next(q for q in catalogue if q['material_id'] == 'Mtest' and q['page_number'] == 2)
        result = self.result(quote_id=selected['quote_id'], quote='模型改写', page_number=1)
        resolve_quotes(result, catalogue)
        self.assertEqual(result.report.findings[0].quote, selected['quote'])
        self.assertEqual(result.report.findings[0].page_number, 2)


if __name__ == '__main__':
    unittest.main()
