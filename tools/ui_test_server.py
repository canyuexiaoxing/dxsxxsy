"""Isolated deterministic UI test server; all conversations are explicitly synthetic."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from reader.config import Settings
from reader.vision import VisionResult
from reader.api import create_app
import agent.routes

ENTRY=json.loads((ROOT/'knowledge/entries.json').read_text(encoding='utf-8'))[0]
class Rag:
    def search(self,q):return [ENTRY]
    def get(self,id):
        if id!=ENTRY['id']:raise ValueError('未知依据')
        return ENTRY
class Vision:
    def extract(self,data,mime):return VisionResult(text='模拟截图：用人单位要求入职前交2000元保证金。',issues=['界面测试模拟识别结果，不是真实OCR。'],unreadable=False)
class Model:
    def __init__(self,*args):pass
    def complete(self,messages,tools=None,force_search=False):
        if force_search:return {'role':'assistant','content':None,'tool_calls':[{'id':'mock-search','type':'function','function':{'name':'search_knowledge','arguments':json.dumps({'query':'入职保证金'})}}]}
        ctx=json.loads(messages[1]['content']);history=ctx['history'];previous=ctx['latest_report']
        action='ask' if not history else ('report' if not previous else ('revise' if '纠正' in ctx['current_message'] else 'answer'))
        result={'action':action,'message':'界面模拟：已读取材料。需要先确认收费主体和用途。' if action=='ask' else '界面模拟：可以先要求对方说明收费主体、用途并提供书面材料。','questions':['这笔2000元由谁收取？','对方说明这笔费用用于什么？'] if action=='ask' else [],'evidence_ids':[ENTRY['id']],'report':None}
        if action in {'report','revise'}:
            material=ctx['materials'][0] if ctx['materials'] else None
            quote=material['pages'][0]['text'] if material else next(m['text'] for m in history if m['role']=='user')
            result['report']={'summary':'模拟展示：发现一项需要核实的收费风险。','findings':[{'title':'入职收费需要警惕','level':'high' if action=='report' else 'uncertain','quote':quote,'material_id':material['material_id'] if material else 'user','page_number':1 if material else 0,'explanation':'收费主体和用途需结合材料核实。','evidence_ids':[ENTRY['id']],'suggestions':['向对方核实收费主体与具体用途。']}],'limitations':['此为界面测试模拟报告，不作为实际风险结论。'],'change_reason':'用户纠正了收费主体。' if action=='revise' else ''}
        return {'role':'assistant','content':json.dumps(result,ensure_ascii=False)}
agent.routes.KnowledgeIndex=lambda *args:Rag()
agent.routes.ChatModel=Model
app=create_app(Settings(data_dir=ROOT/'data/ui-test'),vision=Vision())
