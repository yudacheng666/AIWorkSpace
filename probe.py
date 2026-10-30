import sys,json,tempfile,threading,concurrent.futures,http.client,traceback
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
sys.path.insert(0,'/tmp/pr3-audit-8341816');import app
P='PROJECT-'+'A'*32;Q='PROJECT-'+'B'*32

def pe(eid='project-create-001',pid=P,action='create',rev=0,name='虚构项目甲'):
 return dict(version=1,event_id=eid,project_id=pid,action=action,actor='user',base_revision=rev,changes={'name':name})
def te(eid='legacy-create-001',**kw):
 v=dict(version=1,event_id=eid,task_id='TASK-LEGACY-001',action='create',actor='chatgpt',base_revision=0,changes={'title':'虚构旧版任务','status':'todo'});v.update(kw);return v

def snap(d):return {str(p.relative_to(d)):p.read_bytes() for p in d.rglob('*.json')}
for case in ['missing','out-of-order','duplicate-identical','duplicate-content','duplicate-cross-project','concurrent-revision','corrupt']:
 with tempfile.TemporaryDirectory() as td:
  d=Path(td)
  if case=='missing':app.append_project_event(d,pe('project-update-001',action='update',rev=1,name='新名称'))
  else:app.append_project_event(d,pe())
  if case=='out-of-order':app.append_project_event(d,pe('project-update-002',action='update',rev=2,name='第三名称'))
  if case=='duplicate-identical':(d/'project_events'/'copy.json').write_text(json.dumps(pe()))
  if case=='duplicate-content':(d/'project_events'/'copy.json').write_text(json.dumps(pe(name='不同名称')))
  if case=='duplicate-cross-project':(d/'project_events'/'copy.json').write_text(json.dumps(pe(pid=Q,name='另一项目')))
  if case=='concurrent-revision':
   for n in [1,2]:app.append_project_event(d,pe(f'project-update-{n:03}',action='update',rev=1,name=f'并发{n}'))
  if case=='corrupt':(d/'project_events'/'broken.json').write_text('{broken')
  before=snap(d);state=app.read_workspace(d);assert state['warnings'];assert snap(d)==before
  if case not in ['corrupt','duplicate-identical']:assert all(x['conflict'] for x in state['projects'])
  if case=='out-of-order':
   app.append_project_event(d,pe('project-update-001',action='update',rev=1,name='第二名称'));s=app.read_projects(d)['projects'][0];assert s['name']=='第三名称' and s['revision']==3 and not s['conflict']
  if case=='missing':
   app.append_project_event(d,pe());assert app.read_projects(d)['projects'][0]['name']=='新名称'
  print('PASS project event',case,'warnings/freeze/recovery, original bytes unchanged',flush=True)
# Same ID no overwrite at atomic publication point for both event streams.
for append in [app.append_project_event,app.append_event]:
 with tempfile.TemporaryDirectory() as td:
  d=Path(td);barrier=threading.Barrier(8);link=app.os.link
  def gate(a,b):barrier.wait(timeout=5);return link(a,b)
  def write(n):
   record=pe(name=f'竞争项目{n}') if append==app.append_project_event else te(changes={'title':f'竞争任务{n}'})
   try:
    p=append(d,record);return ('ok',record,p.read_bytes())
   except FileExistsError:return ('exists',None,None)
  with patch.object(app.os,'link',gate):
   with concurrent.futures.ThreadPoolExecutor(8) as ex:r=list(ex.map(write,range(8)))
  won=[x for x in r if x[0]=='ok'];assert len(won)==1 and sum(x[0]=='exists' for x in r)==7;files=list(d.rglob('*.json'));assert len(files)==1 and files[0].read_bytes()==won[0][2] and json.loads(won[0][2])==won[0][1]
  print('PASS',append.__name__,'8 writers: one success, seven FileExistsError, exact successful event retained',flush=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);app.append_event(d,te());old=snap(d);app.append_project_event(d,pe());app.append_project_event(d,pe(pid=Q,eid='project-create-002',name='虚构项目乙'))
 legacy=app.read_workspace(d)['tasks'][0];assert legacy['project_id'] is None and legacy['related_project_ids']==[] and legacy['title']=='虚构旧版任务'
 s=ThreadingHTTPServer(('127.0.0.1',0),app.handler_factory(d));t=threading.Thread(target=s.serve_forever,daemon=True);t.start();port=s.server_port
 def request(path,body=None,host=None,origin=None):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=5);h={'Host':host or f'localhost:{port}','Content-Type':'application/json'}
  if origin:h['Origin']=origin
  try:
   c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h);r=c.getresponse();return r.status,r.read().decode()
  finally:c.close()
 assert request('/api/tasks',host='evil.example')[0]==403
 assert request('/api/projects',{'name':'不可创建'},origin='https://evil.example')[0]==403
 assert request('/api/projects',{'name':'不可创建'},host='evil.example')[0]==403
 path=f'/api/projects/{P}/update'
 with concurrent.futures.ThreadPoolExecutor(8) as ex:codes=list(ex.map(lambda n:request(path,{'name':f'并发重命名{n}','revision':1})[0],range(8)))
 assert sorted(codes)==[200]+[409]*7
 assert request('/api/tasks/TASK-LEGACY-001/update',{'title':'归属已修改','status':'todo','revision':1,'project_id':P,'related_project_ids':[Q]})[0]==200
 assert request('/api/tasks/TASK-LEGACY-001/update',{'title':'旧版覆盖','status':'todo','revision':1})[0]==409
 task=app.read_workspace(d)['tasks'][0];assert task['project_id']==P and task['related_project_ids']==[Q];assert all((d/name).read_bytes()==raw for name,raw in old.items())
 print('PASS legacy task read/edit with project fields; API Host/Origin403; project concurrent rename1x200/7x409; task stale409; original bytes retained',flush=True)
 # Valid task edits contain related project arrays: reducer must freeze, not crash.
 for n,related in [(1,[]),(2,[Q])]:app.append_event(d,te(f'conflict-related-{n:03}',action='update',base_revision=2,changes={'related_project_ids':related}))
 try:app.read_workspace(d);print('unexpected reducer success')
 except Exception as e:print('FAIL P2 related_project_ids conflict reducer:',type(e).__name__,str(e));traceback.print_exc()
 try:print('HTTP conflict GET result',request('/api/tasks')[0])
 except Exception as e:print('FAIL HTTP GET after conflict:',type(e).__name__,str(e))
 print('HTTP POST after conflict:',request('/api/projects',{'name':'无关新项目'})[0],flush=True)
 s.shutdown();s.server_close();t.join()
