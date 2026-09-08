"""Exact, fail-closed hooks against the inspected original v0.6.0 source.

Only these small anchors change existing files. All new implementation lives in
app/quality_review and two additional static files. No backend rewrite.
"""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path

VERSION='0.6.1-rc1'
BASE_HASHES={
 'app/__init__.py':'7080f58cb9c2fef8f8f0680c37a61bd4503726c43de73366087991604f131616',
 'app/studio_storage.py':'4b42a6fe45734a11f8c65f2522cdedde3d9f8b3a7317e3d929bccf261c1bb568',
 'app/server.py':'f919900d33622fc018b734aa9495681897f0834484fb142e4aa3e58b5010bf2c',
 'app/pipeline_jobs.py':'ed0af727be1b16d7972de2467f05b043b717c4600ea909743808482100c47b84',
 'app/ai_pipeline.py':'2a9c3fe0650bd484ffa24b70c6b8715af8d386a288f94e17ce52d4e84cdf1a7e',
 'app/safe_build.py':'9f83522df885c34d31c3e2a267d016a3c72e312a1b1db1f2923e9d2fcbe57217',
 'app/static/index.html':'3250cef6d0537451f2d525f10314a009996c5679feaec5b7378e9568e5b0420b',
}
HOOKS={
 'app/__init__.py':[( '__version__ = "0.6.0"', f'__version__ = "{VERSION}"')],
 'app/studio_storage.py':[(
  '        init_workbench(self)\n',
  '        init_workbench(self)\n        from .quality_review.repo import init as init_quality_review\n        init_quality_review(self)\n')],
 'app/server.py':[(
  'from .ollama_runtime import ManagedOllama\n',
  'from .ollama_runtime import ManagedOllama\nfrom .quality_review import routes as quality_routes\n'),(
  "        arg=lambda key,default='':q.get(key,[default])[0]\n",
  "        arg=lambda key,default='':q.get(key,[default])[0]\n        if quality_routes.get(self,parts,arg):return\n"),(
  "        with self.server.mutation_lock:\n            if parts==['api','ai','discover']:",
  "        with self.server.mutation_lock:\n            if quality_routes.post(self,parts,data):return\n            if parts==['api','ai','discover']:")],
 'app/pipeline_jobs.py':[(
  "        if kind=='curate':curate_legacy(t,options)\n",
  "        if kind in {'quality_auto','quality_review','quality_improve','quality_technical'}:\n            from .quality_review.jobs import run as run_quality\n            run_quality(t,kind,options)\n        elif kind=='curate':curate_legacy(t,options)\n")],
 'app/ai_pipeline.py':[(
  "        store.suggest_terms(db,pid,value['terms'],jid)\n",
  "        from .quality_review.jobs import sync_queue_after_legacy\n        sync_queue_after_legacy(db,jid)\n        store.suggest_terms(db,pid,value['terms'],jid)\n")],
 'app/safe_build.py':[(
  'def run_build(t,kind,options):\n',
  'def run_build(t,kind,options):\n    from .quality_review.repo import guard_build as guard_quality\n    guard_quality(t.storage,t.pid)\n')],
 'app/static/index.html':[(
  'ContinueRetro Studio · v0.6.0',f'ContinueRetro Studio · v{VERSION}'),(
  '</head>','<link href="/quality-workbench.css" rel="stylesheet"/></head>'),(
  '<script src="/workbench-ui.js"></script>',
  '<script src="/workbench-ui.js"></script><script src="/quality-workbench.js"></script>')],
}


def sha(data):return hashlib.sha256(data).hexdigest()


def transform(relative,raw):
    if relative not in BASE_HASHES:raise ValueError('ไม่ใช่ไฟล์ที่อนุญาตให้แพตช์')
    if sha(raw)!=BASE_HASHES[relative]:raise ValueError('ซอร์สไม่ตรง v0.6.0 ที่ตรวจแล้ว: '+relative+' — หยุด ไม่เขียนทับ')
    text=raw.decode('utf-8')
    for before,after in HOOKS[relative]:
        if text.count(before)!=1:raise ValueError('จุดเชื่อมไม่ตรงหรือซ้ำ: '+relative)
        text=text.replace(before,after,1)
    if relative.endswith('.py'):ast.parse(text,filename=relative)
    return text.encode('utf-8')


def verify_baseline(app):
    app=Path(app);summary={}
    for relative,expected in BASE_HASHES.items():
        path=app/relative
        if path.is_symlink() or not path.is_file():raise ValueError('ไฟล์ฐานหายหรือเป็น symlink: '+relative)
        raw=path.read_bytes()
        if sha(raw)!=expected:raise ValueError('แอปไม่ตรงฐาน v0.6.0: '+relative+' — เก็บรุ่นเดิมไว้ ไม่แพตช์โดยเดา')
        # Validate every anchor before any retained source file is changed.
        changed=transform(relative,raw)
        summary[relative]={'before':expected,'after':sha(changed)}
    return summary


def apply_to_stage(app):
    app=Path(app);summary=verify_baseline(app)
    for relative in BASE_HASHES:
        p=app/relative;p.write_bytes(transform(relative,p.read_bytes()))
    return summary
