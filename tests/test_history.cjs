const assert=require('node:assert/strict');
const H=require('../docs/history.js');
const rows=[{brand:'Cartier',model:'Tank',reference:''},{brand:'Patek Philippe',model:'Nautilus',reference:'5711'}];
assert.equal(H.filtered(rows,'Cartier','5711').length,0);
assert.equal(H.filtered(rows,'Patek Philippe','5711').length,1);
assert.equal(H.filtered(rows,'','nautilus').length,1);
assert.equal(H.median([100,300,99999]),300);
assert.equal(H.median([100,300]),200);
assert.equal(H.median([]),null);
assert.equal(H.escape('<script>'),'&lt;script&gt;');
const points=[[Date.UTC(2020,0,1),100],[Date.UTC(2020,1,1),300],[Date.UTC(2022,0,1),600]];
assert.deepEqual(H.annual(points).map(y=>y.year),[2020,2022]);
assert.match(H.chart(points,'annual'),/年度樣本中位數/);
assert.match(H.chart(points,'scatter'),/歷史價格散點/);
assert.match(H.chart([],'annual'),/沒有觀察值/);
assert.doesNotMatch(H.chart([[Date.UTC(2020,0,1),100]],'scatter'),/NaN|Infinity/);
const data=require('../docs/price_history.json');
for(const s of data.series){assert.doesNotMatch(H.chart(s.points,'scatter'),/NaN|Infinity/);assert.equal(H.annual(s.points).reduce((n,y)=>n+y.count,0),s.points.length);}
console.log('History filters, chart arithmetic, sparse years and real series passed');
