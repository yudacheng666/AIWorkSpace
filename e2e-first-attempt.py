import sys,os,json,tempfile,subprocess,time,socket,hashlib,shutil,http.client,io,zipfile,traceback,signal
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
SRC=Path('/tmp/pr7-audit-42573a3');OUT=Path('/workspace/scratch/pr7-audit-42573a3');SHA='42573a34c3190b46c28c1573e98fbca202924a9c';sys.path.insert(0,str(SRC));import app,updater

def files(p):return {str(f.relative_to(p)):f.read_bytes() for f in p.rglob('*') if f.is_file()}
def hs(v):return {n:hashlib.sha256(b).hexdigest() for n,b in v.items()}
def request(port,path,body=None):
 c=http.client.HTTPConnection('127.0.0.1',port,timeout=1);c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,{'Content-Type':'application/json'});r=c.getresponse();v=r.read();status=r.status;c.close();return status,json.loads(v)
BOOT=r'''
import os,sys,json,time,io
from pathlib import Path
import urllib.request
cfgpath=Path(os.environ['AIWORKSPACE_AUDIT_CONFIG']);cfg=json.loads(cfgpath.read_text());Path.home=classmethod(lambda cls:Path(cfg['home']))
(Path(cfg['pids'])/f'{os.getpid()}.json').write_text(json.dumps({'pid':os.getpid(),'argv':sys.argv}))
if Path(sys.argv[0]).name=='app.py' and cfg.get('fail_new_startup'):
 try:build=json.loads((Path(cfg['root'])/'.aiworkspace-build.json').read_text())
 except Exception:build={}
 if build.get('commit')==cfg['sha']:os._exit(71)
real=urllib.request.urlopen
class Response(io.BytesIO):
 def __init__(self,b,url):super().__init__(b);self.url=url;self.headers={'Content-Length':str(len(b))}
 def geturl(self):return self.url

def mock(req,*args,**kwargs):
 url=req.full_url if hasattr(req,'full_url') else str(req)
 if url.startswith('http://127.0.0.1:'):return real(req,*args,**kwargs)
 with open(cfg['network_log'],'a') as f:f.write(json.dumps({'pid':os.getpid(),'url':url})+'\n')
 api='https://api.github.com/repos/yudacheng666/AIWorkSpace/'
 if url==api+'commits/main':body=json.dumps({'sha':cfg['sha'],'commit':{'message':'虚构隔离端到端更新'}}).encode()
 elif url=='https://raw.githubusercontent.com/yudacheng666/AIWorkSpace/'+cfg['sha']+'/VERSION':body=b'1.0.0\n'
 elif url==api+'zipball/'+cfg['sha']:
  Path(cfg['hold_seen']).touch()
  while not Path(cfg['gate']).exists():time.sleep(.05)
  body=Path(cfg['archive']).read_bytes()
 else:raise RuntimeError('Unexpected non-local destination '+url)
 return Response(body,url)
urllib.request.urlopen=mock
'''
results=[]
with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
 base=Path(td);browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 for kind in ['success','startup-failure-rollback']:
  case=base/kind;root=case/'application';data=case/'fictional-data';boot=case/'audit-bootstrap';home=case/'isolated-home';pids=case/'pids'
  for p in [root,data,boot,home,pids]:p.mkdir(parents=True)
  for n in updater.APP_FILES:p=root/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC/n,p)
  (root/'VERSION').write_text('0.9.0\n');(root/updater.BUILD_INFO_NAME).write_text(json.dumps({'version':'0.9.0','commit':'b'*40}))
  app.append_event(data,{'version':1,'event_id':'fictional-e2e-task','task_id':'TASK-E2E','action':'create','actor':'chatgpt','base_revision':0,'changes':{'title':'虚构端到端任务'}})
  app.append_project_event(data,{'version':1,'event_id':'fictional-e2e-project','project_id':'PROJECT-'+'B'*32,'action':'create','actor':'chatgpt','base_revision':0,'changes':{'name':'虚构端到端项目'}})
  app.append_step_event(data,{'version':1,'event_id':'fictional-e2e-step','task_id':'TASK-E2E','step_id':'STEP-'+'A'*32,'action':'create','actor':'chatgpt','base_revision':0,'changes':{'title':'虚构端到端步骤','position':1}})
  (data/'history.bin').write_bytes(b'fictional history\x00\xff');(data/'events'/'archive').mkdir();(data/'events'/'archive'/'old.txt').write_bytes(b'fictional archived event history')
  olddata=files(data);oldprogram={n:(root/n).read_bytes() for n in updater.APP_FILES+(updater.BUILD_INFO_NAME,)}
  package=case/'fixed-product.zip'
  with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
   for n in updater.APP_FILES:z.writestr('yudacheng666-AIWorkSpace-'+SHA[:7]+'/'+n,(SRC/n).read_bytes())
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
  cfg={'root':str(root),'home':str(home),'pids':str(pids),'network_log':str(case/'network.jsonl'),'sha':SHA,'archive':str(package),'gate':str(case/'release-download'),'hold_seen':str(case/'download-held'),'fail_new_startup':kind!='success'}
  config=case/'config.json';config.write_text(json.dumps(cfg));(boot/'sitecustomize.py').write_text(BOOT);env=os.environ.copy();env['PYTHONPATH']=str(boot);env['AIWORKSPACE_AUDIT_CONFIG']=str(config)
  logfile=open(OUT/f'e2e-{kind}-process.log','w');proc=subprocess.Popen([sys.executable,str(root/'app.py'),'--data-dir',str(data),'--port',str(port)],cwd=root,env=env,stdout=logfile,stderr=subprocess.STDOUT)
  ctx=browser.new_context(viewport={'width':1440,'height':1100},locale='zh-CN');ctx.tracing.start(screenshots=True,snapshots=True,sources=False);page=ctx.new_page();ds=[];ps=[];rs=[];page.on('dialog',lambda d:(ds.append({'type':d.type,'message':d.message,'accepted':True}),d.accept()));page.on('request',lambda r:ps.append({'method':r.method,'url':r.url,'body':r.post_data}) if r.method=='POST' else None);page.on('response',lambda r:rs.append({'url':r.url,'status':r.status}) if r.request.method=='POST' else None)
  result={'case':kind,'port':port,'fixture':{'fixed_archive_sha':SHA,'old_version':'0.9.0','old_commit':'b'*40,'home_override':'Path.home mocked to isolated-home; HOME env unchanged','transport':'only official GitHub commit/version/archive URLs mocked; localhost real','fault':'new app exits71 via external sitecustomize before app.main' if kind!='success' else None},'before_data':hs(olddata)}
  try:
   deadline=time.monotonic()+10
   while time.monotonic()<deadline:
    try:
     if request(port,'/api/update/status')[0]==200:break
    except OSError:time.sleep(.1)
   page.goto(f'http://127.0.0.1:{port}');expect(page.locator('#app-version')).to_have_text('v0.9.0 · build bbbbbbb');page.locator('#check-update').click();expect(page.locator('#update-message')).to_contain_text('发现新版本 v1.0.0');page.locator('.update-panel').screenshot(path=str(OUT/f'e2e-{kind}-before.png'));page.locator('#apply-update').click()
   deadline=time.monotonic()+5
   while not Path(cfg['hold_seen']).exists() and time.monotonic()<deadline:page.wait_for_timeout(100)
   assert Path(cfg['hold_seen']).exists();expect(page.locator('#check-update')).to_be_disabled();expect(page.locator('#apply-update')).to_be_disabled();status,payload=request(port,'/api/update/apply',{'commit':SHA});assert status==409;result['concurrent_post']={'status':status,'body':payload};page.locator('.update-panel').screenshot(path=str(OUT/f'e2e-{kind}-locked.png'));assert files(data)==olddata
   Path(cfg['gate']).touch();deadline=time.monotonic()+45;final=None
   while time.monotonic()<deadline:
    proc.poll() # reap old parent, allowing helper to distinguish exit from zombie on Linux
    page.wait_for_timeout(200)
    try:
     status,v=request(port,'/api/update/status')
     if (kind=='success' and v.get('build_commit')==SHA) or (kind!='success' and (v.get('last_update') or {}).get('status')=='rolled_back'):final=v;break
    except (OSError,ValueError):pass
   if final is None:result['failure']='service did not return expected installed/rolled_back status';raise AssertionError(result['failure'])
   if kind=='success':expect(page.locator('#app-version')).to_have_text('v1.0.0 · build 42573a3',timeout=10000);assert all((root/n).read_bytes()==(SRC/n).read_bytes() for n in updater.APP_FILES)
   else:expect(page.locator('#update-message')).to_contain_text('恢复旧版本',timeout=10000);assert final['version']=='0.9.0' and final['build_commit']=='b'*40;assert all((root/n).read_bytes()==b for n,b in oldprogram.items())
   expect(page.locator('.task')).to_have_count(1);assert files(data)==olddata;page.locator('.update-panel').screenshot(path=str(OUT/f'e2e-{kind}-after.png'))
   backups=list((home/'.aiworkspace'/'update-backups').glob('*/manifest.json'));assert len(backups)==1;backup=backups[0].parent;assert all((backup/n).read_bytes()==b for n,b in oldprogram.items());assert not list(root.glob('.aiworkspace-update-staging-*'))
   result.update({'status':'PASS','final_status':final,'after_data':hs(files(data)),'data_bytes_unchanged':True,'backup_valid':True,'backup_files':hs(files(backup)),'program_after':hs({n:(root/n).read_bytes() for n in updater.APP_FILES}),'network': [json.loads(x) for x in Path(cfg['network_log']).read_text().splitlines()]});print('PASS E2E',kind,': same port/data-dir restart, native helper, valid external backup, data bytes identical',flush=True)
  except Exception:
   result['status']='FAIL';result['level']='P2';traceback.print_exc();page.screenshot(path=str(OUT/f'e2e-{kind}-failure.png'),full_page=True);raise
  finally:
   result['dialogs']=ds;result['posts']=ps;result['responses']=rs;result['processes']=[json.loads(f.read_text()) for f in pids.glob('*.json')];result['after_data']=hs(files(data));results.append(result);(OUT/'e2e-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));ctx.tracing.stop(path=str(OUT/f'e2e-{kind}-trace.zip'));ctx.close()
   for f in pids.glob('*.json'):
    pid=json.loads(f.read_text())['pid']
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   logfile.close()
 browser.close()
