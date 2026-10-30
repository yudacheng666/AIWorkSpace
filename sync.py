import sys,json,tempfile,threading,traceback
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr5-recheck-ce7ae42');import app
OUT=Path('/workspace/scratch/pr5-recheck-ce7ae42');T='TASK-SYNC';A='STEP-'+'A'*32;B='STEP-'+'B'*32

def parent():return dict(version=1,event_id='parent-create-001',task_id=T,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构：重复事件专项'})
def create(sid=A,pos=1):return dict(version=1,event_id='create-'+sid,task_id=T,step_id=sid,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构步骤'+str(pos),'position':pos})
def update(rev=1,title='虚构变更'):return dict(version=1,event_id='step-update-001',task_id=T,step_id=A,action='update',actor='chatgpt',base_revision=rev,changes={'title':title})
def reorder(rev=0,ids=None):return dict(version=1,event_id='order-event-001',task_id=T,action='reorder',actor='chatgpt',base_revision=rev,changes={'step_ids':ids or [A,B]})
def setup(d):app.append_event(d,parent());app.append_step_event(d,create());app.append_step_event(d,create(B,2))
def task(d):return app.read_workspace(d)['tasks'][0]
def snap(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*') if f.is_file()}
with tempfile.TemporaryDirectory() as td:
 d=Path(td);app.append_step_event(d,create());assert app.read_workspace(d)['tasks']==[] and app.read_workspace(d)['warnings'];app.append_event(d,parent());assert task(d)['steps'][0]['step_id']==A;print('PASS B sync: step create before parent warns, parent arrival reconstructs without rewriting',flush=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);app.append_event(d,parent());app.append_step_event(d,update());assert task(d)['steps']==[];app.append_step_event(d,create());assert task(d)['steps'][0]['title']=='虚构变更' and task(d)['steps'][0]['revision']==2;print('PASS B sync: step update before create recovers title/revision after create arrives',flush=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);app.append_event(d,parent());app.append_step_event(d,reorder(ids=[B,A]));assert task(d)['step_order_incomplete'];app.append_step_event(d,create());app.append_step_event(d,create(B,2));assert [s['step_id'] for s in task(d)['steps']]==[B,A] and not task(d)['step_order_incomplete'];print('PASS B sync: reorder before all step creation events reconstructs B,A',flush=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);setup(d);second=reorder(1,[B,A]);second['event_id']='order-event-002';app.append_step_event(d,second);assert task(d)['step_order_conflict'];app.append_step_event(d,reorder());assert not task(d)['step_order_conflict'] and task(d)['step_order_revision']==2 and [s['step_id'] for s in task(d)['steps']]==[B,A];print('PASS B sync: later order revision arriving first freezes, fills gap then reconstructs chain',flush=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);setup(d);(d/'step_events'/'copy-create.json').write_text(json.dumps(create()));app.append_step_event(d,reorder());(d/'step_events'/'copy-order.json').write_text(json.dumps(reorder()));before=snap(d);assert len(task(d)['steps'])==2 and not task(d)['steps'][0]['conflict'] and not task(d)['step_order_conflict'];assert app.read_workspace(d)['warnings'];assert snap(d)==before;print('PASS B duplicate identical create/reorder event IDs: ignored with warnings, no extra revisions or file changes',flush=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);setup(d);app.append_step_event(d,update());(d/'step_events'/'duplicate-update.json').write_text(json.dumps(update(rev=2,title='虚构不同内容')));assert next(s for s in task(d)['steps'] if s['step_id']==A)['conflict'];assert not next(s for s in task(d)['steps'] if s['step_id']==B)['conflict'];print('PASS B duplicate step-update ID across revisions with different content: only affected step frozen',flush=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);setup(d);app.append_step_event(d,reorder());(d/'step_events'/'duplicate-order.json').write_text(json.dumps(reorder(ids=[B,A])));assert task(d)['step_order_conflict'];assert not any(s['conflict'] for s in task(d)['steps']);print('PASS B duplicate order ID same base revision with different content freezes order only',flush=True)
# Same event_id with conflicting content must be an identity conflict even if bases differ.
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);setup(d);first=reorder();second=reorder(1,[B,A]);app.append_step_event(d,first);(d/'step_events'/'z-duplicate-order.json').write_text(json.dumps(second));before=snap(d);state=app.read_workspace(d);current=state['tasks'][0]
 if not current['step_order_conflict']:
  (OUT/'duplicate-failure.json').write_text(json.dumps({'original_event':first,'conflicting_same_id_event':second,'workspace':state,'all_event_bytes_unchanged':snap(d)==before},ensure_ascii=False,indent=2))
  s=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));t=threading.Thread(target=s.serve_forever,daemon=True);t.start();b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1440,'height':1200},locale='zh-CN');p.goto(f'http://127.0.0.1:{s.server_port}');expect(p.locator('.step-row')).to_have_count(2);expect(p.locator('.step-row').first.locator('.step-actions button').nth(1)).to_be_enabled();p.screenshot(path=str(OUT/'04-duplicate-order-not-frozen.png'),full_page=True);b.close();s.shutdown();s.server_close();t.join()
  print('FAIL P2: same reorder event_id has different content/base_revision0+1; reducer applies both as valid chain (revision2), step_order_conflict=false; browser reorder remains enabled despite duplicate-content warning. No further mutation performed; stopping.',flush=True);sys.exit(1)
 print('PASS B duplicate order identity conflict across different revisions frozen',flush=True)
