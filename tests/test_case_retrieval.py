import unittest
from rag.index import select_evidence


class CaseRetrievalTests(unittest.TestCase):
    def test_cases_do_not_displace_laws_and_case_context_is_complete(self):
        entries=[{'id':'L'+str(i),'kind':'law'} for i in range(4)]
        entries += [{'id':'W','kind':'warning'}]
        entries += [{'id':'C-'+role,'kind':'case','case_id':'C','chunk_role':role} for role in ['facts','reasoning','outcome']]
        mapping={e['id']:e for e in entries}
        selected=select_evidence(['C-facts','C-reasoning','C-outcome','L0','L1','L2','L3','W'],mapping)
        self.assertEqual(len([e for e in selected if e['kind']=='law']),3)
        self.assertEqual({e.get('chunk_role') for e in selected if e['kind']=='case'},{'facts','reasoning','outcome'})
        self.assertIn('W',[e['id'] for e in selected])

    def test_one_case_group_is_expanded_without_unrelated_cases(self):
        entries=[{'id':case+'-'+role,'kind':'case','case_id':case,'chunk_role':role} for case in ['A','B'] for role in ['facts','reasoning','outcome']]
        result=select_evidence(['A-reasoning','B-facts'],{e['id']:e for e in entries})
        self.assertEqual([e['chunk_role'] for e in result],['facts','reasoning','outcome'])
        self.assertTrue(all(e['case_id']=='A' for e in result))

    def test_no_candidates_do_not_invent_evidence(self):
        self.assertEqual(select_evidence([],{'L':{'id':'L','kind':'law'}}),[])

if __name__=='__main__': unittest.main()
