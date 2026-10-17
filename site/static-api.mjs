// Static-data adapter. No provider requests, credentials or server writes.
const base = new URL('./', import.meta.url);
const memory = new Map();
const favoritesKey = 'economic-note-pages-favorites:' + base.pathname;
let releasePromise;
export async function decodeJSON(response) {
  if (!response.ok) throw Error(`公開データを読み込めません (${response.status})。ページを再読込してください。`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes[0] !== 0x1f || bytes[1] !== 0x8b) return JSON.parse(new TextDecoder().decode(bytes));
  if (typeof DecompressionStream === 'undefined') throw Error('このブラウザは圧縮データに対応していません。Safari 16.4以降など、新しいブラウザで開いてください。');
  return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).json();
}
async function release() {
  if (!releasePromise) releasePromise = fetch(new URL('release.json', base), {cache:'no-store'}).then(decodeJSON).catch(e=>{releasePromise=null;throw e});
  return releasePromise;
}
async function file(path) {
  if (typeof path !== 'string' || !/^data\/[a-f0-9]{64}\.json\.gz$/.test(path)) throw Error('公開データの参照が不正です。');
  if (!memory.has(path)) {
    memory.set(path, fetch(new URL(path, base)).then(decodeJSON).catch(e=>{memory.delete(path);throw e}));
    // Bound the browser cache on phones; the HTTP cache still avoids downloads.
    if (memory.size > 160) memory.delete(memory.keys().next().value);
  }
  return memory.get(path);
}
async function series(id, r) {
  const index = await file(r.seriesIndex);
  if (!Object.hasOwn(index,id)) throw Error('系列が見つかりません。');
  return file(index[id]);
}
function favorites() {
  try {const f=JSON.parse(localStorage.getItem(favoritesKey)||'{"items":[]}');return Array.isArray(f.items)?f:{items:[]}}
  catch {throw Error('このブラウザのお気に入りを読み込めません。ブラウザの保存設定を確認してください。')}
}
function saveFavorite(payload) {
  const f=favorites(),name=typeof payload.name==='string'?payload.name.trim():'',c=payload.config;
  if (!name || name.length>100 || !c || !Array.isArray(c.series) || c.series.length<1 || c.series.length>8) throw Error('名前と分析条件を確認してください。');
  if (payload.id && !f.items.some(i=>i.id===payload.id)) throw Error('上書きする条件がありません。');
  if (!payload.id && f.items.length>=100) throw Error('保存上限は100件です。');
  const row={id:payload.id||crypto.randomUUID(),name,config:c,updatedAt:new Date().toISOString()};
  try {localStorage.setItem(favoritesKey,JSON.stringify({items:[...f.items.filter(i=>i.id!==row.id),row]}))}
  catch {throw Error('ブラウザに保存できません。空き容量・プライベートブラウズ設定を確認してください。')}
  return row;
}
export function calendarAt(calendar, now=new Date()) {
  return {...calendar,now:now.toISOString(),running:false,events:calendar.events.map(e=>({...e,reflection:new Date(e.scheduledAt)>now?{code:'upcoming',label:'発表予定',details:e.reflection.details}:e.afterDue||e.reflection}))};
}
export async function request(url,options={}) {
  const u=new URL(url,'https://static.invalid'),path=u.pathname,method=options.method||'GET';
  if (path==='/api/analysis/favorites') return method==='POST'?saveFavorite(JSON.parse(options.body)):favorites();
  if (method!=='GET') {
    if (path==='/api/update'||path==='/api/calendar/update') {location.reload();return {message:'公開データを再読込しています。'}}
    throw Error('公開版ではこの操作を実行できません。');
  }
  const r=await release();
  if (path==='/api/status') return {app:'economic-note-pages',token:'',auto:false,running:false,lastOfficial:r.builtAt,lastResult:r.revision,reportId:r.revision,fingerprint:(await file(r.manifest)).fingerprint,failed:false,message:r.cloudUpdate ? `毎朝4時（日本時間）に自動更新。前回：${r.cloudUpdate.changedSeries}拡張系列の値が変更、${r.cloudUpdate.failedSources}件の取得処理が未完了。詳細は「自動更新の結果」。` : '公開用データを表示しています。公式データの更新は公開者が行い、再公開後に反映されます。'};
  const plain={'/api/manifest':'manifest','/api/explorer':'catalog','/api/analysis/catalog':'analysisCatalog','/api/update-report':'updateReport'};
  if (plain[path]) return file(r[plain[path]]);
  if (path==='/api/calendar') return calendarAt(await file(r.calendar));
  if (path.startsWith('/api/dataset/')) {
    const id=decodeURIComponent(path.slice('/api/dataset/'.length));
    if (!Object.hasOwn(r.datasets,id)) throw Error('データ表が見つかりません。');
    return file(r.datasets[id]);
  }
  if (path==='/api/explorer/series') return series(u.searchParams.get('id'),r);
  if (path==='/api/explorer/series-batch') {
    const ids=u.searchParams.getAll('id');
    if (!ids.length||ids.length>32) throw Error('系列の指定が不正です。');
    return {series:await Promise.all(ids.map(id=>series(id,r)))};
  }
  if (path==='/api/analysis/series') {
    const id=u.searchParams.get('id')||'';
    if (id.startsWith('ex:')) return {...await series(id.slice(3),r),id};
    const meta=(await file(r.analysisCatalog)).series.find(s=>s.id===id);
    if (!meta?.descriptor) throw Error('分析系列が見つかりません。');
    const [dataset,sid,season,metric]=meta.descriptor,d=await file(r.datasets[dataset]),s=d.series.find(s=>s.id===sid);
    const values=d.kind==='base'?s.bases[season]:s.values[metric];
    return {...meta,observations:d.dates.map((date,i)=>({date:date+'-01',value:values[i]??null,raw:values[i]==null?null:String(values[i]),status:'saved_workbook',releaseDate:null}))};
  }
  throw Error('公開版で対応していない読み込みです。');
}
