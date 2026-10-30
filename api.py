import sys,json,tempfile,threading,http.client
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,'/tmp/pr4-audit-1c9324b');import app
DATES=['due_date','planned_date','follow_up_date'];FIELDS=['owner','priority',*DATES]
with tempfile.TemporaryDirectory() as td:
 d=Path(td);s=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
 def req(payload,path='/api/tasks'):
  c=http.client.HTTPConnection('127.0.0.1',s.server_port,timeout=5)
  try:
   c.request('POST',path,json.dumps(payload),{'Content-Type':'application/json'});r=c.getresponse();return r.status,json.loads(r.read())
  finally:c.close()
 valid={'title':'虚构API任务','owner':'虚构负责人','priority':'high','due_date':'2028-02-29','planned_date':'2026-01-01','follow_up_date':'2026-12-31'};code,result=req(valid);assert code==201;tid=result['task_id'];path=f'/api/tasks/{tid}/update'
 def state():return next(x for x in app.read_workspace(d)['tasks'] if x['task_id']==tid)
 def snap():return {p.name:p.read_bytes() for p in (d/'events').glob('*.json')}
 invalid=[]
 for f in DATES:
  for value in ['2026-02-29','2026-02-30','2026-13-01','2026-2-03','2026-01-01T00:00:00Z','2026-W01-1','0000-01-01',42,{},True]:invalid.append({f:value})
 invalid += [{'owner':101*'中'},{'owner':123},{'owner':[]},{'priority':'critical'},{'priority':None},{'priority':[]},{'priority':{}}]
 before=snap()
 for fields in invalid:
  assert req({'title':'应拒绝',**fields})[0]==400,fields
  assert req({'title':valid['title'],'status':'todo','revision':1,**fields},path)[0]==400,fields
 assert snap()==before;print('PASS 37 invalid field cases x create/update =74 HTTP400; invalid calendars/types/format/owner/priority never write')
 # Explicit empty web date normalizes to null independently, omitted fields stay intact.
 for field in DATES:
  current=state();assert req({'title':valid['title'],'status':'todo','revision':current['revision'],field:''},path)[0]==200
  updated=state();assert updated[field] is None;assert all(updated[k]==current[k] for k in FIELDS if k!=field)
 current=state();assert req({'title':valid['title'],'status':'todo','revision':current['revision'],'owner':'   '},path)[0]==200;assert state()['owner'] is None and state()['priority']=='high'
 assert all((d/'events'/name).read_bytes()==raw for name,raw in before.items());print('PASS API independent empty-date clears store null, blank owner clears without resetting priority; initial JSON byte-identical')
 s.shutdown();s.server_close();t.join()
