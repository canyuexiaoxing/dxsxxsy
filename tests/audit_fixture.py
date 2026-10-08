def audit(issues=None):
 from agent.quality import AUDIT_CHECKS
 return {'issues':issues or [],'employment_stage':'unknown','stage_reason':'测试材料未明确阶段',
         'checks':[{'name':n,'verdict':'issues' if issues and n=='facts' else 'pass','detail':'逐项核对测试材料'} for n in AUDIT_CHECKS]}
