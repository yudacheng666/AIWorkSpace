import sys,json,tempfile,threading,http.client,hashlib,traceback,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect,Error as PWError
sys.path.insert(0,'/tmp/pr6-recheck-eb035c6');import app
OUT=Path('/workspace/scratch/pr6-recheck-eb035c6');T='TASK-MAIN';SECOND='TASK-SECOND';S='STEP-'+'A'*32;H='STEP-'+'E'*32;P='PROJECT-'+'B'*32

def snap(d):return {str(f.relative_to(d)):f.read_bytes() for f in d.rglob('*') if f.is_file()}
def hashes(data):return {n:hashlib.sha256(v).hexdigest() for n,v in data.items()}
def task_event(tid,title,owner):return dict(version=1,event_id='create-'+tid,task_id=tid,action='create',actor='chatgpt',base_revision=0,changes={'title':title,'owner':owner})
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 d=Path(td);app.append_event(d,task_event(T,'虚构任务原始标题','虚构甲'));app.append_event(d,task_event(SECOND,'虚构第二任务原始标题','虚构乙'));app.append_step_event(d,dict(version=1,event_id='step-create-001',task_id=T,step_id=S,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构步骤原始标题','position':1}));app.append_project_event(d,dict(version=1,event_id='project-create-001',project_id=P,action='create',actor='chatgpt',base_revision=0,changes={'name':'虚构项目'}));initial=snap(d);original_initial=initial.copy()
 server=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1440,'height':1200},locale='zh-CN',timezone_id='Asia/Shanghai');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);p=ctx.new_page();dialogs=[];navs=[];posts=[];responses=[];reloads=[];mode={'accept':False};stage='init';failure=None
 p.on('framenavigated',lambda frame:navs.append(frame.url) if frame==p.main_frame else None)
 def on_dialog(di):
  dialogs.append({'stage':stage,'type':di.type,'message':di.message,'accept':mode['accept']});di.accept() if mode['accept'] else di.dismiss()
 p.on('response',lambda r:responses.append({'url':r.url,'status':r.status,'stage':stage}) if r.request.method=='POST' else None)
 p.on('dialog',on_dialog);p.on('request',lambda r:posts.append({'url':r.url,'body':json.loads(r.post_data)}) if r.method=='POST' else None)
 def card(tid=T):return p.locator('.task').filter(has=p.locator('.task-id',has_text=tid))
 def title(tid=T):return card(tid).locator('.task-form > label').first.locator('input')
 def task(tid=T):return next(t for t in app.read_workspace(d)['tasks'] if t['task_id']==tid)
 def ready():expect(p.locator('#sync')).not_to_contain_text('正在读取');expect(card()).to_be_visible()
 def ui():return p.evaluate('''()=>({create:[...document.querySelectorAll('#create-task input,#create-task select')].map(n=>[n.id,n.value]),tasks:[...document.querySelectorAll('.task')].map(c=>({id:c.querySelector('.task-id').textContent,title:c.querySelector('.task-form>label input').value,meta:[...c.querySelectorAll('.edit-meta input,.edit-meta select')].map(n=>n.value),steps:[...c.querySelectorAll('.step-edit-form input,.step-edit-form select')].map(n=>n.value),newStep:c.querySelector('.step-add-form input').value}))})''')
 def reload_case(name,prompt,accept=False):
  global stage,failure
  stage=name;mode['accept']=accept;nd=len(dialogs);nn=len(navs);before=snap(d);beforeui=ui();trigger='F5';err=None
  try:p.keyboard.press('F5');p.wait_for_timeout(300)
  except PWError as e:err=str(e)
  if len(dialogs)==nd and len(navs)==nn:
   trigger='Chromium Page.reload (F5 key not dispatched by headless)'
   try:p.reload(wait_until='domcontentloaded',timeout=1500)
   except PWError as e:err=str(e)
  p.wait_for_timeout(100);new=dialogs[nd:];after=snap(d);record={'case':name,'expected_prompt':prompt,'accept':accept,'trigger':trigger,'dialogs':new,'navigation_delta':len(navs)-nn,'before_hashes':hashes(before),'after_hashes':hashes(after),'event_bytes_unchanged':after==before}
  if err:record['navigation_result']=err
  reloads.append(record)
  if prompt and not (len(new)==1 and new[0]['type']=='beforeunload'):
   if len(navs)>nn:ready()
   failure={'level':'P2','case':name,'reason':'required native beforeunload missing','before_ui':beforeui,'after_ui':ui(),'record':record};p.screenshot(path=str(OUT/'failure-missing-native-prompt.png'),full_page=True);raise AssertionError('P2: dirty draft has no native beforeunload prompt')
  if not prompt and new:
   failure={'level':'P2','case':name,'reason':'unnecessary native prompt for clean page','before_ui':beforeui,'after_ui':ui(),'record':record};p.screenshot(path=str(OUT/'failure-unnecessary-native-prompt.png'),full_page=True);raise AssertionError('P2: clean page still prompts')
  assert after==before
  if prompt and not accept:assert len(navs)==nn and ui()==beforeui
  else:assert len(navs)>nn;ready()
  mode['accept']=False
 try:
  p.goto(base);ready();title().click();reload_case('clean page',False)
  def stepinput():return card().locator('.step-edit-form input').first
  # The original third P2, now with an explicit in-page refusal to discard B.
  for kind in ['task','step']:
   stage=kind+' baseline with sibling draft';control=title() if kind=='task' else stepinput();old=control.input_value();saved='虚构'+kind+'保存后基线Y';oldb=title(SECOND).input_value();original_node=control.element_handle();control.fill(saved);title(SECOND).fill('虚构兄弟未保存草稿')
   (card().locator('.task-form > .save') if kind=='task' else card().locator('.step-edit-form button').first).click()
   if kind=='task':expect(card().locator('.message').first).to_contain_text('已保存独立修改记录')
   else:expect(stepinput()).to_be_enabled()
   assert (task()['title'] if kind=='task' else task()['steps'][0]['title'])==saved
   assert control.evaluate('(el,original)=>el===original',original_node)
   nd=len(dialogs);p.locator('#refresh').click();assert len(dialogs)==nd+1 and dialogs[-1]['type']=='confirm' and not dialogs[-1]['accept'];expect(title(SECOND)).to_have_value('虚构兄弟未保存草稿');assert control.evaluate('(el,original)=>el===original',original_node)
   title(SECOND).fill(oldb);control.fill(old);before=snap(d);np=len(posts);card().screenshot(path=str(OUT/f'10-{kind}-old-X-before-reload.png'));reload_case(kind+' saved Y sibling restored then old X cancel',True,False);expect(control).to_have_value(old);assert snap(d)==before and len(posts)==np
   card().screenshot(path=str(OUT/f'11-{kind}-old-X-after-cancel.png'));control.fill(saved);reload_case(kind+' restored to persisted Y is clean',False)
   print('PASS third-P2',kind,': server Y saved, B refusal keeps identical editor, B reverted then old X native-confirm/cancel retains, persisted Y clears prompt',flush=True)
  # Hold a real successful HTTP response after the isolated server has saved it.
  # The task editor is editable during its request; the step editor is disabled.
  for kind in ['task','step']:
   stage=kind+' input during save';control=title() if kind=='task' else stepinput();old=control.input_value();saved='虚构'+kind+'请求已提交Y';new='虚构请求期间后续输入Z';oldb=title(SECOND).input_value();pending={};url=base+(f'/api/tasks/{T}/update' if kind=='task' else f'/api/tasks/{T}/steps/{S}/update')
   def hold(route):pending['response']=route.fetch();pending['route']=route
   p.route(url,hold);control.fill(saved);(card().locator('.task-form > .save') if kind=='task' else card().locator('.step-edit-form button').first).click();p.wait_for_timeout(100);assert 'route' in pending
   assert (task()['title'] if kind=='task' else task()['steps'][0]['title'])==saved
   if kind=='task':expect(control).to_be_enabled();control.fill(new)
   else:expect(control).to_be_disabled();title(SECOND).fill(new)
   pending['route'].fulfill(response=pending['response']);p.unroute(url,hold)
   if kind=='task':expect(card().locator('.message').first).to_contain_text('保存期间输入的新草稿已保留')
   else:expect(control).to_be_enabled()
   expect(control if kind=='task' else title(SECOND)).to_have_value(new if kind=='task' else new);reload_case(kind+' input during save remains protected',True,False)
   card().screenshot(path=str(OUT/f'12-{kind}-inflight-after-cancel.png'))
   if kind=='step':title(SECOND).fill(oldb)
   control.fill(old);reload_case(kind+' after inflight save old X still dirty',True,False);control.fill(saved);reload_case(kind+' after inflight save persisted Y clears prompt',False)
   print('PASS inflight',kind,': real server saved Y before response; '+('task newer Z retained/dirty' if kind=='task' else 'step input disabled, sibling Z retained/dirty')+'; old X dirty, persisted Y clean; no extra POST',flush=True)
  regression_initial=snap(d);regression_post_count=len(posts)
  # Eight new-task fields: independent change/cancel/restore, combined, each sole remaining field.
  fields=[('new-task-title','虚构逐字段任务',''),('new-task-project',P,''),('new-task-related',[P],[]),('new-task-owner','虚构逐字段负责人',''),('new-task-priority','high','normal'),('new-task-due','2030-02-03',''),('new-task-planned','2030-02-04',''),('new-task-follow','2030-02-05','')]
  def setfield(fid,value):
   ctl=p.locator('#'+fid)
   if fid in ['new-task-project','new-task-related','new-task-priority']:ctl.select_option(value)
   else:ctl.fill(value)
  for fid,changed,original in fields:
   setfield(fid,changed);reload_case('single field '+fid+' cancel reload',True,False);setfield(fid,original);reload_case('single field '+fid+' restored clean',False)
   print('PASS new-task independent field',fid,': dirty native prompt/cancel preserves; restored clean no prompt; zero writes',flush=True)
  for fid,changed,original in fields:setfield(fid,changed)
  reload_case('all eight fields dirty cancel reload',True,False);p.locator('.create-panel').screenshot(path=str(OUT/'01-eight-fields-dirty-cancel.png'))
  for fid,changed,original in fields:setfield(fid,original)
  p.locator('.create-panel').screenshot(path=str(OUT/'02-eight-fields-restored-clean.png'));reload_case('all eight fields restored clean',False)
  for remaining,changed,original in fields:
   for fid,v,orig in fields:setfield(fid,v)
   for fid,v,orig in fields:
    if fid!=remaining:setfield(fid,orig)
   reload_case('only remaining '+remaining+' cancel reload',True,False);setfield(remaining,original);reload_case('last remaining '+remaining+' restored clean',False)
   print('PASS one remaining field',remaining,': native confirmation remains until last field restored; zero writes',flush=True)
  assert snap(d)==regression_initial and len(posts)==regression_post_count;print('PASS all eight fields/multiple/one-remaining cases zero POST, saved filenames and bytes unchanged',flush=True)
  kinds=['task-title','task-metadata','step-edit','step-add','new-task','new-task-metadata-only']
  for i,kind in enumerate(kinds):
   stage='prepare '+kind
   if kind=='task-title':controls=[(title(),'虚构任务未保存草稿',task()['title'])]
   elif kind=='task-metadata':controls=[(card().locator('.edit-meta input').nth(0),'虚构负责人未保存草稿','虚构甲'),(card().locator('.edit-meta input').nth(1),'2030-01-02','')]
   elif kind=='step-edit':controls=[(card().locator('.step-edit-form input').first,'虚构步骤未保存修改',task()['steps'][0]['title'])]
   elif kind=='step-add':controls=[(card().locator('.step-add-form input'),'虚构新增步骤未保存草稿','')]
   elif kind=='new-task':controls=[(p.locator('#new-task-title'),'虚构新任务未保存草稿',''),(p.locator('#new-task-owner'),'虚构新负责人',''),(p.locator('#new-task-due'),'2030-02-03','')]
   else:controls=[(p.locator('#new-task-owner'),'虚构仅负责人草稿',''),(p.locator('#new-task-follow'),'2031-04-05','')]
   controls[0][0].click()
   for ctl,draft,original in controls:ctl.fill(draft)
   reload_case(kind+' cancel browser reload',True,False)
   if kind in ['task-title','step-edit','step-add','new-task']:card().screenshot(path=str(OUT/f'0{i+1}-{kind}-after-cancel.png')) if not kind.startswith('new-task') else p.locator('.create-panel').screenshot(path=str(OUT/f'0{i+1}-{kind}-after-cancel.png'))
   for ctl,draft,original in controls:expect(ctl).to_have_value(draft);ctl.fill(original)
   reload_case(kind+' revert to clean',False)
   for ctl,draft,original in controls:ctl.click();ctl.fill(draft)
   reload_case(kind+' accept browser reload',True,True)
   print('PASS native',kind,': beforeunload shown; cancel retains entire UI; restore clean=no prompt; accept navigates; all saved event bytes unchanged',flush=True)
  assert snap(d)==regression_initial and len(posts)==regression_post_count;print('PASS all native cancel/revert/accept cases are zero POST and initial filenames/bytes identical',flush=True)
  # Confirmed successful saves should clear dirty-state prompts.
  stage='task save';title().fill('虚构已保存任务新标题');card().locator('.task-form > .save').click();expect(p.locator('#sync')).to_contain_text('保存成功');assert task()['title']=='虚构已保存任务新标题';reload_case('after task saved successfully',False)
  stage='step save';card().locator('.step-edit-form input').first.fill('虚构已保存步骤新标题');card().locator('.step-edit-form button').first.click();expect(card().locator('.step-edit-form button').first).to_be_enabled();expect(card().locator('.step-edit-form input').first).to_have_value('虚构已保存步骤新标题');assert task()['steps'][0]['title']=='虚构已保存步骤新标题';reload_case('after step saved successfully',False)
  stage='step add saved';card().locator('.step-add-form input').fill('虚构新增步骤已保存');card().locator('.step-add-form button').click();expect(card().locator('.step-row')).to_have_count(2);reload_case('after new step saved successfully',False)
  stage='new task create under active query';p.locator('#query-keyword').fill('虚构查询中创建任务');p.locator('#query-apply').click();expect(p.locator('.task')).to_have_count(0);p.locator('#new-task-title').fill('虚构查询中创建任务');p.locator('#new-task-owner').fill('虚构创建负责人');p.locator('#new-task-due').fill('2030-03-04');p.locator('#create-submit').click();expect(p.locator('#create-message')).to_contain_text('创建成功');expect(p.locator('.task')).to_have_count(1);expect(p.locator('#new-task-title')).to_have_value('');assert any(t['title']=='虚构查询中创建任务' for t in app.read_workspace(d)['tasks']);reload_case('after new task saved successfully',False)
  print('PASS successful task edit/step edit/step add/new-task create under query clear prompts; no native confirm after saved clean page',flush=True)
  # New-task registry must survive list-only rerenders; those operations keep the form in place.
  stage='persistent new task draft under query';p.locator('#new-task-title').fill('虚构持续新建草稿');p.locator('#new-task-owner').fill('虚构持续负责人');before=snap(d);np=len(posts);p.locator('#query-keyword').fill('无结果');p.locator('#query-apply').click();expect(p.locator('#new-task-title')).to_have_value('虚构持续新建草稿');p.locator('#query-reset').click();p.locator('#refresh').click();expect(p.locator('#new-task-owner')).to_have_value('虚构持续负责人');assert snap(d)==before and len(posts)==np;reload_case('persistent new-task draft after query rerender',True,False)
  p.locator('#new-task-title').fill('');p.locator('#new-task-owner').fill('');reload_case('persistent new-task restored after rerender',False)
  # In-page confirmation and one actual automatic poll, scoped to the new guard integration.
  stage='in-page protections';title().fill('虚构页面内保留草稿');before=snap(d);np=len(posts)
  for selector in ['#refresh','#view-risk','#query-apply','#query-reset']:
   nd=len(dialogs);p.locator(selector).click();assert len(dialogs)==nd+1 and dialogs[-1]['type']=='confirm' and not dialogs[-1]['accept'];expect(title()).to_have_value('虚构页面内保留草稿')
  p.locator('h1').click();p.wait_for_timeout(5500);expect(title()).to_have_value('虚构页面内保留草稿');expect(p.locator('#sync')).to_contain_text('尚未保存');assert snap(d)==before and len(posts)==np
  title().fill(task()['title']);reload_case('after in-page draft restored',False);print('PASS in-page refresh/view/apply/reset cancellation and real automatic poll retain draft, no writes; persistent new-task registry survives query rerender',flush=True)
  # Failed task save keeps its dirty warning.
  stage='failed save guard';title().fill('虚构失败保存草稿');before=snap(d)
  with patch.object(app.os,'link',side_effect=OSError('fictional write error')):card().locator('.task-form > .save').click();expect(card().locator('.message').first).to_contain_text('保存失败')
  assert snap(d)==before;reload_case('after failed save retain prompt',True,False);title().fill(task()['title']);reload_case('failed draft restored to clean',False)
  # Required adjacent step409 while a query is active.
  stage='step409 under query';p.locator('#query-keyword').fill(S.lower());p.locator('#query-apply').click();expect(p.locator('.task')).to_have_count(1);st=task()['steps'][0];card().locator('.step-edit-form input').first.fill('虚构旧版本步骤草稿');app.append_step_event(d,dict(version=1,event_id='external-step-update-001',task_id=T,step_id=S,action='update',actor='chatgpt',base_revision=st['revision'],changes={'title':'虚构外部步骤新版本'}));before=snap(d);card().locator('.step-edit-form button').first.click();expect(card().locator('.step-message')).to_contain_text('step changed');assert snap(d)==before;expect(card().locator('.step-edit-form input').first).to_have_value('虚构旧版本步骤草稿');reload_case('step409 draft retains native protection',True,False)
  mode['accept']=True;p.locator('#refresh').click();mode['accept']=False;expect(card().locator('.step-edit-form input').first).to_have_value('虚构外部步骤新版本');print('PASS step-level409 under active query, no writes, dirty native prompt remains; explicit app refresh loads latest version',flush=True)
  # Required partial-sync adjacent regression only, not the full old feature path.
  stage='partial sync under query';existing=[x['step_id'] for x in task()['steps']];assert len(existing)==2;op=app.append_step_event(d,dict(version=1,event_id='query-partial-order-001',task_id=T,action='reorder',actor='chatgpt',base_revision=0,changes={'step_ids':[existing[0],H,existing[1]]}));raw=op.read_bytes();p.locator('#refresh').click();expect(card().locator('.step-order-warning')).to_contain_text('尚未同步')
  for bt in card().locator('.step-actions button').all():expect(bt).to_be_disabled()
  before=snap(d);conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);conn.request('POST',f'/api/tasks/{T}/steps/reorder',json.dumps({'step_ids':list(reversed(existing)),'revision':1}),{'Content-Type':'application/json'});r=conn.getresponse();assert r.status==409;r.read();conn.close();assert snap(d)==before
  app.append_step_event(d,dict(version=1,event_id='late-query-step-create-001',task_id=T,step_id=H,action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构迟到步骤','position':3}));p.locator('#refresh').click();expect(card().locator('.step-row')).to_have_count(3);assert [x['step_id'] for x in task()['steps']]==[existing[0],H,existing[1]] and not task()['step_order_incomplete'] and op.read_bytes()==raw;p.screenshot(path=str(OUT/'07-partial-sync-query-restored.png'),full_page=True);p.locator('#query-reset').click();print('PASS partial sync under query: disabled reorder, direct409 byte-identical; late create restores complete order with original event intact',flush=True)
  stage='legal reorder after partial sync recovery';before=snap(d);ids=[x['step_id'] for x in task()['steps']];card().locator('.step-actions').first.locator('button').nth(1).click();expect(card().locator('.step-id').first).to_have_text(H);assert [x['step_id'] for x in task()['steps']]==[H,ids[0],ids[2]];assert all(snap(d).get(k)==v for k,v in before.items());reload_case('after legal reorder following partial sync recovery',False)
  print('PASS legal browser reorder after missing step arrives; every previous event byte unchanged',flush=True)
  print('PASS all planned independent Chromium/API cases completed; no confirmed P1/P2',flush=True)
 except Exception:
  if failure is None:failure={'level':'UNCLASSIFIED','stage':stage,'ui':ui()}
  traceback.print_exc();(OUT/'failure.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2));raise
 finally:
  (OUT/'responses.json').write_text(json.dumps(responses,ensure_ascii=False,indent=2));(OUT/'final-events.json').write_text(json.dumps({n:v.decode('utf-8') for n,v in snap(d).items()},ensure_ascii=False,indent=2));(OUT/'initial-event-hashes.json').write_text(json.dumps(hashes(original_initial),indent=2));(OUT/'dialogs.json').write_text(json.dumps(dialogs,ensure_ascii=False,indent=2));(OUT/'reload-records.json').write_text(json.dumps(reloads,ensure_ascii=False,indent=2));(OUT/'posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));(OUT/'final-event-hashes.json').write_text(json.dumps(hashes(snap(d)),indent=2));ctx.tracing.stop(path=str(OUT/'trace.zip'));ctx.close();b.close();server.shutdown();server.server_close();thread.join()
