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
  matchMedia: () => ({ matches: false }),
  // Keep initial async load pending; fixtures exercise the real render function.
  fetch: () => new Promise(() => {}),
});
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
