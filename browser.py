import sys,json,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,'/tmp/pr3-audit-8341816');import app
OUT=Path('/workspace/scratch/pr3-audit-8341816')
def task(eid,tid,title,**extra):return dict(version=1,event_id=eid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes=dict(title=title,status='todo',**extra))
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);legacy=app.append_event(d,task('legacy-browser-001','TASK-OLD-001','虚构：旧任务兼容'));old=legacy.read_bytes()
 s=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);p=ctx.new_page();requests=[]
 p.on('request',lambda r:requests.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None)
 p.goto(f'http://127.0.0.1:{s.server_port}');expect(p.locator('.task')).to_have_count(1);expect(p.locator('.project-group-head')).to_contain_text('未归类')
 for name in ['虚构项目甲','虚构项目乙']:
  p.locator('#new-project-name').fill(name);p.locator('#project-submit').click();expect(p.locator('#project-message')).to_contain_text('项目创建成功');expect(p.locator('.project-card')).to_have_count(1 if name.endswith('甲') else 2)
 projects=app.read_projects(d)['projects'];a=next(x['project_id'] for x in projects if x['name']=='虚构项目甲');bb=next(x['project_id'] for x in projects if x['name']=='虚构项目乙');original={f.name:f.read_bytes() for f in (d/'project_events').glob('*.json')}
 p.locator('#new-task-title').fill('虚构：跨项目任务');p.locator('#new-task-project').select_option(a);p.locator('#new-task-related').select_option([bb]);p.locator('#create-submit').click();expect(p.locator('.task')).to_have_count(2)
 tid=next(t['task_id'] for t in app.read_workspace(d)['tasks'] if t['title']=='虚构：跨项目任务')
 card=lambda tid:p.locator('.task').filter(has=p.locator('.task-id',has_text=tid))
 expect(card(tid).locator('select').nth(1)).to_have_value(a);expect(card(tid).locator('select').nth(2)).to_have_values([bb]);assert p.locator('.project-group').filter(has=p.locator('.project-group-head strong',has_text='虚构项目甲')).locator('.task').count()==1
 p.screenshot(path=str(OUT/'01-project-groups.png'),full_page=True);print('PASS browser legacy inbox, create two Chinese projects, create primary A/related B task, grouping and selectors',flush=True)
 projectcard=p.locator('.project-card').filter(has=p.locator('small',has_text=a));projectcard.locator('input').fill('虚构项目甲-重命名');projectcard.locator('button').click();expect(p.locator('#project-message')).to_contain_text('项目名称已保存');expect(p.locator('.project-group-head').filter(has_text='虚构项目甲-重命名')).to_have_count(1)
 assert all((d/'project_events'/n).read_bytes()==raw for n,raw in original.items());assert len(list((d/'project_events').glob('*.json')))==3
 card(tid).locator('select').nth(1).select_option(bb);card(tid).locator('select').nth(2).select_option([a]);card(tid).locator('button').click();expect(card(tid).locator('select').nth(1)).to_have_value(bb);assert next(t for t in app.read_workspace(d)['tasks'] if t['task_id']==tid)['project_id']==bb
 card(tid).locator('select').nth(1).select_option('');card(tid).locator('select').nth(2).select_option([]);card(tid).locator('button').click();expect(card(tid).locator('select').nth(1)).to_have_value('');assert p.locator('.project-group-head strong',has_text='未归类 / 收件箱').count()==1
 p.screenshot(path=str(OUT/'02-edit-and-inbox.png'),full_page=True);assert legacy.read_bytes()==old;print('PASS browser rename appends history; edit primary/related; explicit unassignment returns inbox; original project/task files intact',flush=True)
 # Missing primary and related references must not be silently dropped during a title edit.
 missing='PROJECT-'+'C'*32;missingrel='PROJECT-'+'D'*32;app.append_event(d,task('missing-ref-browser','TASK-MISSING-001','虚构：项目尚未同步',project_id=missing,related_project_ids=[missingrel]))
 p.reload();expect(p.locator('#warnings')).to_be_visible();expect(card('TASK-MISSING-001')).to_be_visible();expect(card('TASK-MISSING-001').locator('select').nth(1)).to_have_value('');expect(card('TASK-MISSING-001').locator('select').nth(2)).to_have_values([])
 p.screenshot(path=str(OUT/'03-missing-ref-before.png'),full_page=True)
 card('TASK-MISSING-001').locator('input').fill('虚构：只修改标题');card('TASK-MISSING-001').locator('button').click();expect(card('TASK-MISSING-001').locator('input')).to_have_value('虚构：只修改标题');expect(p.locator('#sync')).to_contain_text('保存成功')
 saved=next(t for t in app.read_workspace(d)['tasks'] if t['task_id']=='TASK-MISSING-001');assert saved['project_id'] is None and saved['related_project_ids']==[]
 p.screenshot(path=str(OUT/'04-missing-ref-lost.png'),full_page=True);print('FAIL P2 missing references: title-only UI edit sends project_id=null/related_project_ids=[] and silently removes both references. Last POST:',json.dumps(requests[-1],ensure_ascii=False),flush=True)
 # A project conflict itself is displayed and its rename operation disabled.
 proj=next(x for x in app.read_projects(d)['projects'] if x['project_id']==a)
 for n in [1,2]:app.append_project_event(d,dict(version=1,event_id=f'project-conflict-{n:03}',project_id=a,action='update',actor='user',base_revision=proj['revision'],changes={'name':f'虚构冲突候选{n}'}))
 p.reload();pc=p.locator('.project-card').filter(has=p.locator('small',has_text=a));expect(pc.locator('input')).to_be_disabled();expect(pc.locator('button')).to_be_disabled();p.screenshot(path=str(OUT/'05-project-conflict.png'),full_page=True);print('PASS project conflict UI disables rename',flush=True)
 # Task related-project conflict crashes the full reducer, including unrelated tasks.
 for n,related in [(1,[]),(2,[bb])]:app.append_event(d,dict(version=1,event_id=f'task-related-conflict-{n:03}',task_id='TASK-OLD-001',action='update',actor='user',base_revision=1,changes={'related_project_ids':related}))
 p.reload();expect(p.locator('#sync')).to_contain_text('读取失败');p.screenshot(path=str(OUT/'06-related-conflict-read-failure.png'),full_page=True);print('FAIL P2 task related list conflict: real browser entire workspace read fails instead of showing conflict',flush=True)
 (OUT/'browser-posts.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/'browser-trace.zip'));ctx.close();b.close();s.shutdown();s.server_close();thread.join()
