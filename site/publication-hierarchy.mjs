import {complementHierarchy} from './complement-hierarchy-data.mjs?v=fb50a9456b1253befcc1';
import {retailHierarchy,joltsHierarchy,cesHierarchy} from './publication-hierarchy-data.mjs?v=fb50a9456b1253befcc1';
// Ancestry is explicit metadata, never a count of digits or a guess from words.
export function hierarchyMetadata(s){
 const id=s.sourceId||s.id?.replace(/^ex:/,'')||'',h=s.hierarchy;
 let path=Array.isArray(h)?h:h?.path,section=h?.section||s.hierarchySection||'',order=s.sourceOrder??s.sourceRow;
 let label=s.matchLabel||s.label,kind=path?'source-path':'flat';
 if(id.startsWith('gdp:')&&!path&&s.depth>0){const parts=s.label.split(' / ');if(parts.length===s.depth+1){path=parts.slice(0,-1);label=parts.at(-1);kind='bea-source-path'}}
 if(id.startsWith('retail:')){const meta=retailHierarchy[s.officialId];if(meta){path=meta.path;section=meta.section;label=meta.label;kind='census-classification'}else{path=[];section='分類未確認';kind='unverified'}}
 if(s.category==='求人・採用（JOLTS）'&&s.industryCode){const meta=joltsHierarchy[s.industryCode];if(meta){path=meta.path;order=meta.order;label=s.industryName;section=({JO:'求人数',HI:'採用数',TS:'総離職数',QU:'自発的離職数',LD:'解雇・レイオフ',OS:'その他離職数'}[s.measure]||s.measure)+' / '+s.unit;kind='bls-industry'}}
 if(id.startsWith('local:CES_')){const parts=id.split(':'),meta=cesHierarchy[parts[1].replace(/_(SA|NSA)$/,'')+':'+parts.slice(2).join(':')];if(meta){path=meta.path;order=meta.order;section=meta.section;kind='ces-workbook'}}
 if(id.startsWith('adp:')){const [,freq,dimension,name]=id.split(':');path=[];section=(freq==='M'?'月次':'週次')+' / '+({'National':'全国合計','Industry':'業種別（全国合計の内訳）','Establishment Size':'事業所規模別（全国合計の別内訳）','Census Divisions':'地域別（全国合計の別内訳）'}[dimension]||dimension);label=name;order=dimension==='Establishment Size'?parseInt(name):order;kind='source-dimensions'}
 if(id.startsWith('complement:')){
  const family=id.split(':')[1],parts=s.label.split(' / '),meta=family==='c30'?complementHierarchy.c30[id]:complementHierarchy[family]?.[s.sourceCategory];
  if(meta&&(family!=='c30'||meta.expectedMeasure===s.sourceMeasure)){
   path=meta.path;label=meta.label;order=meta.order;
   section=family==='c30'?meta.section:[parts.slice(1).join(' / '),meta.section].filter(Boolean).join(' / ');
   kind='census-official-classification';
  }
 }
 if(id.startsWith('housing:')){const parts=s.label.split(' / ');if(parts.length>=3){label=parts.at(-1);if(!id.includes('_quarterly_cust:')){section=parts[0]+' / '+parts[1];path=label==='Total'?[]:['Total'];order=label==='Total'?-1:order}else{section=parts[0]+' / '+s.sourceTable+' / '+s.unit;path=parts.slice(1,-1)}kind='census-housing-dimensions'}}
 return {...s,hierarchy:[...(path||[])],depth:(path||[]).length,hierarchySection:section,hierarchyKind:kind,sourceOrder:order,matchLabel:label};
}
// Lay out each parent before its descendants. Missing parent rows become labelled
// headings, not fictional numeric series. Preserve all rows, values and IDs.
export function layoutPublicationSeries(series){
 const decorated=series.map((s,i)=>({...hierarchyMetadata(s),_position:i}));
 const sections=new Map();
 for(const s of decorated){const key=s.hierarchySection||'';if(!sections.has(key))sections.set(key,[]);sections.get(key).push(s)}
 const output=[];
 const entries=[...sections].sort(([a],[b])=>Number(a.startsWith('別集計'))-Number(b.startsWith('別集計')));
 for(const [section,ss] of entries){
  ss.sort((a,b)=>(a.sourceOrder??a._position)-(b.sourceOrder??b._position));
  const root={children:new Map(),rows:[]};
  for(const s of ss){let node=root;for(const label of [...s.hierarchy,s.matchLabel||s.label]){if(!node.children.has(label))node.children.set(label,{label,children:new Map(),rows:[]});node=node.children.get(label)}node.rows.push(s)}
  let pending=section?[{label:section,depth:0,section:true}]:[];
  function walk(node,depth){
   if(!node.rows.length)pending.push({label:node.label,depth,section:false});
   for(const row of node.rows){const {_position,...s}=row;output.push({...s,displayHeaders:pending});pending=[]}
   for(const child of node.children.values())walk(child,depth+1);
  }
  for(const child of root.children.values())walk(child,0);
 }
 return output;
}
