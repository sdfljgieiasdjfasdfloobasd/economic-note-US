// Optional, independent right axis shared by all chronological charts.
export const policyId='policy:target-midpoint';
export const policyLabel='米国政策金利（目標レンジ中央）';
const color='#923c92',states=new Map();
let requestData=null,pending=null;
export function setupPolicyOverlay(request){requestData=request;pending=null}
export function invalidatePolicyOverlay(){pending=null}
async function load(){
 if(!requestData)throw Error('保存データへの接続がありません');
 if(!pending)pending=requestData('/api/explorer/series?id='+encodeURIComponent(policyId)).catch(e=>{pending=null;throw e});
 return pending;
}
export function periodEnd(date,frequency='D'){
 const d=date.length===7?date+'-01':date;
 if(!/^\d{4}-\d{2}-\d{2}$/.test(d))return null;
 const [y,m]=d.split('-').map(Number);
 if(frequency==='M')return new Date(Date.UTC(y,m,0)).toISOString().slice(0,10);
 if(frequency==='Q')return new Date(Date.UTC(y,Math.ceil(m/3)*3,0)).toISOString().slice(0,10);
 if(frequency==='A')return `${y}-12-31`;
 return d;
}
export function policyPoints(observations,timeline){
 const anchors=timeline.points.map(p=>({x:p.x,date:periodEnd(p.date,timeline.frequency)})).filter(p=>p.date).sort((a,b)=>a.date.localeCompare(b.date));
 if(!anchors.length)return [];
 const start=anchors[0].date,end=anchors.at(-1).date;
 let j=0;
 return observations.filter(r=>r.date>=start&&r.date<=end).map(r=>{
  while(j<anchors.length-2&&r.date>anchors[j+1].date)j++;
  const a=anchors[j],b=anchors[j+1]||a,span=Date.parse(b.date)-Date.parse(a.date);
  return {...r,x:a.x+(span?(Date.parse(r.date)-Date.parse(a.date))/span:0)*(b.x-a.x)};
 });
}
const format=v=>Number.isFinite(v)?Number(v.toFixed(6)).toString():'—';
function node(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n}
export function mountPolicyOverlay(svg,{key,timeline,left,right,top,bottom,panel}){
 svg._policyCleanup?.();
 if(!timeline?.points?.length)return;
 let alive=true,rows=[],group=null,generation=0;
 const base=svg.getAttribute('viewBox'),[vx,vy,w,h]=base.split(/\s+/).map(Number);
 const bar=document.createElement('div');bar.className='policy-overlay-controls';
 bar.style.cssText='display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0;font-size:13px';
 const label=document.createElement('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=states.get(key)||false;
 label.append(checkbox,' 政策金利を重ねる（レンジ中央・右軸％）');bar.append(label);
 const readout=document.createElement('span');readout.setAttribute('role','status');bar.append(readout);
 const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='計算方法・出典';details.append(summary);
 const note=document.createElement('p');note.textContent='目標レンジの上限と下限の平均。金利そのものを右軸％で表示し、左の指標の前月比などには変換しません。月次は月末、四半期は期末、年次は年末に位置を合わせ、期間内の変更は階段状に表示します。日次・週次は対象日。未取得日・2008年12月16日以前は空欄。';details.append(note);
 for(const code of ['DFEDTARL','DFEDTARU']){const a=document.createElement('a');a.href='https://fred.stlouisfed.org/series/'+code;a.textContent='FRB / FRED '+code;a.target='_blank';a.rel='noopener noreferrer';details.append(a,' ')}
 bar.append(details);panel.before(bar);
 function clear(){group?.remove();group=null;rows=[];svg.setAttribute('viewBox',base);delete svg.policyOverlayContext}
 function nearest(e){if(!rows.length)return;const matrix=svg.getScreenCTM();if(!matrix)return;const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());if(p.x<left||p.x>right)return;let a=0,b=rows.length-1;while(a<b){const m=(a+b)>>1;if(rows[m].x<p.x)a=m+1;else b=m}if(a&&Math.abs(rows[a-1].x-p.x)<Math.abs(rows[a].x-p.x))a--;const r=rows[a];readout.textContent=`${r.date}：${format(r.value)}％`}
 async function draw(){
  const ticket=++generation;clear();if(!checkbox.checked){readout.textContent='';return}
  readout.textContent='政策金利を読み込み中…';
  try{
   const data=await load();if(!alive||ticket!==generation||!checkbox.checked||!svg.isConnected)return;
   rows=policyPoints(data.observations||[],timeline);
   const valid=rows.filter(r=>Number.isFinite(r.value));
   if(!valid.length){readout.textContent='この期間の政策金利は未収録です';return}
   const min=Math.min(0,Math.floor(Math.min(...valid.map(r=>r.value)))),max=Math.max(1,Math.ceil(Math.max(...valid.map(r=>r.value)))),y=v=>top+(max-v)/(max-min)*(bottom-top);
   svg.setAttribute('viewBox',`${vx} ${vy} ${w+72} ${h}`);group=node('g',{'data-policy-overlay':'true'});
   group.append(node('text',{x:right+8,y:bottom+24,fill:color,'font-size':11},'政策金利 %'));
   for(let i=0;i<=4;i++){const v=min+(max-min)*i/4;group.append(node('text',{x:right+8,y:y(v)+4,fill:color,'font-size':11},format(v)))}
   let path='',previous=null;
   for(const r of rows){if(!Number.isFinite(r.value)){previous=null;continue}const contiguous=previous&&Date.parse(r.date)-Date.parse(previous.date)===86400000;path+=contiguous?`H${r.x}V${y(r.value)} `:`M${r.x},${y(r.value)} `;previous=r}
   group.append(node('path',{d:path,stroke:color,'stroke-width':2.4,fill:'none','pointer-events':'none'}));
   if(valid.length===1)group.append(node('circle',{cx:valid[0].x,cy:y(valid[0].value),r:3,fill:color}));
   svg.append(group);svg.policyOverlayContext={label:policyLabel+' · 右軸 %',color,source:'FRB / FRED DFEDTARL・DFEDTARU、(上限＋下限)÷2',observations:rows};
   const last=valid.at(-1);readout.textContent=`表示内の最新 ${last.date}：${format(last.value)}％${data.status==='fetch_failed'?'（更新失敗・保存値）':''}`;
  }catch(e){if(alive)readout.textContent='政策金利を表示できません：'+e.message}
 }
 checkbox.onchange=()=>{states.set(key,checkbox.checked);draw()};svg.addEventListener('pointermove',nearest);svg.addEventListener('click',nearest);
 svg._policyCleanup=()=>{alive=false;bar.remove();group?.remove();svg.removeEventListener('pointermove',nearest);svg.removeEventListener('click',nearest);delete svg.policyOverlayContext};
 draw();
}
