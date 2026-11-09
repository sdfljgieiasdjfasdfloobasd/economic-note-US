
export const productivityIndicators=[
 ['fred:ULCNFB','単位労働コスト（ULC）'],
 ['fred:OPHNFB','労働生産性'],
 ['fred:OUTNFB','実質産出量'],
 ['fred:HOANBS','総労働時間'],
 ['fred:COMPNFB','時間当たり報酬'],
 ['fred:COMPRNFB','実質時間当たり報酬']
];
// Additional entry point only: existing page memberships and series IDs are unchanged.
export function employmentOtherKind(s){
 const id=s.id||'';
 if(productivityIndicators.some(([key])=>key===id))return 'productivity';
 if(/^ism:(Manufacturing|Services):Employment$/.test(id))return 'ism';
 if(id.startsWith('nfib:'))return 'nfib';
 if(id.startsWith('challenger:'))return 'challenger';
 if(id.startsWith('wgt:'))return 'wgt';
 if(/^sceall:(Job separation expectation|Job finding expectations|Unemployment Expectations|Earnings growth|Earnings uncertainty)( Demo)?:/.test(id))return 'sce';
 if(id.startsWith('indeed:'))return 'indeed';
 return null;
}
export const employmentOtherGroups=[
 {id:'productivity',label:'BLS 生産性・費用統計',note:'非農業企業部門・四半期・季節調整済み。指標ボタンでグラフと表を切替。公表値は2017年＝100の指数です。前期比年率・前年同期比も選べます。総労働時間は働いた時間の合計で、週平均労働時間とは異なります。',series:['fred:ULCNFB']},
 {id:'ism',label:'ISM雇用指数',note:'製造業・サービス業の雇用DI。50が前月からの増減の境目です。',series:['ism:Manufacturing:Employment','ism:Services:Employment']},
 {id:'nfib',label:'NFIB中小企業雇用調査',note:'未充足求人・採用計画・報酬引上げ実績・計画。保存済みの短い履歴を表示します。',series:['nfib:openings','nfib:plans','nfib:compensation','nfib:compensation_plans']},
 {id:'challenger',label:'Challenger解雇計画',note:'企業が発表した人員削減計画。実際の解雇人数ではありません。保存済みの総数のみです。',series:['challenger:cuts']},
 {id:'wgt',label:'Atlanta Fed 賃金上昇率',note:'Wage Growth Tracker：同一労働者の前年比賃金上昇率。グラフは全体・継続勤務者・転職者の3か月平均。表には12か月平均も収録。',series:['wgt:data_overall:1','wgt:data_overall:8','wgt:data_overall:9']},
 {id:'sce',label:'NY連銀SCE 労働見通し',note:'月次SCEの失職・自発的離職・再就職・失業率・賃金の見通しと属性別集計。4か月ごとの専用労働市場調査は未収録です。',series:['sceall:Job separation expectation:1','sceall:Job separation expectation:2','sceall:Job finding expectations:1']},
 {id:'indeed',label:'Indeed求人指数',note:'全国の総求人・新規求人。2020年2月1日＝100、7日移動平均の日次指数（公表更新は週次）。人数ではありません。グラフはSA、表はSA／NSAを切替。',series:['indeed:total:SA','indeed:new:SA']}
];
// PCE's price page excludes real spending, income and saving tables.
export const isPcePricePublication=g=>g.id==='price-table:pce'||/Table (?:2\.3\.4U|2\.4\.4U?|2\.8\.[478])(?:\.|\s|$)/.test(g.label||g.id||'');
export const isRetailSeries=s=>/^(?:realretail:|realretailinput:|retail:|carts:|fred:RRSFS$|macrocalc:(?:retail_|gasoline_share:))/.test(s.id||'');
export const employmentSection=(s,page)=>page==='adp'?/^(?:adp:|adppay:|adppulse:|macrocalc:adp_)/.test(s.id||''):page==='claims'?/^(?:claims:|derived:claims_|fred:(?:ICSA|ICNSA|IC4WSA|CCSA|CCNSA|CC4WSA|IURSA|IURNSA)$)/.test(s.id||''):page==='jolts'?s.category==='求人・採用（JOLTS）':false;
import {isHousehold} from './household-ui.mjs?v=8b372337c3317d9d82ae';
export const belongsToPage=(s,page)=>page==='labor-other'?!!employmentOtherKind(s):page==='household'?isHousehold(s):['adp','claims','jolts'].includes(page)?employmentSection(s,page):page==='retail'?isRetailSeries(s):page==='consumption'&&isRetailSeries(s)?false:(s.page===page||(s.pages||[]).includes(page))&&(page!=='pce'||(s.publications||[statisticalGroup(s)]).some(isPcePricePublication));
// Publication families: institutions with multiple surveys remain separate tables.
export function statisticalGroup(s){
 if(/^macrocalc:(?:retail_control:|retail_breadth:|gasoline_share:)/.test(s.id||''))return {id:'macrocalc:小売 / 派生指標',label:'小売 / コントロールグループ・増加業種の割合・ガソリン売上構成比'};
 if(s.id?.startsWith('retail:'))return {id:'retail',label:'米国国勢調査局 / 小売売上高（MRTS・MARTS 全収録項目）'};
 if(s.publicationId)return {id:s.publicationId,label:s.publicationLabel||s.category};
 const id=s.id||'',p=id.split(':')[0];
 const known={bie:['bie','Atlanta連銀 / Business Inflation Expectations（BIE）'],wgt:['wgt','Atlanta連銀 / Wage Growth Tracker（賃金）'],michigan:['michigan','Michigan / 消費者のインフレ期待'],nyfed:['nyfed','NY連銀 / Survey of Consumer Expectations'],cleveland:['cleveland','Cleveland連銀 / 期待インフレモデル'],spf:['spf','Philadelphia連銀 / Survey of Professional Forecasters'],cie:['cie','FRB / Common Inflation Expectations'],adp:['adp','ADP / National Employment Report'],adppay:['adppay','ADP / Pay Insights'],adppulse:['adppulse','ADP / NER Pulse'],chicago:['chicago','Chicago連銀 / Labor Market Indicators'],claims:['claims','DOL / 州別失業保険'],conference:['conference','Conference Board / 消費者信頼感・雇用判断'],nfib:['nfib','NFIB / 小規模企業調査'],challenger:['challenger','Challenger / 人員削減計画'],revisions:['revisions','BLS / 雇用統計の改定履歴'],benchmark:['benchmark','BLS / 雇用ベンチマーク'],diffusion:['diffusion','BLS / 雇用増減の広がり']};
 if(known[p])return {id:known[p][0],label:known[p][1]};
 if(p==='ism'||id.startsWith('derived:ism_')){const sector=id.includes('Manufacturing')?'Manufacturing':'Services';return {id:'ism:'+sector,label:'ISM / '+(sector==='Manufacturing'?'製造業 PMI':'サービス業 PMI')}}
 if(p==='sp'){const sector=id.split(':')[1];return {id:'sp:'+sector,label:'S&P Global / US '+sector+' PMI'}}
 if(p==='local'){const sheet=id.split(':')[1].replace(/_(?:SA|NSA)$/,'');return {id:'bls:'+sheet,label:'BLS / '+({CES_Employment:'CES 雇用者数',CES_Hourly_Earnings:'CES 平均時給',CES_Weekly_Hours:'CES 週平均労働時間',CES_Weekly_Earnings:'CES 週平均賃金',CES_Overtime:'CES 残業時間',CPS_Main:'CPS 労働力・就業・失業',CPS_U1_U6:'CPS 失業率 U1〜U6'}[sheet]||sheet)}}
 if(s.category==='求人・採用（JOLTS）')return {id:'jolts',label:'BLS / JOLTS 求人・採用・離職'};
 if(s.category==='州別・失業保険')return {id:'claims',label:'DOL / 州別失業保険'};
 if(p==='fred'){
  const name={'市場':'市場 / インフレ補償（FRED）','総合・先行指標':'Kansas City連銀 / Labor Market Conditions','高頻度・失業保険':'DOL / 全国失業保険','生産性・単位労働コスト':'BLS / 労働生産性・単位労働コスト','雇用コスト（ECI）':'BLS / Employment Cost Index','労働移行・レイオフ':'FRB / Ellieroth–Michaud 労働移行'}[s.category];
  if(name)return {id:'fred:'+s.category,label:name};
 }
 return {id:(s.provider||p)+':'+s.category,label:(s.provider||'収録範囲の注記')+' / '+s.category};
}
export function tableGroups(catalog,page){
 if(page==='labor-other')return employmentOtherGroups.map(g=>({id:'labor-other:'+g.id,label:g.label,series:catalog.series.filter(s=>employmentOtherKind(s)===g.id)})).filter(g=>g.series.length);
 const groups=new Map();
 for(const s of catalog.series.filter(s=>belongsToPage(s,page))){
  const memberships=s.id?.startsWith('retail:')?[statisticalGroup(s)]:(s.publications||[statisticalGroup(s)]);
  for(const g of new Map(memberships.map(g=>[g.id,g])).values()){
   if(page==='pce'&&!isPcePricePublication(g))continue;
   if(!groups.has(g.id))groups.set(g.id,{...g,series:[]});
   const view=s.publicationViews?.[g.id],views=Array.isArray(view)?view:[view];
   for(const v of views)groups.get(g.id).series.push(v?{...s,tableView:v,sourceOrder:v.sourceOrder}:{...s,sourceOrder:s.sourceOrder??s.sourceRow});
  }
 }
 for(const g of (catalog.publicationCoverage||[]).filter(g=>g.page===page))if(!groups.has(g.id))groups.set(g.id,{...g,series:[]});
 for(const g of groups.values())if(g.series.some(s=>s.sourceOrder!=null))g.series.sort((a,b)=>(a.sourceOrder??1e9)-(b.sourceOrder??1e9));
 return [...groups.values()].sort((a,b)=>a.label.localeCompare(b.label,'ja',{numeric:true}));
}
