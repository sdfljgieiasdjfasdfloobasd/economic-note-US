import {setRevisionReport} from './revision-view.mjs?v=60b366f3c0ba61ddde70';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kinds={added:'追加',revised:'改定',removed:'欠損・削除',status:'公表状態の変更'};
const fmt=v=>v==null?'—':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:3,maximumFractionDigits:3});
const when=s=>new Date(s).toLocaleString('ja-JP');
const counts=s=>Object.entries(kinds).filter(([k])=>s.counts[k]).map(([k,v])=>`${v} ${s.counts[k]}件`).join(' / ');
export function observationTable(s){return `${s.comparable===false?'<p class="source-note">定義・単位が変更されたため、差分比較の対象外です。</p>':''}<div class="update-report-scroll"><table><thead><tr><th>対象年月・日</th><th>変更</th><th>更新前</th><th>更新後</th><th>改定幅</th></tr></thead><tbody>${s.details.map(d=>`<tr><td>${esc(d.date)}</td><td>${d.kind==='added'?({new_period:'新しい対象期',backfill:'過去データ追加',initial:'初回収録'}[d.additionType]||'追加（分類記録なし）'):kinds[d.kind]}</td><td title="元の値: ${esc(d.before)}">${fmt(d.before)}${d.kind==='status'?` <small>${esc(d.beforeStatus)}</small>`:''}</td><td title="元の値: ${esc(d.after)}">${fmt(d.after)}${d.kind==='status'?` <small>${esc(d.afterStatus)}</small>`:''}</td><td>${fmt(s.comparable!==false&&d.before!=null&&d.after!=null?d.after-d.before:null)} ${esc(s.unit==='%'?'ポイント':s.unit)}</td></tr>`).join('')}</tbody></table></div>`}
export function reportHTML(r){
 if(r?.mode==='snapshot')return '<p>公開者が保存したデータのスナップショットです。元のサイトの更新ログは掲載していません。公開範囲・出典はページ上部のリンクから確認できます。</p>';
 if(!r)return '<p class="source-note">次回の更新から、追加・改定された系列と対象月、更新前後の値をここに表示します。</p>';
 const groups=new Map();r.changed.forEach((s,i)=>{if(!groups.has(s.group))groups.set(s.group,[]);groups.get(s.group).push([s,i])});
 return `<p class="source-note">${r.mode==='maintenance'?'ISM履歴追加・公式取得経路の検証':r.mode==='local'?'保存Excelの変更を反映':'公式データの更新'} · ${esc(when(r.startedAt))} → ${esc(when(r.finishedAt))}</p>
 <div class="update-report-totals"><span><b>${r.counts.changed}</b> 系列が更新</span>${r.format===2?['new_period','backfill','initial'].map((k,i)=>`<span>${['新しい対象期','過去データ追加','初回収録'][i]} ${r.changed.filter(s=>s.details.some(d=>d.additionType===k)).length}系列</span>`).join(''):`<span>追加 ${r.counts.added}系列</span>`}<span>改定 ${r.counts.revised}系列</span><span>保存値変更なし ${r.counts.unchanged}系列</span><span class="${r.failures.length?'update-report-failed':''}">取得・処理失敗 ${r.failures.length}件</span></div>
 <label>変更の種類 <select class="revision-report-filter"><option value="all">すべて</option><option value="new_period">新しい対象期</option><option value="revised">過去値の改定</option><option value="backfill">過去データ追加</option><option value="initial">初回収録</option><option value="removed">欠損・削除</option><option value="status">公表状態の変更</option></select></label><p class="source-note">追加は、取得済みの末尾より新しい対象期／過去の欠損を埋めた追加／系列の初回収録に分けます。新しい対象期でも公表日は未確認のため、今回初めて公表されたとは断定しません。改定幅は更新後−更新前。取得失敗は下の別欄です。</p>
 ${r.changed.length?'':'<p>保存データの追加・改定はありませんでした。</p>'}
 ${[...groups].map(([name,ss])=>`<details class="update-report-group"><summary><strong>${esc(name)}</strong><span>${ss.length}系列が更新</span></summary><div>${ss.map(([s,i])=>`<details class="update-report-series" data-report-series="${i}"><summary><span>${esc(s.label)} <small>${esc(s.measure)}${s.unit?' / '+esc(s.unit):''}</small></span><span>${counts(s)}<small>${esc(s.details.at(-1).date)}${s.details.length>1?' 〜 '+esc(s.details[0].date):''}</small></span></summary><div class="update-report-values"></div></details>`).join('')}</div></details>`).join('')}
 ${r.failures.length?`<details class="update-report-errors"><summary>取得・処理に失敗したデータ（${r.failures.length}件）</summary><p class="source-note">取得できなかった系列は、保存済みの値がある場合にその値を表示しています。</p><ul>${r.failures.map(s=>`<li><strong>${esc(s.group)} / ${esc(s.label)} ${esc(s.measure)}</strong><small>${esc(s.error)}</small></li>`).join('')}</ul></details>`:''}
 <details class="update-report-unchanged"><summary>保存値に変更がなかったデータ（${r.counts.unchanged}系列）</summary><ul>${r.unchanged.map(s=>`<li>${esc(s.group)}：${s.count}系列</li>`).join('')}</ul></details>
 <p class="source-note">「保存値変更なし」には、取得失敗や手動更新対象のため以前の値を保持した系列も含みます。公式確認の成功を意味しません。SA・NSAと公表表の各指標は別系列として数え、拡張ページの参照用の重複系列は除外しています。前年比など画面上の計算値は元データで判定します。追加と改定の件数は重複する場合があります。</p>`;
}
export function setupUpdateReport({request}){
 const panel=document.querySelector('#update-report-panel'),body=document.querySelector('#update-report-body'),summary=document.querySelector('#update-report-summary');
 let report=null,loaded=false,seen=null,loading=false,wasRunning=false;
 body.addEventListener('change',e=>{if(!e.target.matches?.('.revision-report-filter'))return;const kind=e.target.value;body.querySelectorAll('[data-report-series]').forEach(node=>{const s=report.changed[Number(node.dataset.reportSeries)],details=s.details.filter(d=>kind==='all'||d.kind===kind||d.additionType===kind);node.hidden=!details.length;node.querySelector('.update-report-values').innerHTML=observationTable({...s,details})});body.querySelectorAll('.update-report-group').forEach(g=>g.hidden=![...g.querySelectorAll('[data-report-series]')].some(n=>!n.hidden))});
 body.addEventListener('toggle',e=>{const d=e.target;if(!d.open||!d.hasAttribute('data-report-series'))return;const target=d.querySelector('.update-report-values');if(!target.innerHTML)target.innerHTML=observationTable(report.changed[Number(d.dataset.reportSeries)])},true);
 return {async sync(status){
  const completed=wasRunning&&!status.running;wasRunning=status.running;
  summary.textContent=status.running?'更新中 — 完了後に更新内容を表示します':report?.mode==='snapshot'?'公開データについて':report?`今回の更新内容 · ${report.counts.changed}系列が更新${report.failures.length?' / 失敗 '+report.failures.length+'件':''}`:'今回の更新内容';
  if(loading||status.running||(loaded&&seen===status.reportId))return false;
  loading=true;
  try{
   const next=await request('/api/update-report');const changed=loaded&&next?.id!==report?.id;
   report=next;setRevisionReport(report);seen=status.reportId;loaded=true;body.innerHTML=reportHTML(report);
   summary.textContent=report?.mode==='snapshot'?'公開データについて':report?`今回の更新内容 · ${report.counts.changed}系列が更新${report.failures.length?' / 失敗 '+report.failures.length+'件':''}`:'今回の更新内容';
   if(changed||completed)panel.open=true;
   return !!changed||completed;
  }catch{body.textContent='更新内容を読み込めませんでした。次の状態確認で再試行します。';return false}
  finally{loading=false}
 }};
}
