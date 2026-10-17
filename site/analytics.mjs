// Pure calculations shared by the charts, tables and regression. Never fill missing data.
export const transforms=[['yoy','前年比',12],['mom','前月比',1],['m3','3か月前比',3],['m6','6か月前比',6],['a3','3か月前比・年率換算',3],['a6','6か月前比・年率換算',6],['level','指数・水準',0],['change','前月差',1]];
export const employmentAverages=[['avg3','雇用者数（水準）の3か月平均',3,'level'],['avg6','雇用者数（水準）の6か月平均',6,'level'],['delta_avg3','前月差の3か月平均',3,'change'],['delta_avg6','前月差の6か月平均',6,'change'],['delta_avg12','前月差の12か月平均',12,'change']];
export function shiftMonth(month,lag){const [y,m]=month.split('-').map(Number),n=y*12+m-1+lag;return `${Math.floor(n/12)}-${String((n%12+12)%12+1).padStart(2,'0')}`;}
export function availableMetrics(d,series,season){
 if(d.kind==='base')return (series.bases?.[season]?.some(v=>v!=null)?[...transforms,...(d.id==='employment'?employmentAverages:[])]:[]).map(([id,label])=>({id,label:d.id==='employment'&&id==='level'?'雇用者数（水準）':d.id==='employment'&&id==='change'?'雇用者数の前月差':label,unit:employmentAverages.some(m=>m[0]===id)?d.baseUnit:id==='level'?d.baseUnit:id==='change'?(d.baseUnit==='%'?'ポイント':d.baseUnit):'%'}));
 return d.metrics.filter(m=>m.id==='ri'||m.id==='effect'||m.id==='core'||(season==='NSA'&&['yoy','nsa_mom'].includes(m.id))||(season==='SA'&&m.id==='mom')).map(m=>({...m,label:m.label.replace(/（(?:NSA|SA)）/g,'')}));
}
export function seasons(d,s){if(d.kind==='base')return ['SA','NSA'].filter(k=>s.bases?.[k]?.some(v=>v!=null));return ['SA','NSA'];}
export function valuesFor(d,s,season,transform){
 if(d.kind==='release')return availableMetrics(d,s,season).some(m=>m.id===transform)?s.values[transform]:d.dates.map(()=>null);
 const values=s.bases?.[season]||d.dates.map(()=>null);if(transform==='level')return values;
 const average=d.id==='employment'?employmentAverages.find(m=>m[0]===transform):null;
 if(average){
  const input=average[3]==='level'?values:valuesFor(d,s,season,'change');
  const byMonth=new Map(d.dates.map((date,i)=>[date,input[i]]));
  return d.dates.map(date=>{const window=Array.from({length:average[2]},(_,i)=>byMonth.get(shiftMonth(date,-i)));return window.every(Number.isFinite)?window.reduce((a,b)=>a+b,0)/average[2]:null});
 }
 const desc=transforms.find(m=>m[0]===transform);if(!desc)return d.dates.map(()=>null);
 const byDate=new Map(d.dates.map((date,i)=>[date,values[i]])),lag=desc[2];
 return d.dates.map((date,i)=>{const a=values[i],b=byDate.get(shiftMonth(date,-lag));if(a==null||b==null)return null;if(transform==='change')return a-b;if(b===0)return null;const ratio=a/b;if(transform.startsWith('a')&&(ratio<=0||a<=0||b<=0))return null;const v=(transform.startsWith('a')?Math.pow(ratio,12/lag)-1:ratio-1)*100;return Number.isFinite(v)?v:null});
}
export function alignPairs(xDates,xValues,yDates,yValues,from,to,lag){
 if(!Number.isInteger(lag)||lag < -120||lag>120)throw Error('ラグは−120〜120か月の整数にしてください。');
 if(!/^\d{4}-\d{2}$/.test(from)||!/^\d{4}-\d{2}$/.test(to)||from>to)throw Error('開始月と終了月を確認してください。');
 const xs=new Map(xDates.map((d,i)=>[d,xValues[i]]));let missing=0,total=0;const pairs=[];
 yDates.forEach((date,i)=>{if(date<from||date>to)return;total++;const xDate=shiftMonth(date,-lag),x=xs.get(xDate),y=yValues[i];if(!Number.isFinite(x)||!Number.isFinite(y)){missing++;return}pairs.push({date,xDate,x,y})});return {pairs,missing,total};
}
export function regress(pairs,degree=1){
 if(![1,2].includes(degree))throw Error('近似方法を確認してください。');
 const n=pairs.length,p=degree+1;if(n<=p)throw Error(`有効な観測が不足しています。${p+1}点以上になる期間を選んでください。`);
 const mean=pairs.reduce((s,r)=>s+r.x,0)/n,scale=Math.sqrt(pairs.reduce((s,r)=>s+(r.x-mean)**2,0)/n);
 if(!Number.isFinite(scale)||scale<1e-12*Math.max(1,Math.abs(mean)))throw Error('説明変数Xに変動がないため、回帰できません。');
 const z=pairs.map(r=>(r.x-mean)/scale),ys=pairs.map(r=>r.y),Q=[],R=Array.from({length:p},()=>Array(p).fill(0));
 for(let j=0;j<p;j++){const v=z.map(a=>a**j);for(let k=0;k<j;k++){R[k][j]=v.reduce((s,a,i)=>s+a*Q[k][i],0);for(let i=0;i<n;i++)v[i]-=R[k][j]*Q[k][i];}R[j][j]=Math.hypot(...v);if(R[j][j]<1e-10)throw Error('Xの異なる値が不足しており、この近似曲線を計算できません。');Q.push(v.map(a=>a/R[j][j]));}
 const beta=Q.map(q=>q.reduce((s,v,i)=>s+v*ys[i],0));for(let j=p-1;j>=0;j--){for(let k=j+1;k<p;k++)beta[j]-=R[j][k]*beta[k];beta[j]/=R[j][j];}
 const predict=x=>beta.reduce((s,b,j)=>s+b*((x-mean)/scale)**j,0),yMean=ys.reduce((a,b)=>a+b,0)/n,sse=pairs.reduce((s,r)=>s+(r.y-predict(r.x))**2,0),sst=ys.reduce((s,y)=>s+(y-yMean)**2,0);
 const c2=degree===2?beta[2]/scale**2:0,c1=beta[1]/scale-2*c2*mean,c0=beta[0]-beta[1]*mean/scale+c2*mean**2;
 return {n,degree,coefficients:[c0,c1,...(degree===2?[c2]:[])],r2:sst<=1e-20?null:Math.max(0,Math.min(1,1-sse/sst)),rmse:Math.sqrt(sse/n),predict};
}
export function heatColor(value,limit){if(value==null)return '#f0f2f5';const a=Math.min(Math.abs(value)/limit,1),end=value<0?[249,147,151]:[103,189,233];return `rgb(${end.map(v=>Math.round(255+(v-255)*a)).join(',')})`;}
