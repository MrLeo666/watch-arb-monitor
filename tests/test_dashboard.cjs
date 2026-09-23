const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('docs/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = {};
const context = vm.createContext({
  document: { getElementById(id) {
    return elements[id] ||= { value: '', checked: false, innerHTML: '', addEventListener() {} };
  } },
  setInterval: () => 0,
  localStorage: {getItem: () => null, setItem() {}},
  matchMedia: () => ({ matches: false }),
  // Keep initial async load pending; fixtures exercise the real render function.
  fetch: () => new Promise(() => {}),
});
vm.runInContext(fs.readFileSync('docs/decision.js', 'utf8'), context);
vm.runInContext(script, context);
function render(lot) {
  context.fixture = lot;
  vm.runInContext('LOTS=[fixture];render()', context);
  return elements.main.innerHTML;
}
const base = { brand: 'Cartier', platform: 'Example', status: 'live', current_bid: 1000,
  estimate_currency: 'EUR', current_bid_usd: 1200 };
assert.match(render(base), /USD 1,200/);
assert.match(render(base), /EUR 1,000/);
assert.doesNotMatch(render(base), /USD 1,000/);
assert.match(render({ ...base, current_bid_usd: null }), /EUR 1,000/);
assert.doesNotMatch(render({ ...base, current_bid_usd: null }), /USD 1,000/);
assert.match(render({ ...base, estimate_currency: 'USD', current_bid_usd: 1000 }), /USD 1,000/);
assert.match(render({ ...base, estimate_currency: '', current_bid_usd: null }), /幣種未提供 1,000/);
// Render the full synchronized dataset, then exercise platform and search filters.
context.fixtures = JSON.parse(fs.readFileSync('docs/lots.json', 'utf8'));
vm.runInContext('LOTS=fixtures;render()', context);
assert.ok(elements.main.innerHTML.includes('Cartier'));
elements.platform.value = 'does-not-exist';
vm.runInContext('render()', context);
assert.match(elements.main.innerHTML, /沒有符合條件/);
console.log('Dashboard currency, dataset rendering and filter checks passed');

const evalJS = code => vm.runInContext(code, context);
assert.equal(evalJS('bidCap({net:20000,premium:25,other:5,fixed:1000,profit:3000,step:100})'), 12300);
assert.equal(evalJS('bidCap({net:100,premium:0,other:0,fixed:200,profit:0,step:1})'), 0);
assert.equal(evalJS('bidCap({net:100,premium:0,other:0,fixed:0,profit:0,step:0})'), null);
assert.equal(evalJS('bidCap({net:100,premium:"",other:0,fixed:0,profit:0,step:1})'), null);
assert.equal(evalJS('isFresh({last_seen:new Date().toISOString()})'), true);
assert.equal(evalJS('isFresh({last_seen:"2020-01-01T00:00:00Z"})'), false);
assert.equal(evalJS('isFresh({last_seen:"bad"})'), false);
assert.equal(evalJS('Number.isNaN(endTime({ends_at:"2026-09-23"}))'), true);
assert.equal(evalJS('actionable({status:"live",last_seen:new Date().toISOString(),ends_at:"2020-01-01T00:00:00Z"})'), false);
elements.platform.value = '';
assert.doesNotMatch(render({...base, title_raw:'<img src=x onerror=alert(1)>', source_url:'javascript:alert(1)'}), /<img src=x|href="javascript:/);
elements.favoritesOnly.checked = true;
assert.match(render({...base,lot_id:'test'}), /沒有符合條件/);
evalJS('privateState.favorites=["test"]');
assert.match(render({...base,lot_id:'test'}), /已收藏/);
elements.favoritesOnly.checked = false;
elements.flagOnly.checked = true;
assert.match(render({...base,arb_flag:true,last_seen:'2020-01-01T00:00:00Z'}), /沒有符合條件/);
console.log('Decision caps, stale-data gating, favorites and escaping passed');
