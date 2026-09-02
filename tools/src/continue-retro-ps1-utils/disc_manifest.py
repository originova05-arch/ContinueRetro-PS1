#!/usr/bin/env python3
import argparse,csv,xml.etree.ElementTree as ET
def main():
    p=argparse.ArgumentParser(); p.add_argument('xml'); p.add_argument('-o','--output',required=True); a=p.parse_args(); rows=[]; root=ET.parse(a.xml).getroot()
    def walk(n,prefix=''):
        for c in n:
            if c.tag=='dir': walk(c,prefix+c.attrib.get('name','')+'/')
            elif c.tag=='file': rows.append([prefix+c.attrib.get('name',''),c.attrib.get('offs',''),c.attrib.get('type',''),c.attrib.get('source','')])
    walk(root.find('.//directory_tree'))
    with open(a.output,'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['path','lba','type','source']); w.writerows(rows)
if __name__=='__main__': main()
