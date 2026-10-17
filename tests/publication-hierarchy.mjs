import assert from 'node:assert/strict';
import fs from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {tableGroups} from '../site/explorer-groups.mjs';
import {hierarchyMetadata,layoutPublicationSeries} from '../site/publication-hierarchy.mjs';
const release=JSON.parse(fs.readFileSync(new URL('../site/release.json',import.meta.url)));
const catalog=JSON.parse(gunzipSync(fs.readFileSync(new URL('../site/'+release.catalog,import.meta.url))));
const pages=[...new Set(catalog.series.flatMap(s=>[s.page,...s.pages||[]]))];let views=0;
for(const page of pages)for(const g of tableGroups(catalog,page))for(const season of new Set(g.series.map(s=>s.seasonal))){
 const before=g.series.filter(s=>s.seasonal===season).map(s=>({...s,...s.tableView})),after=layoutPublicationSeries(before);
 assert.deepEqual(after.map(s=>s.id).sort(),before.map(s=>s.id).sort(),g.id);
 for(const s of after){assert.equal(s.depth,s.hierarchy.length,g.id);assert.ok(s.hierarchy.every(v=>typeof v==='string'&&v.length));}
 views++;
}
const one=id=>hierarchyMetadata(catalog.series.find(s=>s.id===id));
const retail=code=>hierarchyMetadata(catalog.series.find(s=>s.id.startsWith('retail:')&&s.officialId===code&&s.seasonal==='SA'));
assert.equal(retail('441X').hierarchy.at(-1),'Motor Vehicle and Parts Dealers');
assert.equal(retail('4413').depth,retail('441X').depth);
assert.match(retail('44Y72').hierarchySection,/別集計/);
assert.equal(one('complement:c30:privtime.xlsx:9').hierarchy.at(-1),'Office');
assert.equal(one('complement:m3:34G:VS:US:NSA').hierarchy.at(-1),'Computer and Electronic Products');
const observations=[{date:'2026-01-01',value:12.345,raw:'12.345'}];
assert.equal(layoutPublicationSeries([{id:'x',label:'leaf',hierarchy:['parent'],observations}])[0].observations,observations);
console.log('Public publication hierarchy: PASS;',views,'table/season views; identities and numeric observations preserved.');
