export function monthShift(d,k){const [y,m]=d.slice(0,7).split('-').map(Number),n=y*12+m-1+k;return `${Math.floor(n/12)}-${String((n%12+12)%12+1).padStart(2,'0')}-${d.slice(8)||'01'}`;}
const days=(d,k)=>{const a=new Date(d+'T12:00:00Z');a.setUTCDate(a.getUTCDate()+k);return a.toISOString().slice(0,10)};
export function frequency(s){return s.frequency==='Triennial'?'T':s.frequency==='4-monthly'?'F':/daily/i.test(s.frequency)?'D':/weekly/i.test(s.frequency)?'W':/quarter/i.test(s.frequency)?'Q':/annual/i.test(s.frequency)?'A':'M'};
export function lagDate(s,d,k){const f=frequency(s);if(s.calendar==='48week'){const [y,m,day]=d.split('-').map(Number),slot=(y*12+m-1)*4+Math.min(3,Math.floor((day-1)/7))-k;return `${Math.floor(slot/48)}-${String(Math.floor(((slot%48)+48)%48/4)+1).padStart(2,'0')}-${String((((slot%4)+4)%4+1)*7).padStart(2,'0')}`;}return f==='W'?days(d,-7*k):f==='D'?days(d,-k):monthShift(d,-k*(f==='Q'?3:f==='T'?36:f==='A'?12:f==='F'?4:1))}
// Differences of published decimal strings are exact; no binary float tails in details.
export function difference(a,b){if(a==null||b==null)return null;const p=Math.max((String(a).split('.')[1]||'').length,(String(b).split('.')[1]||'').length);const toInt=v=>{const [i,f='']=String(v).split('.');return BigInt(i+f.padEnd(p,'0'))};const v=toInt(a)-toInt(b),sign=v<0n?'-':'',digits=String(v<0n?-v:v).padStart(p+1,'0');return sign+(p?digits.slice(0,-p)+'.'+digits.slice(-p):digits)}
export const metrics=[['level','公表値'],['bp1d','前営業日差（bp・日次金利用）'],['bp1w','1週前差（bp・日次金利用）'],['bp1m','1か月前差（bp・日次金利用）'],['bp3m','3か月前差（bp・日次金利用）'],['bp1y','1年前差（bp・日次金利用）'],['delta1','前期・前週差'],['delta3','3期前との差'],['delta6','6期前との差'],['delta12','12期前との差'],['ma3','3期平均'],['ma6','6期平均'],['ma12','12期平均'],['ma4','4期平均'],['yoy','前年比（%）'],['qoq','前期比（%）'],['annual','前期比・年率換算（%）'],['growth3','3か月前比（%）'],['growth6','6か月前比（%）'],['annual3','3か月前比・年率（%）'],['annual6','6か月前比・年率（%）'],['eight','8四半期前比（%）'],['eightannual','8四半期前比・年率（%）'],['delta_ma3','前期差の3期平均'],['delta_ma6','前期差の6期平均'],['delta_ma12','前期差の12期平均'],['percentile','過去分布の百分位']];
export function periodKey(s,d){const f=frequency(s);return f==='M'?d.slice(0,7):f==='Q'?d.slice(0,4)+'Q'+Math.ceil(Number(d.slice(5,7))/3):['A','T'].includes(f)?d.slice(0,4):d}
const pceMetrics=[['level','公表値（所得・消費額・貯蓄率など）'],['qoq','前月比（%）'],['annual','前月比・年率換算（%）'],['yoy','前年比（%）'],['growth3','3か月前比（%）'],['growth6','6か月前比（%）'],['annual3','3か月前比・年率換算（%）'],['annual6','6か月前比・年率換算（%）'],['delta1','前月差'],['delta3','3か月前との差'],['delta6','6か月前との差'],['delta12','前年同月差'],['ma3','3か月平均'],['ma6','6か月平均'],['ma12','12か月平均'],['delta_ma3','前月差の3か月平均'],['delta_ma6','前月差の6か月平均']];
export function pceMetricApplicable(s,m){return !['qoq','annual','yoy','growth3','growth6','annual3','annual6'].includes(m)||!['%','Percent','ポイント'].includes(s.unit)}
export function metricApplicable(s,m){
 const f=frequency(s),rate=/%|Percent|ポイント|DI|倍/.test(s.unit||'');
 if(m==='level')return true;
 if(s.frequency==='Triennial')return false;
 if(s.alreadySmoothed&&/^(?:delta_)?ma/.test(m))return false;
 if(s.frequency==='4-monthly')return ['level','yoy','delta1'].includes(m);
 if(m.startsWith('bp'))return f==='D'&&['%','Percent'].includes(s.unit);
 if(m.startsWith('eight'))return f==='Q'&&!rate;
 if(/^(growth|annual)[36]$/.test(m))return f==='M'&&!rate;
 if(m==='annual')return ['M','Q'].includes(f)&&!rate;
 if(['qoq','yoy'].includes(m))return f!=='D'&&!rate;
 if(m==='ma4')return ['W','Q'].includes(f);
 if(m==='percentile')return false;
 return f!=='D'||m==='delta1';
}
export function pageMetrics(page,series=[],table=false){
 const ss=series.filter(s=>s.count!==0),fs=[...new Set(ss.map(frequency))],f=fs.length===1?fs[0]:null;
 const period={M:'月',W:'週',Q:'四半期',A:'年',D:'営業日',F:'4か月期'}[f]||'期';
 const allRates=ss.length&&ss.every(s=>/%|Percent|ポイント|DI/.test(s.unit||''));
 return metrics.filter(([id])=>!ss.length?['level'].includes(id):(table?ss.some(s=>metricApplicable(s,id)):ss.every(s=>metricApplicable(s,id)))).map(([id,label])=>{
 if(id==='qoq')label='前'+period+'比（%）';
 if(id==='annual')label='前'+period+'比・年率換算（%）';
 if(id==='delta1')label='前'+period+'差';
 if(/^delta\d+$/.test(id)&&id!=='delta1')label=id.slice(5)+(f==='M'?'か月':period)+'前との差';
 if(/^(?:delta_)?ma\d+$/.test(id))label=(id.startsWith('delta_')?'前'+period+'差の':'')+id.match(/\d+$/)[0]+(f==='M'?'か月':period)+'平均';
 if(allRates&&id.startsWith('delta'))label+='（ポイント）';
 return [id,label];
 });
}
// Keep every observation within a period: a later survey must not leak into an earlier calculation.
function periodRows(s,rows){const out=new Map();for(const r of rows){const k=periodKey(s,r.date);if(!out.has(k))out.set(k,[]);out.get(k).push(r)}for(const group of out.values())group.sort((a,b)=>a.date.localeCompare(b.date));return out}
export function transform(s,metric){const rs=s.observations,f=frequency(s),map=periodRows(s,rs);if(metric==='level')return rs;if(!metricApplicable(s,metric))return rs.map(r=>({...r,value:null,raw:null,status:'incompatible'}));if(s.alreadySmoothed&&/^(?:delta_)?ma/.test(metric)||s.frequency==='4-monthly'&&!['level','yoy','delta1'].includes(metric))return rs.map(r=>({...r,value:null,raw:null,status:'incompatible'}));
 const at=(source,r,k)=>source.get(periodKey(s,lagDate(s,r.date,k)))?.findLast(v=>v.date<=r.date);
 const get=(r,k)=>at(map,r,k);
 const changes=metric.startsWith('delta_ma')?periodRows(s,transform(s,'delta1')):null;
 return rs.map((r,i)=>{let value=null,raw=null;if(r.value==null)return {...r,value,raw};
 if(metric.startsWith('bp')){if(f!=='D'||!['%','Percent'].includes(s.unit))return {...r,value:null,raw:null,status:'derived'};const target=metric==='bp1w'?days(r.date,-7):monthShift(r.date,metric==='bp1m'?-1:metric==='bp3m'?-3:-12);const old=metric==='bp1d'?rs.slice(0,i).findLast(v=>v.value!=null):rs.slice(0,i).findLast(v=>v.date<=target&&v.value!=null&&Date.parse(target)-Date.parse(v.date)<=7*86400000);const diff=difference(r.raw,old?.raw);if(diff!=null)value=Number(diff)*100}
 else if(/^delta\d+$/.test(metric)){const old=f==='D'&&metric==='delta1'?rs.slice(0,i).findLast(v=>v.value!=null):get(r,Number(metric.slice(5)));raw=difference(r.raw,old?.raw);value=raw==null?null:Number(raw)}
 else if(/^(?:delta_)?ma\d+$/.test(metric)){const n=Number(metric.match(/\d+$/)[0]),source=changes||map,window=Array.from({length:n},(_,j)=>at(source,r,j)?.value);if(window.every(Number.isFinite))value=window.reduce((a,b)=>a+b,0)/n}
 else if(/^(growth|annual)[36]$/.test(metric)){const n=Number(metric.at(-1)),old=get(r,n)?.value;if(f==='M'&&Number.isFinite(old)&&old>0&&r.value>0)value=(Math.pow(r.value/old,metric.startsWith('annual')?12/n:1)-1)*100}
 else if(metric==='percentile'){const history=rs.slice(0,i+1).map(r=>r.value).filter(Number.isFinite);value=100*history.filter(v=>v<=r.value).length/history.length}
 else {const n=metric.startsWith('eight')?8:metric==='yoy'?({M:12,Q:4,W:s.calendar==='48week'?48:52,D:365,A:1,F:3}[f]):1;const old=get(r,n)?.value;if(Number.isFinite(old)&&old!==0&&(!['annual','eightannual'].includes(metric)||(r.value>0&&old>0))){const exponent=metric==='eightannual'?0.5:metric==='annual'?({M:12,Q:4,W:s.calendar==='48week'?48:52,D:365,A:1,F:3}[f]):1;value=(Math.pow(r.value/old,exponent)-1)*100}}
 return {...r,value:Number.isFinite(value)?value:null,raw:raw??(Number.isFinite(value)?String(Number(value.toPrecision(15))):null),status:'derived'};});}
export function compatibleUnit(s,m){return m.startsWith('bp')?'bp':['yoy','qoq','annual','growth3','growth6','annual3','annual6','eight','eightannual','percentile'].includes(m)?'%':m.startsWith('delta')&&['%','Percent'].includes(s.unit)?'ポイント':s.unit}

// Classify the meaning of the displayed value, not merely its percent unit.
// An unemployment rate, saving rate or probability is not a growth rate.
export function tableHeatRule(s,metric='level'){
 if(/^(delta\d+|delta_ma\d+|bp1d|bp1w|bp1m|bp3m|bp1y|yoy|qoq|annual|growth[36]|annual[36]|eight|eightannual)$/.test(metric))return {center:0,label:'増減・差（0基準）'};
 if(metric!=='level'&&!/^ma\d+$/.test(metric))return null;
 const id=(s.sourceId||s.id||'').replace(/^ex:/,''),unit=s.unit||'',label=s.label||'';
 const text=[label,s.publicationLabel,s.publication,s.measure].filter(Boolean).join(' ');
 if(/^(ism|sp):/.test(id)&&unit==='DI')return {center:50,label:'PMI（50基準）'};
 if(/^derived:ism_/.test(id))return {center:0,label:'指数差（0基準）'};
 if(/uncertainty|probability|percentile|standard deviation|variance|確率|不確実|分散/i.test(text))return null;
 if(/^sloos:/.test(id)&&/net percentage/i.test(label))return {center:0,label:'ネット回答比率（0基準）'};
 if(/%|Percent|ポイント/i.test(unit)&&/percent(?:age)? change|contributions? to|growth|成長率|伸び率|寄与度|上昇率|前年比|前月比|前期比/i.test(text))return {center:0,label:'伸び率・寄与度（0基準）'};
 if(/Percent Change/i.test(unit))return {center:0,label:'伸び率（0基準）'};
 if(/^macrocalc:(pce_dpi_gap|adp_pay_gap):/.test(id))return {center:0,label:'伸び率の差（0基準）'};
 return null;
}
export function tableHeatLimit(values,center=0){
 const a=values.filter(Number.isFinite).map(v=>Math.abs(v-center)).filter(v=>v>0).sort((a,b)=>a-b);
 return a.length?a[Math.ceil(a.length*.9)-1]:1;
}
export function tableHeatColor(value,rule,limit){
 if(!Number.isFinite(value)||!rule)return null;
 const delta=value-rule.center;
 if(rule.manual){const span=delta<0?rule.center-rule.lower:rule.upper-rule.center,hex=delta<0?rule.negative:rule.positive;const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));return `rgba(${rgb.join(',')},${(Math.min(Math.abs(delta)/span,1)*.7).toFixed(4)})`}
 const alpha=Math.min(Math.abs(delta)/(limit||1),1)*.7;
 return `rgba(${delta<0?'238,142,153':'99,180,215'},${alpha.toFixed(4)})`;
}

export function manualHeatRule(config){
 if(!config)return null;
 const {lower,center,upper}=Object.fromEntries(['lower','center','upper'].map(k=>[k,String(config[k]??'').trim()===''?NaN:Number(config[k])]));
 if(![lower,center,upper].every(Number.isFinite)||!(lower<center&&center<upper))return null;
 const validColor=c=>/^#[0-9a-f]{6}$/i.test(c);
 if(!validColor(config.negative)||!validColor(config.positive))return null;
 return {manual:true,lower,center,upper,negative:config.negative,positive:config.positive,label:`手動基準 ${center} / 下限 ${lower} / 上限 ${upper}`};
}
