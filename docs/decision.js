// Private state stays in this browser; no account or network writes.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = value => /^https?:\/\//i.test(value || '') ? esc(value) : '#';
let privateState = {favorites: [], quotes: {}};
try {
  const saved = JSON.parse(localStorage.getItem('watch-decision-v1') || 'null');
  if (saved && Array.isArray(saved.favorites) && saved.quotes && typeof saved.quotes === 'object') privateState = saved;
} catch (_) {}
function savePrivate() {
  try { localStorage.setItem('watch-decision-v1', JSON.stringify(privateState)); }
  catch (_) { $('privacyNotice').textContent = '儲存不可用：本次修改只保留到頁面關閉。'; }
}
function isFresh(l, now = Date.now()) {
  const age = now - Date.parse(l.last_seen);
  return Number.isFinite(age) && age >= 0 && age <= 30 * 60 * 1000;
}
function endTime(l) {
  return /^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/.test(l.ends_at || '') ? Date.parse(l.ends_at) : NaN;
}
function actionable(l) {
  const end = endTime(l);
  return l.status !== 'past' && isFresh(l) && !(Number.isFinite(end) && end <= Date.now());
}
function timing(l) {
  const end = endTime(l);
  if (!Number.isFinite(end)) return esc(l.auction_date || '日期未提供') + '<div class="sub">逐件結標時間待核實</div>';
  const mins = Math.ceil((end - Date.now()) / 60000);
  const label = mins <= 0 ? '時間已過，結果待核實' : mins < 60 ? `${mins} 分鐘後` : `${Math.floor(mins / 60)} 小時 ${mins % 60} 分後`;
  return esc(new Date(end).toLocaleString('zh-HK', {timeZone:'Asia/Hong_Kong',hour12:false})) + '<div class="sub">香港時間 · '+label+'</div>';
}
function bidCap(p) {
  const keys = ['net','premium','other','fixed','profit','step'];
  if (keys.some(k => p[k] === '' || !Number.isFinite(Number(p[k])) || Number(p[k]) < 0) || Number(p.step) <= 0 || Number(p.net) <= 0) return null;
  const raw = (Number(p.net) - Number(p.fixed) - Number(p.profit)) / (1 + (Number(p.premium) + Number(p.other)) / 100);
  return Math.max(0, Math.floor(raw / Number(p.step)) * Number(p.step));
}
function renderOverview(meta) {
  const favorites = LOTS.filter(l => privateState.favorites.includes(l.lot_id));
  const soon = favorites.filter(l => l.status !== 'past' && endTime(l) > Date.now() && endTime(l) - Date.now() <= 24*3600000);
  const old = LOTS.filter(l => l.status !== 'past' && !isFresh(l)).length;
  $('overview').innerHTML = `<b>決策清單</b> · 收藏 ${favorites.length} 件 · 24 小時內結標 ${soon.length} 件 · 待刷新 ${old} 件
    <p class="sub">價格超過 30 分鐘即停用套利提示；目前仍為每日抓取。收藏與報價只存於此瀏覽器，不跨裝置同步。</p>
    ${soon.map(l=>`<p>${esc(l.title_raw)} · ${timing(l)} · <a href="${safeUrl(l.source_url)}" target="_blank" rel="noopener">核對官方出價</a></p>`).join('')}`;
  const states = {returned:'已返回資料，完整性未驗證',empty_or_failed:'無資料或抓取失敗',partial_or_failed:'可能不完整',failed:'抓取失敗'};
  $('health').innerHTML = '<summary>平台資料狀態</summary>' + (meta?.sources?.length ? meta.sources.map(s=>`<p>${esc(s.source)} · ${esc(states[s.state] || '未知')} · ${Number(s.count)||0} 件 · ${esc(s.checked_at)}</p>`).join('') : '<p>此批資料尚無平台健康記錄；下次抓取後產生。不能將缺少資料視為沒有拍品。</p>');
}
function openQuote(id) {
  const lot = LOTS.find(l => l.lot_id === id);
  if (!lot) return;
  const p = privateState.quotes[id] || {net:'',premium:lot.buyers_premium_pct ?? '',other:'',fixed:'',profit:'',step:''};
  $('quoteTitle').textContent = lot.title_raw;
  $('quoteContext').textContent = `全表使用 ${lot.estimate_currency || '未提供幣種（請先核對）'}。淨回款須已扣出售費用。佣金為資料預填估算，請按場次核實；階梯佣金需另行核算。`;
  $('quoteForm').dataset.lot = id;
  const labels = {net:'保守出售淨回款',premium:'買家佣金 %',other:'其他按落槌价計費 %',fixed:'固定成本（運保／维修／持有）',profit:'最低目標利潤',step:'競價步幅'};
  $('quoteFields').innerHTML = Object.entries(labels).map(([k,v])=>`<label>${v}<input name="${k}" type="number" min="${k==='step'?'0.01':'0'}" step="any" required value="${esc(p[k])}"></label>`).join('');
  $('quoteResult').textContent = '請填妥並核實全部成本。計算結果為假設情境，並非即時可成交報價。';
  $('quoteDialog').showModal();
}
function setupDecision() {
  $('main').addEventListener('click', e => {
    const button = e.target.closest('button[data-lot]');
    if (!button) return;
    const id = button.dataset.lot;
    if (button.dataset.action === 'quote') { openQuote(id); return; }
    const set = new Set(privateState.favorites);
    set.has(id) ? set.delete(id) : set.add(id);
    privateState.favorites = [...set]; savePrivate(); render();
  });
  $('quoteClose').addEventListener('click', () => $('quoteDialog').close());
  $('quoteForm').addEventListener('submit', e => {
    e.preventDefault();
    const p = Object.fromEntries(new FormData(e.target));
    const cap = bidCap(p);
    if (cap === null) { $('quoteResult').textContent = '請輸入有效的非負金額及正數步幅。'; return; }
    const lot = LOTS.find(l => l.lot_id === e.target.dataset.lot);
    privateState.quotes[lot.lot_id] = p; savePrivate();
    $('quoteResult').textContent = `情境最高落槌價：${lot.estimate_currency || '幣種待確認'} ${fmt(cap)}。公式：（淨回款 − 固定成本 − 目標利潤）÷（1 + 佣金% + 其他費率%），按步幅向下取整。${cap === 0 ? '此假設下沒有正數報價空間。' : ''} ${!actionable(lot) ? '資料非新鮮有效報價，請先在官方頁面核實。' : '仍需核實官方競價檔位及品相。'}`;
  });
  setInterval(() => { if (LOTS.length) render(); }, 60000);
}
