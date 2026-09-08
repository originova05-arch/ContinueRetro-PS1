"""SQLite/HTTP contract tests for the incremental review module.

The minimal host schema below is an authored fixture matching inspected v0.6.0
columns. It is NOT the whole app, a game, a real model or a Mac install test.
The updater separately runs the user's actual baseline app tests on a staged copy.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from app.quality_review import repo,technical,reviewer,jobs,routes
    from app.quality_review.quality import ReviewIdentity,parse_review,InvalidReview
except ImportError:
    from integration.quality_review import repo,technical,reviewer,jobs,routes
    from integration.quality_review.quality import ReviewIdentity,parse_review,InvalidReview


class HostFixture:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(exist_ok=True)
        self.db_path=self.root/'fixture.sqlite3';self.projects_root=self.root/'projects';self.projects_root.mkdir(exist_ok=True)
        self.workspace_root=self.root;self.fontkits_root=self.root/'fonts-not-included'
        with self.connect() as db:
            db.executescript('''
             CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT,archived_at TEXT,source_sha256 TEXT,selected_font_profile TEXT,pipeline_revision INTEGER DEFAULT 0);
             CREATE TABLE work_items(id INTEGER PRIMARY KEY,stable_id TEXT UNIQUE,project_id TEXT,source_file TEXT,file_offset INTEGER,
              physical_offset INTEGER,encoding TEXT,original_text TEXT,translation TEXT,original_hex TEXT,source_fingerprint TEXT,
              byte_length INTEGER,terminator TEXT,category TEXT,notes TEXT,confirmed INTEGER,revision INTEGER,approved_revision INTEGER,
              linguistic_revision INTEGER,ai_polished_revision INTEGER,ai_review_revision INTEGER,ai_review_status TEXT,ai_review_json TEXT,
              ai_last_model TEXT,qa_status TEXT,qa_json TEXT,max_bytes INTEGER,max_lines INTEGER,max_pixel_width INTEGER,updated_at TEXT);
             CREATE TABLE project_settings(project_id TEXT,key TEXT,value_json TEXT,PRIMARY KEY(project_id,key));
             CREATE TABLE cr4_terms(id INTEGER PRIMARY KEY,project_id TEXT,source TEXT,target TEXT,category TEXT,status TEXT);
             CREATE TABLE cr5_ready(work_id INTEGER PRIMARY KEY,fingerprint TEXT,status TEXT);
             CREATE TABLE edit_history(id INTEGER PRIMARY KEY,work_id INTEGER,revision INTEGER,snapshot_json TEXT,changed_at TEXT);
             CREATE TABLE cr4_file_issues(project_id TEXT,source_file TEXT);
            ''')
            db.execute('INSERT INTO projects VALUES(?,?,?,?,?,0)',('p','Fixture',None,'0'*64,'16x13'))
            db.execute('INSERT INTO projects VALUES(?,?,?,?,?,0)',('other','Other',None,'1'*64,'16x13'))
        repo.init(self)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db_path,timeout=5);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
        try:yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def ensure_editable(self,pid):
        if self.get_project(pid).get('archived_at'):raise ValueError('archived')
    def get_project(self,pid):
        with self.connect() as db:
            r=db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
            if not r:raise KeyError(pid)
            d=dict(r);d['entry_count']=db.execute('SELECT COUNT(*) FROM work_items WHERE project_id=?',(pid,)).fetchone()[0];return d
    def settings(self,pid,key,default=None):
        with self.connect() as db:r=db.execute('SELECT value_json FROM project_settings WHERE project_id=? AND key=?',(pid,key)).fetchone()
        return json.loads(r[0]) if r else default
    def setting(self,key,value,pid='p'):
        with self.connect() as db:db.execute('INSERT INTO project_settings VALUES(?,?,?) ON CONFLICT(project_id,key) DO UPDATE SET value_json=excluded.value_json',(pid,key,repo.dump(value)))
    def work_item(self,eid):
        with self.connect() as db:return repo.row_now(db,eid)
    def add(self,eid=1,pid='p',source='セーブしますか？',target='บันทึกเกมหรือไม่',category='menu_system'):
        row={'id':eid,'stable_id':f'{eid:032x}','project_id':pid,'source_file':'TEXT.DAT','file_offset':eid*32,
             'physical_offset':eid*32,'encoding':'shift_jis','original_text':source,'translation':target,
             'original_hex':source.encode('shift_jis').hex(),'source_fingerprint':repo.fingerprint([pid,eid,source]),
             'byte_length':len(source.encode('shift_jis')),'terminator':'00','category':category,'notes':'',
             'confirmed':1,'revision':1,'approved_revision':None,'linguistic_revision':None,'ai_polished_revision':None,
             'ai_review_revision':None,'ai_review_status':'pending','ai_review_json':'{}','ai_last_model':'',
             'qa_status':'pending','qa_json':'{}','max_bytes':None,'max_lines':None,'max_pixel_width':None,'updated_at':repo.now()}
        with self.connect() as db:db.execute('INSERT INTO work_items('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',list(row.values()))
        return self.work_item(eid)
    def edit(self,eid,**fields):
        with self.connect() as db:
            r=repo.row_now(db,eid);db.execute('INSERT INTO edit_history(work_id,revision,snapshot_json,changed_at) VALUES(?,?,?,?)',(eid,r['revision'],repo.dump(r),repo.now()))
            fields['revision']=r['revision']+1
            db.execute('UPDATE work_items SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',[*fields.values(),eid])
        return self.work_item(eid)


class OllamaFixture:
    """Actual loopback HTTP framing with authored answers, NOT model inference."""
    def __init__(self):
        self.mode='normal';self.calls=[];self.content_override=None;self.suggestion=None;self.callback=None;f=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                p=json.loads(self.rfile.read(int(self.headers['Content-Length'])));f.calls.append(p)
                inp=json.loads(p['messages'][-1]['content'])
                if f.callback:f.callback(inp)
                if f.mode=='delay':time.sleep(1)
                ident=inp['identity'];scores=dict(inp['rubric'])
                if not inp['context']['context_sufficient']:scores['context']=None
                result={**ident,'scores':scores,'issues':[],'suggested_target':f.suggestion,'review_confidence':.5}
                if f.mode=='major':result['issues']=[{'type':'semantic','severity':'major','message':'Authored fixture meaning warning','source_quote':'','target_quote':''}]
                if f.mode=='wrong_id':result['key']='wrong'
                content=f.content_override if f.content_override is not None else json.dumps(result,ensure_ascii=False)
                envelope={'model':p['model'],'done':f.mode!='truncated','done_reason':'length' if f.mode=='length' else 'stop',
                          'message':{'role':'assistant','thinking':'SHOULD_NOT_APPEAR_IN_SAVED_REVIEW','content':content},'eval_count':12}
                if f.mode=='tool':envelope['message']['tool_calls']=[{'function':{'name':'never_execute'}}]
                if f.mode=='remote':envelope['remote_host']='https://forbidden.invalid'
                raw=json.dumps(envelope,ensure_ascii=False).encode()
                if f.mode=='duplicate':raw=raw.replace(b'"done": true',b'"done": true, "done": true')
                status=503 if f.mode=='error' else 302 if f.mode=='redirect' else 200
                self.send_response(status)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(reviewer.MAX_BODY+1 if f.mode=='oversized' else len(raw)))
                self.end_headers()
                try:self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
    def client(self):return SimpleNamespace(host='127.0.0.1',port=self.server.server_port,timeout=5)


class IntegrationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.http=OllamaFixture()
    @classmethod
    def tearDownClass(cls):cls.http.close()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=HostFixture(self.temp.name);self.r=self.s.add()
        self.http.mode='normal';self.http.calls=[];self.http.content_override=None;self.http.suggestion=None;self.http.callback=None
        self.model={'name':'test:authored','digest':'a'*64,'capabilities':['completion','thinking']}
        self.cfg={'num_ctx':32768,'num_predict':2048}
    def tearDown(self):self.temp.cleanup()
    def review(self,r=None,**kwargs):
        r=r or self.s.work_item(1)
        return reviewer.review_record(self.s,r,self.http.client(),self.model,self.cfg,'fixture-job',**kwargs)
    def human(self,action='APPROVED',eid=1,**kwargs):
        r=self.s.work_item(eid);data={'revision':r['revision'],'action':action,'confirm':'USER_ACTION',**kwargs}
        return repo.human_action(self.s,r['project_id'],eid,data,actor='local_user')
    def test_additive_init_idempotent_preserves_old_columns_and_row(self):
        before=self.s.work_item(1);repo.init(self.s);self.assertEqual(self.s.work_item(1),before)
    def test_http_review_persists_host_total_and_separate_human(self):
        rid,review=self.review();d=repo.detail(self.s,'p',1)
        self.assertEqual(d['quality']['score'],100);self.assertEqual(d['human']['state'],'NOT_REVIEWED')
        self.assertEqual(d['technical']['state'],'NOT_EVALUATED');self.assertIsNone(self.s.work_item(1)['approved_revision'])
        self.assertEqual(d['quality']['review_id'],rid)
    def test_review_never_saves_reasoning_as_translation_or_audit(self):
        self.review()
        with self.s.connect() as db:r=db.execute('SELECT payload_json,request_json,usage_json FROM cr7_review_events').fetchone()
        self.assertNotIn('SHOULD_NOT_APPEAR', ''.join(r));self.assertEqual(self.s.work_item(1)['translation'],self.r['translation'])
        self.assertFalse(self.http.calls[-1]['stream']);self.assertIs(self.http.calls[-1]['think'],False)
    def test_gpt_oss_effort_is_string(self):
        self.model['name']='gpt-oss:20b';self.review();self.assertEqual(self.http.calls[-1]['think'],'medium')
    def test_missing_context_produces_partial_not_zero(self):
        r=self.s.edit(1,category='dialogue');_,v=self.review(r)
        self.assertIsNone(v.total);self.assertEqual(v.assessed_maximum,85);self.assertEqual(repo.detail(self.s,'p',1)['quality']['state'],'partial')
    def test_major_meaning_blocks_build_even_score_100(self):
        self.http.mode='major';self.review();d=repo.detail(self.s,'p',1)
        self.assertEqual(d['quality']['score'],100);self.assertTrue(d['meaning_blocked'])
        with self.assertRaises(ValueError):repo.guard_build(self.s,'p')
    def test_target_edit_invalidates_score_and_human_without_deleting_history(self):
        self.review();self.human();self.s.edit(1,translation='เซฟหรือไม่')
        d=repo.detail(self.s,'p',1);self.assertEqual(d['quality']['state'],'stale');self.assertIsNone(d['quality']['score']);self.assertEqual(d['human']['state'],'STALE')
        self.assertEqual(len(repo.history(self.s,'p',1)['reviews']),1)
    def test_stale_model_answer_rejected_at_commit(self):
        self.http.callback=lambda _:self.s.edit(1,translation='ผู้ใช้แก้แล้ว')
        with self.assertRaises(ValueError):self.review()
        self.assertEqual(self.s.work_item(1)['translation'],'ผู้ใช้แก้แล้ว')
        self.assertFalse(repo.history(self.s,'p',1)['reviews'])
    def test_glossary_insertion_invalidates_only_related_rows(self):
        self.s.add(2,source='戻りますか？',target='กลับหรือไม่');self.review();self.review(self.s.work_item(2));self.human()
        with self.s.connect() as db:db.execute("INSERT INTO cr4_terms VALUES(1,'p','セーブ','บันทึก','menu','confirmed')")
        self.assertEqual(repo.detail(self.s,'p',1)['quality']['state'],'stale');self.assertEqual(repo.detail(self.s,'p',2)['quality']['state'],'reviewed')
    def test_font_change_keeps_language_but_invalidates_technical(self):
        self.review();self.human();report=technical.assess(self.s,self.r,metrics={});repo.save_technical(self.s,self.r,report)
        with self.s.connect() as db:db.execute("UPDATE projects SET selected_font_profile='8x13' WHERE id='p'")
        d=repo.detail(self.s,'p',1);self.assertEqual(d['quality']['state'],'reviewed');self.assertEqual(d['human']['state'],'APPROVED');self.assertEqual(d['technical']['state'],'STALE')
    def test_weights_invalidate_ai_score_but_not_human_language(self):
        self.review();self.human();repo.save_preferences(self.s,'p',{'weights':[40,15,15,15,10,5]})
        d=repo.detail(self.s,'p',1);self.assertEqual(d['quality']['state'],'stale');self.assertEqual(d['human']['state'],'APPROVED')
    def test_style_change_requires_language_and_human_review(self):
        self.review();self.human();repo.save_preferences(self.s,'p',{'style':'เปลี่ยนแนวทางสำนวนที่ยืนยัน'})
        d=repo.detail(self.s,'p',1);self.assertEqual(d['quality']['state'],'stale');self.assertEqual(d['human']['state'],'STALE')
    def test_human_action_requires_explicit_confirm_and_known_actor(self):
        for actor,confirm in [('model','USER_ACTION'),('local_user','')]:
            with self.assertRaises(ValueError):repo.human_action(self.s,'p',1,{'revision':1,'action':'APPROVED','confirm':confirm},actor=actor)
        self.assertEqual(repo.detail(self.s,'p',1)['human']['state'],'NOT_REVIEWED')
    def test_human_language_approval_can_coexist_with_technical_fail(self):
        r=self.s.edit(1,original_text='HP %d',translation='HP');report=technical.assess(self.s,r,metrics={});repo.save_technical(self.s,r,report)
        d=self.human();self.assertEqual(d['human']['state'],'APPROVED');self.assertTrue(d['technical_fail']);self.assertIsNone(self.s.work_item(1)['approved_revision'])
        with self.assertRaises(ValueError):repo.guard_build(self.s,'p')
    def test_suggestion_acceptance_creates_revision_not_approval(self):
        self.http.suggestion='ต้องการบันทึกเกมหรือไม่';rid,_=self.review()
        d=self.human('ACCEPT_SUGGESTION',review_id=rid)
        self.assertEqual(d['revision'],2);self.assertEqual(d['translation'],self.http.suggestion);self.assertIsNone(d['quality']['score']);self.assertNotEqual(d['human']['state'],'APPROVED')
    def test_reject_suggestion_does_not_edit_translation(self):
        self.http.suggestion='ต้องการบันทึกเกมหรือไม่';rid,_=self.review();self.human('REJECT_SUGGESTION',review_id=rid)
        self.assertEqual(self.s.work_item(1)['revision'],1);self.assertEqual(self.s.work_item(1)['translation'],self.r['translation'])
    def test_stale_or_cross_project_suggestion_refused(self):
        self.http.suggestion='ต้องการบันทึกเกมหรือไม่';rid,_=self.review();self.s.edit(1,notes='บริบทใหม่')
        with self.assertRaises(ValueError):self.human('ACCEPT_SUGGESTION',review_id=rid)
        with self.assertRaises(KeyError):repo.detail(self.s,'other',1)
    def test_human_context_requires_evidence_and_refreshes_revision(self):
        with self.assertRaises(ValueError):self.human('CONTEXT',speaker='A',scene='intro',verified=True,reason='')
        d=self.human('CONTEXT',speaker='A',scene='intro',verified=True,reason='ผู้ใช้ตรวจบทสนทนาฉากทดสอบแล้ว')
        self.assertEqual(d['revision'],2);self.assertTrue(d['context']['context_sufficient'])
    def test_no_codec_is_unknown_not_fake_pass_or_zero_language(self):
        self.review();report=technical.assess(self.s,self.r,metrics={});repo.save_technical(self.s,self.r,report)
        self.assertEqual(report['status'],'NOT_EVALUATED');self.assertFalse(report['build_ready']);self.assertEqual(repo.detail(self.s,'p',1)['quality']['score'],100)
    def test_codec_failure_is_technical_fail(self):
        self.s.setting('adapter',{'encoding':'ascii'});report=technical.assess(self.s,self.r,metrics={},encoder=lambda text,a:text.encode('ascii'))
        self.assertEqual(report['status'],'FAIL');self.assertTrue(technical.blocks_language_operation(report))
    def test_placeholder_loss_detected_without_ai(self):
        r=self.s.edit(1,original_text='HP %d {NAME}',translation='HP');report=technical.assess(self.s,r,metrics={})
        names={x['name'] for x in report['checks'] if x['state']=='FAIL'};self.assertTrue({'printf','placeholders'}<=names)
    def test_out_of_budget_review_never_calls_network(self):
        self.cfg={'num_ctx':32,'num_predict':16}
        with self.assertRaises(InvalidReview):self.review()
        self.assertFalse(self.http.calls)
    def test_bad_response_does_not_become_score_zero(self):
        for mode in ['wrong_id','truncated','length','tool','duplicate','oversized']:
            self.http.mode=mode
            with self.subTest(mode=mode),self.assertRaises(InvalidReview):self.review()
        self.assertEqual(repo.detail(self.s,'p',1)['quality']['state'],'unreviewed')
    def test_service_failure_is_not_translation_failure(self):
        for mode in ['error','redirect','remote']:
            self.http.mode=mode
            with self.subTest(mode=mode),self.assertRaises(reviewer.ReviewServiceError):self.review()
        self.assertEqual(repo.detail(self.s,'p',1)['technical']['state'],'NOT_EVALUATED')
    def test_cancellation_during_first_token_wait(self):
        self.http.mode='delay';stop=threading.Event();timer=threading.Timer(.1,stop.set);timer.start();started=time.monotonic()
        with self.assertRaises(InterruptedError):self.review(cancel=stop)
        timer.join();self.assertLess(time.monotonic()-started,1);self.assertFalse(repo.history(self.s,'p',1)['reviews'])
    def test_digest_validation_is_strict_only_for_new_review(self):
        for value in ['',True,'fixture-not-a-sha','g'*64]:
            with self.subTest(value=value),self.assertRaises(reviewer.ReviewServiceError):reviewer.normalize_digest({'digest':value})
        self.assertEqual(reviewer.normalize_digest({'digest':'sha256:'+'a'*64}),'a'*64)
    def test_search_filter_and_project_boundary(self):
        self.s.add(2,pid='other',source='OTHER',target='อื่น');self.review()
        p=repo.page(self.s,'p',score='ge90');self.assertEqual([r['id'] for r in p['items']],[1]);self.assertFalse(repo.page(self.s,'p',query='ไม่มีข้อความนี้')['items'])
    def test_dashboard_denominator_excludes_unreviewed_and_stale(self):
        self.s.add(2,source='戻りますか？',target='กลับหรือไม่');self.review()
        d=repo.dashboard(self.s,'p');self.assertEqual(d['translated'],2);self.assertEqual(d['average_denominator'],1);self.assertEqual(d['average_score'],100)
        self.s.edit(1,translation='ฉบับใหม่');d=repo.dashboard(self.s,'p');self.assertIsNone(d['average_score']);self.assertEqual(d['stale'],1)
    def test_unknown_filter_and_bool_revision_refused(self):
        with self.assertRaises(ValueError):repo.page(self.s,'p',score='hacked')
        with self.assertRaises(ValueError):repo.human_action(self.s,'p',1,{'revision':True,'action':'APPROVED','confirm':'USER_ACTION'},actor='local_user')
    def test_selective_polish_does_not_choose_worse_or_partial(self):
        self.http.mode='normal';_,rv=self.review();old=repo.detail(self.s,'p',1)
        self.assertFalse(jobs.better_candidate(old,replace(rv,total=90))[0])
        self.assertFalse(jobs.better_candidate(old,replace(rv,total=None))[0])
        self.assertTrue(jobs.better_candidate(old,rv)[0])
    def test_foreign_key_failure_rolls_back_review_pointer(self):
        before=len(repo.history(self.s,'p',1)['reviews'])
        with self.s.connect() as db:db.execute("UPDATE work_items SET source_fingerprint='changed' WHERE id=1")
        with self.assertRaises(ValueError):self.review(self.r)
        self.assertEqual(len(repo.history(self.s,'p',1)['reviews']),before)
    def test_known_human_rejection_blocks_even_without_score(self):
        self.human('REJECTED')
        with self.assertRaises(ValueError):repo.guard_build(self.s,'p')
    def test_legacy_human_status_retained_without_fabricating_event(self):
        with self.s.connect() as db:db.execute('UPDATE work_items SET linguistic_revision=revision WHERE id=1')
        self.assertEqual(repo.detail(self.s,'p',1)['human']['state'],'LEGACY_REVIEWED');self.assertFalse(repo.history(self.s,'p',1)['human'])
    def test_quality_route_rechecks_write_token_boundary(self):
        class Handler:
            server=SimpleNamespace(storage=self.s)
            def valid_request(self,write=False):raise ValueError('token missing')
        with self.assertRaises(ValueError):routes.post(Handler(),['api','projects','p','quality-action'],{'id':1})


if __name__=='__main__':unittest.main(verbosity=2)
