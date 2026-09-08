"""Whole-scope quality jobs on the existing Studio multiprocessing worker.

Uses v0.6 translation calls without rebuilding its backend. Review, technical QA,
selective repair and human approval are separate persisted operations.
"""
from __future__ import annotations
import json
import uuid
from . import repo, technical, reviewer
from .quality import InvalidReview
from .review_payload import parse_review_response


def dependencies():
    from app import ai_store, ai_pipeline
    from app.ai_client import OllamaClient, AIError, AIResponseError
    return ai_store,ai_pipeline,OllamaClient,AIError,AIResponseError


def scope_query(s,pid,scope):
    store,_,_,_,_=dependencies()
    if scope is not None and (not isinstance(scope,dict) or set(scope)-{'ids','source_file'}):raise ValueError('ขอบเขตงานไม่ถูกต้อง')
    return store.scope_sql(pid,scope or {})


def preflight(s,pid,kind,scope=None):
    if kind not in repo.KINDS:raise ValueError('ชนิดงานคุณภาพไม่ถูกต้อง')
    sql,args=scope_query(s,pid,scope)
    if kind!='quality_auto':sql+=" AND w.translation<>''"
    if kind not in {'quality_review','quality_technical'}:sql+=' AND (w.linguistic_revision IS NULL OR w.linguistic_revision<>w.revision)'
    with s.connect() as db:
        count=db.execute('SELECT COUNT(*) FROM work_items w WHERE '+sql,args).fetchone()[0]
    return dict(count=count,scope=scope or {},kind=kind,whole_scope=True,
                message=f'มี {count:,} รายการในขอบเขตที่พร้อมทำงาน' if count else 'ไม่มีรายการพร้อมในขอบเขตนี้ ดูหมวดแกะ/คัดกรองหรือเปลี่ยนตัวกรอง ไม่ใช่ข้อผิดพลาดของโมเดล')


def counts(s,rid):
    with s.connect() as db:return dict(db.execute('SELECT status,COUNT(*) FROM cr7_queue WHERE run_id=? GROUP BY status',(rid,)).fetchall())


def sync_queue_after_legacy(db,jid):
    """Called inside the unchanged translator's commit transaction by a tiny hook."""
    db.execute('''UPDATE cr7_queue SET input_revision=(SELECT revision FROM work_items w WHERE w.id=cr7_queue.work_id)
       WHERE status='inflight' AND run_id IN (SELECT id FROM cr7_runs WHERE active_job=?)''',(jid,))


def create_run(t,kind,options):
    s=t.storage;store,_,Client,_,_=dependencies();resume=options.get('resume_id')
    if resume:
        with s.connect() as db:r=db.execute('SELECT * FROM cr7_runs WHERE id=? AND project_id=?',(resume,t.pid)).fetchone()
        if not r or r['state'] not in {'running','paused'}:raise ValueError('ไม่พบคิวคุณภาพที่ทำต่อได้')
        run=dict(r);cfg=json.loads(run['config_json']);policy=json.loads(run['policy_json'])
        if policy!={'preferences':repo.preferences(s,t.pid),'glossary_version':store.policy_version(s,t.pid)}:
            raise ValueError('ศัพท์/เกณฑ์เปลี่ยนหลังพักคิว เริ่มรอบใหม่โดยไม่ใช้ผลจากกฎเก่า')
        if kind!=run['kind']:raise ValueError('ชนิดงานไม่ตรงคิวที่พักไว้')
        with s.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE cr7_queue SET status='pending' WHERE run_id=? AND status='inflight'",(resume,))
            db.execute("UPDATE cr7_runs SET state='running',active_job=?,updated_at=? WHERE id=?",(t.jid,repo.now(),resume))
        return run,cfg,policy
    cfg=store.settings(s);prefs=repo.preferences(s,t.pid)
    if kind!='quality_technical' and not cfg.get('model'):raise reviewer.ReviewServiceError('ยังไม่เลือกโมเดล เปิดตั้งค่า AI และค้นหาโมเดลที่ติดตั้งไว้')
    cfg=dict(cfg);cfg['_digests']={}
    if kind!='quality_technical':
        client=Client(cfg['endpoint'],cfg['timeout_seconds'])
        names={cfg.get('review_model') or cfg['model']}
        if kind=='quality_auto':names.add(cfg['model'])
        if kind in {'quality_auto','quality_improve'}:names.add(cfg.get('polish_model') or cfg['model'])
        for name in sorted(names):
            t.check();info=client.inspect(name);cfg['_digests'][name]=info['digest']
            if name==(cfg.get('review_model') or cfg['model']):reviewer.normalize_digest(info)
    sql,args=scope_query(s,t.pid,options.get('scope'))
    if kind!='quality_auto':sql+=" AND w.translation<>''"
    if kind not in {'quality_review','quality_technical'}:sql+=' AND (w.linguistic_revision IS NULL OR w.linguistic_revision<>w.revision)'
    rid=uuid.uuid4().hex;stamp=repo.now();policy={'preferences':prefs,'glossary_version':store.policy_version(s,t.pid)}
    run=dict(id=rid,project_id=t.pid,kind=kind,state='running',scope_json=repo.dump(options.get('scope') or {}),config_json=repo.dump(cfg),policy_json=repo.dump(policy),active_job=t.jid,created_at=stamp,updated_at=stamp)
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO cr7_runs VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(run.values()))
        db.execute('INSERT INTO cr7_queue(run_id,work_id,input_revision) SELECT ?,w.id,w.revision FROM work_items w WHERE '+sql,[rid]+args)
    return run,cfg,policy


def candidate_review(s,r,client,model,cfg,t):
    """Review a hypothetical draft without writing it or assigning it to old score."""
    expected,rubric,inp,schema=reviewer.build_request(s,r,model)
    messages=[dict(role='system',content=reviewer.SYSTEM),dict(role='user',content=repo.dump(inp))]
    if len(repo.dump(messages).encode())+len(repo.dump(schema).encode())+cfg['num_predict']+384>cfg['num_ctx']:
        raise InvalidReview('candidate review exceeds context; original draft retained')
    raw,usage=reviewer.chat_final(client,model,messages,schema,num_ctx=cfg['num_ctx'],num_predict=cfg['num_predict'],cancel=t.cancel,
        heartbeat=lambda elapsed:t.update(f'ตรวจข้อเสนอเกลาก่อนเปลี่ยนฉบับล่าสุด · รอ {int(elapsed)} วินาที'))
    return parse_review_response(raw,expected,rubric),inp,usage


def better_candidate(old,new):
    """Conservative selection, not an assertion of independent human quality."""
    old_issues=old['quality']['issues']
    old_major=sum(x['severity'] in {'major','critical'} for x in old_issues)
    new_major=sum(x.severity in {'major','critical'} for x in new.issues)
    if any(x.severity=='critical' for x in new.issues):return False,'ข้อเสนอใหม่ยังมีปัญหาความหมายร้ายแรง'
    if new_major>old_major:return False,'ข้อเสนอใหม่มีปัญหาความหมายเพิ่ม'
    if new.total is None:return False,'ข้อเสนอใหม่ยังประเมินไม่ครบ เก็บฉบับเดิมไว้'
    old_score=old['quality']['score']
    if new_major<old_major:return True,'จำนวนประเด็นความหมายสำคัญลดลง (ยังต้องให้คนตรวจ)'
    if old_score is not None and new.total<old_score:return False,'คะแนนคำแนะนำลดลงและไม่ได้ลดประเด็นสำคัญ เก็บฉบับเดิม'
    if len(new.issues)>len(old_issues):return False,'ข้อเสนอมีประเด็นเพิ่มเติม เก็บให้ผู้ใช้ตัดสินใจ'
    return True,'ผ่าน QA ข้อความและไม่มีประเด็นที่ตรวจพบเพิ่ม; เป็นฉบับร่าง ไม่ใช่คนอนุมัติ'


def polish_once(t,r,cfg,client,models,old,run_id):
    s=t.storage;store,pipeline,_,_,_=dependencies()
    stage='repair' if old['meaning_blocked'] else 'polish'
    model=models[cfg.get('polish_model') or cfg['model']]
    from app.ai_quality import response_schema,validate_response
    inp=pipeline.build_input(s,t.pid,stage,[r]);schema=response_schema(stage,[r['id']])
    if pipeline.request_budget(inp,schema,cfg)>cfg['num_ctx']:raise InvalidReview('คำขอเกลาเกิน context; ยังไม่เปลี่ยนคำแปลเดิม')
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        q=db.execute('SELECT polish_attempts FROM cr7_queue WHERE run_id=? AND work_id=?',(run_id,r['id'])).fetchone()
        if not q or q[0]>=1:return False
        # Reserve the attempt BEFORE model execution. A lost response cannot create an endless repair loop.
        db.execute('UPDATE cr7_queue SET polish_attempts=polish_attempts+1 WHERE run_id=? AND work_id=?',(run_id,r['id']))
    t.result['requests']+=1
    value,usage=client.chat(model,[dict(role='system',content=pipeline.SYSTEM),dict(role='user',content=store.dump(inp))],schema,
                            num_ctx=cfg['num_ctx'],num_predict=cfg['num_predict'],cancel=t.cancel,
                            heartbeat=lambda elapsed:t.update(f'เกลาเฉพาะรายการ #{r["id"]} · รอ {int(elapsed)} วินาที'))
    validate_response(stage,value,[r],inp['terms']);x=value['items'][0]
    if x['verdict']!='ok' or x['translation']==r['translation']:
        repo.event(s,t.pid,t.jid,'polish','retained','โมเดลยังไม่เสนอคำแปลใหม่ที่ใช้ได้',r['id']);return False
    proposed=dict(r,translation=x['translation'],revision=r['revision']+1,ai_review_revision=None,linguistic_revision=None,approved_revision=None)
    report=technical.assess(s,proposed)
    if technical.blocks_language_operation(report):
        repo.event(s,t.pid,t.jid,'polish','rejected','ข้อเสนอเกลาไม่ผ่านข้อกำหนดข้อความ เก็บคำแปลเดิม',r['id']);return False
    t.result['requests']+=1
    reviewed,review_inp,review_usage=candidate_review(s,proposed,client,models[cfg.get('review_model') or cfg['model']],cfg,t)
    accepted,reason=better_candidate(old,reviewed)
    if not accepted:
        repo.event(s,t.pid,t.jid,'polish','rejected',reason,r['id']);return False
    t.check()
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE');repo.ensure_current(db,r)
        f=repo.facts(s,r,db)
        if f['language_hash']!=reviewed.identity.language_policy_sha256 or f['context_hash']!=reviewed.identity.context_sha256:
            raise ValueError('บริบทหรือศัพท์เปลี่ยน ไม่ใช้ข้อเสนอเก่าทับฉบับปัจจุบัน')
        db.execute('INSERT INTO edit_history(work_id,revision,snapshot_json,changed_at) VALUES(?,?,?,?)',(r['id'],r['revision'],repo.dump(r),repo.now()))
        db.execute("UPDATE work_items SET translation=?,revision=revision+1,qa_status='pending',qa_json='{}',approved_revision=NULL,linguistic_revision=NULL,ai_review_revision=NULL,ai_review_status='pending',ai_review_json='{}',ai_polished_revision=revision+1,ai_last_model=?,updated_at=? WHERE id=?",(proposed['translation'],model['name'],repo.now(),r['id']))
        sync_queue_after_legacy(db,t.jid)
    current=s.work_item(r['id'])
    repo.save_review(s,current,reviewed,models[cfg.get('review_model') or cfg['model']]['name'],review_inp,review_usage,t.jid)
    repo.save_technical(s,current,report)
    repo.event(s,t.pid,t.jid,'polish','committed',reason,r['id'])
    t.result['polished']+=1
    return True


def run(t,kind,options):
    s=t.storage;store,pipeline,Client,AIError,AIResponseError=dependencies()
    if kind not in repo.KINDS:raise ValueError('ชนิดงานไม่ถูกต้อง')
    if not isinstance(options,dict) or set(options)-{'scope','resume_id','force'}:raise ValueError('ตัวเลือกคิวคุณภาพไม่ถูกต้อง')
    if type(options.get('force',False))is not bool:raise ValueError('force ต้องเป็น boolean')
    run_info=None;rid=None
    try:
        if not options.get('resume_id'):
            pf=preflight(s,t.pid,kind,options.get('scope'))
            if not pf['count']:
                t.result.update(terminal_status='needs_input',message=pf['message'],complete=False);return
        run_info,cfg,policy=create_run(t,kind,options);rid=run_info['id']
        t.continuous_queue=True
        directory=s.projects_root/t.pid/'pipeline'/t.jid;directory.mkdir(parents=True,exist_ok=True)
        t.result.update(run_id=rid,quality_queue=True,requests=0,batches=0,cache_hits=0,processed=0,polished=0,reviewed=0,technical_checked=0,skipped_good=0,resumable=True,complete=False,directory=str(directory))
        client=Client(cfg['endpoint'],cfg['timeout_seconds']);models={}
        for name,digest in cfg.get('_digests',{}).items():
            t.check();info=client.inspect(name)
            if info['digest']!=digest:raise reviewer.ReviewServiceError('โมเดลเปลี่ยนจากตอนสร้างคิว เริ่มรอบใหม่แทนใช้ผลคละรุ่น')
            models[name]=info
        def mark(r,status,message=''):
            with s.connect() as db:db.execute('UPDATE cr7_queue SET status=?,error=? WHERE run_id=? AND work_id=?',(status,str(message)[:1500],rid,r['id']))
        while True:
            t.check()
            if policy!={'preferences':repo.preferences(s,t.pid),'glossary_version':store.policy_version(s,t.pid)}:
                raise reviewer.ReviewServiceError('เกณฑ์หรือศัพท์เปลี่ยน พักคิวเพื่อไม่ใช้กฎคละกัน')
            with s.connect() as db:
                batch=[dict(x) for x in db.execute("SELECT q.input_revision,q.attempts,q.polish_attempts,w.* FROM cr7_queue q JOIN work_items w ON w.id=q.work_id WHERE q.run_id=? AND q.status='pending' ORDER BY q.work_id LIMIT 8",(rid,))]
            if not batch:break
            for r in batch:
                t.check()
                if r['input_revision']!=r['revision']:mark(r,'conflict','revision เปลี่ยน ไม่เขียนทับ');continue
                if store.blocked(s,t.pid,r['source_file']):mark(r,'review','ไฟล์ยังไม่พร้อม');continue
                if r['attempts']>=3:mark(r,'error','ถึงขอบเขตทำซ้ำของคิว เปิดตรวจรายการก่อน');continue
                if kind not in {'quality_review','quality_technical'} and r['linguistic_revision']==r['revision']:
                    mark(r,'done','ผู้ใช้ตรวจภาษาแล้ว ไม่แก้อัตโนมัติ');continue
                with s.connect() as db:db.execute("UPDATE cr7_queue SET status='inflight',attempts=attempts+1 WHERE run_id=? AND work_id=?",(rid,r['id']))
                try:
                    if not r['translation']:
                        if kind!='quality_auto':mark(r,'review','ยังไม่มีคำแปล');continue
                        pipeline._call(t,client,cfg,models,'translate',[r],directory)
                        r=s.work_item(r['id'])
                        # Compatible fallback even when a host lacks the optional translator-commit hook.
                        with s.connect() as db:sync_queue_after_legacy(db,t.jid)
                        if not r['translation']:mark(r,'review','ยังแปลไม่ได้ ต้องมีบริบทเพิ่ม');continue
                    report=technical.assess(s,r);repo.save_technical(s,r,report);t.result['technical_checked']+=1
                    if kind=='quality_technical':
                        mark(r,'review' if report['status']=='FAIL' else 'done','ตรวจข้อความแล้ว; UNKNOWN ไม่ใช่ PASS');continue
                    if technical.blocks_language_operation(report):
                        mark(r,'review','Technical FAIL: แก้ตัวแปร/codec/ขอบเขตก่อน ไม่เกลาภาษาเพื่อฝืนผ่าน');continue
                    current=repo.detail(s,t.pid,r['id'])
                    force=options.get('force',False)
                    if not current['quality']['current'] or force:
                        t.result['requests']+=1
                        reviewer.review_record(s,r,client,models[cfg.get('review_model') or cfg['model']],cfg,t.jid,cancel=t.cancel,
                            heartbeat=lambda elapsed:t.update(f'ตรวจคุณภาพ #{r["id"]} · รอ {int(elapsed)} วินาที'),
                            memories=store.memory_for(s,t.pid,r['original_text'],r['id'],limit=2),neighbors=store.neighbors(s,r))
                        t.result['reviewed']+=1;current=repo.detail(s,t.pid,r['id'])
                    score=current['quality']['score'];prefs=policy['preferences']
                    needs_polish=current['meaning_blocked'] or (score is not None and score<prefs['polish_below'])
                    if kind in {'quality_auto','quality_improve'} and needs_polish and prefs['auto_repair_rounds']:
                        polish_once(t,s.work_item(r['id']),cfg,client,models,current,rid)
                        current=repo.detail(s,t.pid,r['id'])
                    elif not needs_polish and current['quality']['current'] and score is not None:
                        t.result['skipped_good']+=1
                    final=current['quality'];needs=current['meaning_blocked'] or current['technical_fail'] or final['score'] is None or final['score']<prefs['minimum_score'] or bool(final['issues'])
                    mark(r,'review' if needs else 'done','ต้องตรวจภาษา/บริบทต่อ' if needs else 'ตรวจฉบับร่างแล้ว ไม่ใช่คนอนุมัติหรือพร้อม Build')
                except (InvalidReview,AIResponseError) as exc:
                    mark(r,'error',str(exc));repo.event(s,t.pid,t.jid,'review','response_error',str(exc),r['id'])
                    # A response failure is NOT a zero score and does not erase a prior valid review.
                c=counts(s,rid);total=sum(c.values());finished=total-c.get('pending',0)-c.get('inflight',0)
                t.result.update(queue_counts=c,selected=total,processed=finished)
                t.update(f'แปล/ตรวจ/เกลา · จัดการ {finished:,}/{total:,} · สำเร็จ {c.get("done",0):,} · พักตรวจ {c.get("review",0)+c.get("error",0)+c.get("conflict",0):,}',finished/max(1,total),force=True)
            c=counts(s,rid);t.result.update(queue_counts=c,selected=sum(c.values()),processed=sum(c.values())-c.get('pending',0)-c.get('inflight',0))
        c=counts(s,rid);issues=sum(c.get(k,0) for k in ('review','error','conflict'))
        with s.connect() as db:db.execute("UPDATE cr7_runs SET state='finished',updated_at=? WHERE id=?",(repo.now(),rid))
        t.result.update(queue_counts=c,selected=sum(c.values()),processed=sum(c.values()),planned_work_finished=True,
            complete=issues==0,warnings=[f'พักตรวจ {issues:,} รายการ'] if issues else [],
            message=f'ทำครบขอบเขตแล้ว · สำเร็จ {c.get("done",0):,} · พักตรวจ {issues:,} · เกลา {t.result["polished"]:,} · ยังไม่ใช่ Human Approval/Build readiness')
        store.atomic_json(directory/'quality-result.json',t.result)
    except (AIError,reviewer.ReviewServiceError) as exc:
        if rid:
            with s.connect() as db:
                db.execute("UPDATE cr7_runs SET state='paused',updated_at=? WHERE id=?",(repo.now(),rid))
                db.execute("UPDATE cr7_queue SET status='pending' WHERE run_id=? AND status='inflight'",(rid,))
        t.result.update(terminal_status='paused',message=str(exc),complete=False,warnings=[str(exc)])
        repo.event(s,t.pid,t.jid,'queue','service_error',str(exc))
    except BaseException:
        if rid:
            with s.connect() as db:
                db.execute("UPDATE cr7_runs SET state='paused',updated_at=? WHERE id=?",(repo.now(),rid))
                db.execute("UPDATE cr7_queue SET status='pending' WHERE run_id=? AND status='inflight'",(rid,))
        raise
