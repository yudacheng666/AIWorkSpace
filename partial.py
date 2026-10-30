import sys,json,tempfile,threading,http.client,traceback
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr5-recheck-ce7ae42');import app
OUT=Path('/workspace/scratch/pr5-recheck-ce7ae42');T='TASK-PARTIAL';A='STEP-'+'A'*32;B='STEP-'+'B'*32;C='STEP-'+'C'*32

def step(sid,name,pos):return dict(version=1,event_id='create-'+sid,task_id=T,step_id=sid,actor='chatgpt',action='create',base_revision=0,changes={'title':name,'position':pos})
def snap(d):return {str(p.relative_to(d)):p.read_bytes() for p in d.rglob('*') if p.is_file()}
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);app.append_event(d,dict(version=1,event_id='parent-create-001',task_id=T,actor='chatgpt',action='create',base_revision=0,changes={'title':'虚构：部分同步复验'}));app.append_step_event(d,step(A,'虚构步骤甲',1));app.append_step_event(d,step(B,'虚构步骤乙',2));order=app.append_step_event(d,dict(version=1,event_id='original-order-001',task_id=T,actor='chatgpt',action='reorder',base_revision=0,changes={'step_ids':[A,C,B]}));orderraw=order.read_bytes()
 server=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();port=server.server_port
 def state():return app.read_workspace(d)['tasks'][0]
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);p=ctx.new_page();posts=[];p.on('request',lambda r:posts.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None)
 result={}
 try:
  p.goto(f'http://127.0.0.1:{port}');expect(p.locator('.step-row')).to_have_count(2);expect(p.locator('.step-order-warning')).to_contain_text('尚未同步');assert state()['step_order_incomplete'] and state()['step_order_missing_ids']==[C]
  for button in p.locator('.step-actions button').all():expect(button).to_be_disabled()
  for button in p.locator('.step-edit-form button').all():expect(button).to_be_enabled()
  before=snap(d);p.locator('.step-row').first.locator('.step-actions button').nth(1).dispatch_event('click');p.wait_for_timeout(100);assert not posts;assert snap(d)==before
  # Directly invoke the real callback as well as the disabled button's handler.
  p.evaluate('async()=>{const d=await(await fetch("/api/tasks")).json();await saveStepOrder(d.tasks[0],0,1,document.querySelector(".step-message"))}');assert not posts;assert snap(d)==before
  print('PASS A1/A2 actual Chromium: warning, only A/B visible, all reorder buttons disabled; synthetic handler/direct callback send zero POST; content edit enabled',flush=True)
  p.screenshot(path=str(OUT/'01-incomplete-protected.png'),full_page=True)
  conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5);conn.request('POST',f'/api/tasks/{T}/steps/reorder',json.dumps({'step_ids':[B,A],'revision':1}),{'Content-Type':'application/json'});response=conn.getresponse();body=json.loads(response.read());assert response.status==409;conn.close();assert snap(d)==before
  result['blocked_reorder']={'status':409,'body':body,'all_event_bytes_unchanged':True};print('PASS A3 direct reorder API409; complete file names and all bytes unchanged',flush=True)
  app.append_step_event(d,step(C,'虚构迟到步骤丙',3));p.reload();expect(p.locator('.step-row')).to_have_count(3);expect(p.locator('.step-order-warning')).to_have_count(0);assert [s['step_id'] for s in state()['steps']]==[A,C,B];assert not state()['step_order_incomplete'] and state()['step_order_missing_ids']==[];assert order.read_bytes()==orderraw
  p.screenshot(path=str(OUT/'02-original-order-restored.png'),full_page=True);print('PASS A4 C create arrives; original A,C,B order restored; missing-ID list empty; original reorder bytes intact',flush=True)
  prior=snap(d);p.locator('.step-row').first.locator('.step-actions button').nth(1).click();expect(p.locator('.step-id').nth(0)).to_have_text(C);assert [s['step_id'] for s in state()['steps']]==[C,A,B];after=snap(d);assert len(after)==len(prior)+1 and all(after[k]==v for k,v in prior.items());assert order.read_bytes()==orderraw
  result['after_sync']={'restored_order':[A,C,B],'new_order':[C,A,B],'post':posts[-1],'all_prior_event_bytes_unchanged':True};p.screenshot(path=str(OUT/'03-reorder-after-sync.png'),full_page=True);print('PASS A5 legitimate reorder appends exactly one event after sync, preserving all earlier bytes',flush=True)
  result['status']='PASS'
 except Exception:
  result['status']='FAIL';traceback.print_exc();p.screenshot(path=str(OUT/'failure.png'),full_page=True);raise
 finally:
  (OUT/'partial-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));(OUT/'partial-posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/'trace.zip'));ctx.close();b.close();server.shutdown();server.server_close();thread.join()
