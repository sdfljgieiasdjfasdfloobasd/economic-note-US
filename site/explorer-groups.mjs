export const belongsToPage=(s,page)=>s.page===page||(s.pages||[]).includes(page);
// Publication families: institutions with multiple surveys remain separate tables.
export function statisticalGroup(s){
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
export function tableGroups(catalog,page){const groups=new Map();for(const s of catalog.series.filter(s=>belongsToPage(s,page))){for(const g of (s.id?.startsWith('retail:')?[statisticalGroup(s)]:(s.publications||[statisticalGroup(s)]))){if(!groups.has(g.id))groups.set(g.id,{...g,series:[]});groups.get(g.id).series.push(s)}}return [...groups.values()].sort((a,b)=>a.label.localeCompare(b.label,'ja'))}
