import sys,json,tempfile,threading,http.client,traceback
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr5-final-633b530');import app
OUT=Path('/workspace/scratch/pr5-final-633b530');T='TASK-IDENTITY';A='STEP-'+'A'*32;B='STEP-'+'B'*32

def parent(tid):return dict(version=1,event_id='parent-'+tid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构：'+tid})
def step(tid,sid,pos):return dict(version=1,event_id='create-'+sid,task_id=tid,step_id=sid,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构步骤'+str(pos),'position':pos})
def order(tid,eid,rev,ids):return dict(version=1,event_id=eid,task_id=tid,action='reorder',actor='chatgpt',base_revision=rev,changes={'step_ids':ids})
def snap(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*') if f.is_file()}
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);app.append_event(d,parent(T));app.append_step_event(d,step(T,A,1));app.append_step_event(d,step(T,B,2));first=order(T,'order-duplicate-001',0,[A,B]);second=order(T,'order-duplicate-001',1,[B,A]);app.append_step_event(d,first);(d/'step_events'/'z-duplicate.json').write_text(json.dumps(second));state=app.read_workspace(d)['tasks'][0]
 s=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start();port=s.server_port
 def req(path,body=None):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
  try:c.request('GET' if body is None else 'POST',path,json.dumps(body) if body is not None else None,{'Content-Type':'application/json'});r=c.getresponse();return r.status,json.loads(r.read())
  finally:c.close()
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);p=ctx.new_page();posts=[];p.on('request',lambda r:posts.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None)
 result={}
 try:
  assert state['step_order_conflict'] and state['step_order_revision']==0 and len(state['step_order_candidates'])==2
  assert {json.dumps(c['changes'],sort_keys=True) for c in state['step_order_candidates']}=={json.dumps(e['changes'],sort_keys=True) for e in [first,second]}
  before=snap(d);code,body=req(f'/api/tasks/{T}/steps/reorder',{'step_ids':[B,A],'revision':0});assert code==409 and snap(d)==before
  result['identity_conflict']={'order_revision':state['step_order_revision'],'conflict':True,'candidates':state['step_order_candidates'],'api_status':code,'all_files_byte_identical':True};print('PASS 1/2 cross-revision same ID different content: frozen at revision0, both candidates retained; reorder409; complete file names/bytes unchanged',flush=True)
  p.goto(f'http://127.0.0.1:{port}');expect(p.locator('.step-order-warning')).to_contain_text('顺序存在冲突')
  for button in p.locator('.step-actions button').all():expect(button).to_be_disabled()
  for button in p.locator('.step-edit-form button').all():expect(button).to_be_enabled()
  p.screenshot(path=str(OUT/'01-identity-order-frozen.png'),full_page=True);prior=snap(d);p.locator('.step-row').first.locator('.step-edit-form input').fill('虚构：冻结排序仍能改内容');p.locator('.step-row').first.locator('.step-edit-form button').click();expect(p.locator('.step-row').first.locator('.step-edit-form button')).to_be_enabled();current=app.read_workspace(d)['tasks'][0];assert current['steps'][0]['title']=='虚构：冻结排序仍能改内容' and current['steps'][0]['revision']==2 and current['revision']==1 and current['step_order_conflict'];after=snap(d);assert len(after)==len(prior)+1 and all(after[n]==v for n,v in prior.items());p.screenshot(path=str(OUT/'02-content-edit-during-order-conflict.png'),full_page=True)
  print('PASS 3 real Chromium order controls disabled, candidates visible, step title independently saved; parent revision and prior event bytes untouched',flush=True)
  # Distinct IDs form a valid revision chain and must not be frozen.
  NT='TASK-NORMAL';C='STEP-'+'C'*32;D='STEP-'+'D'*32;app.append_event(d,parent(NT));app.append_step_event(d,step(NT,C,1));app.append_step_event(d,step(NT,D,2));app.append_step_event(d,order(NT,'order-unique-001',0,[C,D]));app.append_step_event(d,order(NT,'order-unique-002',1,[D,C]));normal=next(t for t in app.read_workspace(d)['tasks'] if t['task_id']==NT);assert normal['step_order_revision']==2 and not normal['step_order_conflict'] and [x['step_id'] for x in normal['steps']]==[D,C]
  before=snap(d);code,body=req(f'/api/tasks/{NT}/steps/reorder',{'step_ids':[C,D],'revision':2});assert code==200 and body['saved'];after=snap(d);assert len(after)==len(before)+1 and all(after[n]==v for n,v in before.items());p.reload();normalcard=p.locator('.task').filter(has=p.locator('.task-id',has_text=NT));expect(normalcard.locator('.step-id').first).to_have_text(C);expect(normalcard.locator('.step-row').first.locator('.step-actions button').nth(1)).to_be_enabled();p.screenshot(path=str(OUT/'03-distinct-ids-order-normal.png'),full_page=True)
  result['distinct_ids']={'initial_valid_revision':2,'next_reorder_status':200,'all_prior_bytes_preserved':True};print('PASS 4 distinct event IDs legal sequential revisions applied; next reorder200 appends1, controls available, no over-freeze',flush=True)
  result['status']='PASS'
 except Exception:
  result['status']='FAIL';traceback.print_exc();p.screenshot(path=str(OUT/'failure-identity.png'),full_page=True);raise
 finally:
  (OUT/'identity-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));(OUT/'identity-posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/'trace.zip'));ctx.close();b.close();s.shutdown();s.server_close();thread.join()
