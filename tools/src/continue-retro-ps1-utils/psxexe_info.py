#!/usr/bin/env python3
import argparse,struct,pathlib,hashlib
def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def main():
 p=argparse.ArgumentParser(); p.add_argument('file'); a=p.parse_args(); d=pathlib.Path(a.file).read_bytes();
 print('magic=',d[:8]); print(f'pc=0x{u32(d,0x10):08X} gp=0x{u32(d,0x14):08X} load=0x{u32(d,0x18):08X} size=0x{u32(d,0x1C):X} sp=0x{u32(d,0x30):08X}'); print('sha256='+hashlib.sha256(d).hexdigest())
if __name__=='__main__': main()
