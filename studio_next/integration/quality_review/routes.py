"""Small HTTP integration hooks for the inspected v0.6.0 Handler.

The caller runs valid_request/body and the existing mutation lock first. This
module rechecks write authorization so an accidental future call cannot bypass
Origin/Host/token checks. No human action is reachable from a model response.
"""
from __future__ import annotations
from . import repo, jobs


def get(handler,parts,arg):
    if len(parts)!=4 or parts[:2]!=['api','projects']:return False
    pid,action=parts[2:];s=handler.server.storage
    if action not in {'quality-page','quality-detail','quality-history','quality-dashboard','quality-preferences','quality-log','quality-memory'}:return False
    s.get_project(pid)
    if action=='quality-page':
        value=repo.page(s,pid,int(arg('after',0)),arg('q'),arg('score'),arg('review'),arg('tech'),arg('source_file'))
    elif action=='quality-detail':value={'entry':repo.detail(s,pid,int(arg('id',0)))}
    elif action=='quality-history':value=repo.history(s,pid,int(arg('id',0)))
    elif action=='quality-dashboard':value=repo.dashboard(s,pid)
    elif action=='quality-preferences':value={'preferences':repo.preferences(s,pid)}
    elif action=='quality-memory':
        eid=int(arg('id',0));r=s.work_item(eid)
        if r['project_id']!=pid:raise ValueError('ข้อความอยู่คนละโปรเจกต์')
        from app.ai_store import memory_for
        value={'items':memory_for(s,pid,r['original_text'],eid,limit=3),
               'retrieval':'existing_character_ngram_search',
               'similarity_is_not_translation_accuracy':True,
               'embedding_for_translation_memory':'not_integrated_in_this_milestone'}
    else:
        after=repo.integer(int(arg('after',0)),'after',0)
        with s.connect() as db:
            rows=[dict(r) for r in db.execute('SELECT id,work_id,job_id,kind,status,message,created_at FROM cr7_attempts WHERE project_id=? AND id>? ORDER BY id LIMIT 100',(pid,after))]
        value={'items':rows,'next_cursor':rows[-1]['id'] if len(rows)==100 else None,'clear_view_does_not_delete_audit':True}
    handler.respond({'ok':True,**value});return True


def post(handler,parts,data):
    if len(parts)!=4 or parts[:2]!=['api','projects']:return False
    pid,action=parts[2:];s=handler.server.storage
    if action=='jobs':
        if data.get('kind') not in repo.KINDS:return False
        handler.valid_request(True)
        s.get_project(pid)
        options=data.get('options',{})
        if not isinstance(options,dict):raise ValueError('options ต้องเป็น object')
        # JobManager supplies the existing single-heavy-job/process/cancel discipline.
        job=handler.server.jobs.start(pid,data['kind'],options)
        handler.respond({'ok':True,'job':job},202);return True
    if action not in {'quality-preflight','quality-preferences','quality-action'}:return False
    handler.valid_request(True);s.get_project(pid)
    if action=='quality-preflight':
        value=jobs.preflight(s,pid,data.get('kind','quality_review'),data.get('scope'))
    elif action=='quality-preferences':
        value={'preferences':repo.save_preferences(s,pid,data)}
    else:
        eid=repo.integer(data.get('id'),'id',1)
        value={'entry':repo.human_action(s,pid,eid,data,actor='local_user')}
        if data.get('action')=='APPROVED':
            # Human language approval and TM eligibility remain separate. A missing
            # codec does not invalidate language approval; unsafe tokens exclude TM.
            r=s.work_item(eid)
            if r['confirmed']:
                try:
                    from app.ai_store import learn
                    learn(s,eid,r['revision'])
                    value['memory_saved']=True
                except ValueError as exc:
                    value['memory_saved']=False;value['memory_warning']=str(exc)
            else:
                value['memory_saved']=False
                value['memory_warning']='อนุมัติภาษาแล้ว แต่ยังไม่เพิ่ม TM เพราะต้นฉบับยังไม่ได้ยืนยันโดยคน'
    handler.respond({'ok':True,**value});return True
