import sys,json,tempfile,threading,http.client,io,zipfile,stat,hashlib,shutil,traceback
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
SRC=Path('/tmp/pr7-audit-42573a3');OUT=Path('/workspace/scratch/pr7-audit-42573a3');SHA='42573a34c3190b46c28c1573e98fbca202924a9c';sys.path.insert(0,str(SRC));import app,updater
results=[];api_requests=[];requests=[];dialogs=[];posts=[];failure=None;stage='setup'
def files(d):return {str(p.relative_to(d)):p.read_bytes() for p in d.rglob('*') if p.is_file()}
def hashes(v):return {n:hashlib.sha256(b).hexdigest() for n,b in v.items()}
def passed(name):results.append({'case':name,'status':'PASS'});print('PASS',name,flush=True)
def archive(values=None,extras=None):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as z:
  for n,b in (values or {n:(SRC/n).read_bytes() for n in updater.APP_FILES}).items():z.writestr('yudacheng666-AIWorkSpace-'+SHA[:7]+'/'+n,b)
  for n,b in extras or []:z.writestr(n,b)
 return out.getvalue()
class Resp(io.BytesIO):
 def __init__(self,b,url):super().__init__(b);self.url=url;self.headers={}
 def geturl(self):return self.url
mode={'kind':'normal'}
def remote(req,timeout=10):
 url=req.full_url;requests.append(url)
 if mode['kind']=='offline':raise URLError('fictional offline')
 if url==updater.API_COMMIT_URL:b=json.dumps({'sha':SHA,'commit':{'message':'虚构独立更新测试'}}).encode()
 elif url==updater.RAW_VERSION_URL.format(commit=SHA):b=b'1.0.0\n'
 else:raise AssertionError('unexpected external destination '+url)
 return Resp(b,url)
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 base=Path(td);root=base/'application';data=base/'fictional-data';root.mkdir();data.mkdir()
 for n in updater.APP_FILES:p=root/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC/n,p)
 app.ROOT=root
 app.append_event(data,{'version':1,'event_id':'fixture-task-001','task_id':'TASK-FICTIONAL','action':'create','actor':'chatgpt','base_revision':0,'changes':{'title':'虚构更新验收任务'}})
 app.append_project_event(data,{'version':1,'event_id':'fixture-project-001','project_id':'PROJECT-'+'B'*32,'action':'create','actor':'chatgpt','base_revision':0,'changes':{'name':'虚构更新项目'}})
 app.append_step_event(data,{'version':1,'event_id':'fixture-step-001','task_id':'TASK-FICTIONAL','step_id':'STEP-'+'A'*32,'action':'create','actor':'chatgpt','base_revision':0,'changes':{'title':'虚构更新步骤','position':1}})
 (data/'history.bin').write_bytes(b'fictional historical binary\x00\xff');(data/'events'/'archived').mkdir();(data/'events'/'archived'/'old.txt').write_bytes(b'fictional archived history')
 original=files(data);code=files(root);server=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(data));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':1440,'height':1100},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);page=ctx.new_page();page.on('dialog',lambda d:(dialogs.append({'case':stage,'type':d.type,'message':d.message}),d.dismiss()));page.on('request',lambda r:posts.append({'url':r.url,'body':r.post_data}) if r.method=='POST' else None)
 def req(path,method='GET',body=None,headers=None):
  c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);h={'Content-Type':'application/json'};h.update(headers or {});c.request(method,path,json.dumps(body) if body is not None else None,h);r=c.getresponse();v=r.read().decode();status=r.status;c.close();api_requests.append({'method':method,'path':path,'body':body,'status':status,'response':v});return status,v
 try:
  with patch.object(updater,'urlopen',side_effect=remote):
   stage='version unknown';page.goto(url);expect(page.locator('#app-version')).to_have_text('v1.0.0 · build 未登记');page.locator('.update-panel').screenshot(path=str(OUT/'01-version-unknown.png'));passed(stage)
   stage='mock latest available';page.locator('#check-update').click();expect(page.locator('#update-message')).to_contain_text('发现新构建');expect(page.locator('#apply-update')).to_be_visible();passed(stage)
   stage='draft blocks update';card=page.locator('.task').first
   for ctl,new,old in [(page.locator('#new-task-title'),'虚构新建未保存',''),(card.locator('.task-form>label input').first,'虚构任务未保存','虚构更新验收任务'),(card.locator('.step-edit-form input').first,'虚构步骤未保存','虚构更新步骤'),(card.locator('.step-add-form input'),'虚构新增步骤未保存','')]:
    ctl.fill(new);n=len(posts);nd=len(dialogs);page.locator('#apply-update').click();expect(page.locator('#update-message')).to_contain_text('请先保存或处理');assert len(posts)==n and len(dialogs)==nd;expect(ctl).to_have_value(new);ctl.fill(old)
   page.locator('.update-panel').screenshot(path=str(OUT/'02-draft-blocked.png'));passed(stage)
   stage='user declines install';page.locator('#apply-update').click();assert dialogs[-1]['type']=='confirm' and posts==[];passed(stage)
   stage='known current build no update';(root/updater.BUILD_INFO_NAME).write_text(json.dumps({'commit':SHA,'version':'1.0.0'}));page.reload();expect(page.locator('#app-version')).to_have_text('v1.0.0 · build 42573a3');page.locator('#check-update').click();expect(page.locator('#update-message')).to_contain_text('当前已是');expect(page.locator('#apply-update')).to_be_hidden();passed(stage)
   stage='offline UI';mode['kind']='offline';page.locator('#check-update').click();expect(page.locator('#update-message')).to_contain_text('检查更新失败');expect(page.locator('.task')).to_have_count(1);page.locator('.update-panel').screenshot(path=str(OUT/'03-offline.png'));passed(stage);mode['kind']='normal'
  stage='Host Origin and invalid update payload'
  for path in ['/api/tasks','/api/update/status','/api/update/check']:assert req(path,headers={'Host':'attacker.example'})[0]==403
  assert req('/api/update/apply','POST',{'commit':SHA},{'Origin':'http://attacker.example'})[0]==403
  for v in [{'commit':'../../evil'},{'commit':SHA,'url':'https://attacker.example'},{'commit':'a'*39}]:assert req('/api/update/apply','POST',v)[0]==400
  assert files(data)==original;passed(stage)
  # Independent archive corpus. No extracted or auxiliary script is executed.
  valid={n:(SRC/n).read_bytes() for n in updater.APP_FILES};prefix='yudacheng666-AIWorkSpace-'+SHA[:7]+'/'
  symlink=zipfile.ZipInfo(prefix+'link');symlink.create_system=3;symlink.external_attr=(stat.S_IFLNK|0o777)<<16
  corrupt=bytearray(archive());idx=corrupt.find(b'Small local AIWorkSpace');assert idx>0;corrupt[idx]^=1
  corpus=[('traversal',archive(extras=[(prefix+'../fictional-data/evil.txt',b'evil')])),('absolute',archive(extras=[('/tmp/fictional-evil.txt',b'evil')])),('backslash',archive(extras=[(prefix+'web\\evil',b'evil')])),('symlink',archive(extras=[(symlink,b'../fictional-data')])),('duplicate app',archive(extras=[(prefix+'app.py',valid['app.py'])])),('missing updater',archive({n:b for n,b in valid.items() if n!='updater.py'})),('wrong commit root',archive().replace(b'42573a3',b'deadbee')),('crc corrupt',bytes(corrupt)),('syntax invalid',archive({**valid,'app.py':b'def broken(:\n'})),('invalid version',archive({**valid,'VERSION':b'latest'})),('oversize entry',archive({**valid,'app.py':b'#'*(updater.MAX_ENTRY_BYTES+1)})),('oversize archive',b'x'*(updater.MAX_ARCHIVE_BYTES+1)),('invalid zip',b'not a zip')]
  for name,payload in corpus:
   stage='archive '+name;before=files(root)
   try:updater.validate_archive_and_stage(payload,SHA,root,data)
   except updater.UpdateError as e:results.append({'case':stage,'status':'PASS','rejection':str(e),'payload_sha256':hashlib.sha256(payload).hexdigest()})
   else:failure={'level':'P2','case':stage,'reason':'malicious/invalid archive accepted'};raise AssertionError(failure)
   assert files(root)==before and files(data)==original;print('PASS',stage,flush=True)
  stage='allowlist excludes arbitrary scripts';s=updater.validate_archive_and_stage(archive(extras=[(prefix+'evil.py',b'raise Exception("must never execute")')]),SHA,root,data);assert set(files(s))==set(updater.APP_FILES);updater.remove_stage(s);assert files(data)==original;passed(stage)
  for overlap in [root,base,root/'web']:
   stage='overlap '+str(overlap.relative_to(base))
   try:updater.validate_archive_and_stage(archive(),SHA,root,overlap)
   except updater.UpdateError:passed(stage)
   else:failure={'level':'P2','case':stage,'reason':'application/data overlap accepted'};raise AssertionError(failure)
  stage='bad upstream API commit redirect lengths'
  for name,response in [('API invalid JSON',Resp(b'{',updater.API_COMMIT_URL)),('API invalid SHA',Resp(b'{"sha":"wrong"}',updater.API_COMMIT_URL)),('untrusted redirect',Resp(b'{}','https://untrusted.example/redirect'))]:
   with patch.object(updater,'urlopen',return_value=response):
    try:updater.check_latest_update(root)
    except updater.UpdateError:passed(name)
    else:failure={'level':'P2','case':name};raise AssertionError(failure)
  with patch.object(updater,'check_latest_update',return_value={'latest_commit':'a'*40}),patch.object(updater,'_read_url') as dl:
   try:updater.prepare_update(root,data,SHA)
   except updater.UpdateError:assert not dl.called;passed('stale non-main commit not downloaded')
   else:failure={'level':'P2','case':'stale commit accepted'};raise AssertionError(failure)
  stage='targeted task step writes';s,b=req('/api/tasks/TASK-FICTIONAL/update','POST',{'title':'虚构更新前合法编辑','status':'todo','revision':1});assert s==200;s,b=req('/api/tasks/TASK-FICTIONAL/steps/'+('STEP-'+'A'*32)+'/update','POST',{'title':'虚构步骤合法编辑','revision':1});assert s==200;after=files(data);assert all(after.get(n)==b for n,b in original.items()) and len(after)==len(original)+2;passed(stage)
  print('PASS all preflight Chromium and independent archive checks',flush=True)
 except Exception:
  if failure is None:failure={'level':'UNCLASSIFIED','case':stage}
  traceback.print_exc();(OUT/'failure.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2));page.screenshot(path=str(OUT/'failure.png'),full_page=True);raise
 finally:
  (OUT/'api-requests.json').write_text(json.dumps(api_requests,ensure_ascii=False,indent=2));(OUT/'preflight-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));(OUT/'preflight-requests.json').write_text(json.dumps(requests,indent=2));(OUT/'preflight-posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2));(OUT/'preflight-dialogs.json').write_text(json.dumps(dialogs,ensure_ascii=False,indent=2));(OUT/'preflight-data.json').write_text(json.dumps({'initial':hashes(original),'final':hashes(files(data))},indent=2));ctx.tracing.stop(path=str(OUT/'preflight-trace.zip'));browser.close();server.shutdown();server.server_close();thread.join()
