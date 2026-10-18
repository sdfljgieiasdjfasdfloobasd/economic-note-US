import {layoutPublicationSeries} from './publication-hierarchy.mjs?v=c833b310d3d3687ca566';
import {mountRevisionView,explorerRevisionInput,markRevisionCells} from './revision-view.mjs?v=c833b310d3d3687ca566';
import {seriesAttribution,seriesAttributions} from './expectation-presets.mjs?v=c833b310d3d3687ca566';
import {tableGroups,statisticalGroup} from './explorer-groups.mjs?v=c833b310d3d3687ca566';
import {transform,metrics,pageMetrics,metricApplicable,compatibleUnit,frequency,tableHeatRule,tableHeatLimit,tableHeatColor,manualHeatRule} from './explorer-math.mjs?v=c833b310d3d3687ca566';
export function publicationFilename(page,label,metric,dates,series=[]){
 const table=label.match(/Table (\d+(?:\.\d+)*U?)/)?.[1];
 const fs=[...new Set(series.map(s=>s.frequency).filter(Boolean))];
 const freq=fs.length===1?fs[0]:fs.length?'Mixed':label.includes('Quarterly')?'Quarterly':label.includes('Annual')?'Annual':'';
 // qoq is the shared internal previous-period transform; name exports by frequency.
 if(/^qoq(?:_|$)/.test(metric))metric=metric.replace(/^qoq/,({Monthly:'mom',Quarterly:'qoq',Weekly:'wow',Daily:'dod',Annual:'yoy'})[freq]||'previous_period_change');
 const name=table?['Table',table,freq].filter(Boolean).join('_'):label;
 return [page,name,metric,dates.at(-1),dates[0]].filter(Boolean).join('_').replace(/[\\/:*?"<>|\x00-\x1f]/g,'-').slice(0,180);
}
const cpiLinkedChoices=[['cpi_effect','総合への寄与（前月比・SA）'],['cpi_core','コアへの寄与（前月比・SA・計算値）'],['cpi_ri','相対的重要度（ウェイト）']];
const isCpiIndex=id=>['price-table:cpi','price-table:cpi_detail'].includes(id);
const linkedKind=metric=>cpiLinkedChoices.some(([id])=>id===metric)?metric.slice(4):null;
// Match exact, unique item labels. Never substitute a nearby aggregate or infer values.
export function cpiAnalysisMatches(catalog,items,kind){
 const byLabel=new Map();
 for(const s of catalog.series){if(s.alias?.dataset!=='cpi6'||s.alias.metric!==kind)continue;const key=s.matchLabel||s.label;if(!byLabel.has(key))byLabel.set(key,[]);byLabel.get(key).push(s)}
 return new Map(items.map(s=>{const key=s.matchLabel||s.label,matches=byLabel.get(key)||[];return [key,matches.length===1?matches[0]:null]}));
}
export function cpiAnalysisRows(items,analyses,matches,kind){
 const loaded=new Map(analyses.map(s=>[s.id,s])),unique=new Map();
 for(const s of items){const key=s.matchLabel||s.label;if(!unique.has(key))unique.set(key,s)}
 return [...unique].flatMap(([key,base])=>{
  const meta=matches.get(key),source=meta&&loaded.get(meta.id);
  if(kind==='core'&&meta?.coreApplicable===false)return [];
  const missing={id:'cpi-unmatched:'+base.id,observations:[],source:'',definition:'Table 6に一意に対応する品目がないため空欄です。',error:'Table 6の対応品目なし',unit:kind==='ri'?'%':'ポイント',frequency:'Monthly',status:'unavailable'};
  return [{...(source||missing),label:base.matchLabel||base.label,matchLabel:base.matchLabel||base.label,hierarchy:base.hierarchy,depth:base.depth,sourceOrder:base.sourceOrder,hierarchySection:base.hierarchySection,seasonal:kind==='ri'?'非該当':'SA',sourceMetric:kind==='ri'?'相対的重要度（RI）':kind==='core'?'コアへの寄与':'総合への寄与'}];
 });
}
export function setupPublicationTable({root,esc,fmt,csv,loadMany}){
 const panel=root.querySelector('.ex-table');
 panel.innerHTML=`<div class="panel-heading"><div><p class="eyebrow">ALL SERIES BY PUBLICATION</p><h2>公式表・統計ごとの全系列</h2></div><button id="ex-csv" class="text-button">表示中の表をCSV保存 ↓</button></div><p id="ex-export-status" class="source-note" role="status"></p><div class="ex-publication-controls"><label class="ex-publication-picker">表番号・表名<select id="ex-table-publication"></select></label><label>表示する値<select id="ex-table-metric"></select></label><label><span id="ex-table-season-label">季節調整</span><select id="ex-table-season"><option value="">すべて</option><option>SA</option><option>NSA</option><option>非該当</option><option>一部SAの合成</option></select></label><label>色分け<select id="ex-table-heat"><option value="auto">指標に合わせて自動</option><option value="manual">数値を指定</option><option value="off">なし</option></select></label><label>観測数<select id="ex-count"><option>24</option><option>60</option><option value="all">全期間</option></select></label><label>開始日<input id="ex-table-from" type="date"></label><label>終了日<input id="ex-table-to" type="date"></label></div><p class="source-note">グラフの比較系列とは独立して、選んだ統計の収録カタログ内の全系列を表示します。左が最新。数値は小数第3位、セルを選ぶと元の精度・出典を確認できます。未取得の値は補完しません。段差は分類上の親子関係です。内訳の合計が親の値と一致するとは限りません。</p><div id="ex-heat-manual" hidden></div><p id="ex-heat-error" class="source-note" role="alert"></p><p id="ex-table-source-note" class="source-note"></p><p id="ex-table-attributions" class="source-note"></p><p id="ex-table-summary" class="source-note" role="status"></p><p id="ex-table-heat-note" class="source-note"></p><div class="heat-scroll"><table id="ex-table"></table></div><div id="ex-detail" class="ex-detail" role="status">セルを選択すると、観測の詳細をここに表示します。</div>`;
 const manualSettings=new Map();
 const $=s=>panel.querySelector(s);let groups=[],selected=[],catalog,page,series=[],rows=[],dates=[],exportRows=[],seq=0,rendered=false,loading=false,loadedGroupKey='',pendingGroupKey='',exportSnapshot=null;let analysisSeries=[],analysisMatches=new Map(),loadedAnalysisMetric='';
 $('#ex-table-metric').innerHTML=metrics.map(([id,label])=>`<option value="${id}">${label}</option>`).join('');
 function seasonControl(publishedPpi,displayMetric,metricSeries=series){
  const control=$('#ex-table-season'),previous=control.value;
  const actual=[...new Set(metricSeries.map(s=>s.seasonal||'非該当'))];
  const order=['SA','NSA','非該当','一部SAの合成'];
  const choices=[...order.filter(v=>actual.includes(v)),...actual.filter(v=>!order.includes(v))];
  control.innerHTML=choices.map(v=>`<option value="${esc(v)}">${esc(v||'すべて')}</option>`).join('');
  control.value=choices.includes(previous)?previous:choices[0]||'';
  control.disabled=publishedPpi;
  if(publishedPpi)control.value=displayMetric==='published_yoy'?'NSA':'SA';
 }
 function options(){$('#ex-table-publication').innerHTML=groups.map(g=>`<option value="${esc(g.id)}">${esc(g.label)}（${g.id==='ppi:table1'?g.series.filter(s=>s.sourceMetric==='公表前月比').length+'品目・前月比／前年比':g.series.length?g.series.length+'系列':'未収録'}）</option>`).join('')+'<option value="__selected">グラフで比較中の系列</option>';}
 function group(){return $('#ex-table-publication').value==='__selected'?{label:'グラフで比較中の系列',series:selected.map(id=>catalog.series.find(s=>s.id===id)).filter(Boolean)}:groups.find(g=>g.id===$('#ex-table-publication').value)}
 function groupKey(){return JSON.stringify([page,$('#ex-table-publication').value,$('#ex-table-publication').value==='__selected'?selected:[]])}
 function clearExport(){$('#ex-table-attributions').textContent='';exportRows=[];exportSnapshot=null;rendered=false;$('#ex-csv').disabled=true;$('#ex-export-status').textContent=''}
 async function refresh(reset=true){const token=++seq,g=group(),key=groupKey();pendingGroupKey=key;loadedGroupKey='';loading=true;series=[];rows=[];clearExport();$('#ex-detail').textContent='セルを選択すると、観測の詳細をここに表示します。';if(!g){loading=false;pendingGroupKey='';return}
  $('#ex-table-source-note').innerHTML=g.note?esc(g.note)+(g.source?` <a href="${esc(g.source)}" target="_blank" rel="noopener noreferrer">公式の表 ↗</a>`:''):'';
  $('#ex-table-summary').textContent=g.label+' の全 '+g.series.length+' 系列を読み込み中…';$('#ex-table').innerHTML='';$('#ex-table-heat-note').textContent='';
  try{const kind=isCpiIndex(g.id)?linkedKind($('#ex-table-metric').value):null,matches=kind?cpiAnalysisMatches(catalog,g.series,kind):new Map(),extra=[...new Set([...matches.values()].filter(Boolean).map(s=>s.id))];
   const values=await loadMany([...g.series.map(s=>s.id),...extra]);if(token!==seq)return;series=values.slice(0,g.series.length).map((s,i)=>({...s,...(g.series[i]?.tableView||{})}));analysisSeries=values.slice(g.series.length);analysisMatches=matches;loadedAnalysisMetric=kind||'';loading=false;loadedGroupKey=key;pendingGroupKey='';
   if(reset){const ds=series.flatMap(s=>s.observations.filter(o=>o.value!=null).map(o=>o.date)).sort();$('#ex-table-from').value=ds[0]||'';$('#ex-table-to').value=ds.at(-1)||''}
   draw();
  }catch(e){if(token!==seq)return;loading=false;pendingGroupKey='';series=[];rows=[];clearExport();$('#ex-table-summary').textContent='統計表を読み込めませんでした。'+e.message}
 }
 function draw(){if(loading)return;clearExport();if(loadedGroupKey!==groupKey())return;const g=group();if(!g)return;if(!series.length){$('#ex-table-summary').textContent=g.label+' · 未収録';$('#ex-table').innerHTML='';$('#ex-table-heat-note').textContent='';$('#ex-heat-manual').hidden=true;$('#ex-heat-error').textContent='';return}const cpi6=g.id==='price-table:cpi6',publishedPpi=g.id==='ppi:table1',publishedExtra=['ppi:table2','cpi:table4','cpi:table5','cpi:table7'].includes(g.id);
  const sourceChoices=[['published_mom','公表前月比'],['published_yoy','公表前年比'],['published_two','公表2か月前比'],['published_effect','前年比寄与度'],['published_ri','相対的重要度'],['published_se','標準誤差']];
  const previousMetric=$('#ex-table-metric').value,choices=cpi6?[['cpi_analysis','寄与度・ウェイト'],['cpi_mom','SA（前月比）']]:publishedPpi?[['published_mom','公表前月比（SA・%）'],['published_yoy','公表前年比（NSA・%）']]:publishedExtra?sourceChoices.filter(([,label])=>series.some(s=>s.sourceMetric===label)):[...pageMetrics(page,series,true),...(isCpiIndex(g.id)?cpiLinkedChoices:[])];
  $('#ex-table-metric').innerHTML=choices.map(([id,label])=>`<option value="${id}">${label}</option>`).join('');$('#ex-table-metric').value=choices.some(([id])=>id===previousMetric)?previousMetric:choices[0][0];
  const displayMetric=$('#ex-table-metric').value,analysisKind=isCpiIndex(g.id)?linkedKind(displayMetric):null,m=cpi6||publishedPpi||publishedExtra||analysisKind?'level':displayMetric;
  let valueLabel=choices.find(([id])=>id===displayMetric)?.[1]||m,exportMetric=displayMetric,displayedSeries,season;
  $('#ex-table-season-label').textContent=cpi6?'内訳':'季節調整';
  if(cpi6){
   const control=$('#ex-table-season'),previous=control.value;
   const items=displayMetric==='cpi_mom'?[['mom','季節調整済み（SA）','前月比（SA）']]:[['effect','総合への寄与','総合への寄与'],['core','コアへの寄与（計算値）','コアへの寄与'],['ri','相対的重要度（ウェイト）','相対的重要度（RI）']];
   control.innerHTML=items.map(([id,label])=>`<option value="${id}">${label}</option>`).join('');control.value=items.some(([id])=>id===previous)?previous:items[0][0];control.disabled=items.length===1;
   const [kind,label,source]=items.find(([id])=>id===control.value);season=kind==='ri'?'非該当':'SA';
   // Legacy catalog classifies effect/core as non-applicable; these Table 6
   // observations describe seasonally adjusted monthly changes. Correct the view
   // metadata without transforming or rounding any observations.
   displayedSeries=series.filter(s=>s.sourceMetric===source&&(kind!=='core'||s.coreApplicable!==false)).map(s=>({...s,seasonal:season}));
   valueLabel=kind==='mom'?'公表前月比（SA・%）':label+(kind==='ri'?'（%）':'（前月比・SA・ポイント）');exportMetric=(kind==='core'?'calculated_':'published_')+kind;
   $('#ex-table-source-note').textContent=kind==='ri'?'相対的重要度は各品目のウェイト（%）です。寄与度とは異なります。小数第3位まで表示します。':kind==='mom'?'各品目そのものの季節調整済み前月比です。BLSの公表精度は小数第1位で、寄与度とは異なります。':label+'：季節調整済みの前月比を何ポイント押し上げ・押し下げたかを示します。小数第3位まで表示します。'+(kind==='core'?' 総合への寄与 ÷（コアの相対的重要度 / 100）で換算した計算値で、BLSの直接公表値ではありません。食品・エネルギーなど計算対象外の品目は非表示です。対象品目でも元の寄与度・ウェイトがない月は空欄のまま表示します。':'');
  }else if(analysisKind){
   season=analysisKind==='ri'?'非該当':'SA';
   $('#ex-table-season').innerHTML=`<option value="${season}">${analysisKind==='ri'?'非該当（ウェイト）':'SA（前月比への寄与）'}</option>`;$('#ex-table-season').value=season;$('#ex-table-season').disabled=true;
   displayedSeries=cpiAnalysisRows(series,analysisSeries,analysisMatches,analysisKind);
   valueLabel=choices.find(([id])=>id===displayMetric)[1]+(analysisKind==='ri'?'（%）':'（ポイント）');
   exportMetric='table6_'+(analysisKind==='core'?'calculated_':'published_')+analysisKind;
   $('#ex-table-source-note').textContent='Table 1・Table 2の品目・階層に、Table 6の同名品目の値を対応づけています。'+(analysisKind==='ri'?'相対的重要度は総合CPIに占めるウェイト（%）です。寄与度ではありません。':'季節調整済み前月比への寄与（ポイント）です。指数から計算した前月比とは公表・改定時点が異なる場合があります。')+(analysisKind==='core'?' コアへの寄与は総合への寄与 ÷（コアの相対的重要度 / 100）の計算値です。食品・エネルギーなど計算対象外の品目は非表示です。':'')+' 対応する値がない月は空欄です。小数第3位まで表示し、CSVは元の精度を保持します。';
  }else{
   $('#ex-table-source-note').textContent=(g.note||'')+(page==='ppi'&&series.some(s=>s.historySource)?(['ppi:table1','ppi:table2'].includes(g.id)?' 過去の公表変化率は当時のBLS公表資料（FRASER保存版）から補完しています。全期間を最新改定値に統一した値ではありません。':' 過去の指数はFRED配布履歴をBLS公式表の重複月と照合し、未収録部分は同じコード・指数基準のBLS保存資料で補完しています。保存資料分は当時の公表値です。非公表の値は埋めません。'):'');
   const sourceMetric=sourceChoices.find(([id])=>id===displayMetric)?.[1];displayedSeries=publishedPpi||publishedExtra?series.filter(s=>s.sourceMetric===sourceMetric):series;seasonControl(publishedPpi,displayMetric,displayedSeries);season=$('#ex-table-season').value;
  }
  const from=$('#ex-table-from').value,to=$('#ex-table-to').value;
  if(from&&to&&from>to){$('#ex-table-summary').textContent='表の開始日と終了日を確認してください。';$('#ex-table').innerHTML='';$('#ex-csv').disabled=true;return}
  rows=layoutPublicationSeries(displayedSeries.filter(s=>!season||(s.seasonal||'非該当')===season)).map(s=>{const incompatible=!metricApplicable(s,m);return {s,unit:compatibleUnit(s,m),incompatible,heat:$('#ex-table-heat').value==='off'||incompatible?null:tableHeatRule(s,m),rs:(incompatible?[]:transform(s,m)).filter(o=>(!from||o.date>=from)&&(!to||o.date<=to))}});
  $('#ex-table-attributions').textContent=seriesAttributions(rows.map(r=>r.s)).join(' ／ ');
  const manual=$('#ex-table-heat').value==='manual', units=[...new Set(rows.filter(r=>!r.incompatible).map(r=>r.unit))];
  $('#ex-heat-manual').hidden=!manual;
  const configs=units.map(unit=>{const key=JSON.stringify([page,$('#ex-table-publication').value,m,unit]);if(!manualSettings.has(key))manualSettings.set(key,{lower:-5,center:0,upper:5,negative:'#ee8e99',positive:'#63b4d7'});return {key,unit,config:manualSettings.get(key)}});
  $('#ex-heat-manual').innerHTML=manual?'<p class="source-note">単位ごとに設定します。赤の上限濃度になる値 ＜ 白の基準値 ＜ 青の上限濃度になる値。間は徐々に色が濃くなり、範囲外は最大の濃さになります。水準・割合にも適用します。</p>'+configs.map(({key,unit,config:c},i)=>`<fieldset class="ex-publication-controls" data-heat-key="${esc(key)}"><legend>${esc(unit||'単位なし')}</legend>${[['lower','赤が最も濃い値'],['center','白の基準値'],['upper','青が最も濃い値']].map(([field,label])=>`<label>${label}<input aria-label="${esc(unit)} ${label}" type="number" step="any" data-heat-field="${field}" value="${esc(String(c[field]))}"></label>`).join('')}<label>基準より下の色<input type="color" data-heat-field="negative" value="${c.negative}"></label><label>基準より上の色<input type="color" data-heat-field="positive" value="${c.positive}"></label></fieldset>`).join(''):'';
  const invalid=manual?configs.filter(x=>!manualHeatRule(x.config)):[];
  $('#ex-heat-error').textContent=invalid.length?'数値を確認してください：下限 ＜ 基準 ＜ 上限の順で入力してください。不正な単位の行は色分けしません。':'';
  if(manual)for(const r of rows)r.heat=r.incompatible?null:manualHeatRule(configs.find(x=>x.unit===r.unit)?.config);
  const n=$('#ex-count').value;dates=[...new Set(rows.flatMap(r=>r.rs.map(o=>o.date)))].sort().reverse().slice(0,n==='all'?undefined:Number(n));
  const available=displayedSeries.filter(s=>s.observations.some(o=>o.value!=null)).length,publishedMissing=displayedSeries.filter(s=>s.status==='published_missing'&&!s.observations.some(o=>o.value!=null)).length;$('#ex-table-summary').textContent=`${g.label} · 全${displayedSeries.length}系列（データあり${available}・未収録${displayedSeries.length-available-publishedMissing}${publishedMissing?`・公式空欄${publishedMissing}`:''}）／表示${rows.length}系列・${dates.length}観測日。`;
  const heatGroups=new Map(),visibleDates=new Set(dates);
  for(const r of rows){if(!r.heat)continue;r.heatKey=JSON.stringify([r.unit,r.heat.center]);if(!heatGroups.has(r.heatKey))heatGroups.set(r.heatKey,[]);heatGroups.get(r.heatKey).push(...r.rs.filter(o=>visibleDates.has(o.date)&&Number.isFinite(o.value)).map(o=>o.value))}
  const limits=new Map([...heatGroups].map(([k,vs])=>[k,tableHeatLimit(vs,JSON.parse(k)[1])]));
  const rules=[...new Set(rows.filter(r=>r.heat).map(r=>r.heat.label))];
  $('#ex-table-heat-note').textContent=$('#ex-table-heat').value==='off'?'色分けはオフです。':rules.length?'色：基準より上は青、下は赤、基準と同じ値は白、欠損は灰色。対象：'+rules.join('／')+'。良し悪しの判定ではありません。濃さは表示期間・観測数内の同じ単位と基準で共通にし、基準からの差の絶対値の90パーセンタイルで最大になります。水準・割合など対象外の行は無着色。'+(rows.some(r=>r.heat?.center===50)?'PMIの納期は50超が遅延、在庫判断は50超が過剰を表す場合があります。':''):'この表示は水準・割合などのため、自動色分けの対象外です。';
  if(manual)$('#ex-table-heat-note').textContent='手動色分け：入力した基準・上下限・色を使用します。基準は白、欠損は灰色。期間を変えても基準は固定です。良し悪しの判定ではありません。';
  exportRows=[['統計','系列','季節調整','頻度','単位','表示する値',...dates]];
  $('#ex-table').className=page==='ppi'?'ppi-compact-table':'';
  const monthlyPpi=page==='ppi'&&rows.every(r=>r.s.frequency==='Monthly');
  let out='<thead><tr><th>品目 / 季節調整 / 単位</th>'+dates.map(d=>`<th title="${esc(d)}">${esc(monthlyPpi?d.slice(0,7):d)}</th>`).join('')+(!dates.length?'<th>収録状況</th>':'')+'</tr></thead><tbody>';
  rows.forEach((r,i)=>{for(const header of r.s.displayHeaders||[])out+=`<tr class="hierarchy-section"><th colspan="${dates.length+1}" style="padding-left:${8+header.depth*14}px">${esc(header.label)}${header.section?'':'（分類見出し）'}</th></tr>`;const byDate=new Map(r.rs.map(o=>[o.date,o])),vals=dates.map(d=>byDate.get(d));r.byDate=byDate;
   const missing=!r.s.observations.some(o=>o.value!=null),reason=r.incompatible?'この頻度・単位には選択した計算を適用できません（率・寄与度には変化率を重ねません）':missing?(r.s.error||r.s.definition||'数値未収録'):'';
   exportRows.push([g.label,r.s.label,r.s.seasonal,r.s.frequency,r.unit,valueLabel,...vals.map(o=>o?.raw??'')]);
   out+=`<tr><th title="${esc([r.s.hierarchy?.join(' › '),reason||r.s.definition].filter(Boolean).join(' / '))}" style="padding-left:${8+(r.s.depth||0)*14}px">${esc(publishedPpi?r.s.matchLabel||r.s.label:r.s.sourceMetric&&r.s.sourceMetric!=='価格指数'?r.s.label:r.s.matchLabel||r.s.label)}<small class="hierarchy-trail">${esc(r.s.seasonal||'—')} · ${esc(r.s.sourceMetric||'')} · ${esc(r.s.frequency||'—')} · ${esc(r.unit||'—')}${reason?' · '+esc(reason):''}${/^(derived|macrocalc):/.test(r.s.id)?' · 計算系列':''}</small></th>`+vals.map((o,j)=>{const background=tableHeatColor(o?.value,r.heat,limits.get(r.heatKey));return `<td class="${o?.value==null?'missing':''}" ${background?`style="background:${background}"`:''}><button class="ex-cell" data-table-cell="${i},${j}" title="${esc(r.s.label)} · ${dates[j]} · ${fmt(o?.value)} ${esc(r.unit)}${r.heat?' · '+esc(r.heat.label)+(manual?'':' · 色の最大差 '+fmt(limits.get(r.heatKey))):''}">${fmt(o?.value)}</button></td>`}).join('')+(!dates.length?`<td>${esc(reason||'選択期間の数値なし')}</td>`:'')+'</tr>';
  });$('#ex-table').innerHTML=out+'</tbody>';const revisionInputs=rows.map(r=>explorerRevisionInput(r.s,m));if(panel.append){mountRevisionView(panel,{inputs:revisionInputs,from:dates.at(-1)||from,to:dates[0]||to,csv});markRevisionCells([...$('#ex-table').querySelectorAll('[data-table-cell]')].map(b=>{const [i,j]=b.dataset.tableCell.split(',').map(Number);return {cell:b.parentElement,date:dates[j],input:revisionInputs[i]}}),$('#ex-detail'));}$('#ex-csv').disabled=!rows.length||!dates.length;rendered=true;exportSnapshot={key:loadedGroupKey,name:publicationFilename(page,g.label,[exportMetric,...[season]].filter(Boolean).join('_'),dates,rows.map(r=>r.s)),rows:rows.some(r=>seriesAttribution(r.s))?exportRows.map((r,i)=>[...r,i===0?'出典・利用条件':seriesAttribution(rows[i-1].s)]):exportRows};$('#ex-csv').title=g.label+' · '+valueLabel;
 }
 panel.addEventListener('click',e=>{const b=e.target.closest('[data-table-cell]');if(!b)return;const [i,j]=b.dataset.tableCell.split(',').map(Number),r=rows[i],o=r.byDate.get(dates[j]);$('#ex-detail').innerHTML=`<b>${esc(r.s.label)} · ${dates[j]}</b><br>表示値 ${fmt(o?.value)} ${esc(r.unit)} / 元の精度 ${esc(o?.raw??'欠損・未収録')}${o?.sourceRaw&&o.sourceRaw!==o.raw?'（ファイルの原数値 '+esc(o.sourceRaw)+'）':''}<br>観測の季節調整 ${esc(o?.seasonal||r.s.seasonal)} / 観測の状態 ${esc(o?.status||'未収録')} / 公表日 ${esc(o?.releaseDate||'配布ファイルに記載なし・未確認')} / 取得日時 ${esc(r.s.retrievedAt||'保存Excel参照')}<br>${esc(r.s.definition||'')}${r.s.historySource?'<br>'+esc(r.s.historySource):''}${o?.sourceReleaseMonth?' / 公表資料の対象月 '+esc(o.sourceReleaseMonth):''}${r.s.relativeImportance?' / ウェイト '+esc(r.s.relativeImportance.raw)+'%（'+esc(r.s.relativeImportance.reference)+'）':''}${r.s.error?'<br>'+esc(r.s.error):''}${r.s.source?`<br><a href="${esc(o?.source||r.s.source)}" target="_blank" rel="noopener noreferrer">系列の出典 ↗</a>`:''}`});
 panel.addEventListener('change',e=>{const field=e.target.dataset.heatField;if(!field)return;const key=e.target.closest('[data-heat-key]').dataset.heatKey;manualSettings.get(key)[field]=e.target.value;draw()});
 const switchPublication=()=>{if(pendingGroupKey===groupKey()||(!loading&&loadedGroupKey===groupKey()))return;$('#ex-table-season').value='';$('#ex-table-season').disabled=false;if(group()?.id==='price-table:cpi6')$('#ex-table-metric').value='cpi_analysis';return refresh(true)};
 $('#ex-table-publication').oninput=switchPublication;$('#ex-table-publication').onchange=switchPublication;
 $('#ex-table-metric').onchange=()=>isCpiIndex(group()?.id)&&(loading||(linkedKind($('#ex-table-metric').value)||'')!==loadedAnalysisMetric)?refresh(false):draw();
 for(const id of ['#ex-table-heat','#ex-table-season','#ex-count','#ex-table-from','#ex-table-to'])$(id).onchange=draw;
 $('#ex-csv').onclick=async()=>{
  // Reconcile native select/input values at save time, even before a change event.
  if(loading)return;
  if(loadedGroupKey!==groupKey())await refresh(true);else if(isCpiIndex(group()?.id)&&(linkedKind($('#ex-table-metric').value)||'')!==loadedAnalysisMetric)await refresh(false);else draw();
  if(loading||!exportSnapshot||exportSnapshot.key!==groupKey()||$('#ex-csv').disabled)return;
  const snapshot=exportSnapshot;
  csv(snapshot.name,snapshot.rows);
  $('#ex-export-status').textContent='保存を開始しました：'+snapshot.name+'.csv';
 };
 return {async show(c,p,ids){catalog=c;page=p;selected=ids;groups=tableGroups(c,p);const preferred=ids[0]?statisticalGroup(c.series.find(s=>s.id===ids[0])||{}).id:'';options();if(groups.some(g=>g.id===preferred))$('#ex-table-publication').value=preferred;$('#ex-table-season').value='';$('#ex-table-metric').value='level';$('#ex-count').value='24';await refresh(true)},selection(ids){selected=ids;if($('#ex-table-publication').value==='__selected')refresh(false)},async invalidate(c){const oldLatest=series.flatMap(s=>s.observations.filter(o=>o.value!=null).map(o=>o.date)).sort().at(-1),followLatest=$('#ex-table-to').value===oldLatest;const previous=$('#ex-table-publication').value;catalog=c;groups=tableGroups(c,page);options();if(previous==='__selected'||groups.some(g=>g.id===previous))$('#ex-table-publication').value=previous;const latest=group()?.series.map(s=>s.latest?.date).filter(Boolean).sort().at(-1);if(followLatest&&latest&&latest>oldLatest)$('#ex-table-to').value=latest;await refresh(false)},cancel(){seq++;loading=false;loadedGroupKey='';pendingGroupKey='';clearExport()},summary(){return rendered?{publication:group()?.label,series:rows.length,dates:dates.length}:null}};
}
