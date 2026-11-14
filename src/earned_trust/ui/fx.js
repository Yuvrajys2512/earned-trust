/* FX layer: presentation only. It reads the data already embedded in the page and never changes a number:
   every animated value ends on the exact text the page rendered. Inlined by `et` (placeholder FX_JS). */
(function(){
'use strict';
const doc = document, root = doc.documentElement;
const RM = matchMedia('(prefers-reduced-motion: reduce)').matches || /[?&#]still/.test(location.search+location.hash);
if(RM) document.documentElement.classList.add('fx-still');
const h = (html)=>{ const t=doc.createElement('template'); t.innerHTML=html.trim(); return t.content.firstChild; };
const E = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const wait = ms => new Promise(r=>setTimeout(r, RM?0:ms));
if(!root.dataset.theme) root.dataset.theme = 'dark';

/* ---------- count-up: animate every number in a node, end on the original text ---------- */
function countUp(el, dur=1100){
  if(el.dataset.fxCounted) return; el.dataset.fxCounted='1';
  const nodes=[]; const w=doc.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
  while((n=w.nextNode())) if(/\d/.test(n.nodeValue)) nodes.push({n, orig:n.nodeValue});
  // only single-number values count up: a frozen frame of "6 / 10" must never read "5 / 8"
  if(nodes.length!==1 || (nodes[0].orig.match(/\d+(\.\d+)?/g)||[]).length!==1 || RM) return;
  const t0=performance.now();
  const step=(t)=>{ const p=Math.min(1,(t-t0)/dur), e=1-Math.pow(1-p,3);
    for(const o of nodes) o.n.nodeValue = p>=1 ? o.orig : o.orig.replace(/\d+(\.\d+)?/g, m=>{ const d=(m.split('.')[1]||'').length; return (parseFloat(m)*e).toFixed(d); });
    if(p<1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

/* ---------- scroll reveal + count-up on first sight ---------- */
function armReveal(){
  const els=[...doc.querySelectorAll('.wrap > h2, .wrap .card, .wrap .stat, #app > div > h2, .fx-hero, .fx-machine')];
  if(!('IntersectionObserver' in window) || RM){ doc.querySelectorAll('.stat .n,.num .n').forEach(x=>x.dataset.fxCounted='1'); return; }
  const io=new IntersectionObserver(es=>es.forEach(e=>{ if(!e.isIntersecting) return; const t=e.target; t.classList.add('fx-in');
    t.querySelectorAll('.stat .n,.num .n').forEach(x=>countUp(x)); if(t.matches('.stat')) t.querySelectorAll('.n').forEach(x=>countUp(x));
    t.dispatchEvent(new CustomEvent('fx:seen')); io.unobserve(t); }),{threshold:.12});
  els.forEach((el,i)=>{ if(el.closest('.reveal')) return; el.classList.add('fx-r'); el.style.transitionDelay=Math.min(i%6,5)*60+'ms'; io.observe(el); });
}
function onSeen(el, fn){ if(RM||!('IntersectionObserver' in window)){ fn(); return; }
  const io=new IntersectionObserver(es=>{ if(es.some(e=>e.isIntersecting)){ io.disconnect(); fn(); } },{threshold:.3}); io.observe(el); }

/* ---------- brand mark in header ---------- */
function brand(){ const h1=doc.querySelector('header h1'); if(h1 && !h1.querySelector('.fx-mark')) h1.prepend(h('<span class="fx-mark" aria-hidden="true"><i></i></span>'), ' '); }

/* =========================== REVIEW PAGE =========================== */
function reviewPage(R){
  const app=doc.getElementById('app'); if(!app) return;
  const a=R.ledger_counts.agent_tests||{}, rv=R.ledger_counts.reviewer_tests||{};
  const agentTotal=Object.values(a).reduce((x,y)=>x+y,0);
  const proven=R.behavior_changes.filter(b=>b.status==='proven').length;
  const zero=Object.entries((R.calibration&&R.calibration.reviewer_on_real_pr)||{}).find(([,v])=>v===0);
  const broken=(a['broken-by-pr']||0)+(rv['broken-by-pr']||0);

  // hero
  const lead = zero
    ? `AI reviewer: <em>0 issues</em>.<br>Receipts: <b>${proven} proven behavior changes</b>, ${R.refusals.length} refusals.`
    : broken ? `<em>${broken} proven regression${broken>1?'s':''}</em> the agent's tests missed.<br><b>${proven} proven behavior changes</b>, ${R.refusals.length} refusals.`
    : `<b>${proven} proven behavior changes</b>, ${R.refusals.length} refusals.<br>${a.placebo?`<em>${a.placebo} of ${agentTotal}</em> agent tests prove nothing.`:''}`;
  const hero=h(`<section class="fx-hero"><div class="fx-scan"></div>
    <div class="k">${E(R.requirement.id)} · agent-written PR · review record</div>
    <div class="big">${lead}</div>
    <p class="sub">Nothing on this page is the AI's opinion unless it says <i>hearsay</i>. Every claim points at something that was executed: a test on the old and new code, a git fact, a byte compare.</p>
    <div class="fx-steps">${['Prove','Predict','Measure','Refuse','Sign'].map((s,i)=>`<span style="animation-delay:${300+i*140}ms"><b>${i+1}</b> ${s}</span>`).join('')}</div></section>`);
  const firstH2=[...app.children].find(c=>c.tagName==='H2'); app.insertBefore(hero, firstH2);

  // "Not in history" glitch
  app.querySelectorAll('.stat .n').forEach(n=>{ if(n.textContent.trim()==='Not in history'){ n.innerHTML=`<span class="fx-glitch" data-t="Not in history">Not in history</span>`; n.dataset.fxCounted='1'; } });

  receiptMachine(R, app, agentTotal, a, rv);
  timeline(R);
  calibration(R);
  watchReveals();
  window.ET_SUBMIT = rec => printReceipt(R, rec);
}

function receiptMachine(R, app, agentTotal, a, rv){
  const ev=[]; const seen=new Set();
  R.behavior_changes.forEach(b=>b.evidence.forEach(e=>{ if(!seen.has(e.test)){ seen.add(e.test); ev.push({test:e.test, verdict:e.verdict, base:e.base, head:e.head}); } }));
  const isRev = t => /(^|\.)Et[A-Z]/.test(t);
  const agentEv = ev.filter(e=>!isRev(e.test));
  const agentPl = (R.placebo_tests||[]).filter(t=>!isRev(t.test)).map(t=>({test:t.test, verdict:'placebo', base:t.base, head:t.head}));
  let tiles;
  const agentNamed = agentEv.length + agentPl.length;
  if(agentNamed===agentTotal) tiles = [...agentPl, ...agentEv].map(t=>({...t, who:'agent'}));
  else tiles = [...agentEv.map(t=>({...t,who:'agent'}))];
  ev.filter(e=>isRev(e.test)).forEach(t=>tiles.push({...t, who:'reviewer'}));
  (R.placebo_tests||[]).filter(t=>isRev(t.test)).forEach(t=>tiles.push({test:t.test, verdict:'placebo', base:t.base, head:t.head, who:'reviewer'}));
  if(!tiles.length) return;
  // interleave agent placebo/catching so the reveal reads as a sweep, not two blocks
  if(agentNamed===agentTotal){ const ag=tiles.filter(t=>t.who==='agent'), rest=tiles.filter(t=>t.who!=='agent');
    const pl=ag.filter(t=>t.verdict==='placebo'), ca=ag.filter(t=>t.verdict!=='placebo'); const mix=[];
    while(pl.length||ca.length){ if(pl.length) mix.push(pl.shift()); if(pl.length) mix.push(pl.shift()); if(ca.length) mix.push(ca.shift()); }
    tiles=[...mix, ...rest]; }

  const ST={catching:['CATCHING','catching'], placebo:['PLACEBO','placebo'], 'broken-by-pr':['REGRESSION','broken'], 'failing-both':['STILL FAILS','fboth']};
  const short = t => t.split('.').pop().replace(/_/g,' ');
  const res = o => o==='Passed'?['PASS','p']:o==='Failed'?['FAIL','f']:[String(o||'?').toUpperCase(),''];
  const trx = (R.placebo_tests&&R.placebo_tests[0]&&R.placebo_tests[0].trx_sha256)||'';
  const box=h(`<div><h2>Receipt machine: every test, run on the old code and the new code</h2>
    <div class="fx-machine">
      <div class="fx-term"><div class="bar"><i></i><i></i><i></i></div><div data-lines></div></div>
      <div><div class="fx-tiles"></div>
        <div class="fx-verdict"></div>
        <div class="row" style="margin-top:8px"><button class="fx-replay fx-plain" type="button">↻ replay</button><span class="muted" style="font-size:12px">replay of the executed run · results from the TRX files in the record${trx?` · trx sha256 ${E(trx.slice(0,12))}…`:''}</span></div>
      </div></div></div>`);
  const tbox=box.querySelector('.fx-tiles');
  tiles.forEach(t=>tbox.append(h(`<div class="fx-tile" title="${E(t.test)}"><div class="nm">${t.who==='reviewer'?'<span style="color:var(--accent)">receipt · </span>':''}${E(short(t.test))}</div>
     <div class="rs"><span data-b>BASE ·</span><span data-h>HEAD ·</span></div><div class="st">${(ST[t.verdict]||[String(t.verdict).toUpperCase()])[0]}</div></div>`)));
  const target=[...app.children].find(c=>c.tagName==='H2' && /story vs the receipts/i.test(c.textContent));
  app.insertBefore(box, target||null);
  const lines=box.querySelector('[data-lines]'), vEl=box.querySelector('.fx-verdict');
  const verdictTxt = a.placebo
    ? `<span class="x">${a.placebo} of ${agentTotal}</span> of the agent's tests pass on the old code too. They prove nothing about this PR.`
    : (a['broken-by-pr']||rv['broken-by-pr']) ? `<span class="x">${(a['broken-by-pr']||0)+(rv['broken-by-pr']||0)} test passes before and fails after</span>: a proven regression.`
    : `${(a.catching||0)+(rv.catching||0)} tests fail before and pass after: proven behavior changes.`;
  let runId=0;
  async function run(){
    const my=++runId; lines.innerHTML=''; vEl.classList.remove('on'); vEl.innerHTML=verdictTxt;
    [...tbox.children].forEach(el=>{ el.className='fx-tile'; el.querySelector('[data-b]').className=''; el.querySelector('[data-b]').textContent='BASE ·'; el.querySelector('[data-h]').className=''; el.querySelector('[data-h]').textContent='HEAD ·'; });
    const say = async (html, ms=380)=>{ if(my!==runId) return false; lines.querySelector('.fx-cur')?.remove(); lines.append(h(`<div class="ln">${html} <span class="fx-cur"></span></div>`)); await wait(ms); return my===runId; };
    if(!await say(`<span class="pr">$</span> uv run et prove ${E(R.requirement.id.replace('#',''))}`,520)) return;
    if(!await say(`<span class="dim"># base</span> ${E(R.base.slice(0,8))} <span class="dim">→ dotnet test</span>`)) return;
    for(let i=0;i<tiles.length;i++){ if(my!==runId) return; const el=tbox.children[i], [tx,c]=res(tiles[i].base); el.classList.add('run'); const s=el.querySelector('[data-b]'); s.textContent='BASE '+tx; s.className=c; await wait(70); }
    if(!await say(`<span class="dim"># head</span> ${E(String(R.head).slice(0,8))} <span class="dim">→ dotnet test</span>`)) return;
    for(let i=0;i<tiles.length;i++){ if(my!==runId) return; const el=tbox.children[i], [tx,c]=res(tiles[i].head); el.classList.remove('run'); void el.offsetWidth; el.classList.add('run'); const s=el.querySelector('[data-h]'); s.textContent='HEAD '+tx; s.className=c; await wait(70); }
    if(!await say(`<span class="dim"># compare per test: fail→pass = proven change, pass→pass = placebo</span>`,300)) return;
    for(let i=0;i<tiles.length;i++){ if(my!==runId) return; const el=tbox.children[i]; el.classList.remove('run'); el.classList.add('done', (ST[tiles[i].verdict]||['','x'])[1]); await wait(110); }
    for(const who of ['agent','reviewer']){ const cnt={}; tiles.filter(t=>t.who===who).forEach(t=>cnt[t.verdict]=(cnt[t.verdict]||0)+1);
      if(Object.keys(cnt).length) await say(`<span class="dim">${who==='agent'?'agent tests   ':'our receipts  '}</span>`+Object.entries(cnt).map(([k,v])=>`<span class="${k==='catching'?'grn':k==='placebo'?'dim':'red'}">${v} ${E(k)}</span>`).join('  '),200); }
    vEl.classList.add('on');
  }
  box.querySelector('.fx-replay').onclick=run;
  onSeen(box, run);
}

function timeline(R){
  const tm=R.time_machine; if(!tm) return;
  const card=[...doc.querySelectorAll('h2')].find(x=>/Time Machine/.test(x.textContent))?.parentElement?.querySelector('.card'); if(!card) return;
  const hs=tm.history||{}, p=hs.pr||{}, iss=hs.issue||{};
  const d=s=>s?String(s).slice(0,10):'?';
  const months=(p.merged_at&&iss.created_at)?Math.round((new Date(iss.created_at)-new Date(p.merged_at))/2.63e9):null;
  const el=h(`<div><div class="row" style="justify-content:space-between;margin-top:6px"><span class="fx-rewind">◀◀ REWIND: replaying today's tests on the 2024 commit</span>
      <button class="fx-replay fx-plain" type="button">↻ rewind</button></div>
    <div class="fx-tl">
      <div class="rail"></div>
      ${months?`<div class="gap" style="left:31%">${months} months unnoticed</div>`:''}
      <div class="pt" style="left:8%;color:var(--bad)"><i></i><div class="d">${d(p.merged_at)}</div><div class="w">PR #${E((p.html_url||'').split('/').pop())} merged<br><b style="color:var(--bad)">${hs.review_count===0?'0 reviews':E(hs.review_count)+' reviews'}</b></div></div>
      <div class="pt" style="left:55%;color:var(--warn)"><i></i><div class="d">${d(iss.created_at)}</div><div class="w">a user reports ${E(R.requirement.id)}</div></div>
      <div class="pt" style="left:92%;color:var(--accent)"><i></i><div class="d">now</div><div class="w">agent's PR + its ${tm.entries.length} tests</div></div>
      <div class="probe"></div>
      <div class="boom" style="left:8%"></div>
      <div class="catch" style="left:calc(8% + 14px)">⚠ ${tm.caught_by.length} GO RED · analyzer silent in ${tm.silenced_diagnostics.length}/${tm.entries.length}</div>
    </div></div>`);
  card.insertBefore(el, card.children[1]||null);
  const tl=el.querySelector('.fx-tl');
  const go=()=>{ tl.classList.remove('go'); void tl.offsetWidth; tl.classList.add('go'); };
  el.querySelector('.fx-replay').onclick=go; onSeen(tl, go);
}

function calibration(R){
  const cal=R.calibration; if(!cal||cal.status!=='measured') return;
  const h2=[...doc.querySelectorAll('h2')].find(x=>/How far to trust/.test(x.textContent)); const card=h2&&h2.nextElementSibling; if(!card) return;
  const names=Object.keys(cal.screeners);
  const lab=n=>n==='tests'?'Tests':'AI · '+n.split(':')[1];
  const ok=v=>v===true||v==='killed'||v==='killed-by-compiler', no=v=>v===false||v==='survived';
  const bars=names.map(n=>{ const v=cal.screeners[n]; return {l:lab(n), c:v.caught, m:v.measured, col:n==='tests'?'linear-gradient(90deg,#5ad0ff,#7aa2ff)':'linear-gradient(90deg,#9b7aff,#ff7ad9)'}; });
  bars.push({l:'Together', c:cal.union_caught, m:cal.planted, col:'linear-gradient(90deg,#38e09b,#b6ff7a)'});
  const el=h(`<div><p style="margin:0 0 4px"><b>${cal.planted} bugs planted in this PR's changed code.</b> <span class="muted">Each screener is scored on catching them. That score, not the AI's self-report, is its confidence for this PR.</span></p>
    <div class="fx-bars">${bars.map(b=>`<div class="fx-bar"><span>${E(b.l)}</span><div class="tr"><b data-w="${b.m?100*b.c/b.m:0}" style="background:${b.col}"></b></div><span class="v">${b.c}/${b.m}</span></div>`).join('')}</div>
    <div class="fx-cal">${cal.rows.map(r=>{ const ds=names.map(n=>`<span class="${ok(r[n])?'y':no(r[n])?'n':''}" title="${E(lab(n))}">${n==='tests'?'T':'AI'}</span>`).join('');
      const split=names.some(n=>ok(r[n]))&&names.some(n=>no(r[n]));
      return `<div class="fx-mut${split?' split':''}" title="${E(r.description)}"><div class="id">${E(r.id)}</div><div class="rg">${E(r.region)}</div><div class="dots">${ds}</div></div>`; }).join('')}</div>
    <p class="muted" style="font-size:12px;margin:2px 0 12px">T = tests, AI = reviewer · green caught, red missed · amber border = only one screener caught it. They miss <i>different</i> bugs.</p></div>`);
  card.insertBefore(el, card.firstChild);
  onSeen(el, ()=>{ el.querySelectorAll('.fx-bar b').forEach(b=>b.style.width=b.dataset.w+'%');
    el.querySelectorAll('.fx-mut').forEach((m,i)=>setTimeout(()=>m.classList.add('on'), RM?0:120*i)); });
}

/* predict -> reveal theatre */
function watchReveals(){
  const scramble=(el)=>{ if(RM||el.dataset.fxS) return; const fin=el.textContent; el.dataset.fxS='1'; const hex='0123456789abcdef'; let k=0;
    const it=setInterval(()=>{ k++; el.textContent=fin.replace(/[0-9a-f](?=[0-9a-f]*…)/g,()=>hex[Math.random()*16|0]); if(k>14){ clearInterval(it); el.textContent=fin; el.classList.add('fx-seal'); } },45); };
  const stamp=(card, cls, big, small)=>{ card.querySelector('.fx-stamp')?.remove(); const host=card.querySelector('.reveal')||card; host.classList.add('fx-stage');
    host.append(h(`<div class="fx-stamp ${cls}">${big}<small>${small}</small></div>`));
    const v=h(`<div class="fx-veil ${cls==='miss'?'':cls==='match'?'ok':'drill'}"></div>`); doc.body.append(v); setTimeout(()=>v.remove(),1000);
    card.classList.remove('fx-flash-bad','fx-flash-ok'); card.classList.add(cls==='match'?'fx-flash-ok':'fx-flash-bad');
    if(cls!=='match' && !RM){ card.classList.remove('fx-shake'); void card.offsetWidth; card.classList.add('fx-shake'); }
    host.scrollIntoView({behavior:RM?'auto':'smooth', block:'center'}); };
  new MutationObserver(ms=>{ for(const m of ms){
    if(m.type==='characterData' || m.target.matches?.('[data-hash]')){ const t=m.target.nodeType===3?m.target.parentElement:m.target; if(t&&t.matches('[data-hash]')&&t.textContent) scramble(t); }
    for(const n of m.addedNodes){ if(n.nodeType!==1) continue;
      if(n.matches('.banner.b-miss,.banner.b-match') && n.closest('.reveal')){ const card=n.closest('.card[id^="q-"]'); if(card){
        const miss=n.classList.contains('b-miss'); setTimeout(()=>stamp(card, miss?'miss':'match', miss?'MISMATCH':'MATCH', miss?'this is the review':'accepted with evidence'), RM?0:120); } }
      if(n.matches('.drill-ok,.drill-miss')){ const card=n.closest('.card[id^="q-"]'); if(card){ const ok=n.classList.contains('drill-ok');
        setTimeout(()=>stamp(card,'drill', ok?'DRILL · CAUGHT':'DRILL · MISSED', ok?'planted bug, you found it':'signature will be flagged'),RM?0:150); } }
    } } }).observe(doc.getElementById('app'), {childList:true, subtree:true, characterData:true});
}

/* thermal receipt after signing (reads the signed record; changes nothing in it) */
function printReceipt(R, rec){
  const out=doc.querySelector('#sign [data-out]'); if(!out) return;
  const bcs=rec.behavior_changes, matched=bcs.filter(b=>b.match).length;
  const hc=rec.human_calibration&&rec.human_calibration.status==='measured'?rec.human_calibration:null;
  const flagged=(rec.signoff.flags||[]).length>0;
  const cal=rec.calibration&&rec.calibration.status==='measured'?rec.calibration:null;
  const a=rec.ledger_counts.agent_tests||{}, at=Object.values(a).reduce((x,y)=>x+y,0);
  const hex=rec.record_sha256||''; let bc='';
  for(let i=0;i<hex.length;i++){ const v=parseInt(hex[i],16); bc+=`<i style="width:${1+(v%4)}px;margin-right:${(v>>2)%3}px"></i>`; }
  const L=(k,v,c='')=>`<div class="l"><span>${k}</span><span class="${c}">${v}</span></div>`;
  const r=h(`<div class="fx-receipt" role="img" aria-label="Signed review receipt">
    <div class="stampd${flagged?' flag':''}">${flagged?'FLAGGED':'SIGNED'}</div>
    <h4>RECEIPT</h4><div class="c">receipts, not reviews · prove · predict · sign</div><hr>
    ${L('requirement',E(rec.requirement.id))}${L('base → head',E(rec.base.slice(0,8))+' → '+E(String(rec.head).slice(0,8)))}<hr>
    ${L('proven behavior changes',bcs.filter(b=>b.status==='proven').length)}
    ${L('predictions matched',matched+' / '+bcs.length, matched===bcs.length?'grn':'')}
    ${L('mismatches (the review)',rec.signoff.mismatches.length?E(rec.signoff.mismatches.join(', ')):'none', rec.signoff.mismatches.length?'red':'')}
    ${L('refused to decide',rec.refusals.length)}
    ${at?L('agent tests that are placebos',(a.placebo||0)+' / '+at, a.placebo?'red':''):''}
    ${cal?L('planted bugs caught (union)',cal.union_caught+' / '+cal.planted):''}
    ${hc?L('human drill',hc.caught+' / '+hc.drills+' caught', hc.caught===hc.drills?'grn':'red'):''}
    ${L('not checked',rec.not_checked.length+' item(s), listed')}<hr>
    ${L('signed by',E(rec.signoff.name))}${rec.signoff.role?L('role',E(rec.signoff.role)):''}${L('at',E(rec.signoff.timestamp.replace('T',' ').slice(0,19))+'Z')}
    <div class="bc">${bc}</div><div class="hx">record sha256 ${E(hex)}</div><hr>
    <div class="c">the AI review is advice with evidence, not the approval</div></div>`);
  out.prepend(r);
  r.scrollIntoView({behavior:RM?'auto':'smooth', block:'center'});
}

/* =========================== BUDGET PAGE =========================== */
function budgetPage(B){
  const stats=doc.getElementById('stats'); if(!stats) return;
  const fnv=s=>{ let x=2166136261; for(const c of s){ x^=c.charCodeAt(0); x=Math.imul(x,16777619)>>>0; } return x; };
  const all=[...B.machine.map(m=>({p:m.path, k:m.cls==='generated'?'gen':'tpl'})), ...B.human.map(m=>({p:m.path,k:'hum'}))].sort((x,y)=>fnv(x.p)-fnv(y.p));
  const gen=all.filter(f=>f.k==='gen').length, tpl=all.filter(f=>f.k==='tpl').length, hum=all.filter(f=>f.k==='hum').length;
  const T=B.totals;
  const el=h(`<div class="card fx-triage"><div class="row" style="justify-content:space-between">
      <div class="fx-count"><span class="big" data-c>${T.files}</span><span><b>files</b><div class="muted" style="font-size:13px" data-cl>changed by the agent</div></span></div>
      <button class="fx-replay fx-plain" type="button">↻ replay</button></div>
    <div class="fx-phase" data-ph>&nbsp;</div>
    <div class="fx-grid">${all.map(f=>`<i class="fx-f ${f.k}" title="${E(f.p)}"></i>`).join('')}</div>
    <div class="fx-legend"><span><i style="background:var(--ok)"></i>${gen} regenerated + byte-compared</span>${tpl?`<span><i style="background:#5ad0ff"></i>${tpl} template output checked</span>`:''}<span><i style="background:var(--warn)"></i>${hum} need a human</span></div></div>`);
  stats.after(el);
  const cEl=el.querySelector('[data-c]'), cl=el.querySelector('[data-cl]'), ph=el.querySelector('[data-ph]'), tiles=[...el.querySelectorAll('.fx-f')];
  let runId=0;
  const tween=async (from,to,ms,my)=>{ const t0=performance.now(); return new Promise(res=>{ const st=t=>{ if(my!==runId) return res(); const p=Math.min(1,(t-t0)/ms);
    cEl.textContent=Math.round(from+(to-from)*(1-Math.pow(1-p,3))); p<1?requestAnimationFrame(st):res(); }; RM?(cEl.textContent=to,res()):requestAnimationFrame(st); }); };
  async function run(){
    const my=++runId; tiles.forEach(t=>t.classList.remove('clr','lit','scan')); cEl.textContent=T.files; cEl.classList.remove('amber'); cl.textContent='changed by the agent';
    ph.textContent='$ regenerate snapshots with the PR\'s own generator, compare bytes…'; await wait(700); if(my!==runId) return;
    const g=tiles.filter(t=>t.classList.contains('gen'));
    for(let i=0;i<g.length;i+=12){ if(my!==runId) return; g.slice(i,i+12).forEach(t=>t.classList.add('scan')); await wait(28); }
    await wait(250); g.forEach(t=>{t.classList.remove('scan');t.classList.add('clr');});
    ph.textContent=`✓ ${gen} cleared by machine (regenerated, byte-compared)`; await tween(T.files, T.files-gen, 900, my); if(my!==runId) return;
    if(tpl){ await wait(400); ph.textContent=`✓ ${tpl} template outputs checked against the .tt changes`; tiles.filter(t=>t.classList.contains('tpl')).forEach(t=>t.classList.add('clr')); await tween(T.files-gen, hum, 600, my); }
    if(my!==runId) return; await wait(350);
    tiles.filter(t=>t.classList.contains('hum')).forEach(t=>t.classList.add('lit')); cEl.textContent=T.human; cEl.classList.add('amber');
    cl.textContent=`need a human · about ${T.human_minutes} min instead of ${T.naive_minutes} (estimate)`; ph.textContent='→ human minutes go only where no machine can give a receipt';
  }
  el.querySelector('.fx-replay').onclick=run; onSeen(el, run);
}

/* =========================== INDEX PAGE =========================== */
function indexPage(){
  const app=doc.getElementById('app'); if(!app||doc.getElementById('record')) return;
  const head=app.querySelector('header'); if(!head || !/4 agent-written PRs|agent-written PRs/.test(head.textContent)) return;
  const n=app.querySelectorAll('.grid > .card').length;
  head.after(h(`<section class="fx-hero"><div class="fx-scan"></div><div class="k">Junction 2026 · Earned Trust in AI Code</div>
    <div class="big">Don't trust the AI.<br>Make it hand over <b>receipts</b>.</div>
    <p class="sub">The AI proves what behavior changed. The human predicts what should happen before seeing it. Every mismatch is the review. Run on ${n} real agent-written PRs.</p>
    <div class="fx-steps">${['Prove','Predict','Measure','Refuse','Sign'].map((s,i)=>`<span style="animation-delay:${300+i*140}ms"><b>${i+1}</b> ${s}</span>`).join('')}</div></section>`));
}

function init(){
  brand();
  const rj=doc.getElementById('record'), bj=doc.getElementById('budget');
  try{
    if(rj && typeof R!=='undefined') reviewPage(R);       // eslint-disable-line no-undef
    else if(bj && typeof B!=='undefined') budgetPage(B);  // eslint-disable-line no-undef
    else indexPage();
  }catch(e){ console.error('[fx]', e); }   // presentation must never break the page
  armReveal();
}
init();
})();
