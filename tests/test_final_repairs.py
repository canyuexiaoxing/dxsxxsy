import unittest
from agent.engine import material_quotes, AgentEngine, CitationError
from agent.report_layout import normalize_layout
from tests.test_content_layout import result

class FinalRepairTests(unittest.TestCase):
    def test_pdf_soft_wrap_keeps_complete_sentence(self):
        body='确认劳动待遇全部结清，离职\n后不再主张任何赔偿或补偿。\n\n下一段独立事实。'
        qs=material_quotes({'messages':[]},[{'material_id':'M1','pages':[{'page_number':1,'text':body,'method':'pdf_text'}]}],'')
        self.assertTrue(any(q['quote']=='确认劳动待遇全部结清，离职\n后不再主张任何赔偿或补偿。' for q in qs))
        self.assertFalse(any('下一段' in q['quote'] and '结清' in q['quote'] for q in qs))

    def test_user_newlines_and_pdf_pages_remain_separate(self):
        ms=[{'material_id':'M1','pages':[{'page_number':1,'text':'离职','method':'pdf_text'},{'page_number':2,'text':'后补偿。','method':'pdf_text'}]}]
        qs=material_quotes({'messages':[]},ms,'第一条\n第二条')
        self.assertFalse(any('离职' in q['quote'] and '后补偿' in q['quote'] for q in qs))
        self.assertFalse(any('第一条' in q['quote'] and '第二条' in q['quote'] for q in qs))

    def test_offer_loss_components_do_not_count_as_three_risks(self):
        r=result(['录用承诺被反复推迟后单方取消','取消录用可能涉及缔约过失赔偿','8月社保自行缴纳，可作为取消录用后的直接经济损失项目'],['合理信赖。','工资损失需举证。','社保损失需证明因果关系。'])
        normalize_layout(r,{'current_message':'录用后辞去原工作，尚未实际入职，公司取消录用，8月社保自行缴纳。','history':[],'materials':[]})
        self.assertEqual(len(r.report.findings),1)
        self.assertIn('工资损失',r.report.findings[0].explanation)
        self.assertIn('因果关系',r.report.findings[0].explanation)

    def test_case_only_is_not_normative_evidence(self):
        r=result(['押金风险']);f=r.report.findings[0];f.material_id='user';f.page_number=0;f.quote='用户真实材料。'
        with self.assertRaises(CitationError):
            AgentEngine(None,None,None,None)._validate(r,{'reports':[],'messages':[]},[],'用户真实材料。',{'LCL-022':{'kind':'case'}})

    def test_context_rules_use_facts_and_preserve_retrieved_entries(self):
        from agent.quality import context_sources
        sources={sid:{'id':sid,'kind':'law'} for sid in ['CIV-500','LCL-007','LAB-J1-035','LCL-026','LAB-J2-019']}
        def get(sid):
            if sid not in sources:raise ValueError('not found')
            return sources[sid]
        found=[{'id':'C','kind':'case','text':'案例有取消录用、结清和放弃社保。'}]
        self.assertEqual(context_sources('普通问题',found,get),[])
        extra=context_sources('取消录用',[sources['CIV-500']],get)
        self.assertEqual([e['id'] for e in extra],['LCL-007'])
        self.assertEqual(len(context_sources('结清与放弃社保',found,get,limit=1)),1)

    def test_offer_merge_keeps_separate_deposit_injury(self):
        r=result(['取消录用信赖利益损失','公司扣留身份证','入职押金不退'])
        normalize_layout(r,{'current_message':'尚未实际入职，取消录用，扣留身份证，入职押金不退。','history':[],'materials':[]})
        self.assertEqual(len(r.report.findings),3)

    def test_registration_insufficient_basis_is_not_abnormal_risk(self):
        r=result(['现有事实不足以认定劳动关系已建立','工伤待遇请求目前缺乏认定基础：先解决劳动关系'])
        normalize_layout(r,{'current_message':'登记参观，未安排劳动。','history':[],'materials':[]})
        self.assertEqual(len(r.report.findings),0)
        self.assertTrue(r.evidence_ids)

    def test_unknown_compensation_and_competition_are_checks(self):
        r=result(['竞业限制约束公开信息','两年期限未载地域范围、违约金合理比例存疑','新岗位是否构成竞争关系需个案判断','公司是否按月支付竞业限制经济补偿不明'])
        normalize_layout(r,{'current_message':'保密协议竞业约定，客户报价公开，完整协议未提供。','history':[],'materials':[]})
        self.assertEqual(len(r.report.findings),1)
        self.assertTrue(any('补偿' in s for s in r.report.limitations))

    def test_registration_wording_variants_do_not_create_risks(self):
        r=result(['仅凭现有事实难以认定已建立劳动关系','工伤主张缺乏事实与程序基础'])
        normalize_layout(r,{'current_message':'求职登记，未安排从事有报酬的工作。','history':[],'materials':[]})
        self.assertEqual(len(r.report.findings),0)

    def test_one_competition_obligation_has_one_risk(self):
        r=result(['竞业限制主体适格性存疑','竞业限制两年期限与无补偿记录并存','公司主张的50000元违约金证据基础薄弱','保密义务与竞业限制义务需区分'])
        normalize_layout(r,{'current_message':'保密协议约定离职后两年不得竞业，否则50000元违约金。','history':[],'materials':[]})
        self.assertEqual(len(r.report.findings),1)

if __name__=='__main__':unittest.main()
