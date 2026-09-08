#!/usr/bin/env python3
"""Guarded incremental update for the exact inspected Studio v0.6.0 installation.

Stages on the same external workspace, runs its actual original regression tests,
adds tested review modules, tests again, then backs up and atomically activates.
Never downloads models, reads ROM/BIOS/font contents, deletes WAL files or uploads.
"""
from __future__ import annotations
import argparse
from contextlib import closing
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import uuid
from patch_v060 import VERSION,verify_baseline,apply_to_stage,BASE_HASHES

HERE=Path(__file__).resolve().parent


class UpdateError(RuntimeError):pass


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()


def atomic_json(path,value):
    tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    tmp.replace(path)


def validate_package():
    path=HERE/'PACKAGE_MANIFEST.json'
    if not path.is_file():raise UpdateError('แพ็กอัปเดตไม่ครบ: ไม่มี PACKAGE_MANIFEST.json')
    m=json.loads(path.read_text('utf-8'))
    for rel,h in m['files'].items():
        p=HERE/rel
        if p.is_symlink() or not p.is_file() or HERE not in p.resolve().parents or digest(p)!=h:
            raise UpdateError('ไฟล์แพ็กอัปเดตไม่ตรง manifest: '+rel)
    return m


def choose_root():
    if sys.platform=='darwin':
        r=subprocess.run(['osascript','-e','POSIX path of (choose folder with prompt "เลือกโฟลเดอร์ ContinueRetro-PS1 เดิมบนไดรฟ์ภายนอก ไม่ใช่ ZIP")'],capture_output=True,text=True,check=False)
        if r.returncode or not r.stdout.strip():raise UpdateError('ยกเลิกการเลือกโฟลเดอร์')
        return Path(r.stdout.strip())
    value=input('พาธ ContinueRetro-PS1 เดิม: ').strip().strip('"')
    if not value:raise UpdateError('ยกเลิก')
    return Path(value)


def app_size(app):
    size=0
    for p in app.rglob('*'):
        if p.is_symlink():raise UpdateError('ตัวแอปมี symlink ที่ต้องตรวจเองก่อนอัปเดต: '+str(p.relative_to(app)))
        if p.is_file():size+=p.stat().st_size
    return size


def copy_database(source,output):
    if output.exists():raise UpdateError('ไฟล์สำรองชื่อซ้ำ ไม่เขียนทับ')
    with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(output)) as dst:
        last=[-1]
        def progress(status,remaining,total):
            percent=(total-remaining)*100//max(1,total)
            if percent//10!=last[0]:print(f'  สำรองฐานข้อมูล {percent}% — ห้ามถอดไดรฟ์',flush=True);last[0]=percent//10
        src.backup(dst,pages=1024,progress=progress)
        if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise UpdateError('ตรวจสำเนาฐานข้อมูลไม่ผ่าน')
    with output.open('rb') as f:os.fsync(f.fileno())


def run_command(args,*,cwd,env,log,timeout=900):
    print('กำลังทดสอบ — ดูความคืบหน้าใน '+str(log),flush=True)
    with log.open('xb') as out:
        p=subprocess.Popen(args,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=p.wait(timeout=timeout)
        except BaseException:
            try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=10)
            except (ProcessLookupError,subprocess.TimeoutExpired):
                if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
            raise
    if code:
        tail=log.read_text('utf-8',errors='replace')[-6000:]
        print(tail,file=sys.stderr)
        raise UpdateError('ชุดตรวจไม่ผ่าน ยังไม่อนุญาตให้ใช้รุ่นใหม่: '+str(log))


def update(root,*,no_launch=False,prepare_only=False):
    manifest=validate_package()
    root=Path(root).expanduser().resolve(strict=True)
    app=root/'apps/continue-retro-studio';db=root/'PRIVATE/studio/studio.sqlite3'
    if not app.is_dir() or not db.is_file():raise UpdateError('ไม่พบแอปและฐานข้อมูลเดิม เลือก ContinueRetro-PS1 ที่ใช้อยู่ ไม่สร้างโปรเจกต์ใหม่')
    identity=(root.stat().st_dev,root.stat().st_ino)
    def check_drive():
        if not root.is_dir() or (root.stat().st_dev,root.stat().st_ino)!=identity:raise UpdateError('ไดรฟ์เปลี่ยนหรือหลุด ไม่สร้างพาธแทน')
    lock_path=root/'PRIVATE/studio/server.lock'
    with lock_path.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise UpdateError('Studio ยังเปิดอยู่ กรุณากด Control+C ใน Terminal ของ Studio ก่อน ไม่ต้องหยุด Ollama') from exc
        check_drive();changes=verify_baseline(app)
        payload=HERE/'payload'
        if not payload.is_dir():raise UpdateError('แพ็กไม่มี payload')
        old_size=app_size(app);wal=Path(str(db)+'-wal');database_size=db.stat().st_size+(wal.stat().st_size if wal.exists() else 0)
        if shutil.disk_usage(root).free<old_size*2+database_size+512*1024*1024:raise UpdateError('พื้นที่ไม่พอสำหรับสำรองแอป ฐานข้อมูล และพื้นที่เผื่อ 512 MiB')
        stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
        journal_dir=root/'PRIVATE/checkpoints'/(f'studio-{VERSION}-'+stamp);journal_dir.mkdir(parents=True,exist_ok=False)
        stage=root/'apps'/('.continue-retro-studio-stage-'+stamp)
        test_tmp=journal_dir/'test-tmp';test_tmp.mkdir()
        journal={'target_version':VERSION,'root':str(root),'stage':str(stage),'phase':'staging',
                 'baseline_changes':changes,'user_game_files_changed':False,'font_assets_changed':False,
                 'models_downloaded':False,'weights_trained':False,'app_activated':False,
                 'backup_app':str(journal_dir/'original-app'),'backup_database':str(journal_dir/'original-database.sqlite3')}
        def record(phase):
            check_drive();journal['phase']=phase;journal['updated_at']=datetime.now(timezone.utc).isoformat();atomic_json(journal_dir/'UPDATE_STATE.json',journal)
        record('copying_original_app_to_stage')
        shutil.copytree(app,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        env=os.environ.copy();env.update(PYTHONPATH=str(stage),PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(test_tmp))
        suite_runner=HERE/'run_suite.py'
        try:
            record('testing_original_staged_app')
            run_command([sys.executable,str(suite_runner),'--app',str(stage),'--pattern','test_v*.py','--minimum','100','--report',str(journal_dir/'baseline-before.json')],cwd=stage,env=env,log=journal_dir/'baseline-before.log')
            check_drive();record('applying_small_source_hooks')
            apply_to_stage(stage)
            for source in payload.rglob('*'):
                if source.is_symlink():raise UpdateError('payload มี symlink ไม่รับ')
                if not source.is_file():continue
                rel=source.relative_to(payload);dest=stage/rel
                if dest.exists():raise UpdateError('ไฟล์เพิ่มชื่อชนกับของเดิม ไม่เขียนทับ: '+str(rel))
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            record('compiling_staged_update')
            run_command([sys.executable,'-m','compileall','-q','app'],cwd=stage,env=env,log=journal_dir/'compile.log')
            # The baseline test list must remain unchanged. New v061 tests run separately.
            new_tests=list((stage/'tests').glob('test_v061*.py'))
            held=[]
            for p in new_tests:
                target=p.with_suffix('.py.hold');p.rename(target);held.append((p,target))
            try:
                run_command([sys.executable,str(suite_runner),'--app',str(stage),'--pattern','test_v*.py','--minimum','100','--report',str(journal_dir/'baseline-after.json')],cwd=stage,env=env,log=journal_dir/'baseline-after.log')
            finally:
                for p,target in held:
                    if target.exists():target.rename(p)
            before=json.loads((journal_dir/'baseline-before.json').read_text('utf-8'));after=json.loads((journal_dir/'baseline-after.json').read_text('utf-8'))
            if sorted(before['test_ids'])!=sorted(after['test_ids']):raise UpdateError('รายการทดสอบฐานเดิมเปลี่ยนหลังอัปเดต ไม่อนุญาตให้ลดชุดทดสอบ')
            record('testing_actual_app_integration')
            run_command([sys.executable,str(suite_runner),'--app',str(stage),'--pattern','test_v061*.py','--minimum','10','--report',str(journal_dir/'new-integration.json')],cwd=stage,env=env,log=journal_dir/'new-integration.log')
            # Validate newly routed methods on a synthetic workspace before touching user DB.
            node=shutil.which('node')
            if node:
                run_command([node,'--check','app/static/quality-workbench.js'],cwd=stage,env=env,log=journal_dir/'javascript-syntax.log')
            journal['validation']={'baseline_before':before['tests'],'baseline_after':after['tests'],
                                   'new_integration':json.loads((journal_dir/'new-integration.json').read_text('utf-8'))['tests'],
                                   'syntax_checked_in_ci':True,'javascript_checked_locally':bool(node),
                                   'native_emulator_tested':False,'live_ollama_tested':False}
            if prepare_only:
                record('validated_stage_not_activated');print('ตรวจสำเนาทดสอบผ่าน ยังไม่เปลี่ยนแอป: '+str(journal_dir),flush=True);return journal
            record('backing_up_user_database');backup=journal_dir/'original-database.sqlite3';copy_database(db,backup)
            journal['backup_database_sha256']=digest(backup);record('ready_to_activate')
            archived=False;activated=False
            try:
                # Rename in the same external filesystem; original app remains recoverable.
                record('moving_old_app_to_backup');app.rename(journal_dir/'original-app');archived=True
                record('activating_validated_stage');stage.rename(app);activated=True
                env['PYTHONPATH']=str(app)
                record('initializing_additive_tables')
                run_command([sys.executable,'-c','from app.studio_storage import Storage; import sys; Storage(sys.argv[1]); print("ADDITIVE_SCHEMA_READY")',str(root)],cwd=app,env=env,log=journal_dir/'migration.log')
                install_record=root/'PRIVATE/studio/install-record.json'
                old=json.loads(install_record.read_text('utf-8')) if install_record.exists() else {}
                old.update(version=VERSION,last_incremental_update=str(journal_dir),previous_version='0.6.0')
                atomic_json(install_record,old)
                journal['app_activated']=True;record('activated')
            except BaseException:
                # No Studio server was launched, and the workspace lock is still held.
                # Keep failed new source for diagnostics, restore the original application.
                try:
                    check_drive()
                    if activated and app.is_dir():app.rename(journal_dir/'failed-new-app')
                    if archived and not app.exists():(journal_dir/'original-app').rename(app)
                    if activated:
                        with closing(sqlite3.connect(backup)) as src,closing(sqlite3.connect(db)) as dst:src.backup(dst)
                    journal['app_activated']=False;record('rolled_back')
                except BaseException as rollback_error:
                    print('หยุด: การย้อนกลับยังไม่ครบ ห้ามลบไฟล์สำรอง โปรดดู '+str(journal_dir)+' / '+str(rollback_error),file=sys.stderr)
                raise
        except BaseException:
            if root.is_dir():
                try:record('failed_before_activation' if not journal['app_activated'] and journal.get('phase') not in {'rolled_back'} else journal['phase'])
                except OSError:pass
            print('เก็บหลักฐานและสำเนาไว้ที่ '+str(journal_dir),file=sys.stderr)
            raise
        print('\nอัปเดต '+VERSION+' สำเร็จ โดยชุดทดสอบแอปเดิมและจุดเชื่อมใหม่ผ่านบนเครื่องนี้',flush=True)
        print('รายงาน: '+str(journal_dir),flush=True)
        print('ไม่ใช่ผลทดสอบโมเดลจริง/เกม London และไม่มีการฝึกน้ำหนักโมเดล',flush=True)
    if not no_launch and sys.platform=='darwin':
        subprocess.Popen(['open',str(root/'START_CONTINUE_RETRO_STUDIO.command')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return journal


def main():
    p=argparse.ArgumentParser(description='อัปเดตเพิ่มระบบ Review/UI แบบรักษาข้อมูลเดิมและทดสอบก่อนเปิดใช้')
    p.add_argument('--root',type=Path);p.add_argument('--no-launch',action='store_true');p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args()
    try:
        if sys.version_info<(3,10):raise UpdateError('ต้องใช้ Python 3.10 ขึ้นไป เช่น Python ที่เปิด Studio เดิม')
        update(a.root or choose_root(),no_launch=a.no_launch,prepare_only=a.prepare_only);return 0
    except KeyboardInterrupt:
        print('หยุดตามคำขอ ตรวจ UPDATE_STATE.json ก่อนทำซ้ำ ไม่ลบฐานข้อมูลหรือ WAL',file=sys.stderr);return 130
    except (UpdateError,ValueError,OSError,sqlite3.Error,subprocess.SubprocessError) as exc:
        print('ยังไม่เปิดใช้รุ่นใหม่: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
