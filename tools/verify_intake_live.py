import argparse,json,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from reader.api import create_app
from reader.config import Settings
p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--baseline',action='store_true');args=p.parse_args()
cases=[
 {'id':'fee-details','turns':['我是大四学生，找第一份工作，HR说要交一笔费用，你帮我看看有没有坑。','我还没入职、签字或付款。招聘广告是行政助理，月薪5000元；要求收费的是招聘公司的HR，费用2000元叫工位保证金，付给同一家招聘公司，不交不给录用通知，入职三个月退。HR用微信文字说明，没有培训或中介服务。请继续分析。'],'expected':['ask','report']},
 {'id':'unknown-then-request','turns':['我还没入职，HR说要先参加收费培训才能安排工作。我不知道费用付给谁，也没拿到协议，你帮我分析一下。','我不知道更多情况，先生成有限报告吧。'],'expected':['ask','report']},
 {'id':'sufficient-contract','turns':['我是应届毕业生，还没入职、签字、付款或交证件。直接招聘我的A公司给了完整劳动合同草案，岗位为软件测试，月薪6500元。草案写公司保管毕业证原件到离职，我的毕业证仍在我手上；没有中介、培训或收费。请分析这个拟签条款。'],'expected':['report']}
]
if args.baseline:cases=cases[:1];cases[0]['turns']=cases[0]['turns'][:1];cases[0]['expected']=cases[0]['expected'][:1]
out=ROOT/'knowledge/evaluations'/args.phase;out.mkdir(parents=True,exist_ok=True);cfg=Settings.load()
def run(case):
 record={'case':case,'turns':[]};start=time.monotonic()
 try:
  with TestClient(create_app(cfg)) as c:
   sid=c.post('/api/sessions',json={'title':'追问行为测试 '+case['id']}).json()['id'];record['session_id']=sid
   for i,t in enumerate(case['turns']):
    r=c.post(f'/api/sessions/{sid}/messages',json={'text':t,'material_ids':[]});r.raise_for_status();body=r.json();record['turns'].append(body)
    print(json.dumps({'id':case['id'],'turn':i+1,'action':body['action'],'questions':body['questions'],'message':body['message']},ensure_ascii=False),flush=True)
   record['session']=c.get(f'/api/sessions/{sid}').json()
  record['actions_pass']=[t['action'] for t in record['turns']]==case['expected']
 except Exception as e:record['error']=str(e);record['actions_pass']=False
 record['elapsed_seconds']=round(time.monotonic()-start,1);(out/(case['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'id':case['id'],'actions_pass':record['actions_pass'],'error':record.get('error')},ensure_ascii=False),flush=True);return record
with ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(run,cases))
(out/'summary.json').write_text(json.dumps([{'id':r['case']['id'],'actions_pass':r['actions_pass'],'error':r.get('error')} for r in records],ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(0 if all(r['actions_pass'] for r in records) else 1)
