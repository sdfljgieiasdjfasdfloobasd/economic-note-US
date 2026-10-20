import {valuesFor} from './analytics.mjs?v=85d107fdd139f49e4aa3';
// Fixed identities/colors. These are a disjoint frontier of the saved BLS tree.
export const industryDefinitions = [
 ['Mining and logging','鉱業・伐採業','#998260'],
 ['Construction','建設業','#c89148'],
 ['Manufacturing','製造業','#547b9d'],
 ['Trade, transportation, and utilities','商業・運輸・公益','#638d8f'],
 ['Information','情報産業','#7d73a3'],
 ['Financial activities','金融関連','#ad7d9d'],
 ['Professional and business services','専門・事業サービス','#739873'],
 ['Private education and health services','民間教育・医療等','#398878'],
 ['Leisure and hospitality','娯楽・宿泊・飲食','#b87960'],
 ['Other services','その他サービス','#97a9bd'],
 ['Government','政府部門','#b0aa76']
].map(([name,label,color])=>({name,label,color}));

export function buildContributions(d){
 if(d.id!=='employment')throw Error('雇用者数のデータ表を選んでください。');
 const byName=new Map(d.series.map(s=>[s.name,s])),byId=new Map(d.series.map(s=>[s.id,s]));
 const total=byName.get('Total nonfarm');
 if(!total)throw Error('Total nonfarm が見つかりません。');
 const industries=industryDefinitions.map(def=>{
  const s=byName.get(def.name);
  if(!s?.bases?.SA||!s.hierarchy)throw Error(`${def.name} の季節調整済み系列または分類がありません。`);
  return {...def,id:s.id,path:s.hierarchy.path,source:s};
 });
 const selected=new Set(industries.map(s=>s.id));
 // No selected ancestor/descendant pair; every selected series belongs to NFP.
 for(const s of industries){
  let parent=s.source.hierarchy.parentId,seen=new Set([s.id]),belongs=false;
  while(parent!=null){
   if(seen.has(parent)||selected.has(parent))throw Error('業種分類が重複しているため、表示を中止しました。');
   seen.add(parent);if(parent===total.id)belongs=true;
   const p=byId.get(parent);if(!p)throw Error('業種分類の親項目がありません。');parent=p.hierarchy?.parentId;
  }
  if(!belongs)throw Error('Total nonfarm に属さない業種が含まれています。');
 }
 const children=new Map();
 for(const s of d.series){const p=s.hierarchy?.parentId;if(p!=null){if(!children.has(p))children.set(p,[]);children.get(p).push(s)}}
 function covered(s){if(selected.has(s.id))return;const cs=children.get(s.id)||[];if(!cs.length)throw Error(`${s.name} を含む主要業種の分類を確認してください。`);cs.forEach(covered)}
 covered(total);
 const monthly=industries.map(s=>valuesFor(d,s.source,'SA','change'));
 const ma3=industries.map(s=>valuesFor(d,s.source,'SA','delta_avg3'));
 const totalValues=valuesFor(d,total,'SA','change'),totalMA3=valuesFor(d,total,'SA','delta_avg3');
 const rows=d.dates.map((date,i)=>{
  const m=monthly.map(v=>v[i]),a=ma3.map(v=>v[i]);
  const complete=m.every(Number.isFinite),completeMA3=a.every(Number.isFinite);
  return {date,monthly:m,ma3:a,total:totalValues[i],totalMA3:totalMA3[i],complete,completeMA3,
   residual:complete&&Number.isFinite(totalValues[i])?totalValues[i]-m.reduce((x,y)=>x+y,0):null,
   residualMA3:completeMA3&&Number.isFinite(totalMA3[i])?totalMA3[i]-a.reduce((x,y)=>x+y,0):null};
 });
 return {industries:industries.map(({source,...s})=>s),rows,latest:d.latest};
}

export function stackContributions(row,mode,hidden=new Set()){
 if(!(mode==='ma3'?row.completeMA3:row.complete))return null;
 let positive=0,negative=0;const segments=[];
 (mode==='ma3'?row.ma3:row.monthly).forEach((value,index)=>{
  if(hidden.has(index))return;
  const start=value>=0?positive:negative,end=start+value;
  if(value>=0)positive=end;else negative=end;
  segments.push({index,value,start,end});
 });
 return {segments,positive,negative};
}
