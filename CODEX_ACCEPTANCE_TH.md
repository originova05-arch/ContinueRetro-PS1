# เกณฑ์รับงาน Codex — ContinueRetro Studio / London-first

ใช้คู่กับ `CODEX_HANDOFF_TH.md` เป็นข้อกำหนดที่ต้องทำและพิสูจน์ ไม่ใช่ผลทดสอบที่ทำแล้ว

## วิธีรายงาน

แต่ละข้อบันทึก `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`, หรือ `PARTIAL` พร้อม command/test ID, commit, environment, input identity, output path/hash และเหตุผล ห้ามให้ source-code inspection เป็น runtime PASS หรือให้ mock เท่ากับ live model/game test

แยกสถานะส่งมอบเสมอ: implemented / unit-tested / integrated / installed-on-Mac / live-model-tested / real-game-static-tested / runtime-tested / release-ready

## A. รับช่วงและรักษาข้อมูลเดิม

- [ ] ตรวจแอปจริง สาขา local changes และ mount ในโฟลเดอร์ที่ผู้ใช้เปิดให้ เก็บฐานซอร์สก่อนแก้ ไม่เปลี่ยน branch ทับงานค้าง
- [ ] สำรองฐานข้อมูลและแอปก่อน migration; เปิดสำเนากู้คืนแล้วอ่านรายการจริงได้ ไม่ทดสอบ restore ทับของใช้งาน
- [ ] บันทึกก่อน/หลัง: project IDs, source identities, work IDs, source/target revisions, notes, categories, constraints, glossary, human decisions, selected font profiles, model endpoints, pending queues
- [ ] คำแปลและสถานะเดิมคงอยู่; ไม่ให้ migration เปลี่ยน draft เป็น human approved หรือใช้ผล QA เก่ากับ revision ใหม่
- [ ] ฟอนต์เดิม/ต้นฉบับเกม/โมเดลไม่ถูกแทนที่หรือย้ายเอง ตรวจassethashตามที่เข้าถึงจริง ไม่อ้างว่าตรวจweightsทั้งก้อนเมื่อแค่ตรวจ marker
- [ ] source-only TXT ใช้ช่วยอ่านได้ แต่ baseline tests ใช้ซอร์สพร้อม resources จริง; ตรวจ missing files ถ้าใช้การกู้คืนจาก TXT
- [ ] รัน app baseline ใหม่ และ `studio_next` tests แยกขอบเขต; จำนวนย้อนหลัง136/131ไม่ใช่ผลรอบใหม่และไม่บวกซ้ำ

## B. แปลและเกลาที่เรียกโมเดลจริง

- [ ] ตรวจ exact tags/digests/capabilities ของสามโมเดลบนบริการผู้ใช้จริง ไม่ดาวน์โหลดหรือเปลี่ยน endpointsโดยเงียบ
- [ ] มี live translation → technical checks → AI review → conditional polish → recheck ที่มี request/result IDs และคำตอบจริง ไม่ใช้ fixtures พิสูจน์ภาษา
- [ ] ขั้นเกลา/review อ่าน target revision ล่าสุดที่ commit; แก้ target ระหว่างคำขอแล้วผลเก่าต้องไม่เขียนทับ
- [ ] คลังศัพท์confirmedมีpriority; ข้อเสนอศัพท์ใหม่มีหลักฐาน ไม่ปนเกมอื่น; ไม่มีโมเดลยืนยันศัพท์ขัดแย้งหรือhuman reviewเอง
- [ ] TM retrievalดึงเฉพาะapproved/currentในscopeที่กำหนด คะแนนsimilarityไม่ถูกตีความเป็นtranslationaccuracy
- [ ] Exact-matchงานที่ตรวจแล้วไม่ถูกส่งแปล/เกลาใหม่เพราะกดStartซ้ำ; การทำใหม่ต้องมีเหตุผลหรือคำสั่งผู้ใช้
- [ ] เก็บหลักฐานคุณภาพจากคนบนชุดholdoutที่หลากหลาย: meaning/negation/numbers/speaker/style/terminology/control tokens ไม่แสดงคะแนนโมเดลตัวเองเป็นผลรับรอง

## C. Scoring / Technical / Human แยกกันจริง

- [ ] แอปรวมคะแนนหกมิติเอง; ปฏิเสธscoreผิดชนิด/เกินช่วงโดยไม่clipหรือเปลี่ยนเป็น0
- [ ] บริบทจำเป็นแต่ไม่มีให้PARTIAL/ไม่ประเมิน ไม่เดาผู้พูดและไม่normalizeคะแนนเป็น100
- [ ] คะแนน100ร่วมกับmajor/critical meaning issueยังแสดงปัญหาและไม่ผ่านนโยบายreleaseที่ต้องแก้ประเด็นนั้น
- [ ] `%d`, named variable หรือcontrol tokenหายถูกvalidatorที่เหมาะกับformatตรวจพบ คะแนนภาษาไม่แก้ผลtechnicalFAIL
- [ ] Codec/Renderer/Pixel metricที่ยังไม่ทราบให้UNKNOWN/NOT_EVALUATED ไม่ใช่PASSเพราะไม่มีerror
- [ ] Reviewer timeout/JSONเสีย/streamถูกตัด/duplicate keys/NaNเป็นreview error ไม่ใช่คะแนน0หรือหลักฐานว่าคำแปลtechnicalfail
- [ ] ยืนยันว่าHTTP outer response/NDJSON frame/accumulated final contentมีขอบเขตก่อนจัดสรรข้อมูล ไม่จำกัดแค่innerJSONที่อ่านเสร็จแล้ว
- [ ] Quotesอ้างอยู่ในsource/targetจริง; hostเป็นเจ้าของidentity/modelmetadata/context/rubric ไม่มีAIเพิ่มfieldเพื่ออนุมัติBuildหรือHuman
- [ ] การกดHumanApproveมีsession/CSRF/action/actorและrevisionชัดเจน; AIและbackgroundjobไม่สามารถเรียกทางลัดตั้งสถานะนี้
- [ ] Accept suggestionสร้างrevisionใหม่และไม่ยกคะแนน/approvalเก่าตามมา การreject suggestionไม่ทำลายtargetปัจจุบัน
- [ ] เปลี่ยนtarget/source/context/glossary/font/modelแล้วinvalidateเฉพาะผลที่เกี่ยวข้องตามpolicy มีประวัติเดิมไม่ลบทิ้ง
- [ ] มีtestsข้ามproject/wrongrevision/stalecontext/malformedpayload และconcurrent edits

## D. คิวกดครั้งเดียวและกรณีล้มเหลว

- [ ] งานทั้งscopeทำต่อจนหมดโดยไม่รอคลิกต่อทุก100/5000รายการ แบ่งbatchตามcontext ไม่ส่งทั้งเกมในคำขอเดียว
- [ ] แถวผิดรูปแบบถูกแยก/พักและทำแถวอื่นต่อแบบbounded ไม่วนretryไม่มีวันจบ
- [ ] บริการหายพักqueueพร้อมสาเหตุ เมื่อกลับมาทำต่อเฉพาะstageที่ยังไม่commit
- [ ] Kill/restartแอปในพื้นที่ทดสอบ แล้วคิว/งานแปล/historyไม่หายและไม่มีduplicate commit ทดสอบbefore/after commit
- [ ] Drive disconnect simulationและdisk-full simulationทำให้หยุดเขียน ไม่สร้างDBใหม่ในpath fallback ไม่ทดสอบด้วยการทำไดรฟ์ผู้ใช้เสียหายจริง
- [ ] Pause/Cancelตอบได้ขณะAIทำงาน; รายงานข้อจำกัดการยกเลิกserver-sidegenerationตามที่วัด ไม่อ้างว่าsocketปิด=backendหยุดทันที
- [ ] Reload/ปิดแท็บไม่ล้างคิว; ปิดเครื่องหรือsleepไม่ได้ถูกอ้างว่าทำงานต่อได้
- [ ] มีcheckpoint/one-step resumeและขอบเขตงานชัดเจน no inputไม่สร้างfailed jobพร้อมtracebackขวางหน้า

## E. UI ที่ตรงการใช้งาน

- [ ] สามหมวดแกะ/แปล/ประกอบมองเห็นเสมอ ตำแหน่งหมวดแกะไม่อยู่ใต้กรอบlogยาว
- [ ] ตารางเป็นพื้นที่หลัก รายละเอียดด้านขวา คิว/logพับด้านล่าง ตามreferenceที่ผู้ใช้ให้; Prompt/ค่าขั้นสูงไม่ยึดพื้นที่หลัก
- [ ] source confidence, translation score, Technical QA, AI statusและHuman statusอ่านแยกได้ มีสถานะnull/staleชัดเจน
- [ ] filters/search/select/batch actionsทำงานกับDBจริง scopeกลับถูกprojectเมื่อสลับเกม
- [ ] 100,000workitemsทดสอบจริงในfixtureที่แยกจากผู้ใช้; จำนวนDOMจำกัดและrequestไม่โหลดทั้งตาราง
- [ ] Legacy8ล้าน candidatesไม่ทำfull-table COUNT/GROUP BYทุกrefresh บันทึกqueryplan/latency/peakRAM/storageบนเครื่องทดสอบจริง อย่าเรียกarrayสั้นที่ตั้งtotal8000000ว่าstress test
- [ ] Dashboardเฉลี่ยมีตัวหาร/จำนวนunassessed/stale/rubricversion มีbacklog/unknownfiles ไม่เอาwalkครบมาแสดงแกะครบเกม
- [ ] ทุกปุ่มที่เปิดใช้ต่อbackendจริง มีdisabled reasonสำหรับcapabilityที่ขาด ไม่มีalertจำลองหรือเลขsampleในproduction path
- [ ] ตรวจบนจอMacBookเป้าหมายจริงและbrowserที่ใช้ ไม่มีJavaScript errors/bodyoverflowที่ทำให้ปุ่มสำคัญหาย มีkeyboard/focusและไม่พึ่งสีอย่างเดียว
- [ ] หลักฐาน screenshotมาจากแอปที่รันจริง; ข้อมูลfixtureติดป้ายชัดเจน ภาพgenerated/mockไม่ใช้แทนผลทดสอบUI

## F. Adapter / London จริง

- [ ] ผ่านrepo read-first/toolchain gatesก่อนแก้เกม คำนวณJapanese BIN/CUE identityจริง แยกEnglish referenceไม่แทนกัน
- [ ] Inventoryจริงมีไฟล์/ขนาด/LBA/geometryและขอบเขตที่ยังไม่รองรับ เลือกpilotfileจากหลักฐาน ไม่เดาcompressionจากextension
- [ ] Adapterจริงของอย่างน้อยหนึ่งformatอ่านrecordทั้งหมดตามscopeได้ พร้อมoccurrences/aliases/pointerrefs/sourceandfilehash/blockoffsets และรักษางานเดิมเมื่อนำเข้าซ้ำ
- [ ] No-op extract/repackสร้างผลแล้วตรวจhash/size/diffได้ ไม่ทำปุ่มPASSโดยไม่เรียกrepacker
- [ ] Controlled mutation same-lengthและshorterผ่าน knownexpected/independentchecks; longerทดสอบเฉพาะcapabilityที่รองรับ ไม่มีการยึดพื้นที่padding/ย้ายpointerโดยเดา
- [ ] Negative tests: truncated/corrupt/badpointer/overlap/wronghash/unsupportedencoding/adapterversion mismatchไม่ทำลายงานเดิม
- [ ] Diffระบุfirstdifference/ranges/size/hashและscope การยกเว้นmetadataกำหนดก่อนทดสอบ ไม่เพิ่มข้อยกเว้นย้อนหลังเพียงเพื่อผ่าน
- [ ] หลักฐานผูกadaptercode/config/toolversion/inputhash/testid/capability/scope การเปลี่ยนcodeไม่รับPASSเก่า deprecatedไม่ผ่านgateแม้เคยverified
- [ ] ข้อเสนอCoderกับobserved evidenceแยกกัน AIไม่promoteตัวเอง; โค้ดAIไม่รันนอกsandboxที่ทดสอบisolationแล้ว
- [ ] ไม่ใช้recordcodec round-tripหรือencodingอ่านได้เป็นหลักฐานว่าเกมเรียกใช้ข้อความครบ/ภาษาไทยแสดงได้

## G. Build / ฟอนต์ / Runtime

- [ ] TextCodec/GlyphCoverage/Layout/Renderer/Runtimeแยกกัน ใช้FontKitv1.3.0เดิมและatlasส่วนอื่นของเกมตามที่พิสูจน์แล้ว
- [ ] ชุดตัวอย่างสระบน/ล่าง/วรรณยุกต์/SARAAM/Latin/ตัวเลข/variable boundaryวัดPreviewเทียบพฤติกรรมเกมจริงตามscope ไม่อ้างความเหมือนทุกพิกเซลจากbrowser font
- [ ] Buildทดลองเป็นไฟล์ใหม่ sourceไม่เปลี่ยน ตรวจbyteallowlist/pointer/length/terminator/sector integrity/readback/hashตามรูปแบบ
- [ ] Unknownrequiredchecks blockrelease; Testmodeยอมภาษาunreviewedได้ตามpolicyแต่ไม่ข้ามcriticalbinaryrequirements
- [ ] เปิดJapanese baselineและmodifiedBuildในemulatorจริงด้วยBIOSที่ผู้ใช้มีสิทธิ์ ใช้buildhashตรงกัน ไม่อ้างlaunchprocessสำเร็จ=runtimeผ่าน
- [ ] มีหลักฐานอย่างน้อยจุดทดสอบที่แก้: boot/menu/dialogue/fontหรือscopeที่ประกาศ พร้อมสิ่งที่ไม่ได้ทดสอบ scenechange/save-loadเมื่อเกี่ยวข้อง ถ้าruntimeเข้าไม่ถึงให้BLOCKED ไม่mockผ่าน
- [ ] ถ้าส่งpatchให้ใช้กับสำเนาbaseอีกครั้งแล้วตรวจoutputhashตรงbuildที่ทดสอบ ไม่เผยแพร่ROM/font/BIOS
- [ ] Partialpilotหรือmenu-onlypatchต้องระบุscope ไม่ขึ้นfullgame100%หรือfullruntimeverified

## H. ความรู้ / Training / สิทธิ์ข้อมูล

- [ ] Clang/MIPS/เครื่องมืออื่นใช้ของมีอยู่ก่อน ดาวน์โหลดใหม่เฉพาะจำเป็นจากต้นทางพร้อมversion/hash/licenseและทำงานตรงสถาปัตยกรรม
- [ ] Knowledge source/สูตรแก้ปัญหามีprovenance/license/scope แยกproposed/failed/verifiedcase ไม่นำข้อมูลจากเว็บมาสอนเป็นtruthอัตโนมัติ
- [ ] Reviewed datasetไม่มีhumanapprovalปลอม ไม่มีconflictingpairs/validationleak/TMเฉลยในbenchmark และไม่ส่งprivatecorpusขึ้นrepoสาธารณะ
- [ ] ถ้าทำLoRAจริงมีtrainingcommand/config/base digest/datasetmanifest/seed/adapterhash/evaluation/rollback; หากทำเพียงRAGหรือexportJSONLระบุweight_training_performed=false
- [ ] Trainingไม่เป็นเงื่อนไขรอที่ทำให้appintegration/gameproofหยุด; วัดbaselineกับoutputจริงก่อนเลือกเพิ่มโมเดล

## I. การส่งมอบและสิ่งที่ยังถือว่าไม่ผ่าน

- [ ] ซอร์สและdiffจริง commitย่อยไม่แตะงานผู้ใช้ พร้อมmodulemap/schema/integrationreport
- [ ] updaterใช้workspaceเดิม สำรอง/คืนค่าทดสอบแล้ว และnativeMac smoke testตามเครื่องที่เข้าถึงได้ เปิดโปรแกรมง่ายด้วยlauncherเดียว
- [ ] ส่งmanifest/รุ่นเครื่องมือ/ZIPหรือวิธีติดตั้ง/hash/ข้อจำกัด/คู่มือสั้นและcheckpointที่ทำต่อได้
- [ ] รายงานunit / integration / live model / realgame static / runtime / installerแยกกัน ไม่มีการรวมจำนวนtestsต่างscopeเพื่ออ้างจบงาน
- [ ] เก็บไฟล์privateไว้บนexternalและไม่publishอัตโนมัติ source-onlyrepoไม่มีROM/font/DB/keys/logละเอียด/โมเดล

ถือว่ายังไม่ผ่านเป้าหมายใช้งานจริงเมื่อ: มีเพียงUIหน้าตาใหม่, มีเฉพาะแปลCSV, มีเพียงfixturetests, กดBuildแล้วสร้างไฟล์แต่ไม่พิสูจน์ผล, ตั้งrenderer=trueโดยไม่มีhook, ได้scoreสูงจากAIอย่างเดียว, หรืออ้างtrainingจากการสร้างคลังศัพท์

หากมีblockerภายนอก ให้ส่งpartialmilestoneที่รันได้จริงพร้อมหลักฐานและnextstepเฉพาะเจาะจง ไม่อ้างว่าเสร็จครบและไม่ทำลายส่วนที่ยังใช้ได้
