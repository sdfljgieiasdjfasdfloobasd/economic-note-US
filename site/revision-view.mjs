import {valuesFor} from './analytics.mjs?v=c4c7379114f9b20ce404';
import {transform,compatibleUnit,frequency} from './explorer-math.mjs?v=c4c7379114f9b20ce404';
import {axisScale,axisControls,dateTicks} from './chart-axis.mjs?v=c4c7379114f9b20ce404';
import {attachTooltip} from './explorer-tooltip.mjs?v=c4c7379114f9b20ce404';
import {seriesAttributions} from './expectation-presets.mjs?v=c4c7379114f9b20ce404';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v==null||!Number.isFinite(v)?'—':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:3,maximumFractionDigits:3});
const date=d=>d.length===7?d+'-01':d;
let report=null,request=null,pending=null,version=0;
export function initRevisions(fn){request=fn}
export function setRevisionReport(r){if(report?.id===r?.id)return;report=r;version++;}
async function getReport(){if(report)return report;if(!request)return null;if(!pending)pending=request('/api/update-report').then(r=>{setRevisionReport(r);return r}).catch(()=>null).finally(()=>pending=null);return pending}
export async function observationHash(observations){
 const encoder=new TextEncoder(),chunks=observations.filter(o=>o.value!=null).map(o=>({date:date(o.date),value:o.value})).sort((a,b)=>a.date.localeCompare(b.date)).map(o=>{const d=encoder.encode(o.date),b=new Uint8Array(d.length+10);b.set(d);new DataView(b.buffer).setFloat64(d.length+1,Number(o.value),false);b[b.length-1]=10;return b});
 const bytes=new Uint8Array(chunks.reduce((n,b)=>n+b.length,0));let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length}
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
}
export function entryKey(s,r){
 if(s.revisionTarget){const t=s.revisionTarget;return r.lookup?.[JSON.stringify([t.dataset,String(t.seriesId),t.measure])]}
 if(s.alias){const t=s.alias;return r.lookup?.[JSON.stringify([t.dataset,String(t.series),t.metric&&t.metric!=='level'?t.metric:t.season])]}
 if(s.descriptor){const [ds,id,season,metric]=s.descriptor;return r.lookup?.[JSON.stringify([ds,String(id),metric==='level'?season:metric])]}
 return 'explorer:'+s.id.replace(/^ex:/,'');
}
export function restoreObservations(current,details){
 const old=new Map(current.map(o=>[date(o.date),{...o,date:date(o.date)}]));
 for(const d of details){const k=date(d.date);if(d.before==null)old.delete(k);else old.set(k,{date:k,value:d.before,raw:String(d.before),status:d.beforeStatus||''})}
 return [...old.values()].sort((a,b)=>a.date.localeCompare(b.date));
}
export function compareRows(latest,previous){
 const a=new Map(latest.map(o=>[date(o.date),o])),b=new Map(previous.map(o=>[date(o.date),o]));
 return [...new Set([...a.keys(),...b.keys()])].sort().map(d=>{const after=a.get(d)?.value??null,before=b.get(d)?.value??null;return {date:d,before,after,delta:before!=null&&after!=null?after-before:null,revised:before!=null&&after!=null&&Math.abs(after-before)>1e-12*Math.max(1,Math.abs(after),Math.abs(before))}});
}
export function explorerRevisionInput(s,metric='level'){return {source:s,label:s.label,unit:compatibleUnit(s,metric),calculate:x=>transform(x,metric)}}
export function baseRevisionInput(d,s,season,metric){
 const measure=d.kind==='base'?season:metric,vs=d.kind==='base'?s.bases?.[measure]:s.values?.[measure];
 return {label:s.label+' · '+season+' · '+metric,unit:d.kind==='base'?(['level','change','avg3','avg6','delta_avg3','delta_avg6','delta_avg12'].includes(metric)?d.baseUnit:'%'):(d.metrics.find(m=>m.id===metric)?.unit||''),
 source:{id:'wb:'+s.id,label:s.label,frequency:'Monthly',revisionTarget:{dataset:d.id,seriesId:s.id,measure},observations:d.dates.map((dt,i)=>({date:date(dt),value:vs?.[i]??null}))},
 calculate:x=>{const dates=x.observations.map(o=>o.date.slice(0,7)),v=x.observations.map(o=>o.value),copy={...s,[d.kind==='base'?'bases':'values']:{[measure]:v}};const vals=valuesFor({...d,dates},copy,season,metric);return dates.map((dt,i)=>({date:date(dt),value:vals[i]}))}};
}
const pairCache=new WeakMap();
export async function revisionPair(input){try{return await checkedRevisionPair(input)}catch{return {reason:'比較履歴を読み込めませんでした。再読込して確認してください。'}}}
async function checkedRevisionPair(input){
 const r=await getReport();if(r?.format!==2)return {reason:'比較履歴は機能追加後の次回更新から記録します。過去の更新前値は推測しません。'};
 const key=entryKey(input.source,r),hash=r.checks?.[key];if(!hash)return {reason:'この系列には今回の比較記録がありません。'};
 let cached=pairCache.get(input.source);if(!cached||cached.version!==version){cached={version,hash:observationHash(input.source.observations)};pairCache.set(input.source,cached)}
 if(await cached.hash!==hash)return {reason:'現在の値と更新履歴が一致しないため比較を表示しません。再読込、または次回更新後に確認してください。'};
 const change=r.changed.find(s=>s.id===key);if(change?.comparable===false)return {reason:'単位・定義が変更されたため同一系列として比較しません。'};
 const old={...input.source,observations:restoreObservations(input.source.observations,change?.details||[])};
 return {rows:compareRows(input.calculate(input.source),input.calculate(old)),report:r,change};
}
export function revisionDescription(row,unit){return `更新前 ${fmt(row.before)} → 最新 ${fmt(row.after)} / 改定幅 ${fmt(row.delta)} ${unit==='%'?'ポイント':unit}`}
export async function markRevisionCells(items,detail){
 const grouped=new Map();for(const item of items){if(!grouped.has(item.input))grouped.set(item.input,[]);grouped.get(item.input).push(item)}
 await Promise.all([...grouped].map(async([input,cells])=>{const pair=await revisionPair(input);if(!pair.rows)return;const rows=new Map(pair.rows.map(r=>[r.date,r]));for(const {cell,date:dt} of cells){const row=rows.get(date(dt));if(!cell?.isConnected||!row?.revised)continue;const text=revisionDescription(row,input.unit),b=document.createElement('button');b.type='button';b.className='revision-mark';b.textContent='改定';b.title=text;b.setAttribute('aria-label',input.label+' '+dt+' '+text);b.onclick=e=>{e.stopPropagation();if(detail)detail.textContent=input.label+' · '+dt+' / '+text;else{let note=cell.closest('table').nextElementSibling;if(!note?.classList.contains('revision-cell-detail')){note=document.createElement('p');note.className='revision-cell-detail source-note';note.setAttribute('role','status');cell.closest('table').after(note)}note.textContent=input.label+' · '+dt+' / '+text}};cell.querySelector('.revision-mark')?.remove();cell.append(b)}}));
}
export function mountRevisionView(host,{inputs,from='',to='',csv}){
 if(!host)return;let panel=[...host.children].find(n=>n.classList.contains('revision-panel'));
 if(!panel){panel=document.createElement('details');panel.className='revision-panel';panel.innerHTML='<summary>改定を見る · 表・グラフ</summary><div class="revision-content"></div>';host.append(panel)}
 const old=panel.revisionState||{};panel.revisionState={inputs,from:date(from||'0000-01-01'),to:date(to||'9999-12-31'),csv,series:Math.min(old.series||0,Math.max(0,inputs.length-1)),mode:old.mode||'overlay'};
 let sequence=(panel.revisionSequence||0)+1;panel.revisionSequence=sequence;
 async function render(){const state=panel.revisionState,seq=++panel.revisionSequence,box=panel.querySelector('.revision-content');if(!state.inputs.length){box.textContent='表示中の系列がありません。';return}const input=state.inputs[state.series],pair=await revisionPair(input);if(seq!==panel.revisionSequence||!panel.isConnected)return;
 box.innerHTML=`<div class="ex-publication-controls"><label>比較する系列<select class="revision-series">${state.inputs.map((s,i)=>`<option value="${i}" ${i===state.series?'selected':''}>${esc(s.label)}</option>`).join('')}</select></label><label>改定グラフの表示<select class="revision-mode">${[['latest','最新値のみ'],['overlay','更新前と比較'],['delta','改定幅']].map(([k,v])=>`<option value="${k}" ${k===state.mode?'selected':''}>${v}</option>`).join('')}</select></label><button class="text-button revision-csv">改定一覧CSV ↓</button></div><p class="source-note revision-note"></p><div class="revision-plot"></div><div class="table-scroll revision-list"></div>`;
 box.querySelector('.revision-series').onchange=e=>{state.series=Number(e.target.value);render()};box.querySelector('.revision-mode').onchange=e=>{state.mode=e.target.value;render()};
 const note=box.querySelector('.revision-note');if(!pair.rows){note.textContent=pair.reason;box.querySelector('.revision-csv').disabled=true;return}
 note.textContent=`比較対象：${new Date(pair.report.startedAt).toLocaleString('ja-JP')} の更新直前 → ${new Date(pair.report.finishedAt).toLocaleString('ja-JP')} の保存値。初回公表値との比較ではありません。表示する値の計算は更新前・更新後にそれぞれ適用しています。実線＝最新、点線＝更新前。改定幅は青＝上方、赤＝下方（良し悪しではありません）。`;
 const rows=pair.rows.filter(r=>r.date>=state.from&&r.date<=state.to),changes=rows.filter(r=>r.revised||r.before==null&&r.after!=null||r.before!=null&&r.after==null).reverse();
 const kinds=new Map((pair.change?.details||[]).map(d=>[date(d.date),d]));
 const kind=r=>r.revised?'改定（計算値を含む）':r.after==null?'欠損・削除':kinds.get(r.date)?.additionType==='new_period'?'新しい対象期':kinds.get(r.date)?.additionType==='backfill'?'過去データ追加':kinds.get(r.date)?.additionType==='initial'?'初回収録':'比較する旧値なし';
 const unit=state.mode==='delta'&&input.unit==='%'?'ポイント':input.unit;
 const tableRows=[['対象日','区分','更新前','更新後','改定幅', '値の単位','改定幅の単位'],...changes.map(r=>[r.date,kind(r),r.before,r.after,r.delta,input.unit,input.unit==='%'?'ポイント':input.unit])];
 box.querySelector('.revision-list').innerHTML=changes.length?'<table><thead><tr>'+tableRows[0].map(v=>'<th>'+v+'</th>').join('')+'</tr></thead><tbody>'+tableRows.slice(1).map(r=>'<tr>'+r.map((v,i)=>`<td>${i>=2&&i<=4?fmt(v):esc(v)}</td>`).join('')+'</tr>').join('')+'</tbody></table>':'<p class="source-note">表示期間に数値の追加・改定はありません。</p>';
 box.querySelector('.revision-csv').onclick=()=>state.csv?.('改定比較_'+input.label,tableRows);
 drawRevisionPlot(box.querySelector('.revision-plot'),rows,input.label,unit,state.mode,input.plotFrequency||input.source.frequency);
 for(const text of seriesAttributions([input.source])){const p=document.createElement('p');p.className='source-note';p.textContent=text;box.append(p)}
 }
 panel.ontoggle=()=>{if(panel.open)render()};if(panel.open)render();
}
export function drawRevisionPlot(box,rows,label,unit,mode,plotFrequency='Monthly'){
 const nums=rows.flatMap(r=>mode==='delta'?[r.delta]:mode==='latest'?[r.after]:[r.before,r.after]).filter(Number.isFinite);if(!nums.length){box.innerHTML='<p>この期間に比較可能な数値がありません。</p>';return}
 const axisKey='revision:'+label+':'+unit+':'+mode,axis=axisScale(axisKey,nums,{include:mode==='delta'?[0]:[]}),w=Math.max(320,box.clientWidth),h=290,L=70,R=18,T=24,B=35,dates=rows.map(r=>r.date),start=Date.parse(dates[0]),end=Date.parse(dates.at(-1)),x=d=>L+(end===start?.5:(Date.parse(d)-start)/(end-start))*(w-L-R),y=v=>T+(axis.max-v)/(axis.max-axis.min)*(h-T-B);
 let out=`<text x="${L}" y="15" font-size="12">${esc(unit+axis.suffix)}</text>`;
 for(const v of axis.ticks)out+=`<line x1="${L}" x2="${w-R}" y1="${y(v)}" y2="${y(v)}" stroke="${v===0?'#607b87':'#e5ebf0'}"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end" font-size="11">${axis.format(v)}</text>`;
 if(mode==='delta'){const bw=Math.max(1,Math.min(22,(w-L-R)/Math.max(1,rows.length)*.7));for(const r of rows)if(r.delta!=null)out+=`<rect x="${x(r.date)-bw/2}" y="${Math.min(y(0),y(r.delta))}" width="${bw}" height="${Math.abs(y(r.delta)-y(0))}" fill="${r.delta>=0?'#3987b6':'#d36673'}"/>`}
 else for(const field of (mode==='latest'?['after']:['before','after'])){let path='',previous=null;for(const r of rows){if(r[field]==null){previous=null;continue}const gap=previous?(Date.parse(r.date)-Date.parse(previous))/86400000:Infinity,maxgap={D:5,W:9,M:40,Q:105,A:380,T:1120,F:140}[frequency({frequency:plotFrequency})];path+=`${gap<=maxgap?'L':'M'}${x(r.date)},${y(r[field])} `;previous=r.date}out+=`<path d="${path}" fill="none" stroke="#007e72" stroke-width="2" ${field==='before'?'stroke-dasharray="5 4"':''}/>`;for(const r of rows)if(r[field]!=null)out+=`<circle cx="${x(r.date)}" cy="${y(r[field])}" r="2" fill="#007e72"/>`}
 const ticks=dateTicks(dates,w-L-R);ticks.forEach((d,i)=>out+=`<text x="${x(d)}" y="${h-8}" font-size="11" text-anchor="${i===0?'start':i===ticks.length-1?'end':'middle'}">${esc(d)}</text>`);
 box.innerHTML=`<div class="legend"><span>${esc(label)} · ${mode==='delta'?'改定幅':mode==='latest'?'最新値':'実線：最新 ／ 点線：更新前'}</span></div><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)} 改定比較">${out}</svg>`;
 axisControls(box.querySelector('svg'),{key:axisKey,unit,axis,left:L,right:w-R,top:T,bottom:h-B,redraw:()=>drawRevisionPlot(box,rows,label,unit,mode,plotFrequency)});
 attachTooltip(box.querySelector('svg'),{esc,fmt,left:L,right:w-R,top:T,bottom:h-B,points:rows.map(r=>({x:x(r.date),label:r.date,values:[{label:'更新前',value:r.before,unit:mode==='delta'&&unit==='ポイント'?'%':unit,color:'#7ca29d'},{label:'最新',value:r.after,unit:mode==='delta'&&unit==='ポイント'?'%':unit,color:'#007e72'},{label:'改定幅',value:r.delta,unit:unit==='%'?'ポイント':unit,color:r.delta>=0?'#3987b6':'#d36673'}]}))});
}
