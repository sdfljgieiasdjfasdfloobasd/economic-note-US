import {axisScale,axisControls,dateTicks} from './chart-axis.mjs?v=54a36504b97861cc70d1';
import {attachTooltip} from './explorer-tooltip.mjs?v=54a36504b97861cc70d1';
import {industryDefinitions} from './contributions.mjs?v=54a36504b97861cc70d1';

const industryMap=new Map(industryDefinitions.map(s=>[s.name,s]));
const industryDatasets=new Set(['employment','wages','hours']);
const majorNames=new Set(['Total nonfarm','Total private',...industryDefinitions.map(s=>s.name)]);
const palette=['#007e72','#526bc4','#d58b35','#bd527f','#299bb0','#7845a1','#8a6b42','#5b8451','#bb603e','#607e9b','#ab8321','#aa4f62','#387ea3','#776b9f','#48785c','#bd713d','#9a5d98','#4a8585','#707784'];
export function chartItems(items,scope){return scope==='major'?items.filter(item=>majorNames.has(item.s.name)):items;}

// Uses the table's already calculated values and dates: no independent data fetch.
export function setupEmploymentCharts({panel,esc,fmt,chartId="employment-table-charts",noteSelector="#heat-note",compactAxis=false}){
 const controls=document.createElement('div');controls.className='employment-chart-controls';controls.hidden=true;
 controls.innerHTML='<div class="employment-chart-views" role="group" aria-label="表とグラフの表示"><button type="button" data-ec-view="both" aria-pressed="true">表＋グラフ</button><button type="button" data-ec-view="chart" aria-pressed="false">グラフ</button><button type="button" data-ec-view="table" aria-pressed="false">表</button></div><label>グラフの形式<select data-ec="layout"><option value="overlay">重ねて比較</option><option value="separate">品目別</option></select></label><label data-ec="scope-label">グラフの品目<select data-ec="scope"><option value="major">総合・主要業種</option><option value="all">全品目</option></select></label>';
 const host=document.createElement('div');host.id=chartId;host.className='employment-charts-host';host.hidden=true;
 const table=panel.querySelector('.heat-scroll'),tableNote=panel.querySelector(noteSelector);table.before(controls,host);
 const $=s=>controls.querySelector(`[data-ec="${s}"]`);
 let model,view='both',key='',hidden=new Set();
 controls.querySelectorAll('[data-ec-view]').forEach(b=>b.onclick=()=>{view=b.dataset.ecView;draw()});
 $('layout').onchange=draw;$('scope').onchange=()=>{hidden.clear();if(chartItems(model.items,$('scope').value).length>24)$('layout').value='separate';draw()};
 function draw(){
  const active=model?.dataset.group==='employment';controls.hidden=!active;host.hidden=!active||view==='table';table.hidden=active&&view==='chart';tableNote.hidden=table.hidden;
  controls.querySelectorAll('[data-ec-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ecView===view)));
  for(const el of controls.querySelectorAll('label'))el.hidden=view==='table';
  $('scope-label').hidden=view==='table'||!industryDatasets.has(model?.dataset.id)||model?.selected;
  host.replaceChildren();if(host.hidden)return;
  const scope=industryDatasets.has(model.dataset.id)&&!model.selected?$('scope').value:'all';
  const items=chartItems(model.items,scope).map(item=>{const industry=industryMap.get(item.s.name),label=industry?.label||item.s.label;return {...item,s:{...item.s,label},label:industry?label:item.label,color:industry?.color||(['Total nonfarm','Total private'].includes(item.s.name)?'#142b42':palette[model.items.indexOf(item)%palette.length])}});
  const separate=$('layout').value==='separate';
  const note=document.createElement('p');note.className='source-note employment-chart-note';note.textContent=model.note||`${items.length}品目を一括表示。表と同じ季節調整・表示値・表示月数です。`+(separate?'各図の縦軸は個別です。目盛りを確認して比較してください。':'凡例を押すと一時的に非表示にできます。')+' 親項目と内訳を含み、積み上げ・合算はしていません。';host.append(note);
  if(!model.dates.length){note.textContent='選択期間にデータがありません。開始月・終了月を確認してください。';return}
  if(!separate){
   const legend=document.createElement('div');legend.className='legend employment-chart-legend';
   for(const item of items){const b=document.createElement('button');b.type='button';b.className='legend-item series-visibility';b.setAttribute('aria-pressed',String(!hidden.has(item.s.id)));b.innerHTML=`<span class="dot" style="background:${item.color}"></span>${esc(item.s.label)}`;b.onclick=()=>{hidden.has(item.s.id)?hidden.delete(item.s.id):hidden.add(item.s.id);draw()};legend.append(b)}
   host.append(legend);
  }
  const plots=document.createElement('div');plots.className='employment-chart-plots'+(separate?' employment-chart-grid':'');host.append(plots);
  const visible=items.filter(item=>separate||!hidden.has(item.s.id));
  if(!visible.length){plots.textContent='凡例の項目名を押すと再表示できます。';return}
  // Different units are never drawn on a common axis.
  const groups=separate?visible.map(item=>[item]):[...new Set(visible.map(item=>item.met?.unit||''))].map(unit=>visible.filter(item=>(item.met?.unit||'')===unit));
  for(const group of groups)plot(plots,group,separate);
 }
 function plot(parent,items,separate){
  const card=document.createElement('section');card.className='employment-chart-card';parent.append(card);
  const title=separate?items[0].s.label:model.dataset.label+' · '+(model.metricLabel||'比較');
  const heading=document.createElement('h3');heading.textContent=title;card.append(heading);
  const unit=items[0].met?.unit||'',numbers=items.flatMap(item=>model.indices.map(i=>item.values[i])).filter(Number.isFinite);
  const context=document.createElement('p');context.className='source-note';context.textContent=`${model.season} · ${model.metricLabel} · ${unit} · ${model.dates[0]} — ${model.dates.at(-1)}`;card.append(context);
  if(!numbers.length){const empty=document.createElement('p');empty.className='source-note';empty.textContent='この品目・季節調整・期間にはデータがありません。';card.append(empty);return}
  const axisKey='employment-table:'+model.dataset.id+':'+model.season+':'+model.metric+':'+(separate?items[0].s.id:'overlay')+':'+unit;
  const axis=axisScale(axisKey,numbers),w=separate?500:Math.max(400,host.clientWidth-24),h=separate?240:340,L=65,R=18,T=20,B=32;
  const x=i=>L+(model.dates.length===1?.5:i/(model.dates.length-1))*(w-L-R),y=v=>T+(axis.max-v)/(axis.max-axis.min)*(h-T-B);
  let body=`<text x="${L}" y="12" font-size="11">${esc(unit+axis.suffix)}</text>`;
  for(const v of axis.ticks)body+=`<line x1="${L}" x2="${w-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e5ebf0"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end" font-size="11">${axis.format(v)}</text>`;
  for(const item of items){let d='',on=false;for(let j=0;j<model.indices.length;j++){const v=item.values[model.indices[j]];if(!Number.isFinite(v)){on=false;continue}d+=`${on?'L':'M'}${x(j)},${y(v)} `;on=true;body+=`<circle cx="${x(j)}" cy="${y(v)}" r="${model.dates.length<=24?2:1}" fill="${item.color}"/>`}body+=`<path data-ec-series="${esc(item.s.id)}" d="${d}" stroke="${item.color}" stroke-width="${item.s.hierarchy?.depth===0?2.8:1.8}" fill="none"/>`}
  for(const date of dateTicks(model.dates,w-L-R)){const i=model.dates.indexOf(date);body+=`<text x="${x(i)}" y="${h-7}" text-anchor="${i===0?'start':i===model.dates.length-1?'end':'middle'}" font-size="11">${date}</text>`}
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('role','img');svg.setAttribute('aria-label',title+' '+context.textContent);svg.innerHTML=body;card.append(svg);
  axisControls(svg,{key:axisKey,unit,axis,left:L,right:w-R,top:T,bottom:h-B,redraw:draw});
  if(separate||compactAxis){const axes=svg.previousElementSibling;const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='縦軸の範囲';details.className='employment-card-axis';details.append(summary);axes.before(details);details.append(axes)}
  attachTooltip(svg,{esc,fmt,left:L,right:w-R,top:T,bottom:h-B,compact:separate,points:model.dates.map((date,j)=>({x:x(j),label:date,values:items.map(item=>({label:item.label||item.s.label,value:item.values[model.indices[j]]??null,color:item.color,unit:item.met?.unit||''}))}))});
 }
 return {update(next){const nextKey=next.dataset.id;if(key!==nextKey){key=nextKey;hidden.clear();$('scope').value=industryDatasets.has(nextKey)?'major':'all';$('layout').value=next.defaultLayout||(nextKey==='labor'?'separate':'overlay')}model=next;draw()},resize(){if(!host.hidden)draw()}};
}
