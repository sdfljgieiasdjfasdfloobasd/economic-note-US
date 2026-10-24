import assert from 'node:assert/strict';
const {setupPublicationTable,hasContributions}=await import(process.env.TABLE_MODULE||'../site/explorer-table.mjs');
class Control{value='';disabled=false;textContent='';hidden=false;title='';set innerHTML(html){this.html=html;if(this.select)this.value=[...html.matchAll(/<option(?: value="([^"]*)")?[^>]*>([^<]*)<\/option>/g)][0]?.[1]||''}get innerHTML(){return this.html||''}}
const controls=new Map(),panel={set innerHTML(html){for(const m of html.matchAll(/<(\w+)[^>]*id="([^"]+)"[^>]*>/g)){const c=new Control();c.select=m[1]==='select';controls.set('#'+m[2],c)}},querySelector:id=>controls.get(id),addEventListener(){}};
const $=id=>controls.get(id),downloads=[];
let catalog;
const table=setupPublicationTable({root:{querySelector:()=>panel},esc:String,fmt:v=>v==null?'—':v.toFixed(3),csv:(name,rows)=>downloads.push({name,rows}),loadMany:async ids=>ids.map(id=>catalog.series.find(s=>s.id===id))});
const observations=(dates,values)=>dates.map((date,i)=>({date,value:values[i]==null?null:Number(values[i]),raw:values[i]}));
const make=(id,pub,label,freq='Monthly',extra={})=>({id,publicationId:pub,publicationLabel:label,page:'gdp',label:id,unit:'ポイント',seasonal:'SA',frequency:freq,count:6,observations:observations(['2026-01-01','2026-02-01','2026-03-01','2026-05-01','2026-06-01','2026-07-01'],['0.300','0.100',null,'-0.200','0.000','0.000']),...extra});
for(const [freq,dates,prior] of [['Monthly',['2026-01-01','2026-02-01','2026-03-01'],'前月'],['Quarterly',['2025-10-01','2026-01-01','2026-04-01'],'前四半期'],['Annual',['2024-01-01','2025-01-01','2026-01-01'],'前年']]){
 const s=make('sample','bea:test','BEA / Table 1.1.2. Contributions to Percent Change',freq,{observations:observations(dates,['0.300','0.100','0.150'])});catalog={series:[s]};await table.show(catalog,'gdp',[s.id]);
 assert.equal($('#ex-contribution-control').hidden,false);assert.match($('#ex-contribution-view').innerHTML,new RegExp(prior));
 $('#ex-contribution-view').value='delta1';$('#ex-table-from').value=dates[1];await $('#ex-csv').onclick();const out=downloads.at(-1);
 assert.deepEqual(out.rows[1].slice(6),['0.050','-0.200']);assert.equal(out.rows[1][4],'ポイント');assert.match(out.name,/contribution_delta1/);assert.match(out.rows[1][5],new RegExp(prior+'差'));assert.equal($('#ex-contribution-note').hidden,false);
 $('#ex-contribution-view').value='level';await $('#ex-csv').onclick();assert.deepEqual(downloads.at(-1).rows[1].slice(6),['0.150','0.100']);
}
const gap=make('gap','bea:test','Contributions to growth');catalog={series:[gap]};await table.show(catalog,'gdp',[gap.id]);$('#ex-contribution-view').value='delta1';await $('#ex-csv').onclick();assert.deepEqual(downloads.at(-1).rows[1].slice(6),['0.000','0.200','','','-0.200','']);
// Mixed CPI Table 6: only effect/core supports this control; weight and inflation do not.
const effect=make('effect','price-table:cpi6','BLS / CPI Table 6','Monthly',{page:'cpi',frequency:'Monthly',sourceMetric:'総合への寄与',alias:{dataset:'cpi6',metric:'effect'},matchLabel:'item'});
const core={...effect,id:'core',sourceMetric:'コアへの寄与',alias:{dataset:'cpi6',metric:'core'},coreApplicable:true};
const food={...core,id:'food',coreApplicable:false,matchLabel:'food'};
const weight={...effect,id:'ri',sourceMetric:'相対的重要度（RI）',unit:'%',alias:{dataset:'cpi6',metric:'ri'}};
const mom={...effect,id:'mom',sourceMetric:'前月比（SA）',unit:'%',alias:{dataset:'cpi6',metric:'mom'}};
catalog={series:[effect,core,food,weight,mom]};await table.show(catalog,'cpi',[effect.id]);$('#ex-contribution-view').value='delta1';await $('#ex-csv').onclick();assert.match(downloads.at(-1).name,/published_effect_contribution_delta1/);
$('#ex-table-season').value='core';await $('#ex-csv').onclick();assert.equal(downloads.at(-1).rows.length,2);assert.match(downloads.at(-1).name,/calculated_core_contribution_delta1/);
$('#ex-table-season').value='ri';await $('#ex-csv').onclick();assert.equal($('#ex-contribution-control').hidden,true);assert.equal($('#ex-contribution-view').value,'level');assert.match(downloads.at(-1).name,/published_ri/);
$('#ex-table-metric').value='cpi_mom';await $('#ex-csv').onclick();assert.equal($('#ex-contribution-control').hidden,true);
// Table 1/2 linked contributions reuse the same observations and exact item matching.
for(const pub of ['price-table:cpi','price-table:cpi_detail']){
 const item={...effect,id:'index',publicationId:pub,publicationLabel:'CPI index',sourceMetric:'価格指数',unit:'指数',alias:undefined};catalog={series:[item,effect,core,weight]};await table.show(catalog,'cpi',[item.id]);$('#ex-table-metric').value='cpi_effect';await $('#ex-table-metric').onchange();assert.equal($('#ex-contribution-control').hidden,false);
 $('#ex-contribution-view').value='delta1';await $('#ex-csv').onclick();assert.deepEqual(downloads.at(-1).rows[1].slice(6),['0.000','0.200','','','-0.200','']);assert.match(downloads.at(-1).name,/table6_published_effect_contribution_delta1/);
}
// Official annual-inflation contributions (CPI Table 7) still compare adjacent months.
const annualEffect={...effect,id:'annualEffect',publicationId:'cpi:table7',publicationLabel:'CPI Table 7',sourceMetric:'前年比寄与度'};catalog={series:[annualEffect]};await table.show(catalog,'cpi',[annualEffect.id]);$('#ex-contribution-view').value='delta1';await $('#ex-csv').onclick();assert.match(downloads.at(-1).rows[1][5],/前年比寄与度.*前月差/);
assert.equal(hasContributions([mom,weight]),false);
console.log('PASS: monthly/quarterly/annual contribution differences; gaps, zero, exact precision, prior period outside display; CPI 1/2/6/7, core exclusions, CSV and returning to levels.');

// Mixed tables must not present dollar-level changes as contribution changes.
const mixedContribution={...gap,id:'mix-contribution',publicationLabel:'Mixed statistics',label:'growth contribution'};
const dollars={...gap,id:'dollars',publicationLabel:'Mixed statistics',label:'sales',unit:'million USD',frequency:'Weekly'};
catalog={series:[mixedContribution,dollars]};await table.show(catalog,'gdp',[mixedContribution.id]);$('#ex-contribution-view').value='delta1';await $('#ex-csv').onclick();assert.equal(downloads.at(-1).rows.length,2);assert.match($('#ex-contribution-view').innerHTML,/前月/);assert.equal(downloads.at(-1).rows[1][1],'growth contribution');
console.log('PASS: mixed-unit tables only transform contribution rows.');
