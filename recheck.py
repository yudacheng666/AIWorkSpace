import sys,tempfile,json,threading,http.client
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr3-recheck-aaf89a7');import app
OUT=Path('/workspace/scratch/pr3-recheck-aaf89a7');P='PROJECT-'+'A'*32;M='PROJECT-'+'C'*32;R='PROJECT-'+'D'*32;U='PROJECT-'+'E'*32

def task(tid,**extra):return dict(version=1,event_id='create-'+tid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes=dict(title='虚构：'+tid,status='todo',**extra))
def snap(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*.json')}
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);app.append_project_event(d,dict(version=1,event_id='project-create-001',project_id=P,action='create',actor='user',base_revision=0,changes={'name':'虚构正常项目'}))
 app.append_event(d,task('TASK-CONFLICT'));app.append_event(d,task('TASK-UNAFFECTED'));app.append_event(d,task('TASK-MISSING',project_id=M,related_project_ids=[R]));original=snap(d)
 for n,related in [(1,[]),(2,[P])]:app.append_event(d,dict(version=1,event_id=f'conflict-update-{n:03}',task_id='TASK-CONFLICT',action='update',actor='user',base_revision=1,changes={'related_project_ids':related}))
 server=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();port=server.server_port
 def request(path,body=None):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
  try:
   c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,{'Content-Type':'application/json','Host':f'localhost:{port}'});r=c.getresponse();return r.status,json.loads(r.read())
  finally:c.close()
 code,state=request('/api/tasks');assert code==200;tasks={t['task_id']:t for t in state['tasks']};assert tasks['TASK-CONFLICT']['conflict'];assert 'related_project_ids' in tasks['TASK-CONFLICT']['conflict_fields'];assert len(tasks['TASK-CONFLICT']['conflict_candidates'])==2;assert not tasks['TASK-UNAFFECTED']['conflict']
 before=snap(d);assert request('/api/tasks/TASK-CONFLICT/update',{'title':'不应写入','status':'todo','revision':1})[0]==409;assert snap(d)==before
 assert request('/api/projects',{'name':'虚构：冲突时仍能新建项目'})[0]==201
 assert request('/api/tasks/TASK-UNAFFECTED/update',{'title':'虚构：正常任务仍可编辑','status':'doing','revision':1})[0]==200
 print('PASS P2-1 original arrays[]/[P]: workspace GET200, conflict candidates exposed, affected task409/no writes, unrelated task editable and new project201',flush=True)
 # Duplicate event_id with list variants must also freeze rather than fail globally.
 app.append_event(d,task('TASK-DUPLICATE'))
 ev=dict(version=1,event_id='duplicate-list-001',task_id='TASK-DUPLICATE',action='update',actor='user',base_revision=1,changes={'related_project_ids':[]});app.append_event(d,ev);variant={**ev,'changes':{'related_project_ids':[P]}};(d/'events'/'z-duplicate.json').write_text(json.dumps(variant))
 code,state=request('/api/tasks');assert code==200 and next(t for t in state['tasks'] if t['task_id']=='TASK-DUPLICATE')['conflict']
 print('PASS P2-1 duplicate event ID with differing arrays also returns GET200 and freezes task',flush=True)
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);page=ctx.new_page();posts=[];errors=[]
 page.on('request',lambda r:posts.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{port}')
 card=lambda tid:page.locator('.task').filter(has=page.locator('.task-id',has_text=tid))
 expect(page.locator('.task')).to_have_count(4);expect(card('TASK-CONFLICT').locator('button')).to_be_disabled();expect(card('TASK-UNAFFECTED').locator('button')).to_be_enabled();expect(page.locator('#sync')).not_to_contain_text('读取失败');page.screenshot(path=str(OUT/'01-conflict-isolated.png'),full_page=True)
 print('PASS real Chromium shows all four tasks, only conflict rows frozen, no global read error',flush=True)
 missing=card('TASK-MISSING');expect(missing.locator('select').nth(1)).to_have_value(M);expect(missing.locator('select').nth(2)).to_have_values([R]);page.screenshot(path=str(OUT/'02-missing-before-edit.png'),full_page=True)
 missing.locator('input').fill('虚构：只改标题，引用必须保留');missing.locator('button').click();expect(page.locator('#sync')).to_contain_text('保存成功');expect(missing.locator('select').nth(1)).to_have_value(M);expect(missing.locator('select').nth(2)).to_have_values([R]);body=posts[-1]['body'];assert 'project_id' not in body and 'related_project_ids' not in body
 current=next(t for t in request('/api/tasks')[1]['tasks'] if t['task_id']=='TASK-MISSING');assert current['project_id']==M and current['related_project_ids']==[R];page.screenshot(path=str(OUT/'03-missing-after-title.png'),full_page=True)
 print('PASS P2-2 real Chromium title-only edit omits project fields; primary and related placeholders/IDs preserved in DOM and reducer',flush=True)
 # API legacy clients can redundantly send unchanged references too.
 assert request('/api/tasks/TASK-MISSING/update',{'title':'虚构：重复提交旧引用仍保留','status':'doing','revision':current['revision'],'project_id':M,'related_project_ids':[R]})[0]==200
 # Reject unknown new references while preserving original missing IDs.
 current=next(t for t in request('/api/tasks')[1]['tasks'] if t['task_id']=='TASK-MISSING');before=snap(d)
 invalid=[('/api/tasks',{'title':'拒绝未知主要','project_id':U}),('/api/tasks',{'title':'拒绝未知关联','related_project_ids':[U]})]
 for fields in [{'project_id':U},{'related_project_ids':[R,U]},{'project_id':[]},{'related_project_ids':[{}]}]:invalid.append(('/api/tasks/TASK-MISSING/update',dict(title='不能写入',status='todo',revision=current['revision'],**fields)))
 for path,payload in invalid:assert request(path,payload)[0]==400,(path,payload)
 assert snap(d)==before;print('PASS API unchanged existing missing refs accepted; six unknown/malformed create/update references rejected400 with no new or changed JSON',flush=True)
 page.reload();expect(card('TASK-MISSING').locator('select').nth(1)).to_have_value(M)
 # Explicitly remove primary only, keeping the missing related reference.
 card('TASK-MISSING').locator('select').nth(1).select_option('');card('TASK-MISSING').locator('button').click();expect(page.locator('#sync')).to_contain_text('保存成功');expect(card('TASK-MISSING').locator('select').nth(1)).to_have_value('');expect(card('TASK-MISSING').locator('select').nth(2)).to_have_values([R]);assert posts[-1]['body']['project_id'] is None and 'related_project_ids' not in posts[-1]['body'];page.screenshot(path=str(OUT/'04-explicit-primary-clear.png'),full_page=True)
 # Explicitly remove related IDs, now truly unclassified.
 card('TASK-MISSING').locator('select').nth(2).select_option([]);card('TASK-MISSING').locator('button').click();expect(page.locator('#sync')).to_contain_text('保存成功');expect(card('TASK-MISSING').locator('select').nth(2)).to_have_values([]);assert posts[-1]['body']['related_project_ids']==[] and 'project_id' not in posts[-1]['body'];page.screenshot(path=str(OUT/'05-explicit-related-clear.png'),full_page=True)
 current=next(t for t in request('/api/tasks')[1]['tasks'] if t['task_id']=='TASK-MISSING');assert current['project_id'] is None and current['related_project_ids']==[]
 print('PASS explicit UI primary unassign retains missing related ID; explicit related unassign clears it; separate appended events, no automatic deletion',flush=True)
 before=snap(d)
 for fields in [{'project_id':M},{'related_project_ids':[R]}]:assert request('/api/tasks/TASK-MISSING/update',dict(title='不能恢复未知历史引用',status='todo',revision=current['revision'],**fields))[0]==400
 assert snap(d)==before
 print('PASS removed missing references cannot be reintroduced using historical allowance; both rejected400/no writes',flush=True)
 # Project events arrive after a different title edit, should resolve without task migration.
 app.append_event(d,task('TASK-LATE-RESOLVE',project_id=M,related_project_ids=[R]));assert next(t for t in request('/api/tasks')[1]['tasks'] if t['task_id']=='TASK-LATE-RESOLVE')['project_missing']
 for pid,name in [(M,'虚构：迟到主要项目'),(R,'虚构：迟到关联项目')]:app.append_project_event(d,dict(version=1,event_id='late-'+pid,project_id=pid,action='create',actor='chatgpt',base_revision=0,changes={'name':name}))
 state=request('/api/tasks')[1];cleared=next(t for t in state['tasks'] if t['task_id']=='TASK-MISSING');assert cleared['project_id'] is None and cleared['related_project_ids']==[];resolved=next(t for t in state['tasks'] if t['task_id']=='TASK-LATE-RESOLVE');assert resolved['project_name']=='虚构：迟到主要项目' and resolved['related_project_names']==['虚构：迟到关联项目']
 assert all((d/name).read_bytes()==raw for name,raw in original.items());assert not errors,errors
 print('PASS newly available projects resolve names; all original event bytes intact; no browser pageerror',flush=True)
 (OUT/'posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/'trace.zip'));ctx.close();b.close();server.shutdown();server.server_close();thread.join()
