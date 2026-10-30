import sys,json,tempfile,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect,TimeoutError as PWTimeout
sys.path.insert(0,'/tmp/pr6-audit-46d4a8a');import app
OUT=Path('/workspace/scratch/pr6-audit-46d4a8a');P='PROJECT-'+'A'*32;Q='PROJECT-'+'B'*32;S='STEP-'+'1'*32;SELF='虚构甲';OTHER='虚构乙';TODAY='2026-12-28'
def snap(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*') if f.is_file()}
def event(tid,title,**changes):return dict(version=1,event_id='create-'+tid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes={'title':title,**changes})
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td)
 for pid,name in [(P,'虚构主要项目'),(Q,'虚构关联项目')]:app.append_project_event(d,dict(version=1,event_id='project-'+pid,project_id=pid,action='create',actor='chatgpt',base_revision=0,changes={'name':name}))
 fixtures=[('TASK-SELF-TODAY',{'owner':SELF,'planned_date':TODAY,'due_date':TODAY,'follow_up_date':'2026-12-30','project_id':P,'related_project_ids':[Q]}),('TASK-SELF-LATE',{'owner':SELF,'planned_date':'2026-12-27','due_date':'2026-12-27','follow_up_date':TODAY}),('TASK-SELF-FUTURE',{'owner':SELF,'planned_date':'2026-12-29','due_date':'2027-01-04'}),('TASK-OTHER-TODAY',{'owner':OTHER,'planned_date':TODAY,'follow_up_date':TODAY,'due_date':'2027-01-04'}),('TASK-OTHER-FUTURE',{'owner':OTHER,'planned_date':'2026-12-27','follow_up_date':'2026-12-29','due_date':'2027-01-05'}),('TASK-NOOWNER',{}),('TASK-DONE',{'owner':SELF,'planned_date':'2026-12-27','follow_up_date':'2026-12-27','due_date':'2026-12-27'}),('TASK-CONFLICT',{'owner':SELF,'planned_date':TODAY,'follow_up_date':TODAY,'due_date':TODAY})]
 for tid,fields in fixtures:app.append_event(d,event(tid,'虚构：'+tid,**fields))
 for tid,status in [('TASK-SELF-TODAY','doing'),('TASK-SELF-LATE','blocked'),('TASK-DONE','done')]:
  app.append_event(d,dict(version=1,event_id='status-'+tid,task_id=tid,action='update',actor='user',base_revision=1,changes={'status':status},**({'confirmed_done':True} if status=='done' else {})))
 for i,title in enumerate(['虚构冲突候选甲','虚构冲突候选乙']):app.append_event(d,dict(version=1,event_id=f'conflict-title-{i}',task_id='TASK-CONFLICT',action='update',actor='chatgpt',base_revision=1,changes={'title':title}))
 app.append_step_event(d,dict(version=1,event_id='step-create-001',task_id='TASK-SELF-TODAY',step_id=S,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构核对清单','position':1}));initial=snap(d)
 server=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));th=threading.Thread(target=server.serve_forever,daemon=True);th.start();base=f'http://127.0.0.1:{server.server_port}'
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN',timezone_id='Asia/Shanghai');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);p=ctx.new_page();p.clock.set_fixed_time(datetime(2026,12,27,16,30,tzinfo=timezone.utc));posts=[];dialogs=[];decision={'accept':False};stage='init';failure=None
 p.on('request',lambda r:posts.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None)
 def dialog_handler(di):
  dialogs.append({'type':di.type,'message':di.message,'accept':decision['accept']});di.accept() if decision['accept'] else di.dismiss()
 p.on('dialog',dialog_handler)
 def ids():return sorted(p.locator('.task-id').all_text_contents())
 ALL=sorted(x[0] for x in fixtures)
 def visible(expected):expect(p.locator('.task')).to_have_count(len(expected));assert ids()==sorted(expected),(stage,ids(),expected)
 def card(tid):return p.locator('.task').filter(has=p.locator('.task-id',has_text=tid))
 def task(tid):return next(t for t in app.read_workspace(d)['tasks'] if t['task_id']==tid)
 def reset():p.locator('#query-reset').click();visible(ALL)
 try:
  p.goto(base);visible(ALL);expect(p.locator('#overview-date')).to_contain_text(TODAY);expect(p.locator('#view-mine')).to_be_disabled();expect(p.locator('#view-followup')).to_be_disabled();expect(p.locator('#view-mine-count')).to_have_text('—');expect(p.locator('.review-note')).to_contain_text('暂不生成数量');p.screenshot(path=str(OUT/'01-no-self-owner.png'),full_page=True)
  p.locator('#overview-owner').select_option(SELF);assert p.locator('#view-mine-count').inner_text()=='2';assert p.locator('#view-followup-count').inner_text()=='1';assert p.locator('#view-due-count').inner_text()=='3';assert p.locator('#view-risk-count').inner_text()=='2';assert p.locator('#view-all-count').inner_text()=='8'
  for view,wanted in [('mine',['TASK-SELF-TODAY','TASK-SELF-LATE']),('followup',['TASK-OTHER-TODAY']),('due',['TASK-SELF-TODAY','TASK-SELF-FUTURE','TASK-OTHER-TODAY']),('risk',['TASK-SELF-LATE','TASK-CONFLICT'])]:
   stage='overview '+view;p.locator('#view-'+view).click();visible(wanted)
  p.locator('#refresh').click();visible(['TASK-SELF-LATE','TASK-CONFLICT']);expect(p.locator('#overview-owner')).to_have_value(SELF);p.locator('#view-all').click();visible(ALL)
  assert p.evaluate('overviewDates(new Date(2026,11,28,23,30))')=={'today':'2026-12-28','sevenDays':'2027-01-04'};assert p.evaluate('overviewDates(new Date(2028,1,27,23,30))')=={'today':'2028-02-27','sevenDays':'2028-03-05'}
  p.screenshot(path=str(OUT/'02-overview-local-boundary.png'),full_page=True);print('PASS overview: self unset=disabled/—; selected self=2, other=1, due=3, risk=2; today/+7 inclusive,+8 excluded; done/conflict excluded where required; no fabricated approvals; local date differs from UTC, year/leap boundaries correct',flush=True)
  stage='combined queries';p.locator('#query-keyword').fill(S.lower());visible(ALL);p.locator('#query-project').select_option(Q);p.locator('#query-owner').select_option(SELF);p.locator('#query-status').select_option('doing');p.locator('#query-date-from').fill(TODAY);p.locator('#query-date-to').fill('2027-01-04');p.locator('#query-apply').click();visible(['TASK-SELF-TODAY'])
  for keyword in ['虚构核对清单','虚构关联项目','虚构主要项目','task-self-today']:
   p.locator('#query-keyword').fill(keyword);p.locator('#query-apply').click();visible(['TASK-SELF-TODAY'])
  p.locator('#refresh').click();visible(['TASK-SELF-TODAY']);expect(p.locator('#overview-owner')).to_have_value(SELF);p.screenshot(path=str(OUT/'03-combined-query.png'),full_page=True);reset()
  p.locator('#query-status').select_option('conflict');p.locator('#query-apply').click();visible(['TASK-CONFLICT']);reset();p.locator('#query-owner').select_option('__none__');p.locator('#query-apply').click();visible(['TASK-NOOWNER']);reset();p.locator('#query-project').select_option('__none__');p.locator('#query-apply').click();visible([i for i in ALL if i!='TASK-SELF-TODAY']);reset()
  expected={'due_date':['TASK-SELF-TODAY','TASK-CONFLICT'],'planned_date':['TASK-SELF-TODAY','TASK-OTHER-TODAY','TASK-CONFLICT'],'follow_up_date':['TASK-SELF-LATE','TASK-OTHER-TODAY','TASK-CONFLICT']}
  for field,wanted in expected.items():
   p.locator('#query-date-field').select_option(field);p.locator('#query-date-from').fill(TODAY);p.locator('#query-date-to').fill(TODAY);p.locator('#query-apply').click();visible(wanted);reset()
  p.locator('#query-date-from').fill(TODAY);p.locator('#query-date-to').fill('2027-01-04');p.locator('#query-apply').click();visible(['TASK-SELF-TODAY','TASK-SELF-FUTURE','TASK-OTHER-TODAY','TASK-CONFLICT']);p.locator('#query-date-from').fill('2027-01-05');p.locator('#query-date-to').fill(TODAY);p.locator('#query-apply').click();expect(p.locator('#query-message')).to_contain_text('结束日期不得早于');visible(['TASK-SELF-TODAY','TASK-SELF-FUTURE','TASK-OTHER-TODAY','TASK-CONFLICT']);reset()
  p.locator('#query-keyword').fill('虚构不存在的结果');p.locator('#query-apply').click();visible([]);expect(p.locator('.empty strong')).to_have_text('没有符合条件的任务');reset();assert posts==[] and snap(d)==initial
  print('PASS query: explicit apply only; STEP/task IDs, step/title/primary+related project keywords; combined owner/status/related project/date; three dates inclusive; invalid range retains last filter; unassigned/no owner/conflict/empty results/reset; zero POST and all bytes unchanged',flush=True)
  # Actual empty datastore and a distinct read failure.
  es=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d/'empty'));et=threading.Thread(target=es.serve_forever,daemon=True);et.start();ep=ctx.new_page();ep.goto(f'http://127.0.0.1:{es.server_port}');expect(ep.locator('.empty strong')).to_have_text('这里还没有任务');ep.close();es.shutdown();es.server_close();et.join()
  def bad_get(route):route.fulfill(status=500,content_type='application/json',body='{"error":"fictional read failure"}')
  p.route('**/api/tasks',bad_get);p.locator('#refresh').click();expect(p.locator('#sync')).to_contain_text('读取失败');visible(ALL);p.unroute('**/api/tasks',bad_get);p.locator('#refresh').click();expect(p.locator('#sync')).to_contain_text('上次刷新');assert snap(d)==initial
  print('PASS empty data versus empty query and read-error states distinguished; selected self/view/query survive refresh',flush=True)
  # Four dirty-editor types x four navigation actions, dismiss every confirmation.
  for kind in ['task-title','task-metadata','step-content','new-step']:
   stage='draft '+kind;reset();c=card('TASK-SELF-TODAY')
   if kind=='task-title':control=c.locator('.task-form > label').first.locator('input');draft='虚构：尚未保存任务标题';control.fill(draft)
   elif kind=='task-metadata':control=c.locator('.edit-meta input').first;draft='虚构：尚未保存负责人';control.fill(draft);c.locator('.edit-meta input').nth(1).fill('2030-01-02')
   elif kind=='step-content':control=c.locator('.step-edit-form input').first;draft='虚构：尚未保存步骤修改';control.fill(draft)
   else:control=c.locator('.step-add-form input');draft='虚构：尚未保存新增步骤';control.fill(draft)
   handle=control.element_handle();beforeposts=len(posts);p.locator('#query-keyword').fill('不应生效的筛选')
   for selector in ['#view-risk','#query-apply','#query-reset','#refresh']:
    nd=len(dialogs);p.locator(selector).click();assert len(dialogs)==nd+1 and dialogs[-1]['type']=='confirm' and not dialogs[-1]['accept'],(stage,selector,dialogs);expect(control).to_have_value(draft);assert handle.evaluate('(n)=>n.isConnected');visible(ALL)
   if kind in ['task-title','new-step']:
    p.locator('h1').click();p.wait_for_timeout(5500)
   else:p.evaluate('refresh(false)')
   expect(control).to_have_value(draft);assert handle.evaluate('(n)=>n.isConnected');expect(p.locator('#sync')).to_contain_text('尚未保存');assert len(posts)==beforeposts and snap(d)==initial
   if kind=='new-step':p.screenshot(path=str(OUT/'04-cancel-and-auto-refresh-keeps-drafts.png'),full_page=True)
   decision['accept']=True;nd=len(dialogs);p.locator('#view-risk').click();assert len(dialogs)==nd+1 and dialogs[-1]['accept'];visible(['TASK-SELF-LATE','TASK-CONFLICT']);decision['accept']=False;p.locator('#view-all').click();visible(ALL)
   print('PASS draft',kind,': card/apply/reset/manual-refresh all ask; dismiss retains same DOM; auto-refresh pauses; explicit accept discards; zero writes',flush=True)
  reset();stage='related successful saves';legacy=card('TASK-NOOWNER');legacy.locator('.task-form > label').first.locator('input').fill('虚构：旧任务标题保存成功');legacy.locator('.task-form > .save').click();expect(p.locator('#sync')).to_contain_text('保存成功');assert task('TASK-NOOWNER')['title']=='虚构：旧任务标题保存成功';assert not set(posts[-1]['body'])&{'owner','priority','due_date','planned_date','follow_up_date'}
  c=card('TASK-SELF-TODAY');c.locator('.step-edit-form input').fill('虚构：步骤正常保存');c.locator('.step-edit-form button').click();expect(c.locator('.step-edit-form button')).to_be_enabled();assert task('TASK-SELF-TODAY')['steps'][0]['title']=='虚构：步骤正常保存'
  legacy=card('TASK-NOOWNER');legacy.locator('.step-add-form input').fill('虚构：查询页面新增一步');legacy.locator('.step-add-form button').click();expect(legacy.locator('.step-row')).to_have_count(1)
  print('PASS adjacent legacy task edit emits no new metadata; step edit and one new step persist/refresh under query UI, no old full-suite rerun',flush=True)
  stage='failed save draft';c=card('TASK-SELF-TODAY');tc=c.locator('.task-form > label').first.locator('input');tc.fill('虚构：写入失败保留草稿');before=snap(d)
  with patch.object(app.os,'link',side_effect=OSError('fictional disk error')):
   c.locator('.task-form > .save').click();expect(c.locator('.message').first).to_contain_text('保存失败')
  expect(tc).to_have_value('虚构：写入失败保留草稿');assert snap(d)==before;decision['accept']=True;p.locator('#view-all').click();decision['accept']=False
  # Stale revision from an external fake event while editor remains focused.
  stage='adjacent409';c=card('TASK-SELF-TODAY');tc=c.locator('.task-form > label').first.locator('input');tc.fill('虚构：旧版本待保存草稿');cur=task('TASK-SELF-TODAY');app.append_event(d,dict(version=1,event_id='external-task-update-001',task_id=cur['task_id'],action='update',actor='chatgpt',base_revision=cur['revision'],changes={'title':'虚构：外部新版本'}));before=snap(d);c.locator('.task-form > .save').click();expect(c.locator('.message').first).to_contain_text('task changed');expect(tc).to_have_value('虚构：旧版本待保存草稿');assert snap(d)==before
  decision['accept']=True;p.locator('#refresh').click();decision['accept']=False;expect(card('TASK-SELF-TODAY').locator('.task-form > label').first.locator('input')).to_have_value('虚构：外部新版本');print('PASS failure and real stale409 retain draft/no write; explicit confirmed refresh loads saved external version',flush=True)
  # Browser-level page reload is also a manual refresh, distinct from the app button.
  stage='browser-reload draft safety';p.locator('#query-reset').click();tc=card('TASK-SELF-TODAY').locator('.task-form > label').first.locator('input');tc.click();tc.fill('虚构：浏览器刷新前未保存草稿');before=snap(d);nd=len(dialogs);p.screenshot(path=str(OUT/'05-before-browser-reload.png'),full_page=True)
  try:p.reload(wait_until='domcontentloaded',timeout=5000)
  except PWTimeout:pass
  if len(dialogs)==nd:
   expect(card('TASK-SELF-TODAY').locator('.task-form > label').first.locator('input')).to_have_value('虚构：外部新版本');assert snap(d)==before;failure={'level':'P2','stage':stage,'dialogs_before':nd,'dialogs_after':len(dialogs),'lost_draft':'虚构：浏览器刷新前未保存草稿','after_value':card('TASK-SELF-TODAY').locator('.task-form > label').first.locator('input').input_value(),'events_unchanged':True};p.screenshot(path=str(OUT/'06-browser-reload-lost-draft.png'),full_page=True);print('FAIL P2 browser page reload: no beforeunload confirmation, unsaved task title lost; saved event bytes unchanged. App refresh button protection had passed. Stop.',flush=True);raise AssertionError('P2 unsaved draft lost on browser reload without confirmation')
  expect(tc).to_have_value('虚构：浏览器刷新前未保存草稿');print('PASS browser reload dismissal preserves draft',flush=True)
 except Exception:
  if failure is None:failure={'stage':stage,'level':'UNCLASSIFIED','visible_ids':ids()};p.screenshot(path=str(OUT/'unexpected-failure.png'),full_page=True)
  traceback.print_exc();(OUT/'failure.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2));raise
 finally:
  (OUT/'posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));(OUT/'dialogs.json').write_text(json.dumps(dialogs,ensure_ascii=False,indent=2));(OUT/'final-events.json').write_text(json.dumps({n:json.loads(raw) for n,raw in snap(d).items()},ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/'trace.zip'));ctx.close();b.close();server.shutdown();server.server_close();th.join()
