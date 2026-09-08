"""Tests run by the updater against the ACTUAL staged Studio application.

Inputs and model replies are authored fixtures. Tests exercise real Storage,
Job execution, HTTP Handler hooks, source-revision commits and database updates.
No installed user data, ROM, FontKit assets or model weights are used.
"""
from __future__ import annotations
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from app.studio_storage import Storage
from app.pipeline_jobs import execute_job
from app import ai_store
from app.server import StudioServer,Handler as AppHandler
from app.quality_review import repo
from test_v020 import make_iso


class InferenceFixture:
    def __init__(self):
        self.mode='normal';self.calls=[];self.model='qwen3.5:9b-q4_K_M';self.digest='a'*64;self.low=False;self.worse=False;f=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def out(self,data,status=200):
                raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                if self.path=='/api/tags':return self.out({'models':[{'name':f.model,'digest':f.digest,'size':1000}]})
                return self.out({'version':'AUTHORED_HTTP_FIXTURE_NOT_OLLAMA'})
            def do_POST(self):
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path=='/api/show':return self.out({'capabilities':['completion']})
                if self.path!='/api/chat':return self.out({'error':'not allowed'},404)
                inp=json.loads(value['messages'][-1]['content']);f.calls.append(inp)
                if f.mode=='service' and inp['task']=='quality_review':return self.out({'error':'fixture'},503)
                if inp['task']=='quality_review':
                    scores=dict(inp['rubric']);issues=[]
                    if not inp['context']['context_sufficient']:scores['context']=None
                    if f.low and inp['target']=='บันทึกเกมหรือไม่':
                        scores['fluency']=5;issues=[{'type':'fluency','severity':'warning','message':'Authored test requests a different wording','source_quote':'','target_quote':'บันทึกเกมหรือไม่'}]
                    if f.worse and inp['target']=='ต้องการบันทึกเกมหรือไม่':
                        scores['semantic']=0;issues=[{'type':'semantic','severity':'major','message':'Authored test marks proposed wording worse','source_quote':'','target_quote':''}]
                    out={**inp['identity'],'scores':scores,'issues':issues,'suggested_target':None,'review_confidence':.4}
                    if f.mode=='wrong_id':out['key']='wrong'
                else:
                    rows=[]
                    for r in inp['items']:
                        x={'id':r['id'],'verdict':'ok','issues':[]}
                        if inp['task'] in {'translate','polish','repair'}:x['translation']='บันทึกเกมหรือไม่' if inp['task']=='translate' else 'ต้องการบันทึกเกมหรือไม่'
                        rows.append(x)
                    out={'items':rows,'terms':[]}
                return self.out({'model':f.model,'message':{'role':'assistant','content':json.dumps(out,ensure_ascii=False)},'done':True,'done_reason':'stop','eval_count':10})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()


class ActualStudioIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f=InferenceFixture()
    @classmethod
    def tearDownClass(cls):cls.f.close()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='studio-v061-app-test-');self.s=Storage(Path(self.tmp.name)/'workspace')
        self.src=self.s.private_root/'roms/authored-test.iso';make_iso(self.src,{'TEXT.DAT':'セーブしますか？'.encode('shift_jis')+b'\0'})
        self.pid=self.s.create_project('AUTHORED APP TEST',None,str(self.src))['id']
        raw='セーブしますか？'.encode('shift_jis');self.s.put_work([dict(project_id=self.pid,source_file='TEXT.DAT',file_offset=0,physical_offset=24*2048,extent_lba=24,encoding='shift_jis',original_text='セーブしますか？',original_hex=raw.hex(),byte_length=len(raw),terminator='00',category='menu_system')])
        self.r=next(self.s.iter_work(self.pid));self.r=self.s.edit_work(self.r['id'],{'revision':self.r['revision'],'confirmed':True})
        ai_store.save_settings(self.s,{**ai_store.settings(self.s),'endpoint':self.f.url,'model':self.f.model,'polish_model':self.f.model,'review_model':self.f.model,'num_ctx':32768,'num_predict':2048,'max_items':1,'max_requests':1})
        self.f.mode='normal';self.f.calls=[];self.f.low=False;self.f.worse=False
    def tearDown(self):self.tmp.cleanup()
    def job(self,kind,options=None):
        j=self.s.create_job(self.pid,kind);execute_job(str(self.s.root),self.pid,j['id'],kind,options or {},threading.Event());return self.s.get_job(j['id'])
    def done(self,j):
        self.assertIn(j['status'],{'completed','completed_with_warnings'},j.get('error') or j.get('message'));return j['result']
    def test_actual_storage_adds_tables_without_editing_existing_work(self):
        before=self.s.work_item(self.r['id']);Storage(self.s.root);self.assertEqual(before,self.s.work_item(self.r['id']))
        with self.s.connect() as db:self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='cr7_review_events'").fetchone())
    def test_actual_auto_translates_reviews_and_does_not_polish_good_text(self):
        h=hashlib.sha256(self.src.read_bytes()).hexdigest();d=self.done(self.job('quality_auto'))
        self.assertEqual(d['polished'],0);self.assertEqual([c['task'] for c in self.f.calls],['translate','quality_review'])
        r=repo.detail(self.s,self.pid,self.r['id']);self.assertEqual(r['quality']['score'],100);self.assertEqual(r['technical']['state'],'NOT_EVALUATED');self.assertEqual(r['human']['state'],'NOT_REVIEWED')
        self.assertEqual(hashlib.sha256(self.src.read_bytes()).hexdigest(),h)
    def test_actual_selective_polish_commits_only_after_reviewing_candidate(self):
        self.f.low=True;d=self.done(self.job('quality_auto'));r=self.s.work_item(self.r['id'])
        self.assertEqual(r['translation'],'ต้องการบันทึกเกมหรือไม่');self.assertEqual(d['polished'],1)
        self.assertEqual([c['task'] for c in self.f.calls],['translate','quality_review','polish','quality_review'])
        self.assertEqual(repo.detail(self.s,self.pid,r['id'])['quality']['score'],100)
        self.assertGreaterEqual(len(self.s.history(r['id'])),2)
    def test_actual_worse_polish_candidate_preserves_previous_translation(self):
        self.f.low=True;self.f.worse=True;d=self.done(self.job('quality_auto'));self.assertEqual(d['polished'],0)
        self.assertEqual(self.s.work_item(self.r['id'])['translation'],'บันทึกเกมหรือไม่')
    def test_actual_model_service_pause_resumes_at_latest_translation(self):
        self.f.mode='service';j=self.job('quality_auto');self.assertEqual(j['status'],'paused',j.get('error'));rid=j['result']['run_id']
        self.assertEqual(self.s.work_item(self.r['id'])['translation'],'บันทึกเกมหรือไม่')
        self.f.mode='normal';self.f.calls=[];self.done(self.job('quality_auto',{'resume_id':rid}))
        self.assertEqual([c['task'] for c in self.f.calls],['quality_review'])
    def test_actual_stale_user_revision_does_not_get_overwritten_after_pause(self):
        self.f.mode='service';j=self.job('quality_auto');r=self.s.work_item(self.r['id'])
        self.s.edit_work(r['id'],{'revision':r['revision'],'translation':'ผู้ใช้ตรวจแก้แล้ว'})
        self.f.mode='normal';d=self.done(self.job('quality_auto',{'resume_id':j['result']['run_id']}))
        self.assertEqual(d['queue_counts'],{'conflict':1});self.assertEqual(self.s.work_item(r['id'])['translation'],'ผู้ใช้ตรวจแก้แล้ว')
    def test_actual_explicit_review_score_is_separate_from_technical_failure(self):
        r=self.s.edit_work(self.r['id'],{'revision':self.r['revision'],'translation':'บันทึก %d'})
        self.done(self.job('quality_review'));d=repo.detail(self.s,self.pid,r['id'])
        self.assertTrue(d['technical_fail']);self.assertEqual(d['quality']['score'],100)
    def test_actual_empty_scope_has_no_traceback(self):
        j=self.job('quality_review');self.assertEqual(j['status'],'needs_input');self.assertFalse(j.get('error'));self.assertFalse(self.f.calls)
    def test_actual_original_whole_queue_remains_available(self):
        self.done(self.job('queue_translate'));self.assertEqual(self.s.work_item(self.r['id'])['translation'],'บันทึกเกมหรือไม่')
    def test_actual_http_routes_require_token_and_do_not_fake_human_approval(self):
        self.done(self.job('quality_auto'))
        server=StudioServer(('127.0.0.1',0),AppHandler,self.s);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,body=None,token=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            raw=None if body is None else json.dumps(body).encode();headers={'Content-Type':'application/json'}
            if token:headers['X-Studio-Token']=token
            c.request(method,path,raw,headers);r=c.getresponse();value=json.loads(r.read());c.close();return r.status,value
        try:
            code,d=request('GET',f'/api/projects/{self.pid}/quality-page');self.assertEqual(code,200);self.assertEqual(d['items'][0]['quality']['score'],100)
            r=self.s.work_item(self.r['id']);action={'id':r['id'],'revision':r['revision'],'action':'APPROVED','confirm':'USER_ACTION'}
            code,d=request('POST',f'/api/projects/{self.pid}/quality-action',action);self.assertEqual(code,400)
            self.assertEqual(repo.detail(self.s,self.pid,r['id'])['human']['state'],'NOT_REVIEWED')
            code,d=request('POST',f'/api/projects/{self.pid}/quality-action',action,server.token);self.assertEqual(code,200,d);self.assertEqual(d['entry']['human']['state'],'APPROVED');self.assertIsNone(self.s.work_item(r['id'])['approved_revision'])
        finally:server.shutdown();server.server_close();server.jobs.shutdown();thread.join(3)
    def test_actual_source_hooks_keep_old_build_gate(self):
        j=self.job('build',{'confirm':'CREATE_TEST_COPY'});self.assertNotEqual(j['status'],'completed');self.assertFalse(j.get('result',{}).get('binary_generated'))


if __name__=='__main__':unittest.main(verbosity=2)
