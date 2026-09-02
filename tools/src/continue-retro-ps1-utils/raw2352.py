#!/usr/bin/env python3
"""Small 2352-byte PlayStation raw-sector helper.

Commands are deliberately read-only except ``patch``.  ``diff-sectors`` is used
by game verification scripts to produce a deterministic changed-sector allowlist.
"""
import argparse, hashlib, pathlib, shutil, sys
SECTOR = 2352

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def info(path):
    n=pathlib.Path(path).stat().st_size
    print(f'bytes={n} sectors={n//SECTOR} remainder={n%SECTOR} sha256={sha(path)}')

def diff_sectors(a,b,limit):
    sa=pathlib.Path(a).stat().st_size; sb=pathlib.Path(b).stat().st_size
    if sa!=sb:
        print(f'WARNING size differs: a={sa} b={sb}', file=sys.stderr)
    changed=[]; idx=0
    with open(a,'rb') as fa, open(b,'rb') as fb:
        while True:
            xa=fa.read(SECTOR); xb=fb.read(SECTOR)
            if not xa and not xb: break
            if xa != xb: changed.append(idx)
            idx += 1
    print(f'changed_sector_count={len(changed)}')
    if changed:
        shown=changed if limit < 0 else changed[:limit]
        print('changed_lba=' + ','.join(map(str,shown)))
        if limit >= 0 and len(changed)>limit:
            print(f'changed_lba_truncated={len(changed)-limit}')
    return 0 if not changed else 1

def main():
    a=argparse.ArgumentParser(); s=a.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('info'); q.add_argument('image')
    q=s.add_parser('patch'); q.add_argument('src'); q.add_argument('dst'); q.add_argument('--offset',type=lambda x:int(x,0),required=True); q.add_argument('--hex',required=True)
    q=s.add_parser('diff-sectors'); q.add_argument('a'); q.add_argument('b'); q.add_argument('--limit',type=int,default=200,help='maximum LBA values to print; -1 = all')
    o=a.parse_args()
    if o.cmd=='info': info(o.image)
    elif o.cmd=='diff-sectors': raise SystemExit(diff_sectors(o.a,o.b,o.limit))
    else:
        shutil.copyfile(o.src,o.dst); b=bytes.fromhex(o.hex.replace(' ',''))
        with open(o.dst,'r+b') as f: f.seek(o.offset); f.write(b)
        print(f'patched offset=0x{o.offset:X} bytes={len(b)} sha256={sha(o.dst)}')
if __name__=='__main__': main()
