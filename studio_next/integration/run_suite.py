"""Run a named actual-app test suite and produce a machine-readable result.
No silent skips, empty test success, real model claims or game QA claims.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import unittest


def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item.id()


def main():
    p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True);p.add_argument('--pattern',required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--minimum',type=int,default=1);a=p.parse_args()
    app=a.app.resolve();sys.path.insert(0,str(app));sys.path.insert(0,str(app/'tests'))
    suite=unittest.defaultTestLoader.discover(str(app/'tests'),pattern=a.pattern)
    ids=list(flatten(suite));result=unittest.TextTestRunner(verbosity=2).run(suite)
    success=result.wasSuccessful() and result.testsRun>=a.minimum and not result.skipped
    report={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'skipped':[(str(t),reason) for t,reason in result.skipped],'successful':success,
            'test_ids':ids,'scope':'actual_staged_app_with_authored_game_and_HTTP_fixtures',
            'real_game_tested':False,'live_model_tested':False,'human_approval_created_in_user_database':False}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if success else 1


if __name__=='__main__':raise SystemExit(main())
