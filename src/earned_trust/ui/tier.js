/* Risk-router card (shared; inlined by `et` at TIER_JS). Renders out/<pr>/tier.json as embedded in the page. No score:
   the tier is the highest tier any named rule set, and every rule shows the executed fact and its source. */
function tierCard(T){
  if(!T) return '';
  const E = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const top = T.rules.filter(r => r.fired && r.tier === T.tier);
  const lanes = Object.entries(T.lanes).map(([t,v]) =>
    `<span class="tl tl-${t}${v.files?'':' tl-0'}"><b>${t}</b> ${v.files} file${v.files===1?'':'s'}<span class="tl-l"> · ${v.changed_lines} lines</span></span>`).join('');
  const rows = T.rules.map(r => `<tr class="${r.fired?'':'tr-off'}"><td>${r.fired?'<b>fired</b>':'—'}</td><td class="tr-t">${r.tier}</td>`
    + `<td><b>${E(r.id)}</b><div>${E(r.fact)}</div><div class="tr-src">${E(r.source)}</div></td></tr>`).join('');
  return `<section class="tier tier-${T.tier}" aria-label="Risk tier">
    <div class="tier-badge"><span>${T.tier}</span><small>risk tier</small></div>
    <div class="tier-body">
      <div class="tier-h">Risk router: <b>${E(T.tier_name)}</b> <span class="tier-ns">no score · named rules over executed facts</span></div>
      <ul class="tier-why">${top.map(r => `<li><b>${E(r.id)}</b>: ${E(r.fact)}</li>`).join('')}</ul>
      ${T.tier_without_circuit_breaker ? `<p class="tier-cb">Circuit breaker: without the recorded escape this PR would be <b>${E(T.tier_without_circuit_breaker)}</b>. It tightens itself after an escape and loosens only when trust is earned back.</p>` : ''}
      <div class="tier-lanes">${lanes}</div>
      <details><summary>All ${T.rules.length} rules (${T.rules.filter(r=>r.fired).length} fired) and their sources</summary>
        <table class="tier-rules"><tbody>${rows}</tbody></table></details>
    </div></section>`;
}
