'use strict';
/* Incremental data-driven review workbench. Existing backend controls remain in
   the legacy drawer. No demo records, invented quality scores or fake Build OK. */
(() => {
 const Q={pid:'',rows:[],after:0,next:null,back:[],selected:null,dirty:false,picks:new Set(),tab:'text',dashboard:null,loading:false,summaryAt:0,stamp:'',loadToken:0,ready:false};
 const el=id=>document.getElementById(id);
 const req=(suffix,body,method)=>api(`/api/projects/${state.project.id}/${suffix}`,body,method);
 const labels={unreviewed:'ยังไม่ตรวจ',reviewed:'AI ตรวจแล้ว',warning:'มีข้อสังเกต',issues:'ต้องแก้ความหมาย',partial:'ประเมินไม่ครบ',stale:'ผลเก่า',PASS:'ผ่านในขอบเขตที่ตรวจ',FAIL:'ไม่ผ่าน',WARNING:'มีคำเตือน',NOT_EVALUATED:'ยังตรวจไม่ครบ',STALE:'ต้องตรวจใหม่',APPROVED:'คนอนุมัติภาษา',REJECTED:'ไม่รับ',RETURNED:'ส่งกลับตรวจ',NOT_REVIEWED:'ยังไม่ตรวจโดยคน',LEGACY_REVIEWED:'มีผลคนตรวจจากรุ่นเดิม'};
 const label=x=>labels[x]||x||'—';
 const active=()=>!!state.job&&['queued','running'].includes(state.job.status);
 const scoreClass=n=>n==null?'unknown':n>=90?'high':n>=80?'good':n>=70?'caution':'low';
 function notice(text,error=false){el('qr-notice').textContent=text;el('qr-notice').hidden=!text;el('qr-notice').classList.toggle('error',error)}
 function selectionScope(){return Q.picks.size?{ids:[...Q.picks]}:{};}
 function setDirty(value){Q.dirty=value;el('qr-unsaved').hidden=!value;el('qr-save').disabled=!value||active();}
 async function saveDetail(){
  if(!Q.dirty||!Q.selected)return;
  const r=Q.selected,pid=Q.pid;const payload={revision:r.revision,translation:el('qr-target').value,notes:el('qr-notes').value,category:el('qr-category').value};
  const d=await api(`/api/entries/${r.id}`,payload,'PATCH');
  if(pid!==state.project?.id)throw Error('โปรเจกต์เปลี่ยนระหว่างบันทึก โปรดตรวจประวัติรายการ');
  setDirty(false);Q.selected={...r,...d.entry};await refreshDetail(r.id);await refreshProject();await load(true);
 }
 function currentRequest(){return new URLSearchParams({after:String(Q.after),q:el('qr-search').value,score:el('qr-score-filter').value,review:el('qr-review-filter').value,tech:el('qr-tech-filter').value,source_file:el('qr-file-filter').value.trim()});}
 async function load(refreshSummary=false){
  if(!state.project||!Q.ready)return;
  const pid=state.project.id,token=++Q.loadToken;
  el('qr-loading').hidden=false;
  try{
   const d=await api(`/api/projects/${pid}/quality-page?${currentRequest()}`);
   if(pid!==state.project?.id||token!==Q.loadToken)return;
   Q.rows=d.items;Q.next=d.next_cursor;paintRows();
   el('qr-page').textContent=`หน้านี้ ${fmt(d.items.length)} / พื้นที่ทำงาน ${fmt(d.total_work_items)} รายการ · ไม่ใช่จำนวนข้อความทั้งเกม`;
   el('qr-next').disabled=d.next_cursor==null;el('qr-prev').disabled=!Q.back.length;
   if(refreshSummary)await dashboard(true);
  }finally{if(token===Q.loadToken)el('qr-loading').hidden=true;}
 }
 function paintRows(){
  el('qr-rows').innerHTML=Q.rows.map(r=>{
   const q=r.quality,tech=r.technical,h=r.human,issues=(q.current?q.issues.length:0)+(r.technical_fail?1:0);
   return `<tr data-qr-id="${r.id}" tabindex="0" aria-selected="${Q.selected?.id===r.id}" class="${Q.selected?.id===r.id?'selected':''}"><td><input type="checkbox" class="qr-pick" data-id="${r.id}" aria-label="เลือกข้อความ ${r.id}" ${Q.picks.has(r.id)?'checked':''}></td><td><b>#${r.id}</b><small class="qr-key">${esc(r.stable_id.slice(0,10))}</small></td><td class="qr-file" title="${esc(r.source_file)}">${esc(r.source_file)}<small>0x${Number(r.file_offset).toString(16)}</small></td><td lang="ja" class="qr-source-cell">${esc(r.original_text)}</td><td class="qr-target-cell">${r.translation?esc(r.translation):'<span class="qr-muted">ยังไม่แปล</span>'}</td><td><b class="qr-score ${scoreClass(q.score)}">${q.score==null?'—':q.score}</b><small>${q.current?'คำแนะนำ AI':label(q.state)}</small></td><td><span class="qr-status ${tech.state==='FAIL'?'fail':'unknown'}">${esc(label(tech.state))}</span></td><td><span class="qr-status ${h.state==='APPROVED'?'human':'unknown'}">${esc(label(h.state))}</span></td><td>${issues?`<b class="qr-issue-count">${issues}</b>`:'—'}${r.meaning_blocked?'<small class="error">ความหมายสำคัญ</small>':''}</td></tr>`;
  }).join('')||'<tr><td colspan="9" class="qr-empty">ไม่มีรายการในช่วงนี้ เปลี่ยนตัวกรองหรืออ่านหน้าถัดไป ข้อความที่ยังไม่มีตัวอ่านอยู่ในหมวดแกะ / คัดกรอง</td></tr>';
  el('qr-rows').querySelectorAll('tr[data-qr-id]').forEach(tr=>{
   tr.onclick=safe(async e=>{if(e.target.closest('input'))return;await select(Number(tr.dataset.qrId));});
   tr.onkeydown=safe(async e=>{if(e.key==='Enter'&&!e.target.closest('input')){e.preventDefault();await select(Number(tr.dataset.qrId));}});
  });
  el('qr-rows').querySelectorAll('.qr-pick').forEach(box=>box.onchange=()=>{const id=Number(box.dataset.id);if(box.checked)Q.picks.add(id);else Q.picks.delete(id);paintSelection();});
  paintSelection();
 }
 function paintSelection(){el('qr-selection').textContent=Q.picks.size?`เลือก ${fmt(Q.picks.size)} รายการ · ปุ่มตรวจ/เกลาจะใช้เฉพาะที่เลือก`:'ไม่ได้เลือกแถว · ปุ่มหลักใช้ทั้งโปรเจกต์';el('qr-select-all').checked=Q.rows.length>0&&Q.rows.every(r=>Q.picks.has(r.id));}
 async function select(id){await saveDetail();Q.tab='text';await refreshDetail(id);paintRows();if(innerWidth<1250)el('qr-detail').scrollIntoView({block:'nearest',behavior:'smooth'});}
 async function refreshDetail(id){
  const pid=state.project.id,d=await api(`/api/projects/${pid}/quality-detail?id=${id}`);
  if(pid!==state.project?.id)return;
  Q.selected=d.entry;Q.pid=pid;setDirty(false);paintDetail();
 }
 function tabs(){el('qr-detail-tabs').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.view===Q.tab));el('qr-editor').hidden=Q.tab!=='text';el('qr-detail-view').hidden=Q.tab==='text';}
 function paintDetail(){
  const r=Q.selected;el('qr-detail-empty').hidden=!!r;el('qr-detail-content').hidden=!r;if(!r)return;
  el('qr-detail-title').textContent=`#${r.id} · revision ${r.revision}`;
  el('qr-detail-location').textContent=`${r.source_file} · 0x${Number(r.file_offset).toString(16)} · ${r.encoding}`;
  el('qr-source').textContent=r.original_text;el('qr-target').value=r.translation;el('qr-notes').value=r.notes;
  el('qr-category').innerHTML=[r.category,'dialogue','menu_system','item_equipment','battle','system','label_or_name','unknown'].filter((v,i,a)=>a.indexOf(v)===i).map(v=>`<option ${v===r.category?'selected':''}>${esc(v)}</option>`).join('');
  el('qr-statusline').textContent=`ภาษา ${r.quality.score==null?'ยังไม่มีคะแนนปัจจุบัน':r.quality.score+'/100'} · เทคนิค ${label(r.technical.state)} · คน ${label(r.human.state)}`;
  for(const id of ['qr-target','qr-notes','qr-category','qr-human-approve','qr-human-return','qr-context-save'])el(id).disabled=active();
  tabs();if(Q.tab!=='text')safe(paintView)();
 }
 async function paintView(){
  const r=Q.selected;if(!r)return;const pid=state.project.id,id=r.id,view=Q.tab,box=el('qr-detail-view');tabs();
  if(view==='quality'){
   const q=r.quality;box.innerHTML=`<div class="qr-review-heading"><strong class="qr-score ${scoreClass(q.score)}">${q.score==null?'—':q.score+' / 100'}</strong><p>${esc(label(q.state))}</p></div><small>คะแนนเป็นคำแนะนำของโมเดล ไม่ใช่คนอนุมัติหรือความพร้อม Build</small><div class="qr-dimensions">${Object.entries(q.weights).map(([k,max])=>`<div><span>${esc(({semantic:'ความหมาย',fluency:'ความลื่นไหล',terminology:'ศัพท์',context:'บริบท',style:'รูปแบบงาน',conciseness:'ความกระชับ'})[k])}</span><b>${q.current&&q.scores[k]!=null?q.scores[k]:'—'} / ${max}</b></div>`).join('')}</div><h4>ข้อสังเกต</h4>${q.issues.length?q.issues.map(i=>`<article class="qr-issue"><b>${esc(i.severity)} · ${esc(i.category)}</b><p>${esc(i.message)}</p>${i.source_quote?`<small>ต้นฉบับ: ${esc(i.source_quote)}</small>`:''}${i.target_quote?`<small>คำแปล: ${esc(i.target_quote)}</small>`:''}</article>`).join(''):'<p class="qr-muted">ยังไม่มีประเด็นที่บันทึก ไม่ใช่หลักฐานว่าถูกทุกความหมาย</p>'}${q.suggestion?`<h4>ข้อเสนอที่ยังไม่รับ</h4><p class="qr-suggestion">${esc(q.suggestion)}</p><div class="actions"><button id="qr-accept-suggestion" ${!q.current||active()?'disabled':''}>รับเป็นฉบับร่างใหม่</button><button id="qr-reject-suggestion" ${!q.current||active()?'disabled':''}>ไม่ใช้ข้อเสนอ</button></div>`:''}<small>โมเดล: ${esc(q.model||'ยังไม่ตรวจ')}<br>${esc(q.reviewed_at||'')}</small>`;
   if(el('qr-accept-suggestion'))el('qr-accept-suggestion').onclick=safe(()=>human('ACCEPT_SUGGESTION'));
   if(el('qr-reject-suggestion'))el('qr-reject-suggestion').onclick=safe(()=>human('REJECT_SUGGESTION'));
  }else if(view==='technical'){
   const q=r.technical;box.innerHTML=`<h4>Technical QA · ${esc(label(q.state))}</h4><p>UNKNOWN/ยังตรวจไม่ครบ ไม่ใช่ PASS และคะแนนภาษาไม่สามารถปลดล็อกข้อผิดพลาดนี้</p>${(q.report.checks||[]).map(c=>`<article class="qr-check"><strong>${esc(c.name)}</strong><span class="qr-status ${c.state==='FAIL'?'fail':'unknown'}">${esc(label(c.state))}</span><small>${esc(c.message)}</small><small>ขอบเขต: ${esc(c.scope)}</small></article>`).join('')||'<p>ยังไม่มีผลตรวจฉบับปัจจุบัน</p>'}<button id="qr-tech-one" ${active()?'disabled':''}>ตรวจเทคนิคข้อความนี้</button>`;el('qr-tech-one').onclick=safe(()=>start('quality_technical',{ids:[id]}));
  }else if(view==='context'){
   const c=r.context;box.innerHTML=`<h4>บริบทที่ผู้ใช้ระบุ</h4><label>ผู้พูด<input id="qr-speaker" maxlength="200" value="${esc(c.speaker||'')}"></label><label>ฉาก / กลุ่มข้อความ<input id="qr-scene" maxlength="200" value="${esc(c.scene||'')}"></label><label>หลักฐาน / หมายเหตุ<textarea id="qr-context-evidence" maxlength="2000">${esc(c.evidence||'')}</textarea></label><label class="qr-inline"><input id="qr-context-verified" type="checkbox" ${c.verified?'checked':''}> ตรวจหลักฐานบริบทแล้ว</label><button id="qr-context-commit" ${active()?'disabled':''}>บันทึกบริบท</button><p class="qr-muted">แถวก่อน–หลังตาม Offset ไม่ยืนยันว่าอยู่ในบทสนทนาเดียวกัน การเปลี่ยนบริบททำให้ผลตรวจต้องประเมินใหม่</p><h4>ศัพท์ยืนยันที่เกี่ยวข้อง</h4>${r.confirmed_terms.map(x=>`<p>${esc(x.source)} → ${esc(x.target)}</p>`).join('')||'<p>ไม่มีศัพท์ยืนยันที่ตรงกับต้นฉบับนี้</p>'}`;
   el('qr-context-commit').onclick=safe(()=>human('CONTEXT',{speaker:el('qr-speaker').value,scene:el('qr-scene').value,verified:el('qr-context-verified').checked,reason:el('qr-context-evidence').value}));
  }else{
   box.textContent='กำลังอ่านข้อมูลที่บันทึก…';
   let d;
   if(view==='history')d=await req(`quality-history?id=${id}`);
   else if(view==='memory')d=await req(`quality-memory?id=${id}`);
   else d=await req(`occurrence?id=${id}`);
   if(pid!==state.project?.id||Q.selected?.id!==id||Q.tab!==view)return;
   if(view==='memory')box.innerHTML='<h4>ตัวอย่างที่ผู้ใช้ตรวจแล้ว</h4><p class="qr-muted">รุ่นนี้ใช้การค้นคู่ตัวอักษรของระบบเดิม คะแนนความคล้ายไม่ใช่ความแม่นการแปล ไม่อ้างว่าเป็น Embedding</p>'+d.items.map(x=>`<article class="qr-issue"><small>ความคล้ายสำหรับค้นหา ${Number(x.similarity).toFixed(3)}</small><p lang="ja">${esc(x.source)}</p><p>${esc(x.target)}</p><small>${esc(x.source_file)}</small></article>`).join('')+(d.items.length?'':'<p>ยังไม่มีตัวอย่างที่เกี่ยวข้อง</p>');
   else box.innerHTML=`<h4>${view==='history'?'ประวัติผลตรวจและการตัดสินใจ':'หลักฐานตำแหน่งต้นฉบับ'}</h4><pre>${esc(JSON.stringify(d,null,2))}</pre>`;
  }
 }
 async function human(action,extra={}){
  if(!Q.selected)return;await saveDetail();const r=Q.selected;
  const question={APPROVED:'ยืนยันว่าอ่านเทียบต้นฉบับแล้วและอนุมัติภาษา revision นี้? ไม่ใช่อนุมัติ Build',RETURNED:'ส่งคำแปลฉบับนี้กลับให้ตรวจใหม่?',REJECTED:'ไม่รับคำแปลฉบับนี้?',ACCEPT_SUGGESTION:'รับข้อเสนอเป็น revision ใหม่? คะแนนและการอนุมัติเดิมจะไม่ย้ายตาม',REJECT_SUGGESTION:'บันทึกว่าไม่ใช้ข้อเสนอนี้?',CONTEXT:'บันทึกบริบทและให้ตรวจ revision ใหม่?'}[action];
  if(!confirm(question))return;
  const data={id:r.id,revision:r.revision,action,confirm:'USER_ACTION',review_id:r.quality.review_id,reason:el('qr-human-reason').value,...extra};
  const d=await req('quality-action',data);Q.selected=d.entry;setDirty(false);paintDetail();await load(true);await refreshProject();notice(d.memory_warning||'บันทึกการตัดสินใจแล้ว — การตรวจภาษาและ Build เป็นคนละสถานะ');
 }
 async function start(kind,scope=null,force=false){
  if(!state.project)return;await saveAll();
  const selected=scope||selectionScope();const d=await req('quality-preflight',{kind,scope:selected});
  if(!d.count){notice(d.message);return;}
  if(force&&!confirm(`ตรวจคะแนนใหม่ ${fmt(d.count)} รายการโดยใช้โมเดลจริง อาจใช้เวลานาน เริ่มหรือไม่?`))return;
  notice(`เริ่ม ${fmt(d.count)} รายการ แบ่งชุดและบันทึกต่อเนื่อง · รายการที่ต้องตัดสินใจจะพักไว้`);
  await startJob(kind,{scope:selected,force});paintActions();
 }
 function paintActions(){
  if(!Q.ready)return;const busy=active();
  for(const id of ['qr-review-all','qr-tech-all','qr-rescore','qr-approve-selected','qr-save','qr-human-approve','qr-human-return','qr-context-save']){const b=el(id);if(b)b.disabled=busy||(!state.project)||(id==='qr-save'&&!Q.dirty);}
  for(const id of ['qr-target','qr-notes','qr-category'])if(el(id))el(id).disabled=busy;
  el('qr-stop').disabled=!busy;
 }
 async function dashboard(force=false){
  if(!state.project||!Q.ready)return;const pid=state.project.id;
  if(!force&&Date.now()-Q.summaryAt<12000)return;
  Q.summaryAt=Date.now();const d=await api(`/api/projects/${pid}/quality-dashboard`);if(pid!==state.project?.id)return;Q.dashboard=d;
  el('qr-stat-translated').textContent=fmt(d.translated);el('qr-stat-reviewed').textContent=fmt(d.reviewed_current);el('qr-stat-human').textContent=fmt(d.human_approved);el('qr-stat-errors').textContent=fmt(d.technical_errors);
  el('qr-average').textContent=d.average_score==null?'ยังไม่มีคะแนนฉบับปัจจุบัน':`คะแนนเฉลี่ยคำแนะนำ ${d.average_score} จาก ${fmt(d.average_denominator)} รายการที่ประเมินครบ · ไม่ใช่ความพร้อม Build`;
  el('qr-bands').textContent=`≥90: ${fmt(d.ge90)} · 80–89: ${fmt(d['80_89'])} · 70–79: ${fmt(d['70_79'])} · <70: ${fmt(d.lt70)} · ยังไม่ประเมิน: ${fmt(d.unreviewed)} · ผลเก่า: ${fmt(d.stale)} · บริบท/มิติไม่ครบ: ${fmt(d.partial)}`;
  const run=d.last_run;el('qr-resume').hidden=!run||!['running','paused'].includes(run.state)||active();
  if(run)el('qr-resume').textContent=`ทำคิวคุณภาพที่พักไว้ต่อ (${fmt((run.counts.pending||0)+(run.counts.inflight||0))})`;
  pipeline();
 }
 function pipeline(){
  const p=state.project;if(!p)return;const d=Q.dashboard||{},r=state.job||{},busy=active();
  const steps=[['Scan',p.file_count?`มีรายการ ${fmt(p.file_count)} ไฟล์`:'ยังไม่มีรายการไฟล์'],['Triage',`${fmt(p.entry_count)} รายการทำงาน`],['Extract','ขอบเขตขึ้นกับตัวอ่าน'],['Translate',`${fmt(p.translated_count)} มีคำแปล`],['QA',`${fmt(d.reviewed_current)} AI ตรวจปัจจุบัน`],['Repack','ตรวจ Adapter ก่อน'],['Build','สำเนาทดสอบเท่านั้น'],['Test','ดูหลักฐานรายกรณี']];
  el('qr-pipeline').innerHTML=steps.map(([name,text])=>`<div class="qr-step ${busy&&((name==='QA'&&String(r.kind).startsWith('quality'))||(name==='Translate'&&String(r.kind).includes('translate')))?'running':''}"><b>${name}</b><small>${esc(text)}</small></div>`).join('');
 }
 async function showLog(){const d=await req('quality-log');el('qr-log-content').textContent=d.items.map(x=>`${x.created_at} [${x.kind}/${x.status}] ${x.work_id?'#'+x.work_id+' ':''}${x.message}`).join('\n')||'ยังไม่มีบันทึกข้อผิดพลาดของระบบคุณภาพในโปรเจกต์นี้';}
 async function approveSelected(){
  const ids=[...Q.picks];if(!ids.length){notice('เลือกข้อความที่อ่านตรวจแล้วก่อน');return;}
  if(!confirm(`ยืนยันว่าตรวจภาษา ${ids.length} รายการที่เลือกแล้ว? จะไม่อนุมัติ Build ให้ตามไปด้วย`))return;
  await saveAll();let completed=0;
  for(const id of ids){const d=await req(`quality-detail?id=${id}`);await req('quality-action',{id,revision:d.entry.revision,action:'APPROVED',confirm:'USER_ACTION',reason:'ผู้ใช้อนุมัติภาษารายการที่เลือกจากตาราง'});completed++;notice(`บันทึกคนตรวจ ${completed}/${ids.length}`);}
  Q.picks.clear();await load(true);if(Q.selected)await refreshDetail(Q.selected.id);
 }
 function mount(){
  if(!el('language-stage'))return;Q.ready=true;
  document.body.classList.add('quality-workbench');
  const nav=document.querySelector('.main-stages'),side=document.querySelector('body>aside');
  if(nav&&side){nav.classList.add('qr-navigation');side.insertBefore(nav,el('projects'));}
  const header=document.querySelector('#workspace>header');
  const pipelineEl=document.createElement('section');pipelineEl.id='qr-pipeline';pipelineEl.className='qr-pipeline';pipelineEl.setAttribute('aria-label','สถานะข้อมูลตามขั้นตอน ไม่ใช่การยืนยันว่าแกะครบเกม');header.after(pipelineEl);
  const old=document.createElement('details');old.id='qr-legacy';old.className='advanced';old.innerHTML='<summary>เครื่องมือเดิม / ขอบเขตย่อย / คิวเดิม</summary>';
  const language=el('language-stage');language.append(old);for(const id of ['ai-workspace','text-area'])old.append(el(id));
  const section=document.createElement('section');section.id='qr-workbench';section.innerHTML=`
   <div id="qr-notice" class="notice" role="status" hidden></div>
   <div class="qr-statbar"><span>มีคำแปล <b id="qr-stat-translated">—</b></span><span>AI ตรวจฉบับปัจจุบัน <b id="qr-stat-reviewed">—</b></span><span>คนอนุมัติภาษา <b id="qr-stat-human">—</b></span><span>Technical FAIL <b id="qr-stat-errors">—</b></span></div>
   <small id="qr-average"></small><small id="qr-bands"></small>
   <div class="qr-toolbar"><button class="primary" id="qr-review-all">ตรวจคำแปล</button><details class="qr-more"><summary>เพิ่มเติม</summary><button id="qr-tech-all">ตรวจ Technical QA</button><button id="qr-rescore">ให้คะแนนใหม่</button><button id="qr-approve-selected">คนอนุมัติภาษาที่เลือก</button></details><button id="qr-resume" hidden>ทำคิวที่พักไว้ต่อ</button><span id="qr-selection"></span></div>
   <div class="qr-filters"><input id="qr-search" placeholder="ค้นต้นฉบับ / คำแปล / Key" aria-label="ค้นข้อความ"><select id="qr-score-filter" aria-label="ช่วงคะแนน"><option value="">ทุกคะแนน</option><option value="ge90">90 ขึ้นไป</option><option value="80_89">80–89</option><option value="70_79">70–79</option><option value="lt70">ต่ำกว่า 70</option><option value="unassessed">ยังไม่มีคะแนนปัจจุบัน</option></select><select id="qr-review-filter" aria-label="สถานะการตรวจ"><option value="">ทุกสถานะ</option><option value="untranslated">ยังไม่แปล</option><option value="needs_review">ต้องตรวจ / แก้</option><option value="ai_reviewed">AI ตรวจแล้ว</option><option value="human_approved">คนอนุมัติภาษา</option><option value="stale">ผลตรวจเก่า</option><option value="unreviewed">AI ยังไม่ตรวจ</option></select><select id="qr-tech-filter" aria-label="ผลเทคนิค"><option value="">ทุกผลเทคนิค</option><option value="fail">Technical FAIL</option><option value="unknown">ยังตรวจไม่ครบ / ผลเก่า</option></select><input id="qr-file-filter" placeholder="ชื่อไฟล์เต็ม (เว้นว่าง = ทุกไฟล์)" aria-label="กรองชื่อไฟล์"><button id="qr-find">ค้นหา</button></div>
   <div class="qr-workspace"><div class="qr-table-area"><div id="qr-loading" role="status" hidden>กำลังอ่านข้อมูลล่าสุด…</div><div class="qr-table-scroll"><table class="qr-table"><thead><tr><th><input type="checkbox" id="qr-select-all" aria-label="เลือกทุกแถวในหน้านี้"></th><th>Key</th><th>File / Offset</th><th>Source JP</th><th>Target TH</th><th>Score</th><th>Tech QA</th><th>Human Review</th><th>Issues</th></tr></thead><tbody id="qr-rows"></tbody></table></div><div class="pager"><button id="qr-prev">ก่อนหน้า</button><span id="qr-page"></span><button id="qr-next">ถัดไป</button></div></div>
   <section id="qr-detail" class="qr-detail" aria-label="รายละเอียดข้อความที่เลือก"><p id="qr-detail-empty">เลือกแถวในตารางเพื่อแก้ข้อความและดูผลตรวจแต่ละด้าน</p><div id="qr-detail-content" hidden><header><div><h3 id="qr-detail-title"></h3><small id="qr-detail-location"></small></div><span id="qr-unsaved" hidden>ยังไม่บันทึก</span></header><p id="qr-statusline"></p><div id="qr-detail-tabs" class="qr-tabs"><button data-view="text" class="active">ข้อความ</button><button data-view="quality">คะแนน / AI</button><button data-view="technical">Technical</button><button data-view="context">บริบท</button><button data-view="memory">ความจำ</button><button data-view="history">ประวัติ</button><button data-view="source">ตำแหน่ง</button></div>
   <div id="qr-editor"><label>ต้นฉบับ</label><pre id="qr-source" lang="ja"></pre><label for="qr-target">คำแปลล่าสุด</label><textarea id="qr-target" maxlength="16384" rows="5"></textarea><label for="qr-category">ประเภท</label><select id="qr-category"></select><label for="qr-notes">หมายเหตุ / บริบท</label><textarea id="qr-notes" maxlength="16384" rows="3"></textarea><div class="actions"><button class="primary" id="qr-save" disabled>บันทึกฉบับใหม่</button><button id="qr-font">ดูด้วย FontKit</button></div></div>
   <div id="qr-detail-view" hidden></div><details class="qr-human-controls"><summary>การตัดสินใจโดยผู้ใช้</summary><label>หมายเหตุการตรวจ<input id="qr-human-reason" maxlength="2000"></label><div class="actions"><button id="qr-human-approve">อนุมัติภาษา</button><button id="qr-human-return">ส่งกลับตรวจ</button><button id="qr-context-save">เปิดข้อมูลบริบท</button></div><small>อนุมัติภาษาไม่อนุมัติ Build ไม่ทำให้ Technical FAIL หายไป</small></details></div></section></div>`;
  language.insertBefore(section,old);
  const drawer=document.createElement('details');drawer.id='qr-task-drawer';drawer.className='qr-task-drawer';drawer.open=true;drawer.innerHTML='<summary>คิวงาน / บันทึกการทำงาน</summary><div class="actions"><button id="qr-stop">พักงานที่กำลังทำ</button><button id="qr-log-refresh">อ่านบันทึกคุณภาพ</button><button id="qr-log-clear">ล้างเฉพาะที่แสดง</button></div><pre id="qr-log-content" hidden></pre>';
  el('workspace').append(drawer);drawer.insertBefore(el('job-panel'),el('qr-log-content'));
  el('translate-main').textContent='แปลทั้งหมด';el('polish-main').textContent='เกลาเฉพาะที่ต้องแก้';
  el('translate-main').onclick=safe(()=>el('auto-flow').checked?start('quality_auto'):startWhole('queue_translate'));
  el('polish-main').onclick=safe(()=>start('quality_improve'));
  const autoLabel=el('auto-flow').parentElement;for(const child of [...autoLabel.childNodes])if(child.nodeType===3)child.textContent=' หลังแปล ตรวจคุณภาพและเกลาเฉพาะรายการที่มีปัญหา (ไม่เกลาซ้ำทุกแถว)';
  el('qr-review-all').onclick=safe(()=>start('quality_review'));
  el('qr-tech-all').onclick=safe(()=>start('quality_technical'));
  el('qr-rescore').onclick=safe(()=>start('quality_review',null,true));
  el('qr-approve-selected').onclick=safe(approveSelected);
  el('qr-find').onclick=safe(async()=>{await saveAll();Q.after=0;Q.back=[];Q.picks.clear();await load(true)});
  el('qr-search').onkeydown=e=>{if(e.key==='Enter')el('qr-find').click()};
  for(const id of ['qr-score-filter','qr-review-filter','qr-tech-filter'])el(id).onchange=()=>el('qr-find').click();
  el('qr-next').onclick=safe(async()=>{await saveAll();Q.back.push(Q.after);Q.after=Q.next;await load()});
  el('qr-prev').onclick=safe(async()=>{await saveAll();Q.after=Q.back.pop()||0;await load()});
  el('qr-select-all').onchange=()=>{for(const r of Q.rows)if(el('qr-select-all').checked)Q.picks.add(r.id);else Q.picks.delete(r.id);paintRows()};
  for(const id of ['qr-target','qr-notes','qr-category'])el(id).oninput=()=>setDirty(true);
  el('qr-save').onclick=safe(saveDetail);el('qr-font').onclick=safe(()=>openFontPreview(el('qr-target').value));
  el('qr-human-approve').onclick=safe(()=>human('APPROVED'));el('qr-human-return').onclick=safe(()=>human('RETURNED'));
  el('qr-context-save').onclick=safe(async()=>{await saveDetail();Q.tab='context';await paintView()});
  el('qr-detail-tabs').querySelectorAll('[data-view]').forEach(b=>b.onclick=safe(async()=>{await saveDetail();Q.tab=b.dataset.view;await paintView()}));
  el('qr-stop').onclick=safe(async()=>{if(state.job){await api(`/api/jobs/${state.job.id}/cancel`,{});notice('ส่งคำขอพักแล้ว รอให้ worker คืนสถานะคิว')}});
  el('qr-resume').onclick=safe(async()=>{const r=Q.dashboard?.last_run;if(!r)return;await startJob(r.kind,{resume_id:r.id})});
  el('qr-log-refresh').onclick=safe(async()=>{el('qr-log-content').hidden=false;await showLog()});
  el('qr-log-clear').onclick=()=>{el('qr-log-content').textContent='ล้างเฉพาะหน้าจอแล้ว บันทึกจริงยังอยู่ในฐานข้อมูล'};
  const originalDirty=dirty,originalSave=saveAll,originalRender=renderJob;
  dirty=function(){return Q.dirty||originalDirty()};
  saveAll=async function(){await saveDetail();await originalSave()};
  renderJob=function(job){originalRender(job);if(!Q.ready)return;paintActions();pipeline();const stamp=job?job.id+':'+job.status:'';if(stamp!==Q.stamp){Q.stamp=stamp;if(job&&!['queued','running'].includes(job.status)){if(!Q.dirty)safe(async()=>{await load(true);if(Q.selected)await refreshDetail(Q.selected.id)})();else notice('งานเสร็จแล้ว มีการแก้ไขที่ยังไม่บันทึก จึงยังไม่โหลดทับช่องแก้ไข');}}};
  window.addEventListener('studio-project-render',()=>{
   if(!state.project)return;
   if(Q.pid!==state.project.id){Q.pid=state.project.id;Q.after=0;Q.next=null;Q.back=[];Q.picks.clear();Q.selected=null;Q.dashboard=null;Q.summaryAt=0;setDirty(false);paintDetail();for(const id of ['qr-search','qr-score-filter','qr-review-filter','qr-tech-filter','qr-file-filter'])el(id).value='';safe(()=>load(true))();}
   paintActions();pipeline();
  });
  paintActions();if(state.project)safe(()=>load(true))();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
