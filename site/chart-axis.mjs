// One scale for geometry and labels; keep full values in tooltips and tables.
export function niceAxis(values,{include=[],count=5}={}){
 const ns=[...values,...include].filter(Number.isFinite);let lo=ns.length?Math.min(...ns):0,hi=ns.length?Math.max(...ns):1;
 const pad=(hi-lo)*.06||Math.max(Math.abs(hi)*.01,.1);lo-=pad;hi+=pad;
 const rough=(hi-lo)/(count-1),power=10**Math.floor(Math.log10(rough)),step=([1,2,2.5,5,10].find(n=>n*power>=rough)||10)*power;
 const min=Math.floor(lo/step)*step,max=Math.ceil(hi/step)*step;
 const ticks=Array.from({length:Math.round((max-min)/step)+1},(_,i)=>Number((min+i*step).toPrecision(14)));
 const magnitude=Math.max(Math.abs(min),Math.abs(max)),divisor=magnitude>=1e9?1e9:magnitude>=1e6?1e6:magnitude>=1e4?1e3:1,suffix=divisor===1e9?' ×10⁹':divisor===1e6?' ×10⁶':divisor===1e3?' ×10³':'';
 const digits=Math.min(10,Math.max(0,1-Math.floor(Math.log10(step/divisor))));
 const format=v=>new Intl.NumberFormat('ja-JP',{maximumFractionDigits:digits}).format(Math.abs(v)<step*1e-9?0:v/divisor);
 return {min,max,step,ticks,divisor,suffix,format};
}
export function dateTicks(dates,width){const count=Math.min(dates.length,Math.max(2,Math.floor(width/110)));return [...new Set(Array.from({length:count},(_,i)=>dates[Math.round(i*(dates.length-1)/Math.max(1,count-1))]))];}

const settings=new Map();let clipSequence=0;
export function resolveAxis(values,options={},manual={}){
 const auto=niceAxis(values,options),min=manual.min??auto.min,max=manual.max??auto.max;
 if(!Number.isFinite(min)||!Number.isFinite(max)||min>=max||!Number.isFinite(max-min))throw Error('最小値は最大値より小さい数値にしてください。');
 if(manual.min==null&&manual.max==null)return {...auto,auto,manual:false};
 // Exact user limits, with evenly spaced ticks including both endpoints.
 const step=(max-min)/4,display=niceAxis([min,max]),divisor=display.divisor,suffix=display.suffix;
 const digits=Math.min(12,Math.max(0,2-Math.floor(Math.log10(step/divisor))));
 const format=v=>new Intl.NumberFormat('ja-JP',{maximumFractionDigits:digits}).format(v/divisor);
 return {min,max,step,divisor,suffix,format,ticks:Array.from({length:5},(_,i)=>i===4?max:min+i*step),auto,manual:true};
}
export function resetAxis(key){settings.delete(key)}
export function axisScale(key,values,options={}){
 const manual=settings.get(key)||{};let axis;
 try{axis=resolveAxis(values,options,manual)}catch{axis=resolveAxis(values,options);axis.invalidStored=true}
 return {...axis,values,options};
}
export function axisControls(svg,{key,unit='',axis,left,right,top,bottom,redraw}){
 const previous=svg.previousElementSibling;if(previous?.classList.contains('axis-controls'))previous.remove();
 const panel=document.createElement('div');panel.className='axis-controls';
 const title=document.createElement('span');title.textContent='縦軸の範囲';panel.append(title);
 const current=settings.get(key)||{},inputs={};
 for(const [field,label] of [['min','最小値'],['max','最大値']]){
  const wrap=document.createElement('label');wrap.textContent=label;
  const input=document.createElement('input');input.type='number';input.step='any';input.placeholder='自動：'+axis.auto[field];input.value=current[field]??'';input.setAttribute('aria-label','縦軸の'+label+'（'+unit+'）');wrap.append(input);panel.append(wrap);inputs[field]=input;
 }
 const apply=document.createElement('button');apply.type='button';apply.className='text-button';apply.textContent='適用';
 const reset=document.createElement('button');reset.type='button';reset.className='text-button';reset.textContent='自動に戻す';panel.append(apply,reset);
 const note=document.createElement('p');note.className='source-note';note.textContent='入力単位：'+(unit||'グラフの単位')+'。空欄は自動。目盛りに倍率がある場合も、元の数値を入力します。'+(axis.manual?' 指定範囲外は枠内で切り取り、元の数値は下の欄に表示します。':'');panel.append(note);
 const error=document.createElement('p');error.className='axis-error';error.setAttribute('role','alert');if(axis.invalidStored)error.textContent='現在の自動範囲と指定値が逆転したため、自動表示中です。上下限を確認してください。';panel.append(error);
 function submit(){const next={};for(const field of ['min','max']){const input=inputs[field];if(input.validity.badInput||input.value.trim()!==''&&!Number.isFinite(Number(input.value))){error.textContent='有限の数値を入力してください。';return}if(input.value.trim()!=='')next[field]=Number(input.value)}try{resolveAxis(axis.values,axis.options,next)}catch(e){error.textContent=e.message;return}settings.set(key,next);redraw()}
 apply.onclick=submit;reset.onclick=()=>{settings.delete(key);redraw()};Object.values(inputs).forEach(input=>input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();submit()}});
 svg.before(panel);
 if(axis.manual){const ns='http://www.w3.org/2000/svg',id='manual-axis-clip-'+(++clipSequence),defs=document.createElementNS(ns,'defs'),clip=document.createElementNS(ns,'clipPath'),rect=document.createElementNS(ns,'rect');clip.id=id;for(const [k,v] of Object.entries({x:left,y:top,width:right-left,height:bottom-top}))rect.setAttribute(k,v);clip.append(rect);defs.append(clip);for(const shape of svg.querySelectorAll('path,circle,rect,line'))shape.setAttribute('clip-path',`url(#${id})`);svg.prepend(defs)}
}
