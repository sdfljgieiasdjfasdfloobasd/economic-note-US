import {axisScale,axisControls} from './chart-axis.mjs?v=17b2b4b6db30bdcab144';
import {niceAxis} from './chart-axis.mjs?v=17b2b4b6db30bdcab144';
import {buildContributions,stackContributions} from './contributions.mjs?v=17b2b4b6db30bdcab144';
import {shiftMonth} from './analytics.mjs?v=17b2b4b6db30bdcab144';
export function setupContributions({esc,fmt}){
 const $=s=>document.querySelector(s),panel=$('#contribution-panel');
 let model=null,dataRef=null,rows=[],barMode='monthly',lineMode='ma3',chartType='stacked',range='36',hidden=new Set(),hiddenTotals=new Set(),active=-1,geometry=null;
 const signed=v=>Number.isFinite(v)?(v>=.0005?'+':'')+fmt(v):'—';
 const totalKeys=()=>lineMode==='both'?['totalMA3','total']:lineMode==='monthly'?['total']:['totalMA3'];
 const visibleTotalKeys=()=>totalKeys().filter(k=>!hiddenTotals.has(k));
 const totalLabel=k=>k==='totalMA3'?'Total 3か月平均':'Total 単月';
 const lineLabel=()=>visibleTotalKeys().map(totalLabel).join('・')||'非表示';
 function setDataset(d){
  panel.hidden=d.id!=='employment';if(panel.hidden)return;
  if(dataRef===d){draw();return}
  const first=!model;dataRef=d;
  try{model=buildContributions(d);$('#contribution-error').hidden=true;
   if(first){$('#contribution-to').value=model.latest;$('#contribution-from').value=shiftMonth(model.latest,-35)}
   else if(range!=='custom')setRange(range);
   $('#contribution-method-list').innerHTML=model.industries.map(s=>`<li><strong>${esc(s.label)}</strong> / ${esc(s.name)}<small>${esc(s.path.join(' › '))}</small></li>`).join('');
   renderLegend();render();
  }catch(e){model=null;$('#contribution-error').textContent=e.message;$('#contribution-error').hidden=false;$('#contribution-svg').innerHTML='';$('#contribution-tooltip').hidden=true;$('#contribution-audit').textContent='';}
 }
 function setRange(value){range=value;if(!model)return;$('#contribution-to').value=model.latest;$('#contribution-from').value=value==='all'?model.rows[0].date:shiftMonth(model.latest,-Number(value)+1);}
 function renderLegend(){
  $('#contribution-legend').innerHTML=model.industries.map((s,i)=>`<button type="button" data-industry="${i}" aria-pressed="${!hidden.has(i)}" title="${esc(s.name)}" aria-label="${esc(s.label)}を${hidden.has(i)?'表示':'非表示'}"><span class="dot" style="background:${s.color}"></span>${esc(s.label)}</button>`).join('');
  panel.querySelectorAll('[data-industry]').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.industry);if(hidden.has(i))hidden.delete(i);else hidden.add(i);renderLegend();render();panel.querySelector(`[data-industry="${i}"]`)?.focus()});
 }
 function render(){
  if(!model)return;const from=$('#contribution-from').value,to=$('#contribution-to').value;
  const valid=from&&to&&from<=to;$('#contribution-error').hidden=!!valid;
  if(!valid){$('#contribution-error').textContent='寄与チャートの開始月と終了月を確認してください。';rows=[]}else rows=model.rows.filter(r=>r.date>=from&&r.date<=to);
  panel.querySelectorAll('[data-contribution-range]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.contributionRange===range)));
  panel.querySelectorAll('[data-bar-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.barMode===barMode)));
  panel.querySelectorAll('[data-contribution-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.contributionView===chartType)));
  $('#contribution-intro').textContent=(chartType==='lines'?'全11業種の増減を、積み上げずに同じ0基準の折れ線で比較。':'増加は0より上、減少は下へ積み上げ。')+'凡例を押すと業種を表示・非表示にできます。';
  const missing=rows.filter(r=>!(barMode==='ma3'?r.completeMA3:r.complete)).length;
  const differences=rows.filter(r=>Math.abs(barMode==='ma3'?r.residualMA3:r.residual)>1e-7).length;
  $('#contribution-audit').textContent=`${rows.length}か月・${model.industries.length-hidden.size}/11業種を表示。`+(differences?`${differences}か月で業種合計とTotalに差があります（詳細は各月の内訳）。`:'収録済みの月では、11業種合計とTotalが一致しています。')+(missing?` ${missing}か月は内訳に欠損があります。${chartType==='lines'?'欠損箇所は線をつなぎません。':'その月の棒を表示しません。'}`:'')+(hidden.size&&visibleTotalKeys().length?' Totalは非表示業種も含む全業種の値です。':'')+' 縦軸は表示中の系列に合わせて自動調整します。'+(barMode==='monthly'&&visibleTotalKeys().includes('totalMA3')?' 業種別の単月値の合計とTotalの3か月平均は一致しません。':'');
  $('#contribution-line-key').innerHTML=totalKeys().map(k=>`<button type="button" data-total-toggle="${k}" aria-pressed="${!hiddenTotals.has(k)}" aria-label="${totalLabel(k)}を${hiddenTotals.has(k)?'表示':'非表示'}"><i class="line-key ${k==='total'?'monthly':''}"></i>${totalLabel(k)}</button>`).join('')+'<span>（千人）</span>';
  panel.querySelectorAll('[data-total-toggle]').forEach(b=>b.onclick=()=>{const key=b.dataset.totalToggle;if(hiddenTotals.has(key))hiddenTotals.delete(key);else hiddenTotals.add(key);render();panel.querySelector(`[data-total-toggle="${key}"]`)?.focus()});
  $('#contribution-period').textContent=rows.length?`${rows[0].date} — ${rows.at(-1).date} ／ 保存データ最新月 ${model.latest}`:'対象期間にデータがありません。';
  active=-1;$('#contribution-tooltip').hidden=true;draw();
 }
 function draw(){
  if(!model||panel.hidden||$('#time-view').hidden)return;
  const svg=$('#contribution-svg');svg.onpointermove=null;svg.onpointerdown=null;svg.onpointerleave=null;svg.onfocus=null;svg.onkeydown=null;geometry=null;
  const w=Math.max(280,svg.clientWidth),h=w<600?360:440,L=w<600?70:86,R=15,T=20,B=42;
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.innerHTML='';
  if(!rows.length){svg.setAttribute('aria-label','対象期間に表示するデータがありません');$('#contribution-audit').textContent='';svg.innerHTML=`<text x="${w/2}" y="${h/2}" text-anchor="middle" fill="#69788b" font-size="14">表示するデータがありません</text>`;return}
  const stacks=rows.map(r=>stackContributions(r,barMode,hidden)),lineKeys=visibleTotalKeys();
  if(hidden.size===model.industries.length&&!lineKeys.length){svg.setAttribute('aria-label','すべての系列が非表示です。凡例から表示してください。');svg.innerHTML=`<text x="${w/2}" y="${h/2}" text-anchor="middle" fill="#69788b" font-size="12">凡例から表示する系列を選んでください</text>`;return}
  const industryValues=rows.map(r=>barMode==='ma3'?r.ma3:r.monthly);
  const industryExtent=chartType==='lines'?industryValues.flatMap(v=>v.filter((n,i)=>!hidden.has(i)&&Number.isFinite(n))):stacks.filter(Boolean).flatMap(s=>[s.positive,s.negative]);
  const nums=[0,...industryExtent,...rows.flatMap(r=>lineKeys.map(k=>r[k])).filter(Number.isFinite)];
  const axisKey='nfp:'+barMode+':'+chartType,axis=axisScale(axisKey,nums),lo=axis.min,hi=axis.max;
  const step=(w-L-R)/rows.length,x=i=>L+(i+.5)*step,y=v=>T+(hi-v)/(hi-lo)*(h-T-B),barW=Math.max(.35,Math.min(20,step*.76));
  geometry={w,h,L,R,T,B,step,x,y};let out=`<text x="${L}" y="12" font-size="11">千人${axis.suffix}</text>`;
  const latest=rows.findIndex(r=>r.date===model.latest);
  if(latest>=0)out+=`<rect x="${L+latest*step}" y="${T}" width="${step}" height="${h-T-B}" fill="#edf2f6"/>`;
  for(const v of axis.ticks){out+=`<line x1="${L}" x2="${w-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e6ebf0"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end" font-size="12" fill="#64778a">${axis.format(v)}</text>`}
  if(chartType==='stacked')stacks.forEach((stack,i)=>{if(!stack)return;for(const seg of stack.segments){if(seg.value===0)continue;out+=`<rect data-contribution-month="${rows[i].date}" data-contribution-industry="${seg.index}" x="${x(i)-barW/2}" y="${Math.min(y(seg.start),y(seg.end))}" width="${barW}" height="${Math.abs(y(seg.start)-y(seg.end))}" fill="${model.industries[seg.index].color}"/>`}});
  out+=`<line x1="${L}" x2="${w-R}" y1="${y(0)}" y2="${y(0)}" stroke="#526577" stroke-width="1.5"/><text x="${L-8}" y="${y(0)+4}" text-anchor="end" font-size="12" fill="#24394d" stroke="white" stroke-width="3" paint-order="stroke">0</text>`;
  if(chartType==='lines')model.industries.forEach((industry,index)=>{
   if(hidden.has(index))return;let path='',open=false;
   industryValues.forEach((values,i)=>{const v=values[index];if(!Number.isFinite(v)){open=false;return}path+=`${open?'L':'M'}${x(i)},${y(v)} `;open=true});
   out+=`<path data-industry-line="${index}" d="${path}" fill="none" stroke="${industry.color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>`;
   industryValues.forEach((values,i)=>{const v=values[index];if(Number.isFinite(v)&&(i===latest||(!Number.isFinite(industryValues[i-1]?.[index])&&!Number.isFinite(industryValues[i+1]?.[index]))))out+=`<circle data-industry-point="${index}" cx="${x(i)}" cy="${y(v)}" r="2.5" fill="${industry.color}"/>`});
  });
  for(const key of lineKeys){let path='',open=false;rows.forEach((r,i)=>{const v=r[key];if(!Number.isFinite(v)){open=false;return}path+=`${open?'L':'M'}${x(i)},${y(v)} `;open=true});out+=`<path data-total-line="${key}" d="${path}" fill="none" stroke="${key==='total'&&lineMode==='both'?'#64778a':'#142b42'}" stroke-width="${key==='totalMA3'?2.5:1.8}" ${key==='total'?'stroke-dasharray="5 3"':''}/>`;
   // Make a one-month selection visible, too.
   if(rows.length===1&&Number.isFinite(rows[0][key]))out+=`<circle cx="${x(0)}" cy="${y(rows[0][key])}" r="3.5" fill="#142b42"/>`;
  }
  const ticks=Math.min(rows.length,w<600?3:7),seen=new Set();for(let i=0;i<ticks;i++){const index=ticks===1?0:Math.round((rows.length-1)*i/(ticks-1));if(seen.has(index))continue;seen.add(index);out+=`<text x="${x(index)}" y="${h-13}" text-anchor="${i===0?'start':i===ticks-1?'end':'middle'}" fill="#697b8d" font-size="12" font-weight="${index===latest?'700':'400'}">${rows[index].date}</text>`}
  out+=`<line id="contribution-cursor" y1="${T}" y2="${h-B}" stroke="#51687c" stroke-dasharray="3 3" visibility="hidden"/>`;
  svg.innerHTML=out;axisControls(svg,{key:axisKey,unit:'千人',axis,left:L,right:w-R,top:T,bottom:h-B,redraw:draw});svg.setAttribute('aria-label',`業種別雇用増減寄与、季節調整済み、千人。業種別は${chartType==='lines'?'折れ線':'積み上げ棒'}、${barMode==='ma3'?'前月差の3か月平均':'単月前月差'}。折れ線は${lineLabel()}。左右キーで各月の内訳を確認できます。`);
  function point(e){const rect=svg.getBoundingClientRect(),px=(e.clientX-rect.left)*w/rect.width;showMonth(Math.max(0,Math.min(rows.length-1,Math.floor((px-L)/step))))}
  svg.onpointermove=point;svg.onpointerdown=point;svg.onpointerleave=e=>{if(e.pointerType==='mouse'){$('#contribution-cursor')?.setAttribute('visibility','hidden')}};
  svg.onfocus=()=>showMonth(rows.length-1);
  svg.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End','Escape'].includes(e.key)){e.preventDefault();if(e.key==='Escape'){$('#contribution-tooltip').hidden=true;active=-1;$('#contribution-cursor')?.setAttribute('visibility','hidden');return}const next=e.key==='Home'?0:e.key==='End'?rows.length-1:active<0?rows.length-1:active+(e.key==='ArrowRight'?1:-1);showMonth(Math.max(0,Math.min(rows.length-1,next)))}};
  if(active>=0)showMonth(active,true);
 }
 function showMonth(index,force=false){
  if(!geometry||(!force&&index===active))return;active=index;const r=rows[index],tip=$('#contribution-tooltip'),{x,w}=geometry;
  const cursor=$('#contribution-cursor');cursor.setAttribute('x1',x(index));cursor.setAttribute('x2',x(index));cursor.setAttribute('visibility','visible');
  const vals=barMode==='ma3'?r.ma3:r.monthly,order=model.industries.map((s,i)=>({...s,index:i,value:vals[i]})).sort((a,b)=>(Number.isFinite(b.value)?Math.abs(b.value):-1)-(Number.isFinite(a.value)?Math.abs(a.value):-1));
  const residual=barMode==='ma3'?r.residualMA3:r.residual;
  tip.innerHTML=`<strong>${esc(r.date)} <span>季節調整済み・千人</span></strong><div class="contribution-tip-row ${visibleTotalKeys().includes('total')?'':'industry-hidden'}"><b>Total nonfarm・単月${visibleTotalKeys().includes('total')?'':'［非表示］'}</b><b>${signed(r.total)}</b></div><div class="contribution-tip-row ${visibleTotalKeys().includes('totalMA3')?'':'industry-hidden'}"><b>Total・3か月平均${visibleTotalKeys().includes('totalMA3')?'':'［非表示］'}</b><b>${signed(r.totalMA3)}</b></div><p>業種別：${barMode==='ma3'?'前月差の3か月平均':'単月前月差'}（絶対値の大きい順）</p>`+order.map(s=>`<div class="contribution-tip-row ${hidden.has(s.index)?'industry-hidden':''}"><span title="${esc(s.name)}"><i class="dot" style="background:${s.color}"></i>${esc(s.label)}${hidden.has(s.index)?'［非表示］':''}</span><span>${signed(s.value)}</span></div>`).join('')+(!(barMode==='ma3'?r.completeMA3:r.complete)?(chartType==='lines'?'<p>欠損している業種の線はつなぎません。</p>':'<p>内訳に欠損があるため、この月の棒は非表示です。</p>'):'')+(Math.abs(residual)>1e-7?`<p>全11業種合計との差：${signed(residual)} 千人</p>`:'');
  tip.hidden=false;tip.style.left=(x(index)>w*.55?'8px':'auto');tip.style.right=(x(index)>w*.55?'auto':'8px');
 }
 panel.querySelectorAll('[data-contribution-view]').forEach(b=>b.onclick=()=>{chartType=b.dataset.contributionView;render()});
 panel.querySelectorAll('[data-bar-mode]').forEach(b=>b.onclick=()=>{barMode=b.dataset.barMode;render()});
 panel.querySelectorAll('[data-contribution-range]').forEach(b=>b.onclick=()=>{setRange(b.dataset.contributionRange);render()});
 $('#contribution-line').onchange=e=>{lineMode=e.target.value;render()};
 for(const id of ['contribution-from','contribution-to'])$('#'+id).onchange=()=>{range='custom';render()};
 return {setDataset,resize:draw,summary:()=>model?{from:$('#contribution-from').value,to:$('#contribution-to').value,barMode,lineMode,chartType,hiddenTotals:[...hiddenTotals],hidden:[...hidden].map(i=>model.industries[i].name),latest:rows.at(-1)}:null};
}
