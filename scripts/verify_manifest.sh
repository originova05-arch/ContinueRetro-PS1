#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
python3 - "$PROJECT_ROOT" <<'PY'
import hashlib, pathlib, sys
root=pathlib.Path(sys.argv[1]); mf=root/'SHA256SUMS.txt'
if not mf.exists():
    print('MISSING SHA256SUMS.txt', file=sys.stderr); raise SystemExit(2)
fail=0; checked=0
for line in mf.read_text(encoding='utf-8').splitlines():
    if not line.strip(): continue
    try: expected, rel=line.split(None,1)
    except ValueError: print('BAD MANIFEST LINE:', line, file=sys.stderr); fail=1; continue
    rel=rel.strip()
    if rel.startswith('*'): rel=rel[1:]
    p=root/rel
    if not p.is_file(): print('MISSING', rel); fail=1; continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    checked+=1
    if h.hexdigest()!=expected: print('MISMATCH',rel); fail=1
print(f'manifest_checked={checked} status={"FAIL" if fail else "OK"}')
raise SystemExit(fail)
PY
