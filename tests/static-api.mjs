import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gzipSync} from 'node:zlib';
import {decodeJSON,calendarAt,request} from '../templates/static-api.mjs';
import {jpegPdf} from '../templates/static-pdf.mjs';
const root=new URL('../site/',import.meta.url),realFetch=globalThis.fetch;
const requests=[];
globalThis.fetch=async url=>{
 const u=new URL(url);requests.push(u.pathname);
 const suffix=u.pathname.split('/templates/')[1];
 assert.ok(suffix,'全データは相対URLで取得する');
 try{return new Response(await readFile(new URL(suffix,root)),{status:200})}
 catch{return new Response('missing',{status:404})}
};
const saved=new Map();globalThis.localStorage={getItem:k=>saved.get(k)??null,setItem:(k,v)=>saved.set(k,v)};

test('gzip and already-decompressed JSON preserve raw decimals and null',async()=>{
 const value={raw:'1.234567890123456789',value:1.23456789012345,missing:null};
 for(const body of [JSON.stringify(value),gzipSync(JSON.stringify(value))])assert.deepEqual(await decodeJSON(new Response(body)),value);
 await assert.rejects(decodeJSON(new Response('',{status:404})),/404/);
});
test('all endpoint shapes work without a backend',async()=>{
 const manifest=await request('/api/manifest'),catalog=await request('/api/explorer'),analysis=await request('/api/analysis/catalog');
 assert.ok(manifest.datasets.length>0&&catalog.series.length>0);
 for(const d of manifest.datasets)assert.equal((await request('/api/dataset/'+d.id)).id,d.id);
 const alias=catalog.series.find(s=>s.alias),normal=catalog.series.find(s=>!s.alias&&s.count),ids=[alias.id,normal.id];
 const batch=await request('/api/explorer/series-batch?'+ids.map(id=>'id='+encodeURIComponent(id)).join('&'));
 assert.deepEqual(batch.series.map(s=>s.id),ids);assert.ok(batch.series.every(s=>s.observations.length));
 const wb=analysis.series.find(s=>s.id.startsWith('wb:'));
 const result=await request('/api/analysis/series?id='+encodeURIComponent(wb.id));
 const [dataset,sid,season,metric]=wb.descriptor,d=await request('/api/dataset/'+dataset),s=d.series.find(s=>s.id===sid);
 assert.deepEqual(result.observations.map(o=>o.value),d.kind==='base'?s.bases[season]:s.values[metric]);
 const external=await request('/api/analysis/series?id='+encodeURIComponent('ex:'+normal.id));assert.equal(external.id,'ex:'+normal.id);
 assert.equal((await request('/api/status')).running,false);
 assert.ok((await request('/api/calendar')).events.length);
 assert.ok(await request('/api/update-report'));
 await assert.rejects(request('/api/explorer/series?id=not-a-series'),/見つかりません/);
 for(const id of ['ism:Manufacturing:Headline PMI','sp:Composite:Output','adp:M:National:U.S.:SA','derived:ism_Manufacturing_Inventories']) {
  await assert.rejects(request('/api/explorer/series?id='+encodeURIComponent(id)),/見つかりません/);
  await assert.rejects(request('/api/analysis/series?id='+encodeURIComponent('ex:'+id)),/見つかりません/);
 }
 assert.ok(!requests.some(p=>p.includes('/api/')));
});
test('favorites start empty, persist locally and are separate from owner data',async()=>{
 assert.deepEqual(await request('/api/analysis/favorites'),{items:[]});
 const payload={name:'検証条件',config:{series:[{id:'example',metric:'level'}]}};
 const first=await request('/api/analysis/favorites',{method:'POST',body:JSON.stringify(payload)});
 const second=await request('/api/analysis/favorites',{method:'POST',body:JSON.stringify({...payload,id:first.id,name:'変更'})});
 assert.equal(second.id,first.id);assert.equal((await request('/api/analysis/favorites')).items.length,1);
 assert.ok([...saved.keys()].every(k=>k.startsWith('economic-note-pages-favorites:')));
});
test('calendar changes due state at viewing time without inventing new observations',()=>{
 const e={scheduledAt:'2026-10-01T12:00:00Z',reflection:{code:'upcoming',details:[]},afterDue:{code:'pending',label:'未反映',details:[]}};
 assert.equal(calendarAt({events:[e]},new Date('2026-09-01')).events[0].reflection.code,'upcoming');
 assert.equal(calendarAt({events:[e]},new Date('2026-11-01')).events[0].reflection.code,'pending');
 assert.equal(e.reflection.code,'upcoming');
});
test('PDF has correct object offsets and image dimensions',async()=>{
 const blob=jpegPdf(new Uint8Array([255,216,255,217]),400,300),b=new Uint8Array(await blob.arrayBuffer()),text=new TextDecoder().decode(b);
 assert.equal(blob.type,'application/pdf');assert.ok(text.startsWith('%PDF-1.4'));
 const xref=Number(text.match(/startxref\n(\d+)/)[1]);assert.equal(new TextDecoder().decode(b.slice(xref,xref+4)),'xref');
 assert.ok(text.includes('/MediaBox [0 0 400 300]'));
});
