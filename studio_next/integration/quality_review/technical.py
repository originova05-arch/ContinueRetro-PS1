"""Deterministic text-side QA. Unknown game/runtime properties stay unknown."""
from __future__ import annotations
from collections import Counter
import re
from . import repo
from .quality import check_format_tokens

TOKENS=re.compile(r'\{[^{}\r\n]{1,80}\}|<[^<>\r\n]{1,80}>|\[[A-Za-z_][A-Za-z0-9_: =,\-]{0,60}\]')
ESCAPE=re.compile(r'\\(?:n|r|t|x[0-9a-fA-F]{2})')


def assess(s,r,*,encoder=None,metrics=None):
    """No AI verdict contributes to these checks; does not read or patch the ROM.

    Codec/advance settings are declarations, not proof that a game uses them.
    The build adapter and runtime gates still own pointer/renderer validation.
    """
    adapter=s.settings(r['project_id'],'adapter',{}) or {}
    p=s.get_project(r['project_id'])
    if metrics is None:
        from app.translation import load_metrics
        metrics=load_metrics(s,p['selected_font_profile'])
    if encoder is None:
        from app.translation import encode_text
        encoder=encode_text
    source,target=r['original_text'],r['translation'];checks=[]
    def add(name,state,message,severity='info',scope='text_only'):
        checks.append(dict(name=name,state=state,message=message,severity=severity,scope=scope))
    formats=check_format_tokens(source,target)
    for name,state in formats.items():
        add(name,state,'ชนิด/จำนวนตัวแปรตรงต้นฉบับ' if state=='PASS' else 'ตัวแปรหาย เพิ่ม หรือเปลี่ยนลำดับที่จำเป็น',
            'critical' if state=='FAIL' else 'info','declared_named_and_printf_subset')
    controls=Counter(TOKENS.findall(source))==Counter(TOKENS.findall(target)) and ESCAPE.findall(source)==ESCAPE.findall(target)
    add('control_codes','PASS' if controls else 'FAIL',
        'token/escape ที่ตัวตรวจรู้จักคงเดิม; ไม่ใช่การถอดรหัสคำสั่งเกมทุกชนิด' if controls else 'token หรือ escape code เปลี่ยน',
        'info' if controls else 'critical','text_token_integrity_not_binary_opcode_proof')
    invalid=not target.strip() or bool(re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffd]',target))
    add('forbidden_character','FAIL' if invalid else 'PASS',
        'คำแปลว่างหรือมีอักขระเสีย/control bytes' if invalid else 'ไม่พบอักขระควบคุมดิบหรือ replacement character',
        'critical' if invalid else 'info')
    encoded=None
    if adapter.get('encoding') not in {'ascii','shift_jis','custom'}:
        add('encoding','NOT_EVALUATED','ยังไม่มี codec เกมที่อนุญาต ไม่ใช้ UTF-8 แทนรหัสเกม','warning','game_codec_missing')
    else:
        try:
            encoded=encoder(target,adapter)
            if not isinstance(encoded,bytes):raise ValueError('codec ไม่ได้คืน bytes')
            add('encoding','PASS','เข้ารหัสตาม codec ที่ตั้งค่าได้; ความถูกต้องของ codec ต่อเกมต้องพิสูจน์ใน Adapter','info','configured_codec_only')
        except (ValueError,UnicodeError,TypeError,KeyError) as exc:
            add('encoding','FAIL','เข้ารหัสไม่ได้: '+str(exc)[:250],'critical','configured_codec')
    slot=(adapter.get('slots') or {}).get(r['stable_id'],{})
    capacities=[]
    if type(r.get('max_bytes'))is int and r['max_bytes']>0:capacities.append(r['max_bytes'])
    try:
        slot_len=len(bytes.fromhex(slot.get('expected_hex','')))
        if slot_len:capacities.append(slot_len)
    except (ValueError,TypeError):
        add('slot_definition','FAIL','expected_hex ของช่องข้อมูลไม่ถูกต้อง','critical','adapter_declaration')
    cap=min(capacities) if capacities else None
    if encoded is None or cap is None:
        add('byte_length','NOT_EVALUATED','ยังไม่มีผล encode หรือขอบเขตพื้นที่ที่กำหนด','warning','configured_capacity')
    else:
        add('byte_length','PASS' if len(encoded)<=cap else 'FAIL',f'{len(encoded)} / {cap} ไบต์ตาม codec ที่ตั้งค่า',
            'info' if len(encoded)<=cap else 'critical','configured_capacity')
    maximum=r.get('max_lines') or slot.get('max_lines')
    lines=len(target.replace('\r\n','\n').replace('\r','\n').split('\n'))
    if type(maximum)is not int or maximum<=0:
        add('line_count','NOT_EVALUATED','ยังไม่ยืนยันจำนวนบรรทัดสูงสุด','warning','layout_declaration')
    else:
        add('line_count','PASS' if lines<=maximum else 'FAIL',f'{lines} / {maximum} บรรทัด',
            'info' if lines<=maximum else 'critical','explicit_line_breaks_only')
    stripped=TOKENS.sub('',target);unknown=set();widths=[]
    for line in stripped.replace('\r\n','\n').replace('\r','\n').split('\n'):
        width=0
        for ch in line:
            m=metrics.get(f'U+{ord(ch):04X}')
            advance=m.get('advance_pixels') if isinstance(m,dict) else (adapter.get('advance_pixels') or {}).get(ch)
            if type(advance)is not int or advance<0:unknown.add(ch)
            else:width+=advance
        widths.append(width)
    max_width=r.get('max_pixel_width') or slot.get('max_pixel_width')
    variable=bool(TOKENS.search(target) or re.search(r'%(?!%)[^\s]*[dsifu]',target))
    if unknown or type(max_width)is not int or max_width<=0 or variable:
        add('pixel_width','NOT_EVALUATED','ยังขาด metrics/ขนาดกล่อง/ความยาวตัวแปร ไม่รับรองว่าพอดีหน้าจอ','warning','game_layout_unverified')
    elif max(widths,default=0)>max_width:
        add('pixel_width','FAIL',f'ระยะเดินตัวอักษร {max(widths)} เกินกรอบ {max_width} px','critical','declared_advance_only')
    else:
        add('pixel_width','WARNING',f'ระยะเดินในตัวอย่าง {max(widths,default=0)} / {max_width} px; ยังไม่พิสูจน์ Renderer/หมึก/การตัดคำในเกม','warning','preview_only')
    thai={ch for ch in stripped if '\u0e00'<=ch<='\u0e7f'}
    missing_thai=sorted(ch for ch in thai if f'U+{ord(ch):04X}' not in metrics)
    if not metrics:
        add('glyphs','NOT_EVALUATED','ยังไม่พบ metrics ของ FontKit ที่ติดตั้ง','warning','fontkit_not_game_atlas')
    elif missing_thai:
        add('glyphs','FAIL','ไม่พบ Glyph ไทยใน metrics: '+''.join(missing_thai),'critical','fontkit_metrics_only')
    else:
        add('glyphs','WARNING','Glyph ไทยที่ใช้มี metrics แล้ว; atlas เกมและอักษรอื่นยังต้องตรวจ','warning','fontkit_metrics_not_runtime_renderer')
    add('terminator','NOT_EVALUATED','ตรวจตัวจบหลังสร้างระเบียนด้วย Repacker ไม่อนุมานจาก CSV/ต้นฉบับ','warning','repacker_required')
    add('pointer_safety','NOT_EVALUATED','ต้องตรวจตำแหน่งและจุดอ้างอิงจากแผน Build ของ Adapter','warning','build_required')
    failed=any(x['state']=='FAIL' for x in checks)
    unknown_checks=any(x['state']=='NOT_EVALUATED' for x in checks)
    overall='FAIL' if failed else 'NOT_EVALUATED' if unknown_checks else 'WARNING' if any(x['state']=='WARNING' for x in checks) else 'PASS'
    config_hash=repo.fingerprint({'adapter':adapter,'font_profile':p['selected_font_profile'],'metrics':metrics,
                                  'limits':[r.get('max_bytes'),r.get('max_lines'),r.get('max_pixel_width')],'validator':'quality-text-qa-v1'})
    return dict(status=overall,checks=checks,config_hash=config_hash,encoded_bytes=None if encoded is None else len(encoded),
                max_bytes=cap,logical_advances=None if unknown else widths,physical_lines=lines,
                critical_errors=sum(x['state']=='FAIL' and x['severity']=='critical' for x in checks),
                unknown_checks=sum(x['state']=='NOT_EVALUATED' for x in checks),
                language_score_included=False,game_renderer_verified=False,build_ready=False,
                scope='text_side_QA_plus_configured_codec; no binary/renderer/runtime certification')


def blocks_language_operation(report):
    """Do not try linguistic polishing to cure a hard format/codec/layout error."""
    return any(x['state']=='FAIL' and x['severity']=='critical' for x in report['checks'])
