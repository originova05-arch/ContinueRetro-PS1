# งานต่อเนื่อง Studio: Quality Core สำหรับเชื่อม v0.6.0

## สถานะจริง

นี่คือโมดูลแยกสำหรับนำไปเชื่อมกับ ContinueRetro Studio v0.6.0 ในขั้นถัดไป ไม่ใช่ตัวอัปเดตแอป ไม่ใช่เว็บใหม่ และยังไม่ติดตั้งลง Mac หรือไดรฟ์ของผู้ใช้

ทดสอบฝั่งแชทด้วย Container และ Python แล้วทั้งสองทางตอบ ClientError จึงใช้ GitHub connector บันทึกซอร์สและ GitHub Actions ทดสอบโค้ดที่ไม่ต้องอ่าน ROM แทน ไม่ได้แก้ main และไม่เผยแพร่เกม/ฟอนต์/BIOS/งานแปลของผู้ใช้

ซอร์สแอป v0.6.0 อยู่ใน ZIP ที่แนบในบทสนทนา แต่ในรอบนี้ยังแตก/อ่านไฟล์ภายใน ZIP ไม่ได้ การค้น tree ของ repo ที่อ่านได้ยังไม่พบ continue-retro-studio จึงไม่สมมติว่ามี API หรือ schema ใดใน repo ที่ใช้แทน ZIP ได้

## สิ่งที่เขียนแล้ว

- `quality.py`: Snapshot, ReviewIdentity, Rubric, JSON Schema และตัวตรวจผล Reviewer
- คะแนน 35/20/15/15/10/5; แอปเป็นผู้บวกคะแนน ไม่รับ total จาก AI
- คะแนนย่อย null หมายถึงประเมินไม่ได้ ผลรวมเป็น null ไม่ normalize ให้ดูครบ 100
- แยก TechnicalReport, Review, HumanDecision และ LanguageGate
- คะแนนสูงไม่ลบ major/critical issue; confidence ที่โมเดลรายงานเองไม่ใช้ผ่าน gate
- ตรวจ named placeholder/count และ printf/order ในขอบเขตที่ประกาศไว้เท่านั้น
- Technical checks ที่ยังไม่มีหลักฐานเป็น NOT_EVALUATED ไม่ใช่ PASS
- ผลผูก project/key/revision/source hash/target hash และ fingerprint ของกฎ บริบท โมเดล prompt
- เปลี่ยน target ทำให้ผลเก่าไม่ใช้กับฉบับใหม่; เปลี่ยนโมเดลอย่างเดียวไม่ถอน HumanDecision
- การรับ suggestion สร้าง Snapshot ใหม่ ไม่บันทึก/ไม่อนุมัติเอง
- LanguageGate ให้ได้เพียง ready_for_binary_checks ไม่ใช่ build_ready หรือ runtime_verified
- `test_quality.py` และ `test_quality_hardening.py`: ข้อมูลทดสอบที่เขียนขึ้น ไม่ใช่ประโยคจากเกมจริง

## สัญญาการเชื่อมที่ต้องทำต่อ

1. อ่านซอร์ส v0.6.0 จริงก่อนเลือกจุดเชื่อม API/worker/database และทดสอบฐานเดิมซ้ำ
2. เรียก Reviewer ผ่านบริการ Ollama เดิม โดยสร้าง ReviewIdentity จากข้อมูลล่าสุดที่ host อ่านเอง
3. กำหนดขนาด HTTP/JSON input และปฏิเสธ duplicate JSON keys ก่อน parse_review; จำกัด prompt/output ด้วย
4. ไม่ให้โมเดลระบุ model digest, policy hash, technical PASS, HumanDecision หรือสิทธิ์ Build เอง
5. ต้องตรวจ context availability จากหลักฐาน host ด้วย null/คำเตือนในโมเดลไม่พอเป็นตัวคุมเอง
6. TechnicalReport.from_host รับเฉพาะผลจาก validator ของแอป/Adapter ไม่ใช่ JSON ที่ AI ส่งมา
7. HumanDecision ต้องสร้างใน endpoint ที่ตรวจ session/CSRF/actor และมีการกระทำของคนจริง ไม่ได้มีระบบ authentication ในไลบรารี pure functions นี้
8. เก็บผลประเมินและ human events แบบ append-only; เปรียบเทียบ revision/fingerprint ใน transaction ก่อน commit
9. suggested_revision เป็น pure function; ก่อนรับข้อเสนอ host ต้องตรวจ policy/context ปัจจุบันอีกครั้งและทำ compare-and-swap ใน transaction ไม่ให้คะแนนเดิมย้ายไปฉบับใหม่
10. รวม LanguageGate กับ Adapter/code hash/round-trip/mutation tests/renderer/runtime gates เดิม ห้ามใช้เพียง ready_for_binary_checks เปิด Release
11. Counter/filter/dashboard ต้องอ่านผลปัจจุบัน แสดง unassessed/stale แยก ไม่มีข้อมูลจำลองใน UI ใช้งานจริง
12. ตัวตรวจ regex ในโมดูลเป็น subset แบบ conservative ไม่รับรอง control codes ทุกเกม ต้องใช้ parser/codec ของ London เพิ่ม

## UI เป้าหมายที่ยังต้องเชื่อม ไม่ได้สร้างแล้วในรอบนี้

รักษาสามเมนูหลัก แกะ/คัดกรอง, แปล/เกลา/QA, ประกอบ/ทดสอบ ตามเอกสารผู้ใช้ ไม่รื้อ backend

หน้าแปล: ตารางเป็นส่วนหลัก source/target/score/tech/human/issues, detail panel ด้านขวา, queue/log ที่พับได้ และ pipeline ด้านบน ตัวเลขมาจากฐานข้อมูลจริงเท่านั้น

คะแนนภาษา, ความมั่นใจจากการแกะ, Technical QA และ Human Review เป็นคนละข้อมูล สีเป็นตัวช่วยไม่ใช่สิทธิ์ผ่าน Build เก็บปุ่มหลักน้อยและคำสั่งรองในรายละเอียด

## London-first

ใช้งานจริง London Seirei Tanteidan เป็นเกมนำร่องเพียงเกมเดียวในขั้นนี้ อีกเกมพักไว้ ไม่ให้เป็น dependency ที่ทำให้งานหยุด

เริ่มขั้นเกมเมื่อรันไทม์อ่านไฟล์จริงได้: ตรวจ CUE และแฮช BIN จากผู้ใช้ → inventory/เลือกไฟล์ที่รู้โครงสร้าง → extract → no-op round-trip → controlled mutation และ independent checks → จึงเชื่อมคำแปล/ฟอนต์ → สำเนา Build → ทดสอบฉากที่กำหนด

ห้ามใช้ไฟล์ London English แทน Japanese โดยเงียบ ๆ ไม่ใช้ข้อมูลจำลองพิสูจน์ว่าเกมจริงผ่าน และไม่ส่ง ROM ไป GitHub Actions

## คำสั่งสำหรับนักพัฒนา

จากราก repo บนสาขานี้:

```bash
python3 -m unittest discover -s studio_next -p 'test_*.py' -v
```

เป็นการตรวจ core เท่านั้น ไม่รันโมเดล ไม่เปิด ROM ไม่เปลี่ยนแอป ไม่มีโมเดลหรือไลบรารีภายนอกต้องติดตั้งเพิ่ม Python 3.10+ เป็นขอบเขต syntax; ดู log CI สำหรับเวอร์ชันที่รันจริง

## ยังไม่ทำ

ยังไม่ได้ต่อ core เข้าฐานข้อมูล/HTTP/คิว/หน้าเว็บ v0.6.0, ไม่ได้ทำ Migration หรือแพ็กติดตั้ง, ไม่ได้พิสูจน์คุณภาพโมเดลจริง, ไม่มี decoder/renderer London ใหม่, ไม่มี Build เกมจริง และไม่มี LoRA/fine-tuning

อ่าน CHECKPOINT_LATEST.md ก่อนรับงานต่อและคงความแตกต่างระหว่าง implemented / tested / integrated / installed / runtime-tested ไว้ทุกครั้ง
