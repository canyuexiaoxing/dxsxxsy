"""Live synthetic workflow, not competition evaluation data."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from reader.config import Settings
from reader.core import MaterialReader
from reader.store import MaterialStore
from agent.memory import SessionStore
from agent.model import ChatModel
from agent.engine import AgentEngine
from rag.embedding import OllamaEmbedding
from rag.index import KnowledgeIndex

def main():
    cfg=Settings.load()
    sessions=SessionStore(cfg.data_dir); materials=MaterialStore(cfg.data_dir)
    session=sessions.create('模拟验证：收费招聘')
    material=MaterialReader(None).read_text('模拟材料：对方说入职前需要交2000元，但没有说明钱交给谁、用途是什么。')
    materials.save(material,material.pages[0].text.encode('utf-8'))
    rag=KnowledgeIndex(cfg.data_dir/'chroma',ROOT/'knowledge/entries.json',OllamaEmbedding())
    engine=AgentEngine(sessions,materials,rag,ChatModel(cfg))
    cases=[('先分析材料，有必要就追问。',[material.material_id]),('是实际招聘用人单位收取的入职保证金，必须交钱才能入职。没有其他协议。现在请生成风险报告。',[]),('请解释为什么需要警惕，并给出我要向HR核实的问题。不需要修改报告。',[]),('纠正之前的信息：收款方不是用人单位，而是独立培训机构。费用实际是培训费，我尚未看清培训协议，不知道是否贷款。请根据这个纠正修订报告，未知项列明。',[])]
    outcomes=[]
    for text,ids in cases:
        result=engine.turn(session['id'],text,ids)
        outcome={'action':result['action'],'questions':result['questions'],'source_ids':[s['id'] for s in result['sources']],'report_version':result['report']['version'] if result['report'] else None}
        print(json.dumps(outcome,ensure_ascii=False),flush=True)
        outcomes.append(outcome)
    restored=SessionStore(cfg.data_dir).get(session['id'])
    verification={'session_id':session['id'],'synthetic_only':True,'outcomes':outcomes,'persisted_messages':len(restored['messages']),'persisted_report_versions':[r['version'] for r in restored['reports']]}
    (ROOT/'agent-live-verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    expected=['ask','report','answer','revise']
    if [o['action'] for o in outcomes]!=expected or len(restored['reports'])!=2: raise SystemExit('Unexpected workflow; inspect saved session.')

if __name__=='__main__': main()
