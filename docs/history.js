'use strict';
const H = (() => {
  const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = v => Number(v).toLocaleString('en-US', {maximumFractionDigits:0});
  const date = ts => new Date(ts).toISOString().slice(0,10);
  const median = xs => { const s=[...xs].sort((a,b)=>a-b), n=s.length; return n ? (s[Math.floor((n-1)/2)]+s[Math.floor(n/2)])/2 : null; };
  function annual(points) {
    const groups=new Map();
    for(const [ts,p] of points){const y=new Date(ts).getUTCFullYear();if(!groups.has(y))groups.set(y,[]);groups.get(y).push(p);}
    return [...groups].sort((a,b)=>a[0]-b[0]).map(([year,p])=>({year,count:p.length,median:median(p),low:Math.min(...p),high:Math.max(...p)}));
  }
  function filtered(series,brand,q){q=q.toLowerCase().trim();return series.filter(s=>(!brand||s.brand===brand)&&(!q||`${s.model} ${s.reference}`.toLowerCase().includes(q)));}
  function chart(points,mode) {
    if(!points.length)return '<p class="empty">這個時間範圍沒有觀察值。</p>';
    const ys=annual(points), values=mode==='annual'?ys.map(y=>[Date.UTC(y.year,6,1),y.median]):points;
    const minX=Math.min(...values.map(p=>p[0])), maxX=Math.max(...values.map(p=>p[0]));
    const maxY=Math.max(...values.map(p=>p[1]))*1.08;
    const x=t=>70+(maxX===minX?300:(t-minX)/(maxX-minX)*600), y=p=>245-p/maxY*210;
    let content='';
    for(let i=0;i<=4;i++){const v=maxY*i/4;content+=`<line x1="70" y1="${y(v)}" x2="680" y2="${y(v)}" stroke="#e5ebe8"/><text x="62" y="${y(v)+4}" text-anchor="end" fill="#576970" font-size="11">${number(v)}</text>`;}
    if(mode==='annual'&&values.length>1)content+=`<polyline points="${values.map(p=>`${x(p[0])},${y(p[1])}`).join(' ')}" fill="none" stroke="#176c60" stroke-width="2"/>`;
    for(const [ts,p] of values) content+=`<circle cx="${x(ts)}" cy="${y(p)}" r="${mode==='annual'?4:2.7}" fill="#176c60" opacity="${mode==='annual'?1:.45}"><title>${mode==='annual'?new Date(ts).getUTCFullYear():date(ts)} · EUR ${number(p)}</title></circle>`;
    return `<svg class="chart" viewBox="0 0 720 290" role="img" aria-label="${mode==='annual'?'年度樣本中位數':'歷史價格散點'}，EUR。完整數值見下方表格。"><text x="70" y="17" font-size="11" fill="#576970">EUR · ${mode==='annual'?'年度樣本中位數（非固定品質指數）':'來源價格觀察（未逐筆核驗）'}</text>${content}<text x="70" y="274" font-size="11">${new Date(minX).getUTCFullYear()}</text><text x="670" y="274" text-anchor="end" font-size="11">${new Date(maxX).getUTCFullYear()}</text></svg>`;
  }
  return {escape,number,date,median,annual,filtered,chart};
})();
if(typeof module!=='undefined')module.exports=H;
if(typeof document!=='undefined'){
  const $=id=>document.getElementById(id);let data=null,selected=null;
  const params=new URLSearchParams(location.search);
  function draw(){
    const s=selected;if(!s)return;
    const since=Number($('sinceYear').value), mode=$('chartMode').value;
    const points=s.points.filter(p=>new Date(p[0]).getUTCFullYear()>=since), years=H.annual(points);
    $('chartView').innerHTML=H.chart(points,mode);
    $('yearTable').innerHTML=years.length?`<table><thead><tr><th>年份</th><th>觀察數</th><th>中位數 EUR</th><th>最低</th><th>最高</th></tr></thead><tbody>${years.map(y=>`<tr><td>${y.year}</td><td>${y.count}</td><td>${H.number(y.median)}</td><td>${H.number(y.low)}</td><td>${H.number(y.high)}</td></tr>`).join('')}</tbody></table>`:'<p>沒有符合期間的資料；不沿用歷史價格估算現在。</p>';
    $('rangeCount').textContent=`目前顯示 ${points.length} 個觀察值；低樣本年份及特別版本可能顯著影響中位數。`;
  }
  function detail(s){
    selected=s;
    const points=s.points,last=points[points.length-1][0],first=points[0][0];
    const latestYear=H.annual(points).at(-1), age=(Date.now()-last)/86400000;
    const source=new URL(s.source_url);
    const safeSource=source.protocol==='https:'&&source.hostname==='www.collectorsquare.com'?H.escape(source.href):'#';
    $('historyDetail').innerHTML=`<div class="card"><p class="eyebrow">${H.escape(s.brand)} / ${s.reference?'REFERENCE FAMILY':'COLLECTION'}</p><h2>${H.escape(s.model)} ${H.escape(s.reference)}</h2><p class="muted">${s.reference?'參考編號家族，並非相同材質與盤面':'整個系列，混合不同參考編號'} · 單一彙整來源，未經獨立交叉驗證</p><div class="metrics"><div class="metric"><b>${points.length}</b><span>本頁圖表觀察數</span></div><div class="metric"><b>${H.date(last)}</b><span>最新圖表日期（UTC）</span></div><div class="metric"><b>€ ${H.number(latestYear.median)}</b><span>${latestYear.year} 年樣本中位數 · ${latestYear.count} 筆</span></div></div>${age>365?'<p class="warning">最新圖表觀察已超過一年，不代表目前行情。</p>':''}${s.state!=='ok'?'<p class="warning">最近更新失敗，顯示上次成功快照。</p>':''}<div class="chart-controls"><label>展示 <select id="chartMode"><option value="annual">年度中位數</option><option value="scatter">歷史價格散點</option></select></label><label>起始年份 <select id="sinceYear"><option value="0">全部年份</option>${Array.from({length:new Date().getUTCFullYear()-new Date(first).getUTCFullYear()+1},(_,i)=>new Date(first).getUTCFullYear()+i).map(y=>`<option>${y}</option>`).join('')}</select></label></div><div id="chartView"></div><p id="rangeCount" class="muted"></p><div id="yearTable" class="table-wrap"></div></div><div class="card"><b>資料來源與適用範圍</b><p><a href="${safeSource}" target="_blank" rel="noopener">在 Collector Square 核對此系列 ↗</a></p><p class="muted">擷取日期：${H.escape(s.retrieved_at.slice(0,10))} · 歷史範圍：${H.date(first)} — ${H.date(last)}。擷取日期不是成交日期；圖表時間戳按 UTC 顯示，可能與來源當地成交日期相差一天。來源圖表的 EUR 換算方式及含佣口徑待核實；未作今日匯率重算。</p><p class="muted">序列間可能重疊；不合併統計。${s.excluded_nonpositive||0} 個非正價格點未納入，正值極端價格仍保留。此歷史不自動填入公允價、淨回款或報價上限。</p><a href="index.html">返回雷達核對現有拍品與報價假設 →</a></div>`;
    $('chartMode').addEventListener('change',draw);$('sinceYear').addEventListener('change',draw);draw();
  }
  function list(){
    const rows=H.filtered(data.series,$('historyBrand').value,$('historySearch').value);
    $('seriesList').innerHTML=rows.map(s=>`<button type="button" class="series-button" data-id="${H.escape(s.id)}" aria-pressed="${selected?.id===s.id}">${H.escape(s.model)} ${H.escape(s.reference)}<small>${H.escape(s.brand)} · ${s.reference?'編號家族':'系列總覽'}</small></button>`).join('')||'<p class="empty">未接入此型號。清除搜尋可查看已接入系列，不以近似型號替代。</p>';
    if(!rows.some(s=>s.id===selected?.id)){
      selected=null;if(rows.length){detail(rows[0]);list();}else $('historyDetail').innerHTML='<p class="empty">沒有匹配的價格歷史。</p>';
    }
  }
  $('seriesList').addEventListener('click',e=>{const b=e.target.closest('button[data-id]');if(b){const s=data.series.find(x=>x.id===b.dataset.id);if(s){detail(s);list();}}});
  $('historyBrand').addEventListener('change',list);$('historySearch').addEventListener('input',list);
  fetch('price_history.json').then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(d=>{
    if(d.schema_version!==1||!Array.isArray(d.series)||!d.series.length)throw new Error('Invalid history');
    for(const s of d.series){if(!s.points?.length||s.points.some(p=>!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite)||p[1]<=0))throw new Error('Invalid series');}
    data=d;
    const brands=[...new Set(d.series.map(s=>s.brand))];
    $('historyBrand').innerHTML='<option value="">全部品牌</option>'+brands.map(b=>`<option>${H.escape(b)}</option>`).join('');
    if(brands.includes(params.get('brand')))$('historyBrand').value=params.get('brand');
    $('historySearch').value=params.get('q')||'';
    $('loadState').textContent=`已接入 ${d.series.length} 個系列／編號頁面，非全站完整資料庫。最近檢查：${d.checked_at.slice(0,10)}${d.errors.length?'；部分來源更新失敗。':''}`;
    list();
  }).catch(()=>{$('loadState').textContent='歷史資料載入失敗，請稍後重新整理。拍賣雷達不受影響。';});
}
