"""Persistent queue tests on real SQLite + HTTP, with an explicit legacy-host fixture.

This file does not claim to run the original v0.6.0 application. Installer-side
app tests cover actual Storage/JobManager/translator hooks before activation.
"""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_quality_integration import HostFixture,OllamaFixture,repo,technical,reviewer,jobs


class QueueContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.http=OllamaFixture()
    @classmethod
    def tearDownClass(cls):cls.http.close()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=HostFixture(self.temp.name);self.r=self.s.add()
        self.http.mode='normal';self.http.calls=[];self.http.content_override=None;self.http.suggestion=None;self.http.callback=None
        self.stop=threading.Event();self.updates=[];self.translations=[];self.model={'name':'test:authored','digest':'a'*64,'capabilities':['completion']}
        self.cfg={'endpoint':'http://127.0.0.1:1','timeout_seconds':5,'model':self.model['name'],'review_model':self.model['name'],'polish_model':self.model['name'],
                  'num_ctx':32768,'num_predict':2048,'batch_size':4,'max_items':1,'max_requests':1,'repair_once':True}
        self.t=SimpleNamespace(storage=self.s,pid='p',jid='job-fixture',cancel=self.stop,result={})
        def check():
            if self.stop.is_set():raise InterruptedError('cancelled by fixture')
        self.t.check=check
        self.t.update=lambda message,progress=None,force=False:self.updates.append((message,progress))
        def scope_sql(pid,scope):
            sql='w.project_id=? AND w.confirmed=1';args=[pid]
            if scope.get('ids'):sql+=' AND w.id IN ('+','.join('?' for _ in scope['ids'])+')';args+=scope['ids']
            if scope.get('source_file'):sql+=' AND w.source_file=?';args.append(scope['source_file'])
            return sql,args
        def atomic(path,value):
            path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(repo.dump(value))
        self.store=SimpleNamespace(settings=lambda s:dict(self.cfg),scope_sql=scope_sql,policy_version=lambda s,p:0,
                                  blocked=lambda *a:False,memory_for=lambda *a,**k:[],neighbors=lambda *a:[],atomic_json=atomic)
        fixture=self
        class Client:
            def __init__(self,url,timeout):
                c=fixture.http.client();self.host=c.host;self.port=c.port;self.timeout=c.timeout
            def inspect(self,name):return dict(fixture.model,name=name)
        class AIError(ValueError):pass
        class AIResponseError(AIError):pass
        def translate(t,c,cfg,models,stage,rows,directory):
            # Only the legacy translator is stubbed; its commit contract is explicit.
            fixture.translations.append((stage,[r['id'] for r in rows]))
            with fixture.s.connect() as db:
                for r in rows:
                    db.execute("UPDATE work_items SET translation='บันทึกเกมหรือไม่',revision=revision+1 WHERE id=?",(r['id'],))
                jobs.sync_queue_after_legacy(db,t.jid)
            return [fixture.s.work_item(r['id']) for r in rows]
        self.pipeline=SimpleNamespace(_call=translate)
        self.deps=patch.object(jobs,'dependencies',return_value=(self.store,self.pipeline,Client,AIError,AIResponseError));self.deps.start()
        original=technical.assess
        self.qa=patch.object(technical,'assess',side_effect=lambda s,r:original(s,r,metrics={}));self.qa.start()
    def tearDown(self):self.qa.stop();self.deps.stop();self.temp.cleanup()
    def run_job(self,kind='quality_review',options=None):
        self.t.result={};jobs.run(self.t,kind,options or {});return self.t.result
    def test_review_whole_scope_not_limited_by_old_one_item_cap(self):
        for i in range(2,138):self.s.add(i)
        d=self.run_job();self.assertEqual(d['selected'],137);self.assertEqual(d['queue_counts'],{'done':137});self.assertEqual(len(self.http.calls),137)
        self.assertTrue(self.updates);self.assertFalse(any(self.s.work_item(i)['linguistic_revision'] is not None for i in range(1,138)))
    def test_current_good_text_is_not_sent_to_model_again(self):
        self.run_job();n=len(self.http.calls);d=self.run_job();self.assertEqual(len(self.http.calls),n);self.assertEqual(d['skipped_good'],1)
    def test_forced_rescore_is_explicit_and_persisted(self):
        self.run_job();n=len(self.http.calls);d=self.run_job(options={'force':True});self.assertEqual(len(self.http.calls),n+1)
        with self.s.connect() as db:cfg=json.loads(db.execute('SELECT config_json FROM cr7_runs WHERE id=?',(d['run_id'],)).fetchone()[0])
        self.assertTrue(cfg['_force'])
    def test_technical_failure_does_not_prevent_explicit_independent_score(self):
        self.s.edit(1,original_text='HP %d',translation='HP')
        d=self.run_job();r=repo.detail(self.s,'p',1);self.assertTrue(r['technical_fail']);self.assertEqual(r['quality']['score'],100);self.assertEqual(d['queue_counts'],{'review':1})
    def test_technical_failure_parks_auto_before_reviewer_or_polisher(self):
        self.s.edit(1,original_text='HP %d',translation='HP')
        d=self.run_job('quality_auto');self.assertEqual(d['queue_counts'],{'review':1});self.assertEqual(self.http.calls,[]);self.assertEqual(self.translations,[])
    def test_auto_translation_then_review_uses_saved_latest_revision(self):
        self.s.edit(1,translation='');d=self.run_job('quality_auto')
        self.assertEqual(self.translations,[('translate',[1])]);self.assertEqual(d['queue_counts'],{'done':1});self.assertEqual(d['polished'],0)
        inp=json.loads(self.http.calls[0]['messages'][-1]['content']);self.assertEqual(inp['target'],self.s.work_item(1)['translation']);self.assertEqual(inp['identity']['revision'],self.s.work_item(1)['revision'])
    def test_service_failure_pauses_and_resumes_without_retranslating(self):
        self.s.edit(1,translation='');self.http.mode='error';d=self.run_job('quality_auto');self.assertEqual(d['terminal_status'],'paused');rid=d['run_id']
        self.assertEqual(self.translations,[('translate',[1])]);self.http.mode='normal';self.t.jid='resume-job'
        d=self.run_job('quality_auto',{'resume_id':rid});self.assertEqual(d['queue_counts'],{'done':1});self.assertEqual(len(self.translations),1)
    def test_changed_user_revision_on_resume_is_not_overwritten(self):
        self.http.mode='error';d=self.run_job();rid=d['run_id'];self.s.edit(1,translation='ผู้ใช้แก้แล้ว');self.http.mode='normal';self.t.jid='resume-job'
        d=self.run_job(options={'resume_id':rid});self.assertEqual(d['queue_counts'],{'conflict':1});self.assertEqual(self.s.work_item(1)['translation'],'ผู้ใช้แก้แล้ว')
    def test_cancel_returns_inflight_to_pending_without_partial_review(self):
        self.http.callback=lambda inp:self.stop.set()
        with self.assertRaises(InterruptedError):self.run_job()
        rid=self.t.result['run_id'];self.assertEqual(jobs.counts(self.s,rid),{'pending':1});self.assertFalse(repo.history(self.s,'p',1)['reviews'])
        self.stop.clear();self.http.callback=None;self.t.jid='resume-cancel';d=self.run_job(options={'resume_id':rid});self.assertEqual(d['queue_counts'],{'done':1})
    def test_response_failure_isolated_and_does_not_loop_forever(self):
        self.s.add(2);self.http.callback=lambda inp:setattr(self.http,'mode','wrong_id' if inp['identity']['key']==self.r['stable_id'] else 'normal')
        d=self.run_job();self.assertEqual(d['queue_counts'],{'done':1,'error':1});self.assertEqual(len(self.http.calls),2);self.assertIsNone(repo.detail(self.s,'p',1)['quality']['score'])
    def test_context_incomplete_does_not_enter_repair_loop(self):
        self.s.edit(1,category='dialogue');self.http.mode='major';d=self.run_job('quality_improve')
        self.assertEqual(d['queue_counts'],{'review':1});self.assertEqual(d['polished'],0);self.assertEqual(len(self.http.calls),1)
    def test_technical_only_has_progress_without_model_discovery_or_generation(self):
        for i in range(2,12):self.s.add(i)
        d=self.run_job('quality_technical');self.assertEqual(d['technical_checked'],11);self.assertEqual(self.http.calls,[]);self.assertTrue(any(p is not None for _,p in self.updates))
    def test_empty_scope_is_not_an_exception_or_failed_job(self):
        d=self.run_job(options={'scope':{'ids':[999]}});self.assertEqual(d['terminal_status'],'needs_input');self.assertFalse(self.http.calls)
    def test_selected_ids_not_other_project_or_other_records(self):
        self.s.add(2);self.s.add(3,pid='other');d=self.run_job(options={'scope':{'ids':[2,3]}})
        self.assertEqual(d['selected'],1);self.assertEqual(repo.detail(self.s,'p',1)['quality']['state'],'unreviewed');self.assertEqual(repo.detail(self.s,'other',3)['quality']['state'],'unreviewed')
    def test_human_approved_or_build_approved_text_never_auto_rewritten(self):
        with self.s.connect() as db:db.execute('UPDATE work_items SET approved_revision=revision WHERE id=1')
        d=self.run_job('quality_auto');self.assertEqual(d['terminal_status'],'needs_input');self.assertFalse(self.http.calls)
    def test_wrong_resume_kind_is_rejected(self):
        self.http.mode='error';d=self.run_job()
        with self.assertRaises(ValueError):self.run_job('quality_improve',{'resume_id':d['run_id']})
    def test_model_digest_change_pauses_old_queue(self):
        self.http.mode='error';d=self.run_job();rid=d['run_id'];self.http.mode='normal';self.model['digest']='b'*64
        d=self.run_job(options={'resume_id':rid});self.assertEqual(d['terminal_status'],'paused');self.assertIn('โมเดลเปลี่ยน',d['message'])
    def test_prompt_preflight_rejects_unknown_scope_fields(self):
        with self.assertRaises(ValueError):self.run_job(options={'scope':{'sql':'DROP TABLE work_items'}})


if __name__=='__main__':unittest.main(verbosity=2)
