"""Run fixed simulated cases through actual API/RAG; content verdicts require human review."""
import argparse,json,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from reader.api import create_app
from reader.config import Settings

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--case',action='append');parser.add_argument('--output',default='knowledge/evaluations/fact-ledger-20261008');args=parser.parse_args()
 root=Path(__file__).resolve().parents[1];suite=json.loads((root/'knowledge/evaluations/content-regression-cases.json').read_text(encoding='utf-8'))['cases']
 if args.case:
  unknown=set(args.case)-{c['id'] for c in suite}
  if unknown:parser.error('Unknown cases: '+', '.join(sorted(unknown)))
  suite=[c for c in suite if c['id'] in args.case]
 out=(root/args.output).resolve();out.mkdir(parents=True,exist_ok=True)
 cfg=Settings.load()
 def run(case):
  start=time.monotonic();record={'case':case,'turns':[],'content_verdict':'pending_human_review'}
  try:
   with TestClient(create_app(cfg)) as client:
    response=client.post('/api/sessions',json={'title':'事实表固定测试 '+case['title']});response.raise_for_status();sid=response.json()['id'];record['session_id']=sid
    for i,text in enumerate(case['turns']):
     reply=client.post(f'/api/sessions/{sid}/messages',json={'text':text,'material_ids':[]})
     if reply.status_code!=200:raise RuntimeError(f'HTTP {reply.status_code}: '+str(reply.json().get('detail','请求失败')))
     body=reply.json();record['turns'].append(body)
     print(json.dumps({'case':case['id'],'turn':i+1,'action':body['action'],'review':(body.get('report') or {}).get('review_status',{}).get('status')},ensure_ascii=False),flush=True)
    record['session']=client.get(f'/api/sessions/{sid}').json();record['flow_completed']=True
  except Exception as exc:record['flow_completed']=False;record['error']=type(exc).__name__+': '+str(exc)
  record['elapsed_seconds']=round(time.monotonic()-start,1)
  (out/(case['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'case':case['id'],'flow_completed':record['flow_completed'],'error':record.get('error')},ensure_ascii=False),flush=True)
  return record
 with ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(run,suite))
 (out/'summary.json').write_text(json.dumps([{'id':r['case']['id'],'session_id':r.get('session_id'),'flow_completed':r['flow_completed'],'content_verdict':r['content_verdict'],'error':r.get('error')} for r in records],ensure_ascii=False,indent=2),encoding='utf-8')
 return 0 if all(r['flow_completed'] for r in records) else 1
if __name__=='__main__':raise SystemExit(main())
