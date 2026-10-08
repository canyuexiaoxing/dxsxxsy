import unittest
from agent.report_layout import normalize_layout
from agent.schema import TurnResult


def result(titles, explanations=None):
    return TurnResult.model_validate({'action':'report','message':'','questions':[],
        'evidence_ids':['LCL-022'], 'report':{'summary':'分析','limitations':[],
        'findings':[{'title':t,'level':'attention','quote':'用户真实材料。',
            'material_id':'Mtest','page_number':1,'explanation':(explanations or ['判断']*len(titles))[i],
            'evidence_ids':['LCL-022'],'suggestions':['建议'+str(i)]} for i,t in enumerate(titles)]}})


class ContentLayoutTests(unittest.TestCase):
    def context(self, facts):
        return {'current_message':facts,'history':[],'materials':[]}

    def test_recruitment_checks_and_remedies_do_not_count_as_risks(self):
        r=result(['因河南籍贯拒录','求职者可通过诉讼等途径主张就业歧视救济',
            '证据已部分保全，但关键材料缺口影响举证强度','材料性质与信息缺口限制结论范围'])
        normalize_layout(r,self.context('公司招聘法务专员，因河南人拒录。'))
        self.assertEqual([f.title for f in r.report.findings],['因河南籍贯拒录'])
        self.assertIn('建议1',r.report.findings[0].suggestions)
        self.assertTrue(any('关键材料缺口' in s for s in r.report.limitations))

    def test_advice_before_risk_is_preserved(self):
        r=result(['求职者可通过诉讼等途径主张就业歧视救济','因籍贯拒录'])
        normalize_layout(r,self.context('因籍贯拒录。'))
        self.assertEqual(len(r.report.findings),1)
        self.assertIn('建议0',r.report.findings[0].suggestions)

    def test_distinct_training_conditions_are_combined_without_losing_reasoning(self):
        r=result(['培训可能不构成专业技术培训，服务期违约金效力存疑',
            '赔偿全部培训费用可能超出法定违约金上限',
            '仅因短期离职即主张赔偿培训费，存在被用于限制正常离职的风险'],
            ['普通岗前培训不满足专项培训条件。','即便条件成立，不能超出未履行比例。','离职索费属于同一争议。'])
        r.report.findings[1].level='high'
        normalize_layout(r,self.context('培训服务期1.5年，未满赔偿全部培训费。'))
        self.assertEqual(len(r.report.findings),1)
        self.assertIn('未履行比例',r.report.findings[0].explanation)
        self.assertEqual(r.report.findings[0].level,'high')

    def test_actual_withheld_wages_and_documents_remain_distinct(self):
        r=result(['服务期违约金约定风险','以培训费为由扣发工资','扣留证件限制离职'])
        normalize_layout(r,self.context('培训服务期未满，公司索要培训费、扣发工资，并扣留证件。'))
        self.assertEqual(len(r.report.findings),3)

    def test_missing_contract_clause_and_refusal_of_remedy_are_not_generic_checks(self):
        r=result(['合同缺少社会保险约定','公司拒绝配合依法维权'])
        normalize_layout(r,self.context('合同不约定社保，公司拒绝配合依法维权。'))
        self.assertEqual(len(r.report.findings),2)

    def test_assistant_does_not_use_court_identity_but_original_quote_is_preserved(self):
        r=result(['服务期违约金约定风险'],['本院认为需核实专项培训。本院不作认定。'])
        r.report.findings[0].quote='法院原文：本院认为。'
        normalize_layout(r,self.context('培训服务期及违约金约定。'))
        self.assertNotIn('本院',r.report.findings[0].explanation)
        self.assertEqual(r.report.findings[0].quote,'法院原文：本院认为。')

    def test_answer_identity_is_corrected(self):
        r=TurnResult.model_validate({'action':'answer','message':'本院建议保存合同。',
            'questions':[],'evidence_ids':[],'report':None})
        normalize_layout(r,self.context('合同违约金问题。'))
        self.assertNotIn('本院',r.message)

    def test_explicit_court_quotation_in_explanation_is_preserved(self):
        r=result(['合同条款风险'],['公开判决写道：“本院认为条款无效。”本院仅提供风险提示。'])
        normalize_layout(r,self.context('合同条款问题。'))
        self.assertIn('“本院认为条款无效。”',r.report.findings[0].explanation)
        self.assertNotIn('本院仅提供',r.report.findings[0].explanation)


class EditorReintroductionTests(unittest.TestCase):
    def setUp(self):
        from tests.test_editor_stage import EditorStageTests
        EditorStageTests.setUp(self)
    def tearDown(self):
        from tests.test_editor_stage import EditorStageTests
        EditorStageTests.tearDown(self)

    def test_editor_cannot_restore_checks_as_risks(self):
        import json
        from agent.engine import AgentEngine
        from tests.test_editor_stage import EditorStageTests
        from tests.test_report_quality import QualityModel
        from tests.test_agent import FakeRag,tool,output
        raw=EditorStageTests.report(self)
        raw['findings'][0]['title']='保证金收费风险'
        edited=json.loads(output('report',raw)['content'])
        edited['report']['findings'].append(dict(raw['findings'][0],title='关键材料缺口影响举证强度'))
        edited['report']['findings'][0]['explanation']='本院认为该收费有风险。'
        fixed=json.loads(output('report',raw)['content']);fixed['report']['limitations']=['关键材料缺口仅列待核实']
        model=QualityModel([tool(),{'role':'assistant','content':json.dumps(edited)},{'role':'assistant','content':json.dumps(fixed)}],[[{'code':'missing_as_risk','detail':'材料缺口应作为待核实事项，自称法院应改正','finding_indexes':[1],'evidence_ids':[]}],[]])
        reply=AgentEngine(self.sessions,self.materials,FakeRag(),model).turn(self.sid,'公司要求保证金')
        self.assertEqual(len(reply['report']['findings']),1)
        self.assertNotIn('本院',reply['report']['findings'][0]['explanation'])
        self.assertTrue(any('关键材料缺口' in s for s in reply['report']['limitations']))


if __name__=='__main__':unittest.main()
