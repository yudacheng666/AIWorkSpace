import sys,json,tempfile,threading,http.client,concurrent.futures
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr4-audit-1c9324b');import app
OUT=Path('/workspace/scratch/pr4-audit-1c9324b');DATES=['due_date','planned_date','follow_up_date'];META=['owner','priority',*DATES];P='PROJECT-'+'A'*32;M='PROJECT-'+'C'*32;R='PROJECT-'+'D'*32

def create(tid,**fields):return dict(version=1,event_id='create-'+tid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes=dict(title='虚构：'+tid,status='todo',**fields))
def snap(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*.json')}
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);legacy=app.append_event(d,create('TASK-LEGACY'));legacyraw=legacy.read_bytes();app.append_event(d,create('TASK-MISSING',project_id=M,related_project_ids=[R]));app.append_project_event(d,dict(version=1,event_id='project-known-001',project_id=P,action='create',actor='user',base_revision=0,changes={'name':'虚构项目'}))
 s=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));t=threading.Thread(target=s.serve_forever,daemon=True);t.start();port=s.server_port
 def req(path='/api/tasks',body=None):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
  try:
   c.request('GET' if body is None else 'POST',path,json.dumps(body,ensure_ascii=False).encode() if body is not None else None,{'Content-Type':'application/json','Host':f'localhost:{port}'});r=c.getresponse();return r.status,json.loads(r.read())
  finally:c.close()
 def state(tid):return next(x for x in req()[1]['tasks'] if x['task_id']==tid)
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);p=ctx.new_page();posts=[];errors=[]
 p.on('request',lambda r:posts.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None);p.on('pageerror',lambda e:errors.append(str(e)));p.goto(f'http://127.0.0.1:{port}');expect(p.locator('.task')).to_have_count(2)
 card=lambda tid:p.locator('.task').filter(has=p.locator('.task-id',has_text=tid))
 def editcontrols(tid):
  c=card(tid);inputs=c.locator('.edit-meta input');return {'owner':inputs.nth(0),'priority':c.locator('.edit-meta select'),**{f:inputs.nth(i+1) for i,f in enumerate(DATES)}}
 def setcontrol(c,k,v):c[k].select_option(v) if k=='priority' else c[k].fill(v)
 legacyfields=editcontrols('TASK-LEGACY');assert state('TASK-LEGACY')['owner'] is None and state('TASK-LEGACY')['priority']=='normal';assert all(state('TASK-LEGACY')[f] is None for f in DATES)
 card('TASK-LEGACY').locator('input').first.fill('虚构：只改旧任务标题');card('TASK-LEGACY').locator('button').click();expect(p.locator('#sync')).to_contain_text('保存成功');assert not (set(posts[-1]['body'])&set(META));assert legacy.read_bytes()==legacyraw
 print('PASS legacy defaults and title-only UI edit send no new metadata; original create bytes unchanged',flush=True)
 cids={'owner':'#new-task-owner','priority':'#new-task-priority','due_date':'#new-task-due','planned_date':'#new-task-planned','follow_up_date':'#new-task-follow'}
 p.locator('#new-task-title').fill('虚构：五字段任务');p.locator('#new-task-project').select_option(P)
 values={'owner':'虚构负责人甲','priority':'urgent','due_date':'2028-02-29','planned_date':'2026-11-01','follow_up_date':'2026-11-09'}
 for k,v in values.items():setcontrol({k:p.locator(cids[k])},k,v)
 p.locator('#create-submit').click();expect(p.locator('#create-message')).to_contain_text('创建成功');expect(p.locator('.task')).to_have_count(3);tid=next(x['task_id'] for x in req()[1]['tasks'] if x['title']=='虚构：五字段任务');assert all(state(tid)[k]==v for k,v in values.items());assert all(editcontrols(tid)[k].input_value()==v for k,v in values.items())
 for k in META:expect(p.locator(cids[k])).to_have_value('normal' if k=='priority' else '')
 p.screenshot(path=str(OUT/'01-five-fields-created.png'),full_page=True);print('PASS real Chromium five-field create, leap date, default reset after confirmed success, project preserved',flush=True)
 # Independently modify then clear each date, comparing every other metadata field.
 for i,field in enumerate(DATES):
  before=state(tid);new=f'2027-12-{i+1:02}';editcontrols(tid)[field].fill(new);card(tid).locator('button').click();expect(p.locator('#sync')).to_contain_text('保存成功');expect(editcontrols(tid)[field]).to_have_value(new);after=state(tid)
  assert after[field]==new and all(after[k]==before[k] for k in META if k!=field);assert after['project_id']==P;body=posts[-1]['body'];assert set(body)&set(META)=={field}
  editcontrols(tid)[field].fill('');card(tid).locator('button').click();expect(p.locator('#sync')).to_contain_text('保存成功');expect(editcontrols(tid)[field]).to_have_value('');after=state(tid);assert after[field] is None and all(after[k]==before[k] for k in META if k!=field);assert posts[-1]['body'][field] is None and set(posts[-1]['body'])&set(META)=={field}
  print('PASS independent date modify+clear:',field,'other metadata/project unchanged; POST only selected metadata key',flush=True)
 # Owner and priority can independently change/reset too.
 editcontrols(tid)['owner'].fill('');card(tid).locator('button').click();expect(p.locator('#sync')).to_contain_text('保存成功');assert state(tid)['owner'] is None and state(tid)['priority']=='urgent'
 editcontrols(tid)['priority'].select_option('normal');card(tid).locator('button').click();expect(p.locator('#sync')).to_contain_text('保存成功');assert state(tid)['priority']=='normal';p.screenshot(path=str(OUT/'02-cleared-independent.png'),full_page=True)
 # Missing project references survive date-only edits.
 editcontrols('TASK-MISSING')['follow_up_date'].fill('2026-12-20');card('TASK-MISSING').locator('button').click();expect(p.locator('#sync')).to_contain_text('保存成功');assert state('TASK-MISSING')['project_id']==M and state('TASK-MISSING')['related_project_ids']==[R];assert 'project_id' not in posts[-1]['body'] and 'related_project_ids' not in posts[-1]['body']
 print('PASS owner clear, priority reset, date-only edit preserves unsynced project refs',flush=True)
 # Delay actual publication; change full next draft while original request pending.
 entered=threading.Event();release=threading.Event();link=app.os.link
 def gate(a,z):entered.set();assert release.wait(12);return link(a,z)
 p.locator('#new-task-title').fill('虚构：异步任务甲')
 for k,v in values.items():setcontrol({k:p.locator(cids[k])},k,v)
 before=snap(d);beforeposts=len(posts)
 with patch.object(app.os,'link',gate):
  p.locator('#create-submit').click();assert entered.wait(3);expect(p.locator('#create-submit')).to_be_disabled();p.locator('#new-task-title').fill('虚构：异步任务乙草稿')
  nextvalues={'owner':'  虚构负责人乙  ','priority':'high','due_date':'2029-01-01','planned_date':'2029-02-02','follow_up_date':'2029-03-03'}
  for k,v in nextvalues.items():setcontrol({k:p.locator(cids[k])},k,v)
  p.locator('#create-task').evaluate('(f)=>f.dispatchEvent(new Event("submit",{cancelable:true,bubbles:true}))');release.set();expect(p.locator('#create-message')).to_contain_text('草稿已保留');expect(p.locator('#new-task-title')).to_have_value('虚构：异步任务乙草稿')
 assert all(p.locator(cids[k]).input_value()==v for k,v in nextvalues.items());assert len(posts)==beforeposts+1 and len(snap(d))==len(before)+1;created=next(x for x in req()[1]['tasks'] if x['title']=='虚构：异步任务甲');assert all(created[k]==v for k,v in values.items());assert not any(x['title']=='虚构：异步任务乙草稿' for x in req()[1]['tasks'])
 p.screenshot(path=str(OUT/'03-async-draft-preserved.png'),full_page=True);print('PASS delayed real save: original five fields persisted; next title/owner/priority/all dates retained verbatim; duplicate blocked; next draft not submitted',flush=True)
 # Also change only a metadata field, keeping the title unchanged.
 p.locator('#new-task-title').fill('虚构：仅元数据异步草稿');entered.clear();release.clear()
 with patch.object(app.os,'link',gate):
  p.locator('#create-submit').click();assert entered.wait(3);p.locator('#new-task-owner').fill('虚构：仅负责人已改');p.locator('#new-task-follow').fill('2030-04-05');release.set();expect(p.locator('#create-message')).to_contain_text('草稿已保留')
 expect(p.locator('#new-task-title')).to_have_value('虚构：仅元数据异步草稿');expect(p.locator('#new-task-owner')).to_have_value('虚构：仅负责人已改');expect(p.locator('#new-task-follow')).to_have_value('2030-04-05')
 before=snap(d)
 with patch.object(app.os,'link',side_effect=OSError('simulated disk full')):
  p.locator('#create-submit').click();expect(p.locator('#create-message')).to_contain_text('创建结果未确认')
 assert snap(d)==before;expect(p.locator('#new-task-owner')).to_have_value('虚构：仅负责人已改');expect(p.locator('#new-task-follow')).to_have_value('2030-04-05');p.screenshot(path=str(OUT/'04-failure-retains-metadata.png'),full_page=True);print('PASS metadata-only edits preserved on late success; disk error retains draft/no files',flush=True)
 # True simultaneous same-revision HTTP metadata edits.
 current=state(tid);revision=current['revision'];payload={'title':current['title'],'status':'todo','revision':revision}
 with concurrent.futures.ThreadPoolExecutor(8) as ex:results=list(ex.map(lambda i:req('/api/tasks/'+tid+'/update',{**payload,'due_date':f'2027-10-{i+1:02}'}),range(8)))
 assert sorted(x[0] for x in results)==[200]+[409]*7;assert state(tid)['due_date']==f'2027-10-{next(i for i,x in enumerate(results) if x[0]==200)+1:02}'
 print('PASS 8 concurrent metadata HTTP updates: exactly1x200,7x409; winner retained',flush=True)
 # Valid externally synced conflicting metadata events: freeze one task only.
 rev=state(tid)['revision'];candidatevalues=[{'owner':'虚构候选甲','priority':'high','due_date':None,'planned_date':'2026-12-01','follow_up_date':'2026-12-02'},{'owner':'虚构候选乙','priority':'urgent','due_date':'2026-12-03','planned_date':'2026-12-04','follow_up_date':'2026-12-05'}]
 for i,fields in enumerate(candidatevalues):app.append_event(d,dict(version=1,event_id=f'metadata-conflict-{i:03}',task_id=tid,action='update',actor='user',base_revision=rev,changes=fields))
 assert set(state(tid)['conflict_fields'])==set(META);before=snap(d);assert req('/api/tasks/'+tid+'/update',{**payload,'revision':rev})[0]==409;assert snap(d)==before
 p.reload();expect(card(tid).locator('button')).to_be_disabled();expect(card(tid).locator('.conflict-detail')).to_contain_text('截止日期候选');expect(card(tid).locator('.conflict-detail')).to_contain_text('未设置');expect(card('TASK-LEGACY').locator('button')).to_be_enabled();p.screenshot(path=str(OUT/'05-metadata-conflict.png'),full_page=True);assert req()[0]==200
 print('PASS all five metadata conflict candidates rendered, null shown unset, affected row frozen409, others readable',flush=True)
 assert legacy.read_bytes()==legacyraw and not errors,errors;assert all((d/name).read_bytes()==raw for name,raw in before.items());(OUT/'posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/'trace.zip'));ctx.close();b.close();s.shutdown();s.server_close();t.join()
