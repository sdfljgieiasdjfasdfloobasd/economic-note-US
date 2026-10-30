import {pageMetrics,transform,frequency,lagDate,periodKey,compatibleUnit} from './explorer-math.mjs?v=cda8403669651c01da97';
export function prepare(s,metric,target='native',aggregation='mean'){
 const f=frequency(s);if(metric.startsWith('eight')&&f!=='Q'||/^(growth|annual)[36]$/.test(metric)&&f!=='M'||s.alreadySmoothed&&/^(?:delta_)?ma/.test(metric)||metric.startsWith('bp')&&(f!=='D'||!['%','Percent'].includes(s.unit))||f==='F'&&!['level','delta1','yoy'].includes(metric))throw Error('この頻度・単位には選択した変換を適用できません。');let rs=transform(s,metric);let out={...s,unit:compatibleUnit(s,metric),observations:rs};
 if(target==='native'){out.observations=rs.map(r=>{const date=f==='M'?r.date.slice(0,7)+'-01':f==='Q'?r.date.slice(0,4)+'-'+String(Math.floor((Number(r.date.slice(5,7))-1)/3)*3+1).padStart(2,'0')+'-01':f==='A'?r.date.slice(0,4)+'-01-01':r.date;return {...r,date,sourceDate:r.date}});return out;}
 if(!['M','Q'].includes(target)||['A','T','F'].includes(f)||f==='Q'&&target==='M')throw Error('低頻度の系列を高頻度に補完できません。集計頻度を合わせてください。');
 const groups=new Map();for(const r of rs){const d=r.date.slice(0,4)+'-'+String(target==='Q'?Math.floor((Number(r.date.slice(5,7))-1)/3)*3+1:Number(r.date.slice(5,7))).padStart(2,'0')+'-01';if(!groups.has(d))groups.set(d,[]);groups.get(d).push(r)}
 out.observations=[...groups].map(([date,rows])=>{const valid=rows.filter(r=>Number.isFinite(r.value)),complete=f==='M'&&target==='Q'?rows.length===3&&valid.length===3:valid.length>0;const value=!complete?null:aggregation==='last'?rows.at(-1).value:aggregation==='sum'?valid.reduce((a,b)=>a+b.value,0):valid.reduce((a,b)=>a+b.value,0)/valid.length;return {date,value,raw:value==null?null:String(value),status:'aggregated',count:valid.length}});
 out.frequency=target==='Q'?'Quarterly':'Monthly';delete out.calendar;return out;
}
export function displaySeries(series,mode,from,to){
 const trimmed=series.map(s=>({...s,observations:s.observations.filter(r=>r.date>=from&&r.date<=to)}));if(mode==='native')return trimmed;
 if(new Set(trimmed.map(frequency)).size>1)throw Error('指数化・標準化では、先に全系列の集計頻度を合わせてください。');
 const maps=trimmed.map(s=>new Map(s.observations.filter(r=>Number.isFinite(r.value)).map(r=>[periodKey(s,r.date),r])));const common=[...maps[0].keys()].filter(k=>maps.every(m=>m.has(k))).sort();if(common.length<2)throw Error('標準化に使える共通の観測期間が不足しています。');
 return trimmed.map((s,i)=>{const vals=common.map(k=>maps[i].get(k).value),mean=vals.reduce((a,b)=>a+b,0)/vals.length,sd=Math.sqrt(vals.reduce((a,b)=>a+(b-mean)**2,0)/vals.length),base=vals[0];if(mode==='index'&&base===0||mode==='zscore'&&sd===0)throw Error('基準値が0、または変動がないため標準化できません。');return {...s,unit:mode==='index'?'共通開始期=100':'標準偏差',normalizationPeriod:[common[0],common.at(-1)],observations:s.observations.map(r=>({...r,value:r.value==null?null:mode==='index'?r.value/base*100:(r.value-mean)/sd}))}});
}
export function pairSeries(x,y,from,to,lag){
 if(frequency(x)!==frequency(y)||x.calendar!==y.calendar)throw Error('回帰する2系列の頻度・暦を合わせてください。月次または四半期集計を選べます。');
 if(!Number.isInteger(lag)||Math.abs(lag)>120)throw Error('ラグは−120〜120期の整数です。');
 const map=new Map(x.observations.map(r=>[periodKey(x,r.date),r]));const pairs=[];let missing=0;
 for(const r of y.observations){if(r.date<from||r.date>to)continue;const d=lagDate(y,r.date,lag),a=map.get(periodKey(x,d));if(!Number.isFinite(a?.value)||!Number.isFinite(r.value)){missing++;continue}pairs.push({date:r.date,xDate:a.date,x:a.value,y:r.value})}return {pairs,missing};
}


export function metricLabel(source,metric){
 return pageMetrics('',[source]).find(([id])=>id===metric)?.[1]||metric;
}

// Each entry is an independent plot, even when its source ID is shared.
export function comparisonCopy(entry,source,siblings=[]){
 const choices=pageMetrics('',[source]).map(([id])=>id);
 const used=new Set(siblings.filter(s=>s.id===entry.id).map(s=>s.metric));
 used.add(entry.metric);
 const preferred=['qoq','growth3','yoy','delta1','level',...choices];
 const metric=preferred.find(id=>choices.includes(id)&&!used.has(id))
   ||choices.find(id=>id!==entry.metric)||entry.metric;
 return {...entry,metric,hidden:false};
}

export function explorerSelection(source,metric='level',hidden=false){
 const a=source.alias;
 const id=a?'wb:'+JSON.stringify([a.dataset,a.series,a.season,a.metric||'level']):'ex:'+source.id;
 return {id,metric,hidden};
}

export function comparisonTable(series){
 const dates=[...new Set(series.flatMap(s=>s.observations.map(r=>r.date)))].sort().reverse();
 const maps=series.map(s=>new Map(s.observations.map(r=>[r.date,r.value])));
 return {headers:series.map(s=>`${s.label} · ${s.seasonal||'非該当'} · ${s.unit}`),
   rows:dates.map(date=>[date,...maps.map(m=>m.get(date)??null)])};
}
