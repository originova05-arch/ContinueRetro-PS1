#!/usr/bin/env python3
"""Scan binaries for likely CP932/Shift-JIS text runs without modifying input."""
import argparse,csv,pathlib,sys

def pair(a,b): return ((0x81<=a<=0x9f) or (0xe0<=a<=0xfc)) and (((0x40<=b<=0x7e) or (0x80<=b<=0xfc)) and b!=0x7f)
def scan(data,min_chars):
    i=0
    while i<len(data):
        start=i; chunks=[]; j=i
        while j<len(data):
            b=data[j]
            if 0x20<=b<=0x7e or 0xa1<=b<=0xdf: chunks.append(bytes([b])); j+=1; continue
            if j+1<len(data) and pair(b,data[j+1]): chunks.append(data[j:j+2]); j+=2; continue
            break
        if len(chunks)>=min_chars:
            raw=b''.join(chunks)
            try: txt=raw.decode('cp932')
            except UnicodeDecodeError: txt=''
            if txt: yield start,j-start,txt
        i=max(i+1,j)
def main():
    p=argparse.ArgumentParser(); p.add_argument('input'); p.add_argument('-o','--output'); p.add_argument('--min-chars',type=int,default=3); a=p.parse_args()
    rows=list(scan(pathlib.Path(a.input).read_bytes(),a.min_chars)); f=open(a.output,'w',newline='',encoding='utf-8-sig') if a.output else sys.stdout
    w=csv.writer(f); w.writerow(['offset_hex','offset','byte_length','text'])
    try:
        for off,n,t in rows: w.writerow([f'0x{off:X}',off,n,t])
    except BrokenPipeError:
        return
    finally:
        if a.output: f.close()
if __name__=='__main__': main()
