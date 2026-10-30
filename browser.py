import sys,json,tempfile,threading,re,traceback
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr5-audit-4d9e25f');import app
OUT=Path('/workspace/scratch/pr5-audit-4d9e25f');A='STEP-'+'A'*32;B='STEP-'+'B'*32;C='STEP-'+'C'*32

def task(tid):return dict(version=1,event_id='create-'+tid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构：'+tid,'owner':'虚构负责人','priority':'high','due_date':'2026-12-31','planned_date':'2026-11-01','follow_up_date':'2026-11-02'})
def step(eid,sid,tid,title,pos):return dict(version=1,event_id=eid,step_id=sid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes={'title':title,'position':pos})
def snapshot(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*.json')}
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);app.append_event(d,task('TASK-BROWSER'));original=snapshot(d);s=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start();b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);p=ctx.new_page();posts=[]
 p.on('request',lambda r:posts.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None)
 def state(tid):return next(t for t in app.read_workspace(d)['tasks'] if t['task_id']==tid)
 def card(tid):return p.locator('.task').filter(has=p.locator('.task-id',has_text=tid))
 failed=False
 try:
  p.goto(f'http://127.0.0.1:{s.server_port}');expect(card('TASK-BROWSER').locator('.step-empty')).to_be_visible();print('PASS old task with no steps shows empty list, no migration',flush=True)
  parent=state('TASK-BROWSER');meta={k:parent[k] for k in ['revision','owner','priority','due_date','planned_date','follow_up_date']}
  for i in range(3):
   c=card('TASK-BROWSER');c.locator('.step-add-form input').fill(f'虚构步骤{i+1}');c.locator('.step-add-form button').click();expect(c.locator('.step-row')).to_have_count(i+1)
  ids=[x['step_id'] for x in state('TASK-BROWSER')['steps']];assert all(re.fullmatch('STEP-[A-F0-9]{32}',x) for x in ids);assert [x['title'] for x in state('TASK-BROWSER')['steps']]==['虚构步骤1','虚构步骤2','虚构步骤3'];assert card('TASK-BROWSER').locator('.step-number').all_text_contents()==['1.','2.','3.']
  p.screenshot(path=str(OUT/'01-created-steps.png'),full_page=True);before=state('TASK-BROWSER');rows=card('TASK-BROWSER').locator('.step-row');rows.nth(0).locator('.step-edit-form input').fill('虚构步骤1-已编辑');rows.nth(0).locator('.step-edit-form select').select_option('doing');rows.nth(0).locator('.step-edit-form button').click();expect(rows.nth(0).locator('.step-edit-form input')).to_have_value('虚构步骤1-已编辑');expect(rows.nth(0).locator('.step-edit-form button')).to_be_enabled()
  after=state('TASK-BROWSER');assert all(after[k]==v for k,v in meta.items());assert after['steps'][1:]==before['steps'][1:];assert after['steps'][0]['revision']==2
  print('PASS real Chromium stable IDs, numbering/create order, isolated title/status edit; parent revision, other steps and five fields unchanged',flush=True)
  # Both direction buttons followed by reload; ID order stays stable.
  rows.nth(0).locator('.step-actions button').nth(1).click();expect(card('TASK-BROWSER').locator('.step-id').nth(0)).to_have_text(ids[1]);rows.nth(1).locator('.step-actions button').nth(0).click();expect(card('TASK-BROWSER').locator('.step-id').nth(0)).to_have_text(ids[0]);p.reload();expect(card('TASK-BROWSER').locator('.step-id').nth(0)).to_have_text(ids[0])
  print('PASS up/down reorder and reload preserve IDs/order',flush=True)
  rows=card('TASK-BROWSER').locator('.step-row');before=snapshot(d);rows.nth(0).locator('select').select_option('done');p.once('dialog',lambda dialog:dialog.dismiss());rows.nth(0).locator('.step-edit-form button').click();assert snapshot(d)==before and state('TASK-BROWSER')['steps'][0]['status']=='doing'
  p.once('dialog',lambda dialog:dialog.accept());rows.nth(0).locator('.step-edit-form button').click();expect(rows.nth(0).locator('select')).to_have_value('done');expect(rows.nth(0).locator('.step-edit-form button')).to_be_enabled();assert state('TASK-BROWSER')['steps'][0]['status']=='done'
  bad=dict(version=1,event_id='ai-complete-001',task_id='TASK-BROWSER',step_id=ids[1],action='update',actor='chatgpt',base_revision=1,changes={'status':'done'},confirmed_done=True)
  try:app.validate_step_event(bad);raise AssertionError('AI completion accepted')
  except ValueError:pass
  assert all((d/n).read_bytes()==v for n,v in original.items());p.screenshot(path=str(OUT/'02-edit-order-completion.png'),full_page=True);print('PASS completion confirm cancel=no event, confirm=done; ChatGPT actor rejected by event validator; original history intact',flush=True)
  # Special requirement: reorder records arrive before one of their member create files.
  app.append_event(d,task('TASK-PARTIAL'));app.append_step_event(d,step('partial-create-001',A,'TASK-PARTIAL','虚构可见步骤甲',1));app.append_step_event(d,step('partial-create-002',B,'TASK-PARTIAL','虚构可见步骤乙',2))
  order=dict(version=1,event_id='partial-order-001',task_id='TASK-PARTIAL',action='reorder',actor='chatgpt',base_revision=0,changes={'step_ids':[A,C,B]});orderpath=app.append_step_event(d,order);orderraw=orderpath.read_bytes();before=snapshot(d)
  p.reload();expect(card('TASK-PARTIAL').locator('.step-row')).to_have_count(2);assert state('TASK-PARTIAL')['step_order_revision']==1
  p.screenshot(path=str(OUT/'03-partial-sync-before.png'),full_page=True);card('TASK-PARTIAL').locator('.step-row').nth(0).locator('.step-actions button').nth(1).click();expect(card('TASK-PARTIAL').locator('.step-id').nth(0)).to_have_text(B)
  newfiles=[f for f in (d/'step_events').glob('*.json') if str(f.relative_to(d)) not in before];assert len(newfiles)==1;newrecord=json.loads(newfiles[0].read_bytes());assert newrecord['action']=='reorder';assert orderpath.read_bytes()==orderraw
  p.screenshot(path=str(OUT/'04-partial-sync-after.png'),full_page=True)
  details={'fixed_sha':'4d9e25f94195ce6f0c7964a253d4965ea7d0dc85','original_order_event':order,'new_order_event':newrecord,'post':posts[-1],'visible_steps':[x['step_id'] for x in state('TASK-PARTIAL')['steps']],'hidden_step_id':C,'original_event_byte_preserved':True}
  (OUT/'failure.json').write_text(json.dumps(details,ensure_ascii=False,indent=2))
  if C not in newrecord['changes']['step_ids']:
   failed=True;print('FAIL P2 partial sync reorder: original [A,C,B], C create missing; browser reordered visible rows and POST succeeded with [B,A], new full-order record drops C silently. Original order bytes remain intact.',flush=True)
  else:print('PASS partial reorder retains hidden member',flush=True)
 except Exception:
  failed=True;traceback.print_exc();p.screenshot(path=str(OUT/'unexpected-failure.png'),full_page=True)
 finally:
  (OUT/'posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/'trace.zip'));ctx.close();b.close();s.shutdown();s.server_close();thread.join()
 if failed:sys.exit(1)
