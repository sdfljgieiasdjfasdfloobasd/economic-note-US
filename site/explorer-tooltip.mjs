export function nearestIndex(points,x){if(!points.length)return -1;let lo=0,hi=points.length-1;while(lo<hi){const m=(lo+hi)>>1;if(points[m].x<x)lo=m+1;else hi=m}return lo>0&&Math.abs(points[lo-1].x-x)<=Math.abs(points[lo].x-x)?lo-1:lo}
// Readout stays below the plot; hover, touch and keyboard share the same values.
export function attachTooltip(svg,{points,left,right,top,bottom,esc,fmt,compact=false}){
 if(!points.length)return;
 const box=svg.parentElement;box.classList.add('ex-hover-host');
 const tip=document.createElement('div');tip.className='ex-hover-tooltip'+(compact?' ex-hover-compact':'');tip.hidden=true;tip.setAttribute('role','status');svg.after(tip);svg.querySelectorAll('title').forEach(t=>t.remove());
 const ns='http://www.w3.org/2000/svg',guide=document.createElementNS(ns,'line');guide.setAttribute('y1',top);guide.setAttribute('y2',bottom);guide.setAttribute('stroke','#607b87');guide.setAttribute('stroke-dasharray','3 3');guide.setAttribute('pointer-events','none');guide.style.display='none';svg.append(guide);
 let index=points.length-1;
 function hide(){guide.style.display='none'}
 function show(i){index=Math.max(0,Math.min(points.length-1,i));const p=points[index];tip.innerHTML=compact?`<strong>${esc(p.label)}</strong>${p.values.map(v=>`<div aria-label="${esc(v.label)}: ${fmt(v.value)} ${esc(v.unit||'')}"><i style="background:${v.color||'#007e72'}"></i><b>${fmt(v.value)}</b></div>`).join('')}`:`<strong>${esc(p.label)}</strong>${p.values.map(v=>`<div><span><i style="background:${v.color||'#007e72'}"></i>${esc(v.label)}${v.date?'<small>'+esc(v.date)+'</small>':''}</span><b>${fmt(v.value)} <small>${esc(v.unit||'')}</small></b></div>`).join('')}<small>— はこの日・区分の観測なし</small>`;tip.hidden=false;guide.style.display='';guide.setAttribute('x1',p.x);guide.setAttribute('x2',p.x);

 }
 function pointer(e){const matrix=svg.getScreenCTM();if(!matrix)return;const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());if(p.x<left||p.x>right||p.y<top||p.y>bottom){hide();return}show(nearestIndex(points,p.x))}
 svg.addEventListener('pointermove',pointer);svg.addEventListener('click',pointer);svg.addEventListener('pointerleave',hide);svg.addEventListener('blur',hide);
 svg.setAttribute('tabindex','0');svg.setAttribute('aria-label',(svg.getAttribute('aria-label')||'グラフ')+'。カーソル・タップ、左右キーで数値を表示。');
 show(index);hide();
 svg.addEventListener('focus',()=>show(index));svg.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End','Escape'].includes(e.key)){e.preventDefault();if(e.key==='Escape')hide();else show(e.key==='Home'?0:e.key==='End'?points.length-1:index+(e.key==='ArrowLeft'?-1:1))}});
}
