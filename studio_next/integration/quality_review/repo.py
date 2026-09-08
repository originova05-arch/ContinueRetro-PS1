"""Additive SQLite quality/review persistence for the inspected Studio v0.6.0.

No ROM reads, model calls, migrations of old rows or implicit human approvals.
The existing Storage owns its connection/rollback and root-drive checks.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any
from .quality import Snapshot, Rubric, ReviewIdentity, Review, DIMENSIONS, text_hash

PROMPT_VERSION = 'cr-quality-review-2026-09-08.1'
DEFAULT_PREFS = {'weights':[35,20,15,15,10,5], 'polish_below':90,
                 'minimum_score':70, 'auto_repair_rounds':1,
                 'style':'ภาษาไทยเป็นธรรมชาติ รักษาความหมายและศัพท์ที่ยืนยัน ไม่เดาผู้พูด'}
KINDS = frozenset({'quality_review','quality_auto','quality_improve','quality_technical'})


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def dump(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def fingerprint(value):
    return text_hash(dump(value))


def integer(value, name, low=0, high=2**63-1):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f'{name} ต้องเป็นจำนวนเต็ม {low}–{high}')
    return value


def init(s):
    """Only add new tables/indexes/triggers; keep every old record untouched."""
    with s.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS cr7_prefs(
          project_id TEXT PRIMARY KEY REFERENCES projects(id), value_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cr7_context(
          work_id INTEGER PRIMARY KEY REFERENCES work_items(id),speaker TEXT NOT NULL DEFAULT '',
          scene TEXT NOT NULL DEFAULT '',verified INTEGER NOT NULL DEFAULT 0,
          evidence TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cr7_review_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,work_id INTEGER NOT NULL REFERENCES work_items(id),
          revision INTEGER NOT NULL,source_text TEXT NOT NULL,target_text TEXT NOT NULL,
          language_hash TEXT NOT NULL,context_hash TEXT NOT NULL,rubric_hash TEXT NOT NULL,
          model_name TEXT NOT NULL,model_digest TEXT NOT NULL,prompt_hash TEXT NOT NULL,
          status TEXT NOT NULL,total INTEGER,scores_json TEXT NOT NULL,issues_json TEXT NOT NULL,
          suggestion TEXT,payload_json TEXT NOT NULL,request_json TEXT NOT NULL,
          usage_json TEXT NOT NULL,job_id TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS cr7_review_history ON cr7_review_events(work_id,id);
        CREATE TABLE IF NOT EXISTS cr7_tech_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,work_id INTEGER NOT NULL REFERENCES work_items(id),
          revision INTEGER NOT NULL,source_text TEXT NOT NULL,target_text TEXT NOT NULL,
          config_hash TEXT NOT NULL,status TEXT NOT NULL,report_json TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS cr7_tech_history ON cr7_tech_events(work_id,id);
        CREATE TABLE IF NOT EXISTS cr7_human_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,work_id INTEGER NOT NULL REFERENCES work_items(id),
          revision INTEGER NOT NULL,source_text TEXT NOT NULL,target_text TEXT NOT NULL,
          language_hash TEXT NOT NULL,context_hash TEXT NOT NULL,action TEXT NOT NULL,
          actor TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS cr7_human_history ON cr7_human_events(work_id,id);
        CREATE TABLE IF NOT EXISTS cr7_suggestion_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,review_id INTEGER NOT NULL REFERENCES cr7_review_events(id),
          work_id INTEGER NOT NULL REFERENCES work_items(id),revision INTEGER NOT NULL,
          action TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cr7_state(
          work_id INTEGER PRIMARY KEY REFERENCES work_items(id),review_id INTEGER,
          tech_id INTEGER,human_id INTEGER,language_dirty INTEGER NOT NULL DEFAULT 0,
          tech_dirty INTEGER NOT NULL DEFAULT 0,human_dirty INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS cr7_attempts(
          id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,work_id INTEGER,
          job_id TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS cr7_attempt_job ON cr7_attempts(project_id,job_id,id);
        CREATE TABLE IF NOT EXISTS cr7_runs(
          id TEXT PRIMARY KEY,project_id TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,
          scope_json TEXT NOT NULL,config_json TEXT NOT NULL,policy_json TEXT NOT NULL,
          active_job TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS cr7_runs_project ON cr7_runs(project_id,created_at);
        CREATE TABLE IF NOT EXISTS cr7_queue(
          run_id TEXT NOT NULL REFERENCES cr7_runs(id),work_id INTEGER NOT NULL REFERENCES work_items(id),
          input_revision INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,polish_attempts INTEGER NOT NULL DEFAULT 0,
          error TEXT NOT NULL DEFAULT '',PRIMARY KEY(run_id,work_id));
        CREATE INDEX IF NOT EXISTS cr7_next ON cr7_queue(run_id,status,work_id);
        CREATE TRIGGER IF NOT EXISTS cr7_text_changed AFTER UPDATE ON work_items
          WHEN NEW.revision<>OLD.revision OR NEW.original_text<>OLD.original_text
            OR NEW.translation<>OLD.translation OR NEW.notes<>OLD.notes OR NEW.category<>OLD.category
        BEGIN
          UPDATE cr7_state SET language_dirty=1,tech_dirty=1,human_dirty=1 WHERE work_id=NEW.id;
        END;
        CREATE TRIGGER IF NOT EXISTS cr7_limits_changed AFTER UPDATE ON work_items
          WHEN NEW.max_bytes IS NOT OLD.max_bytes OR NEW.max_lines IS NOT OLD.max_lines
            OR NEW.max_pixel_width IS NOT OLD.max_pixel_width
        BEGIN
          UPDATE cr7_state SET tech_dirty=1 WHERE work_id=NEW.id;
        END;
        CREATE TRIGGER IF NOT EXISTS cr7_glossary_changed AFTER UPDATE ON cr4_terms
          WHEN NEW.status='confirmed' OR OLD.status='confirmed'
        BEGIN
          UPDATE cr7_state SET language_dirty=1,human_dirty=1 WHERE work_id IN
            (SELECT id FROM work_items WHERE project_id IN (NEW.project_id,OLD.project_id)
             AND (instr(original_text,NEW.source)>0 OR instr(original_text,OLD.source)>0));
        END;
        CREATE TRIGGER IF NOT EXISTS cr7_glossary_added AFTER INSERT ON cr4_terms WHEN NEW.status='confirmed'
        BEGIN
          UPDATE cr7_state SET language_dirty=1,human_dirty=1 WHERE work_id IN
            (SELECT id FROM work_items WHERE project_id=NEW.project_id AND instr(original_text,NEW.source)>0);
        END;
        CREATE TRIGGER IF NOT EXISTS cr7_glossary_removed AFTER DELETE ON cr4_terms WHEN OLD.status='confirmed'
        BEGIN
          UPDATE cr7_state SET language_dirty=1,human_dirty=1 WHERE work_id IN
            (SELECT id FROM work_items WHERE project_id=OLD.project_id AND instr(original_text,OLD.source)>0);
        END;
        CREATE TRIGGER IF NOT EXISTS cr7_project_changed AFTER UPDATE ON projects
          WHEN NEW.source_sha256 IS NOT OLD.source_sha256 OR NEW.selected_font_profile<>OLD.selected_font_profile
        BEGIN
          UPDATE cr7_state SET tech_dirty=1,
             language_dirty=CASE WHEN NEW.source_sha256 IS NOT OLD.source_sha256 THEN 1 ELSE language_dirty END,
             human_dirty=CASE WHEN NEW.source_sha256 IS NOT OLD.source_sha256 THEN 1 ELSE human_dirty END
          WHERE work_id IN (SELECT id FROM work_items WHERE project_id=NEW.id);
        END;
        CREATE TRIGGER IF NOT EXISTS cr7_adapter_changed AFTER UPDATE ON project_settings WHEN NEW.key='adapter'
        BEGIN
          UPDATE cr7_state SET tech_dirty=1 WHERE work_id IN (SELECT id FROM work_items WHERE project_id=NEW.project_id);
        END;
        CREATE TRIGGER IF NOT EXISTS cr7_adapter_added AFTER INSERT ON project_settings WHEN NEW.key='adapter'
        BEGIN
          UPDATE cr7_state SET tech_dirty=1 WHERE work_id IN (SELECT id FROM work_items WHERE project_id=NEW.project_id);
        END;
        ''')


def preferences(s,pid,db=None):
    if db is None:
        with s.connect() as c:return preferences(s,pid,c)
    row=db.execute('SELECT value_json FROM cr7_prefs WHERE project_id=?',(pid,)).fetchone()
    value=dict(DEFAULT_PREFS)
    if row:value.update(json.loads(row[0]))
    rubric=Rubric(tuple(value['weights']),version='quality-six-dimensions-v1')
    integer(value['polish_below'],'polish_below',1,100)
    integer(value['minimum_score'],'minimum_score',0,100)
    integer(value['auto_repair_rounds'],'auto_repair_rounds',0,1)
    if not isinstance(value['style'],str) or len(value['style'])>2000:raise ValueError('แนวทางสำนวนยาวเกิน 2,000 อักขระ')
    return value


def save_preferences(s,pid,value):
    s.ensure_editable(pid)
    if not isinstance(value,dict) or set(value)-set(DEFAULT_PREFS):raise ValueError('ฟิลด์ตั้งค่าคุณภาพไม่ถูกต้อง')
    merged=preferences(s,pid);merged.update(value)
    Rubric(tuple(merged['weights']))
    integer(merged['polish_below'],'polish_below',1,100)
    integer(merged['minimum_score'],'minimum_score',0,100)
    integer(merged['auto_repair_rounds'],'auto_repair_rounds',0,1)
    if not isinstance(merged['style'],str) or len(merged['style'])>2000:raise ValueError('แนวทางสำนวนไม่ถูกต้อง')
    old=preferences(s,pid)
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO cr7_prefs VALUES(?,?) ON CONFLICT(project_id) DO UPDATE SET value_json=excluded.value_json',(pid,dump(merged)))
        if old['weights']!=merged['weights'] or old['style']!=merged['style']:
            db.execute('UPDATE cr7_state SET language_dirty=1,human_dirty=CASE WHEN ? THEN 1 ELSE human_dirty END WHERE work_id IN (SELECT id FROM work_items WHERE project_id=?)',(old['style']!=merged['style'],pid))
    return merged


def snapshot(r):
    return Snapshot(r['project_id'],r['stable_id'],r['revision'],r['original_text'],r['translation'])


def row_now(db,eid,pid=None):
    r=db.execute('SELECT * FROM work_items WHERE id=?',(integer(eid,'id',1),)).fetchone()
    if not r or (pid is not None and r['project_id']!=pid):raise KeyError('ไม่พบข้อความในโปรเจกต์นี้')
    return dict(r)


def facts(s,r,db=None):
    if db is None:
        with s.connect() as c:return facts(s,r,c)
    prefs=preferences(s,r['project_id'],db)
    terms=[dict(x) for x in db.execute("SELECT source,target,category FROM cr4_terms WHERE project_id=? AND status='confirmed' ORDER BY source,target",(r['project_id'],)) if x['source'] in r['original_text']]
    context=db.execute('SELECT speaker,scene,verified,evidence FROM cr7_context WHERE work_id=?',(r['id'],)).fetchone()
    context=dict(context) if context else dict(speaker='',scene='',verified=0,evidence='')
    p=db.execute('SELECT source_sha256,selected_font_profile FROM projects WHERE id=?',(r['project_id'],)).fetchone()
    if not p:raise KeyError('ไม่พบโปรเจกต์')
    # File-offset neighbours are evidence candidates, not verified scene order.
    required=r['category'] not in {'menu_system','item_equipment','battle','system','menu','item'}
    enough=not required or bool(context['verified'] and context['evidence'].strip())
    context.update(notes=r['notes'],category=r['category'],context_required=required,
                   context_sufficient=enough,source_image_sha=p['source_sha256'])
    return dict(preferences=prefs,terms=terms,context=context,
                language_hash=fingerprint({'terms':terms,'style':prefs['style']}),
                context_hash=fingerprint(context),rubric=Rubric(tuple(prefs['weights'])))


def identity(s,r,model_digest,prompt_hash,db=None):
    f=facts(s,r,db)
    return ReviewIdentity(snapshot(r),f['rubric'].digest,f['language_hash'],f['context_hash'],model_digest,prompt_hash)


def ensure_current(db,r):
    current=row_now(db,r['id'],r['project_id'])
    if any(current[k]!=r[k] for k in ('revision','original_text','translation','source_fingerprint','notes','category')):
        raise ValueError('ข้อความหรือ revision เปลี่ยนระหว่างทำงาน ไม่เขียนทับฉบับล่าสุด')
    return current


def save_review(s,r,review:Review,model_name,request,usage,jid):
    """Recheck host facts under the SAME transaction as append and current pointer."""
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE');current=ensure_current(db,r)
        expected=identity(s,current,review.identity.model_digest,review.identity.prompt_sha256,db)
        if expected!=review.identity:raise ValueError('บริบท/ศัพท์/เกณฑ์เปลี่ยนระหว่างตรวจ ไม่รับคะแนนเก่า')
        f=facts(s,current,db)
        if not f['context']['context_sufficient'] and review.scores[DIMENSIONS.index('context')] is not None:
            raise ValueError('ยังไม่มีหลักฐานบริบท แต่โมเดลให้คะแนน Context ไม่รับการเดา')
        status='issues' if review.has_blocking_meaning_issue else 'partial' if review.total is None else 'warning' if review.issues else 'reviewed'
        issues=[asdict(x) for x in review.issues]
        payload={'identity':asdict(review.identity),'scores':dict(zip(DIMENSIONS,review.scores)),
                 'total':review.total,'assessed_points':review.assessed_points,'assessed_maximum':review.assessed_maximum,
                 'issues':issues,'suggested_target':review.suggested_target,
                 'self_reported_confidence':review.self_reported_confidence,'confidence_is_calibrated':False,
                 'human_approval':False,'scores_apply_to':'supplied_target_not_suggestion'}
        cur=db.execute('''INSERT INTO cr7_review_events(project_id,work_id,revision,source_text,target_text,language_hash,context_hash,rubric_hash,model_name,model_digest,prompt_hash,status,total,scores_json,issues_json,suggestion,payload_json,request_json,usage_json,job_id,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
           (r['project_id'],r['id'],r['revision'],r['original_text'],r['translation'],f['language_hash'],f['context_hash'],f['rubric'].digest,
            model_name,review.identity.model_digest,review.identity.prompt_sha256,status,review.total,dump(payload['scores']),dump(issues),
            review.suggested_target,dump(payload),dump(request),dump(usage),jid,now()))
        rid=cur.lastrowid
        db.execute('INSERT INTO cr7_state(work_id,review_id,language_dirty) VALUES(?,?,0) ON CONFLICT(work_id) DO UPDATE SET review_id=excluded.review_id,language_dirty=0',(r['id'],rid))
        # Preserve old queues/gates with an honest compatibility verdict, not a quality score.
        verdict='fail' if review.has_blocking_meaning_issue else 'needs_context' if review.total is None else 'ok'
        old_issues=[{'type':{'semantic':'mistranslation','fluency':'grammar','terminology':'terminology','context':'context','style':'register','conciseness':'addition'}[i['category']],
                     'severity':'error' if i['severity'] in {'major','critical'} else 'warning','detail':i['message']} for i in issues]
        if verdict=='needs_context' and not old_issues:old_issues=[{'type':'context','severity':'warning','detail':'ยังประเมินบริบทไม่ครบ คะแนนเป็นบางส่วน'}]
        legacy={'verdict':verdict,'issues':old_issues,'model':model_name,'model_digest':review.identity.model_digest,'revision':r['revision'],'quality_review_id':rid}
        db.execute('UPDATE work_items SET ai_review_revision=?,ai_review_status=?,ai_review_json=?,ai_last_model=?,approved_revision=NULL WHERE id=?',(r['revision'],verdict,dump(legacy),model_name,r['id']))
        return rid


def save_technical(s,r,report):
    if report.get('status') not in {'PASS','FAIL','WARNING','NOT_EVALUATED'}:raise ValueError('สถานะ Technical QA ไม่ถูกต้อง')
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE');ensure_current(db,r)
        cur=db.execute('''INSERT INTO cr7_tech_events(project_id,work_id,revision,source_text,target_text,config_hash,status,report_json,created_at)
           VALUES(?,?,?,?,?,?,?,?,?)''',(r['project_id'],r['id'],r['revision'],r['original_text'],r['translation'],report['config_hash'],report['status'],dump(report),now()))
        db.execute('INSERT INTO cr7_state(work_id,tech_id,tech_dirty) VALUES(?,?,0) ON CONFLICT(work_id) DO UPDATE SET tech_id=excluded.tech_id,tech_dirty=0',(r['id'],cur.lastrowid))
        return cur.lastrowid


def event(s,pid,jid,kind,status,message,eid=None):
    # Only a bounded diagnostic summary. Never store reasoning tokens or credentials.
    with s.connect() as db:db.execute('INSERT INTO cr7_attempts(project_id,work_id,job_id,kind,status,message,created_at) VALUES(?,?,?,?,?,?,?)',(pid,eid,jid,kind,status,str(message)[:1500],now()))


JOIN='''FROM work_items w LEFT JOIN cr7_state st ON st.work_id=w.id
 LEFT JOIN cr7_review_events rv ON rv.id=st.review_id
 LEFT JOIN cr7_tech_events te ON te.id=st.tech_id
 LEFT JOIN cr7_human_events hu ON hu.id=st.human_id
 LEFT JOIN cr5_ready rd ON rd.work_id=w.id AND rd.fingerprint=w.source_fingerprint
 LEFT JOIN projects p ON p.id=w.project_id'''
FIELDS='''w.*,COALESCE(rd.status,'review') AS readiness_status,
 rv.id AS review_id,rv.revision AS review_revision,rv.source_text AS review_source,rv.target_text AS review_target,
 rv.language_hash AS review_language_hash,rv.context_hash AS review_context_hash,rv.rubric_hash AS review_rubric_hash,
 rv.model_name AS review_model,rv.status AS review_state,rv.total AS quality_total,rv.scores_json,rv.issues_json,rv.suggestion,
 rv.created_at AS reviewed_at,te.id AS tech_id,te.revision AS tech_revision,te.source_text AS tech_source,te.target_text AS tech_target,
 te.status AS tech_state,te.report_json AS tech_report,te.config_hash AS tech_config_hash,
 hu.id AS human_id,hu.revision AS human_revision,hu.source_text AS human_source,hu.target_text AS human_target,
 hu.language_hash AS human_language_hash,hu.context_hash AS human_context_hash,hu.action AS human_action,
 hu.actor AS human_actor,hu.reason AS human_reason,hu.created_at AS human_at,
 COALESCE(st.language_dirty,0) AS language_dirty,COALESCE(st.tech_dirty,0) AS tech_dirty,COALESCE(st.human_dirty,0) AS human_dirty'''


def decorate(s,row,db=None):
    r=dict(row);f=facts(s,r,db)
    current=bool(r.get('review_id') and not r['language_dirty'] and r['revision']==r['review_revision'] and r['original_text']==r['review_source'] and r['translation']==r['review_target']
                 and r['review_language_hash']==f['language_hash'] and r['review_context_hash']==f['context_hash'] and r['review_rubric_hash']==f['rubric'].digest)
    human=bool(r.get('human_id') and not r['human_dirty'] and r['revision']==r['human_revision'] and r['original_text']==r['human_source'] and r['translation']==r['human_target']
               and r['human_language_hash']==f['language_hash'] and r['human_context_hash']==f['context_hash'])
    tech=bool(r.get('tech_id') and not r['tech_dirty'] and r['revision']==r['tech_revision'] and r['original_text']==r['tech_source'] and r['translation']==r['tech_target'])
    issue_rows=json.loads(r.get('issues_json') or '[]')
    r['quality']={'state':r['review_state'] if current else 'stale' if r.get('review_id') else 'unreviewed',
                  'score':r['quality_total'] if current else None,'historical_score':r.get('quality_total'),
                  'scores':json.loads(r.get('scores_json') or '{}'),'weights':dict(zip(DIMENSIONS,f['rubric'].weights)),
                  'issues':issue_rows,'current':current,'model':r.get('review_model'),
                  'review_id':r.get('review_id'),'suggestion':r.get('suggestion'),'reviewed_at':r.get('reviewed_at')}
    r['technical']={'state':r['tech_state'] if tech else 'STALE' if r.get('tech_id') else 'NOT_EVALUATED',
                    'current':tech,'report':json.loads(r.get('tech_report') or '{}')}
    r['human']={'state':r['human_action'] if human else 'STALE' if r.get('human_id') else 'LEGACY_REVIEWED' if r.get('linguistic_revision')==r['revision'] else 'NOT_REVIEWED',
                'current':human,'actor':r.get('human_actor'),'reason':r.get('human_reason'),'created_at':r.get('human_at')}
    r['context']=f['context'];r['confirmed_terms']=f['terms']
    r['meaning_blocked']=current and any(i['severity'] in {'major','critical'} for i in issue_rows)
    r['technical_fail']=tech and r['tech_state']=='FAIL'
    # Avoid returning full retained request payload/history in every table row.
    keep={k:r[k] for k in ('id','stable_id','project_id','source_file','file_offset','physical_offset','encoding','original_text','translation','source_fingerprint','byte_length','terminator','category','notes','confirmed','revision','approved_revision','linguistic_revision','ai_review_revision','ai_review_status','max_bytes','max_pixel_width','max_lines','readiness_status','quality','technical','human','context','confirmed_terms','meaning_blocked','technical_fail') if k in r}
    return keep


def detail(s,pid,eid):
    with s.connect() as db:
        row=db.execute('SELECT '+FIELDS+' '+JOIN+' WHERE w.project_id=? AND w.id=?',(pid,integer(eid,'id',1))).fetchone()
        if not row:raise KeyError('ไม่พบข้อความในโปรเจกต์')
        return decorate(s,row,db)


def page(s,pid,after=0,query='',score='',review='',tech='',source_file=''):
    integer(after,'after',0);s.get_project(pid)
    if not all(isinstance(x,str) for x in (query,score,review,tech,source_file)):raise ValueError('ตัวกรองต้องเป็นข้อความ')
    if len(query)>300 or len(source_file)>1024:raise ValueError('ตัวกรองยาวเกินขอบเขต')
    if score not in {'','lt70','70_79','80_89','ge90','unassessed'}:raise ValueError('ช่วงคะแนนไม่ถูกต้อง')
    if review not in {'','untranslated','needs_review','ai_reviewed','human_approved','unreviewed','stale'}:raise ValueError('ตัวกรองการตรวจไม่ถูกต้อง')
    if tech not in {'','fail','unknown'}:raise ValueError('ตัวกรองเทคนิคไม่ถูกต้อง')
    where='w.project_id=? AND w.id>?';args=[pid,after]
    if query:
        where+=' AND (instr(lower(w.original_text),lower(?))>0 OR instr(lower(w.translation),lower(?))>0 OR instr(lower(w.source_file),lower(?))>0 OR instr(w.stable_id,?)>0)';args += [query]*4
    if source_file:where+=' AND w.source_file=?';args.append(source_file)
    result=[];cursor=after;inspected=0
    with s.connect() as db:
        rows=db.execute('SELECT '+FIELDS+' '+JOIN+' WHERE '+where+' ORDER BY w.id LIMIT 2000',args).fetchall()
        for row in rows:
            cursor=row['id'];inspected+=1;r=decorate(s,row,db);q=r['quality'];n=q['score']
            if score=='unassessed' and n is not None:continue
            if score and score!='unassessed' and (n is None or not {'lt70':n<70,'70_79':70<=n<80,'80_89':80<=n<90,'ge90':n>=90}[score]):continue
            if tech=='fail' and not r['technical_fail']:continue
            if tech=='unknown' and r['technical']['state'] not in {'NOT_EVALUATED','STALE','WARNING'}:continue
            if review=='untranslated' and r['translation']:continue
            if review=='human_approved' and r['human']['state']!='APPROVED':continue
            if review=='ai_reviewed' and not q['current']:continue
            if review=='unreviewed' and q['state']!='unreviewed':continue
            if review=='stale' and q['state']!='stale':continue
            if review=='needs_review' and not (r['meaning_blocked'] or r['technical_fail'] or q['state'] in {'issues','partial','stale'} or (n is not None and n<90) or r['human']['state'] in {'REJECTED','RETURNED','STALE'}):continue
            result.append(r)
            if len(result)==100:break
    return {'items':result,'next_cursor':cursor if rows and (len(rows)==2000 or len(result)==100) else None,
            'inspected':inspected,'page_limit':100,'total_work_items':s.get_project(pid)['entry_count'],
            'counts_are_not_game_coverage':True}


def history(s,pid,eid):
    with s.connect() as db:
        row_now(db,eid,pid)
        reviews=[dict(r) for r in db.execute('SELECT id,revision,status,total,model_name,model_digest,rubric_hash,prompt_hash,payload_json,created_at FROM cr7_review_events WHERE work_id=? ORDER BY id DESC LIMIT 30',(eid,))]
        human=[dict(r) for r in db.execute('SELECT revision,action,actor,reason,created_at FROM cr7_human_events WHERE work_id=? ORDER BY id DESC LIMIT 30',(eid,))]
        suggestions=[dict(r) for r in db.execute('SELECT review_id,revision,action,actor,created_at FROM cr7_suggestion_events WHERE work_id=? ORDER BY id DESC LIMIT 30',(eid,))]
        attempts=[dict(r) for r in db.execute('SELECT kind,status,message,created_at FROM cr7_attempts WHERE work_id=? ORDER BY id DESC LIMIT 10',(eid,))]
    return dict(reviews=reviews,human=human,suggestions=suggestions,attempts=attempts,scope='latest_bounded_events; older events remain in database')


def human_action(s,pid,eid,data,*,actor):
    """Called ONLY from an explicit token-checked UI endpoint, never model output."""
    s.ensure_editable(pid)
    if not actor or actor!='local_user':raise ValueError('การอนุมัติต้องมาจากผู้ใช้ในหน้าเว็บ')
    action=data.get('action');expected=integer(data.get('revision'),'revision',1)
    if action not in {'APPROVED','REJECTED','RETURNED','ACCEPT_SUGGESTION','REJECT_SUGGESTION','CONTEXT'}:raise ValueError('คำสั่งตรวจไม่ถูกต้อง')
    if data.get('confirm')!='USER_ACTION':raise ValueError('ต้องยืนยันการกระทำโดยผู้ใช้')
    reason=data.get('reason','')
    if not isinstance(reason,str) or len(reason)>2000:raise ValueError('เหตุผลไม่ถูกต้อง')
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE');r=row_now(db,eid,pid)
        if r['revision']!=expected:raise ValueError('revision เปลี่ยน โหลดรายการล่าสุดก่อนตัดสินใจ')
        f=facts(s,r,db)
        if action in {'ACCEPT_SUGGESTION','REJECT_SUGGESTION'}:
            rid=integer(data.get('review_id'),'review_id',1)
            rv=db.execute('SELECT * FROM cr7_review_events WHERE id=? AND work_id=?',(rid,eid)).fetchone()
            state=db.execute('SELECT review_id,language_dirty FROM cr7_state WHERE work_id=?',(eid,)).fetchone()
            if not rv or not state or state['review_id']!=rid or state['language_dirty'] or rv['revision']!=expected or rv['source_text']!=r['original_text'] or rv['target_text']!=r['translation'] or rv['language_hash']!=f['language_hash'] or rv['context_hash']!=f['context_hash'] or rv['rubric_hash']!=f['rubric'].digest:
                raise ValueError('ข้อเสนอเป็นของข้อความ/บริบท/ศัพท์ฉบับเก่า ไม่ใช้ทับงานล่าสุด')
            if not rv['suggestion']:raise ValueError('ยังไม่มีข้อเสนอคำแปล')
            if db.execute('SELECT 1 FROM cr7_suggestion_events WHERE review_id=? AND action=?',(rid,action)).fetchone():raise ValueError('บันทึกการตัดสินใจนี้แล้ว')
            if action=='ACCEPT_SUGGESTION':
                if rv['suggestion']==r['translation']:raise ValueError('ข้อเสนอไม่เปลี่ยนคำแปล')
                db.execute('INSERT INTO edit_history(work_id,revision,snapshot_json,changed_at) VALUES(?,?,?,?)',(eid,expected,dump(r),now()))
                db.execute("UPDATE work_items SET translation=?,revision=revision+1,qa_status='pending',qa_json='{}',approved_revision=NULL,linguistic_revision=NULL,ai_review_revision=NULL,ai_review_status='pending',ai_review_json='{}',ai_polished_revision=NULL,updated_at=? WHERE id=?",(rv['suggestion'],now(),eid))
            db.execute('INSERT INTO cr7_suggestion_events(review_id,work_id,revision,action,actor,created_at) VALUES(?,?,?,?,?,?)',(rid,eid,expected,action,actor,now()))
        elif action=='CONTEXT':
            speaker=data.get('speaker','');scene=data.get('scene','');verified=data.get('verified',False)
            if any(not isinstance(v,str) or len(v)>200 for v in (speaker,scene)) or type(verified)is not bool:raise ValueError('ข้อมูลผู้พูด/ฉากไม่ถูกต้อง')
            if verified and not reason.strip():raise ValueError('ระบุหลักฐานบริบทก่อนยืนยัน ไม่ใช้เพียงชื่อโมเดล')
            db.execute('INSERT INTO cr7_context VALUES(?,?,?,?,?,?) ON CONFLICT(work_id) DO UPDATE SET speaker=excluded.speaker,scene=excluded.scene,verified=excluded.verified,evidence=excluded.evidence,updated_at=excluded.updated_at',(eid,speaker,scene,int(verified),reason,now()))
            db.execute('INSERT INTO edit_history(work_id,revision,snapshot_json,changed_at) VALUES(?,?,?,?)',(eid,expected,dump(r),now()))
            db.execute("UPDATE work_items SET revision=revision+1,ai_review_revision=NULL,ai_review_status='pending',ai_polished_revision=NULL,approved_revision=NULL,linguistic_revision=NULL,qa_status='pending',updated_at=? WHERE id=?",(now(),eid))
        else:
            if action=='APPROVED' and not r['translation'].strip():raise ValueError('ยังไม่มีคำแปลให้อนุมัติภาษา')
            cur=db.execute('''INSERT INTO cr7_human_events(project_id,work_id,revision,source_text,target_text,language_hash,context_hash,action,actor,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (pid,eid,expected,r['original_text'],r['translation'],f['language_hash'],f['context_hash'],action,actor,reason,now()))
            db.execute('INSERT INTO cr7_state(work_id,human_id,human_dirty) VALUES(?,?,0) ON CONFLICT(work_id) DO UPDATE SET human_id=excluded.human_id,human_dirty=0',(eid,cur.lastrowid))
            # Language review is NOT a build approval; it may coexist with a technical FAIL.
            db.execute('UPDATE work_items SET linguistic_revision=?,approved_revision=NULL WHERE id=?',(expected if action=='APPROVED' else None,eid))
    return detail(s,pid,eid)


def latest_run(s,pid):
    with s.connect() as db:
        r=db.execute('SELECT * FROM cr7_runs WHERE project_id=? ORDER BY rowid DESC LIMIT 1',(pid,)).fetchone()
        if not r:return None
        r=dict(r);r.pop('config_json',None);r.pop('policy_json',None)
        r['counts']=dict(db.execute('SELECT status,COUNT(*) FROM cr7_queue WHERE run_id=? GROUP BY status',(r['id'],)).fetchall())
        return r


def dashboard(s,pid):
    """SQL over work/review rows only; never aggregate legacy raw candidates."""
    prefs=preferences(s,pid);rh=Rubric(tuple(prefs['weights'])).digest
    valid="rv.id IS NOT NULL AND st.language_dirty=0 AND rv.revision=w.revision AND rv.source_text=w.original_text AND rv.target_text=w.translation AND rv.rubric_hash=?"
    with s.connect() as db:
        rows=db.execute('''SELECT w.id,w.translation,w.revision,w.original_text,w.linguistic_revision,
           rv.id AS rid,rv.total,rv.status,rv.revision AS rr,rv.source_text AS rs,rv.target_text AS rt,
           rv.rubric_hash,st.language_dirty,te.status AS ts,te.revision AS tr,st.tech_dirty,
           hu.action AS ha,hu.revision AS hr,st.human_dirty
           '''+JOIN+' WHERE w.project_id=?',(pid,))
        count={'work_items':0,'translated':0,'reviewed_current':0,'unreviewed':0,'stale':0,'partial':0,
               'ge90':0,'80_89':0,'70_79':0,'lt70':0,'meaning_issues':0,'technical_errors':0,
               'technical_unknown':0,'human_approved':0,'legacy_human_reviewed':0,'scored_current':0}
        total_score=0
        for r in rows:
            count['work_items']+=1;count['translated']+=bool(r['translation'])
            current=bool(r['rid'] and not r['language_dirty'] and r['rr']==r['revision'] and r['rs']==r['original_text'] and r['rt']==r['translation'] and r['rubric_hash']==rh)
            if current:
                count['reviewed_current']+=1;count['meaning_issues']+=r['status']=='issues';count['partial']+=r['total'] is None
                if r['total'] is not None:
                    n=r['total'];count['scored_current']+=1;total_score+=n
                    count['ge90' if n>=90 else '80_89' if n>=80 else '70_79' if n>=70 else 'lt70']+=1
            else:count['stale' if r['rid'] else 'unreviewed']+=1
            tech_current=bool(r['tr']==r['revision'] and not r['tech_dirty'])
            count['technical_errors']+=tech_current and r['ts']=='FAIL'
            count['technical_unknown']+=not tech_current or r['ts']!='PASS'
            count['human_approved']+=bool(r['ha']=='APPROVED' and r['hr']==r['revision'] and not r['human_dirty'])
            count['legacy_human_reviewed']+=bool(not r['ha'] and r['linguistic_revision']==r['revision'])
    count['average_score']=round(total_score/count['scored_current'],1) if count['scored_current'] else None
    count['average_denominator']=count['scored_current']
    count['not_a_build_gate']=True;count['rubric_hash']=rh;count['last_run']=latest_run(s,pid)
    return count


def guard_build(s,pid):
    """Additional known-issue gate only. Existing binary dry-run remains mandatory."""
    with s.connect() as db:
        rows=db.execute('SELECT '+FIELDS+' '+JOIN+' WHERE w.project_id=? AND w.confirmed=1',(pid,)).fetchall()
        for row in rows:
            r=decorate(s,row,db)
            if r['meaning_blocked']:raise ValueError(f"รายการ #{r['id']} ยังมีข้อผิดพลาดความหมายสำคัญจาก Quality Review คะแนนรวมไม่ปลดล็อกประกอบ")
            if r['technical_fail']:raise ValueError(f"รายการ #{r['id']} ยังมี Technical FAIL ของฉบับปัจจุบัน")
            if r['human']['state'] in {'REJECTED','RETURNED'}:raise ValueError(f"รายการ #{r['id']} ถูกผู้ใช้ส่งกลับตรวจ ไม่อนุมัติประกอบ")
