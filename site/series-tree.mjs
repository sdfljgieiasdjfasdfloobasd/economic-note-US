import {hierarchyMetadata} from './publication-hierarchy.mjs?v=85d107fdd139f49e4aa3';
import {statisticalGroup} from './explorer-groups.mjs?v=85d107fdd139f49e4aa3';
export const categoryNames={'import-prices':'物価',cpi:'物価',pce:'物価',ppi:'物価',employment:'労働市場',labor:'労働市場',expectations:'期待インフレ',sp:'企業活動・PMI',ism:'企業活動・PMI',gdp:'GDP・国内需要',retail:'小売売上高',consumption:'消費','pce-nonprice':'所得・消費・貯蓄',housing:'住宅建設',production:'鉱工業生産'};
export function workbookPath(d,s){
 const publication=d.title===d.label?d.title:`${d.title} / ${d.label}`;
 return [categoryNames[d.group]||d.group,publication,s.hierarchy?.section,...(s.hierarchy?.path||[]),s.label].filter(Boolean);
}
const analysisMetrics={yoy:'yoy',mom:'qoq',m3:'growth3',m6:'growth6',a3:'annual3',a6:'annual6',level:'level',change:'delta1',avg3:'ma3',avg6:'ma6',delta_avg3:'delta_ma3',delta_avg6:'delta_ma6',delta_avg12:'delta_ma12'};
const releaseSeason=metric=>metric==='mom'?'SA':['yoy','nsa_mom'].includes(metric)?'NSA':'非該当';
// Release tables already contain changes/contributions: use the published value,
// rather than applying a second percentage transformation during transfer.
export function workbookSelection(d,c){
 const base=d.kind==='base',season=base?c.season:releaseSeason(c.metric),metric=base?'level':c.metric;
 return {id:'wb:'+JSON.stringify([d.id,c.id,season,metric]),metric:base?analysisMetrics[c.metric]||'level':'level'};
}
export function workbookPickerItems(d){
 return d.series.flatMap(s=>{
  const variants=d.kind==='base'?Object.entries(s.bases||{}).map(([season,values])=>({season,values,metric:'level'})):(d.metrics||[]).map(m=>({season:releaseSeason(m.id),metric:m.id,values:s.values?.[m.id],label:m.label}));
  return variants.filter(v=>v.values?.some(x=>x!=null)).map(v=>{
   const config={id:s.id,season:v.season==='非該当'?'NSA':v.season,...(d.kind==='release'?{metric:v.metric}:{})};
   return {id:workbookSelection(d,{...config,metric:v.metric}).id,datasetId:d.id,config,label:s.label,path:workbookPath(d,s),detail:[v.season,v.label].filter(Boolean).join(' · '),search:s.name};
  });
 });
}
export function explorerPickerItem(s){
 s=hierarchyMetadata(s);
 const native={...s,id:s.sourceId||s.id.replace(/^ex:/,'')},publication=statisticalGroup(native).label;
 let path;
 if(s.pickerPath)path=s.pickerPath;
 else{
  const prefix=[categoryNames[s.page]||s.page||'その他'];
  if(s.page==='expectations'&&s.category&&s.category!==publication)prefix.push(s.category);
  prefix.push(publication||s.publication||'統計');
  let parents=Array.isArray(s.hierarchy)?s.hierarchy:s.hierarchy?.path||[];
  let label=s.matchLabel||s.label;
  // GDP's parser explicitly records indentation depth and joins ancestors with ' / '.
  if(native.id.startsWith('gdp:')&&s.depth>0){const parts=s.label.split(' / ');parents=parts.slice(0,-1);label=parts.at(-1)}
  if(native.id.startsWith('adp:')&&!s.hierarchySection){const p=native.id.split(':');prefix.push(p[1]==='M'?'月次':'週次',p[2]);}
  if(s.measure&&s.industryName&&!s.hierarchySection){prefix.push({JO:'求人数',HI:'採用数',QU:'自発的離職数',LD:'解雇数',TS:'総離職数',OS:'その他離職数'}[s.measure]||s.measure);label=s.industryName;}
  path=[...prefix,s.hierarchySection,...parents,label].filter(Boolean);
 }
 return {id:s.id,label:s.label,path,detail:[s.seasonal,s.frequency,s.unit,s.descriptor&&s.descriptor[3]!=='level'?s.label.split(' / ').at(-1):''].filter(Boolean).join(' · '),search:[s.officialId,s.code,s.id].filter(Boolean).join(' ')};
}
export function buildSeriesTree(items){
 const root={key:'[]',label:'',children:new Map(),items:[],ids:new Set()};
 for(const item of items){const path=(item.path||[item.group||'系列',item.label]).filter(Boolean);let node=root;node.ids.add(item.id);
  for(let i=0;i<path.length;i++){const label=path[i];if(!node.children.has(label))node.children.set(label,{label,key:JSON.stringify(path.slice(0,i+1)),children:new Map(),items:[],ids:new Set()});node=node.children.get(label);node.ids.add(item.id)}
  if(!node.items.some(s=>s.id===item.id))node.items.push(item);
 }
 return root;
}
