import sys,json,tempfile,threading,http.client,concurrent.futures,traceback
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr5-final-633b530');import app
OUT=Path('/workspace/scratch/pr5-final-633b530')
def sid(n):return f'STEP-{n:032X}'
def parent(tid):return dict(version=1,event_id='parent-'+tid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构：'+tid})
def create(tid,n,pos):return dict(version=1,event_id='step-create-'+str(n),task_id=tid,step_id=sid(n),action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构步骤'+str(n),'position':pos})
def order(tid,eid,ids):return dict(version=1,event_id=eid,task_id=tid,action='reorder',actor='chatgpt',base_revision=0,changes={'step_ids':ids})
def snap(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*') if f.is_file()}
with tempfile.TemporaryDirectory() as td:
 d=Path(td)
 for tid,nums in [('TASK-CONCURRENT',[1,2]),('TASK-CONTENT',[11,12]),('TASK-ORDER',[21,22]),('TASK-PARENT',[31,32]),('TASK-INVALID',[41,42])]:
  app.append_event(d,parent(tid))
  for pos,n in enumerate(nums,1):app.append_step_event(d,create(tid,n,pos))
 app.append_event(d,parent('TASK-LIMIT'))
 for n in range(1,100):app.append_step_event(d,create('TASK-LIMIT',1000+n,n))
 initial=snap(d);server=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();port=server.server_port;records=[];recordlock=threading.Lock();stage='start'
 def req(path,body=None,host=None,origin=None):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=12);h={'Content-Type':'application/json','Host':host or f'127.0.0.1:{port}'}
  if origin:h['Origin']=origin
  try:
   c.request('GET' if body is None else 'POST',path,json.dumps(body,ensure_ascii=False).encode() if body is not None else None,h);r=c.getresponse();code=r.status;answer=json.loads(r.read())
   with recordlock:records.append({'path':path,'request':body,'headers':h,'status':code,'response':answer})
   return code,answer
  finally:c.close()
 def task(tid):return next(t for t in app.read_workspace(d)['tasks'] if t['task_id']==tid)
 def updatepath(tid,n):return f'/api/tasks/{tid}/steps/{sid(n)}/update'
 try:
  stage='concurrent step and stale revision';before=snap(d);path=updatepath('TASK-CONCURRENT',1)
  with concurrent.futures.ThreadPoolExecutor(8) as ex:result=list(ex.map(lambda i:req(path,{'title':f'虚构并发胜出{i}','revision':1}),range(8)))
  assert sorted(c for c,_ in result)==[200]+[409]*7;win=next(i for i,x in enumerate(result) if x[0]==200);current=task('TASK-CONCURRENT');assert current['steps'][0]['title']==f'虚构并发胜出{win}' and current['steps'][0]['revision']==2
  after=snap(d);assert len(after)==len(before)+1 and all(after[n]==v for n,v in before.items());before=after;assert req(path,{'title':'虚构旧revision不覆盖','revision':1})[0]==409 and snap(d)==before
  print('PASS step concurrency:8 writers=1x200/7x409; winner exact, one appended event, all old bytes intact; explicit stale409/no writes',flush=True)
  stage='concurrent order revision';before=snap(d)
  with concurrent.futures.ThreadPoolExecutor(8) as ex:result=list(ex.map(lambda _:req('/api/tasks/TASK-CONCURRENT/steps/reorder',{'step_ids':[sid(2),sid(1)],'revision':0}),range(8)))
  assert sorted(c for c,_ in result)==[200]+[409]*7;assert task('TASK-CONCURRENT')['step_order_revision']==1;after=snap(d);assert len(after)==len(before)+1 and all(after[n]==v for n,v in before.items())
  print('PASS order concurrency:8 same-revision requests=1x200/7x409; one appended order, no overwrite',flush=True)
  stage='content conflict isolation'
  for n,title in [(1,'虚构候选甲'),(2,'虚构候选乙')]:app.append_step_event(d,dict(version=1,event_id=f'content-conflict-{n}',task_id='TASK-CONTENT',step_id=sid(11),action='update',actor='user',base_revision=1,changes={'title':title}))
  state=task('TASK-CONTENT');assert state['steps'][0]['conflict'] and not state['steps'][1]['conflict'] and not state['step_order_conflict'];before=snap(d);assert req(updatepath('TASK-CONTENT',11),{'title':'被拒绝','revision':1})[0]==409 and snap(d)==before
  assert req(updatepath('TASK-CONTENT',12),{'title':'虚构兄弟步骤可编辑','revision':1})[0]==200;assert req('/api/tasks/TASK-CONTENT/steps/reorder',{'step_ids':[sid(12),sid(11)],'revision':0})[0]==200
  print('PASS content conflict freezes only affected step409; sibling edit200 and ordering200 remain available',flush=True)
  stage='distinct-ID same-revision order conflict';app.append_step_event(d,order('TASK-ORDER','order-conflict-one',[sid(21),sid(22)]));app.append_step_event(d,order('TASK-ORDER','order-conflict-two',[sid(22),sid(21)]));assert task('TASK-ORDER')['step_order_conflict'];before=snap(d);assert req('/api/tasks/TASK-ORDER/steps/reorder',{'step_ids':[sid(22),sid(21)],'revision':0})[0]==409 and snap(d)==before;assert req(updatepath('TASK-ORDER',21),{'status':'doing','revision':1})[0]==200
  print('PASS distinct IDs at same order revision freeze only reorder409/no writes; step content update200',flush=True)
  stage='100-step limit and racing last slot';before=snap(d)
  with concurrent.futures.ThreadPoolExecutor(8) as ex:result=list(ex.map(lambda i:req('/api/tasks/TASK-LIMIT/steps',{'title':str(i)+'中'*199}),range(8)))
  assert sorted(c for c,_ in result)==[201]+[409]*7;assert len(task('TASK-LIMIT')['steps'])==100;after=snap(d);assert len(after)==len(before)+1 and all(after[n]==v for n,v in before.items());before=after;assert req('/api/tasks/TASK-LIMIT/steps',{'title':'虚构第101步'})[0]==409 and snap(d)==before
  print('PASS 99->100 last-slot race:1x201/7x409; 200-character title accepted; step101 rejected409, no files changed',flush=True)
  stage='invalid titles/status/IDs/order members';before=snap(d);rejects=0
  for title in ['', '   ', '中'*201, None,17,[],{}]:
   for path,payload in [('/api/tasks/TASK-INVALID/steps',{'title':title}),(updatepath('TASK-INVALID',41),{'title':title,'revision':1})]:assert req(path,payload)[0]==400;(rejects:=rejects+1)
  for status in ['invalid','Done',None,[],{},12]:assert req(updatepath('TASK-INVALID',41),{'status':status,'revision':1})[0]==400;(rejects:=rejects+1)
  for payload in [{'title':'不能冒充','step_id':sid(50)},{'title':'不能冒充','actor':'user'}]:assert req('/api/tasks/TASK-INVALID/steps',payload)[0]==400;(rejects:=rejects+1)
  for bad in ['STEP-bad','STEP-'+'a'*32,'../../outside']:
   assert req('/api/tasks/TASK-INVALID/steps/'+bad+'/update',{'title':'不应写入','revision':1})[0]==404;(rejects:=rejects+1)
  for members in [[],[sid(41)],[sid(41),sid(41)],[sid(41),sid(42),sid(99)],[sid(41),sid(99)],[sid(41),sid(31)],['BAD',sid(42)],None,list(range(101))]:assert req('/api/tasks/TASK-INVALID/steps/reorder',{'step_ids':members,'revision':0})[0]==400;(rejects:=rejects+1)
  assert snap(d)==before;assert req('/api/tasks/TASK-INVALID/steps',{'title':'界'})[0]==201
  print(f'PASS {rejects} invalid title/status/spoofed/malformed ID/order-member requests rejected400/404; no writes; 1-character title accepted',flush=True)
  stage='Host Origin local security';current=task('TASK-INVALID');ids=[x['step_id'] for x in current['steps']];paths=[('/api/tasks/TASK-INVALID/steps',{'title':'虚构安全拒写'}),(updatepath('TASK-INVALID',41),{'title':'虚构安全拒写','revision':1}),('/api/tasks/TASK-INVALID/steps/reorder',{'step_ids':list(reversed(ids)),'revision':0})];before=snap(d);denied=0
  for path,payload in paths:
   for host in ['attacker.example',f'localhost:{port}.evil.example',f'localhost.evil.example:{port}']:assert req(path,payload,host=host)[0]==403;denied+=1
   for origin in ['https://evil.example',f'http://localhost:{port+1}']:assert req(path,payload,origin=origin)[0]==403;denied+=1
  assert req('/api/tasks',host='attacker.example')[0]==403;assert req('/api/tasks',origin='https://evil.example')[0]==403;assert snap(d)==before
  assert req('/api/tasks',host=f'localhost:{port}',origin=f'http://localhost:{port}')[0]==200
  assert req(updatepath('TASK-INVALID',41),{'title':'虚构合法同源保存','revision':1},host=f'localhost:{port}',origin=f'http://localhost:{port}')[0]==200
  print(f'PASS Host/Origin:{denied} malicious create/update/reorder POSTs403 plus GET checks403, no writes; exact localhost origin GET/edit200',flush=True)
  stage='parent task conflict'
  for n,title in [(1,'虚构父候选甲'),(2,'虚构父候选乙')]:app.append_event(d,dict(version=1,event_id=f'parent-conflict-{n}',task_id='TASK-PARENT',action='update',actor='user',base_revision=1,changes={'title':title}))
  assert task('TASK-PARENT')['conflict'];before=snap(d)
  for path,payload in [('/api/tasks/TASK-PARENT/steps',{'title':'禁止新增'}),(updatepath('TASK-PARENT',31),{'title':'禁止改名','revision':1}),('/api/tasks/TASK-PARENT/steps/reorder',{'step_ids':[sid(32),sid(31)],'revision':0})]:assert req(path,payload)[0]==409
  assert snap(d)==before;print('PASS conflicted parent blocks child create/update/reorder409; every event byte unchanged',flush=True)
  stage='targeted browser conflict and limit evidence'
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1440,'height':1200},locale='zh-CN');p.goto(f'http://127.0.0.1:{port}')
   def card(tid):return p.locator('.task').filter(has=p.locator('.task-id',has_text=tid))
   oc=card('TASK-ORDER');expect(oc.locator('.step-order-warning')).to_be_visible()
   for button in oc.locator('.step-actions button').all():expect(button).to_be_disabled()
   for button in oc.locator('.step-edit-form button').all():expect(button).to_be_enabled()
   oc.screenshot(path=str(OUT/'04-distinct-order-conflict.png'))
   parentcard=card('TASK-PARENT')
   for button in parentcard.locator('.step-edit-form button,.step-actions button,.step-add-form button').all():expect(button).to_be_disabled()
   parentcard.screenshot(path=str(OUT/'05-parent-conflict.png'));limit=card('TASK-LIMIT');expect(limit.locator('.step-row')).to_have_count(100);expect(limit.locator('.step-add-form button')).to_be_disabled();limit.locator('.steps-head').screenshot(path=str(OUT/'06-hundred-step-counter.png'));limit.locator('.step-add-form').scroll_into_view_if_needed();p.screenshot(path=str(OUT/'07-hundred-step-blocked.png'))
   b.close()
  assert all((d/n).read_bytes()==v for n,v in initial.items());print('PASS real Chromium: order-only freeze, parent child-controls freeze, 100-step add disabled; all initial files intact',flush=True)
  (OUT/'remaining-result.json').write_text(json.dumps({'status':'PASS','invalid_rejections':rejects,'security_post_rejections':denied,'http_requests':len(records)},indent=2))
 except Exception:
  traceback.print_exc();(OUT/'remaining-result.json').write_text(json.dumps({'status':'FAIL','stage':stage,'http_requests':len(records)},indent=2));raise
 finally:
  (OUT/'api-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));server.shutdown();server.server_close();thread.join()
