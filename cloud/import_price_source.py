"""BLS MXP import indexes: eight bulk files, no per-series API requests.
Only monthly observations; missing/suppressed months and annual averages are not imputed.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv, io, json, re, time, hashlib
import expansion as e
BASE='https://download.bls.gov/pub/time.series/ei/'
GROUPS={
 'IR':('ei.data.01.BEAImport','用途別（BEA End Use）・詳細品目',1),
 'IZ':('ei.data.03.NAICSImport','産業別（NAICS）・詳細業種',3),
 'IP':('ei.data.05.HarmonizedImport','品目別（HS）・詳細品目',5),
 'CO':('ei.data.07.LocalityofOrigin','原産国・地域別／産業別',7),
 'IV':('ei.data.10.ServicesImport','サービス輸入（航空貨物・旅客運賃）',10),
 'IC':('ei.data.12.ServicesInbound','米国向け航空貨物（Inbound・輸入サービスとは別定義）',10),
}
FILES=['ei.series','ei.footnote',*[g[0] for g in GROUPS.values()]]
NOTE='BLS MXPの公表指数。季節調整前（NSA）。品目ごとに指数の基準時点が異なるため水準の大小を価格の高低として比較しない。前月比・前年比は公表指数水準から計算（丸め済み公表伸び率と差が出る場合あり）。初期の履歴は四半期等の疎な観測で、未観測月を補間しない。年平均M13は月次表に混在させない。2025年10月は調査データを必要とする一部系列がBLSにより非公表。公表値がある系列は保持。'

def tsv(blob):
 text=blob.decode('utf-8-sig')
 if '<html' in text[:500].lower() or 'Access Denied' in text[:500]:raise ValueError('BLS bulk response is not data')
 reader=csv.DictReader(io.StringIO(text),delimiter='\t')
 return [{k.strip():v.strip() for k,v in row.items() if k is not None} for row in reader]

def parse(blobs):
 meta=tsv(blobs['ei.series'])
 if not meta or not {'series_id','index_code','series_name','base_period','seasonal'}<=meta[0].keys():raise ValueError('BLS系列定義の構成変更')
 selected={m['series_id']:m for m in meta if m['index_code'] in GROUPS}
 if len(selected)<500 or len(selected)!=sum(m['index_code'] in GROUPS for m in meta):raise ValueError('輸入系列の不足・重複')
 foot={r['footnote_code']:r['footnote_text'] for r in tsv(blobs['ei.footnote'])}
 observations={sid:[] for sid in selected}
 for group,(filename,_,_) in GROUPS.items():
  for row in tsv(blobs[filename]):
   sid=row['series_id']
   if sid not in selected:continue # Series absent from the current official dictionary are not silently invented.
   if selected[sid]['index_code']!=group:raise ValueError('分類と一括ファイルが不一致: '+sid)
   period=row['period']
   if period=='M13':continue
   if not re.fullmatch(r'M(?:0[1-9]|1[0-2])',period):raise ValueError('月次以外の期間: '+period)
   raw=e.dec(row['value'])
   if raw is None and row['value'] not in ('','-','–','—','(D)','(S)'):raise ValueError('不明な数値: '+row['value'])
   observations[sid].append(e.obs(row['year']+'-'+period[1:]+'-01',raw,'revised' if 'R' in row['footnote_codes'] else 'published',footnoteCodes=row['footnote_codes'],sourceValue=row['value']))
 out=[]
 for order,(sid,m) in enumerate(selected.items()):
  if m['seasonal']!='U':raise ValueError('想定外の季節調整: '+sid)
  rows=sorted(observations[sid],key=lambda r:r['date'])
  if not rows or not any(r['value'] is not None for r in rows):raise ValueError('公式定義にある系列の履歴が不足: '+sid)
  if len(rows)!=len({r['date'] for r in rows}):raise ValueError('重複した観測: '+sid)
  # Stale/truncated files must not replace the existing data.
  end=m['end_year']+'-'+m['end_period'][1:]+'-01'
  if rows[-1]['date']!=end:raise ValueError('公式定義と最終観測月が不一致: '+sid)
  group=m['index_code'];filename,title,table=GROUPS[group];pub='mxp:'+group
  label={'EIUIR':'総合（All commodities）','EIUIREXFUELS':'燃料を除く輸入（All imports excluding fuels）','EIUIREXFDFLS':'食品・燃料を除く輸入（All imports excluding food and fuels）','EIUIREXPET':'石油を除く輸入（All imports excluding petroleum）'}.get(sid,m['series_name'])
  out.append(dict(id='mxp:'+sid,officialId=sid,label=label,matchLabel=label,page='import-prices',category=title,
    provider='Bureau of Labor Statistics',source=BASE+filename,sourceTable=f'MXP Table {table} / database {group}',
    publicationId=pub,publicationLabel='BLS / 輸入物価指数 · '+title,publications=[dict(id=pub,label='BLS / 輸入物価指数 · '+title)],
    unit='指数',basePeriod=m['base_period'],frequency='Monthly',seasonal='NSA',measure='価格指数',definition=NOTE+' 基準：'+m['base_period']+'。'+('Inboundは運送事業者の居住地を問わない米国向け輸送で、輸入サービスIVと合算しない。' if group=='IC' else ''),
    sourceOrder=order,indexCode=group,sourceName=m['series_name'],sourceTitle=m['series_title'],seriesFootnotes=[foot.get(x,x) for x in m['footnote_codes'].split(',') if x],
    hierarchy=[],observations=rows))
 return out

def decorate(items):
 """Use reviewed official table paths first, classification-code descendants second.
 Special aggregates never become children just because their names sound related.
 """
 mapping=json.loads(Path(__file__).with_name('import-price-hierarchy.json').read_text())
 byid={s['officialId']:s for s in items}
 for s in items:
  sid=s['officialId'];group=s['indexCode'];code=sid[5:];path=[]
  if group=='IR':
   # Exclusion aggregates are interleaved in Table 1; indentation alone
   # would incorrectly put fuels below "excluding fuels".
   if code.isdigit():
    parents=sorted([p for p in byid if p.startswith('EIUIR') and p[5:].isdigit() and sid.startswith(p) and p!=sid],key=len)
    path=[byid['EIUIR']['label']]+[byid[p]['label'] for p in parents]
   elif code and code[0].isdigit():
    prefix=re.match(r'\d+',code)[0]
    parents=sorted([p for p in byid if p.startswith('EIUIR') and p[5:].isdigit() and prefix.startswith(p[5:])],key=len)
    path=[byid['EIUIR']['label']]+[byid[p]['label'] for p in parents]
  elif group=='IP' and code.isdigit():
   # HS section headers use Roman numerals, so prefix matching alone loses
   # chapters that have detailed indexes but no published chapter aggregate.
   sections=[(5,'I'),(14,'II'),(15,'III'),(24,'IV'),(27,'V'),(38,'VI'),(40,'VII'),(43,'VIII'),(46,'IX'),(49,'X'),(63,'XI'),(67,'XII'),(70,'XIII'),(71,'XIV'),(83,'XV'),(85,'XVI'),(89,'XVII'),(92,'XVIII'),(93,'XIX'),(96,'XX'),(97,'XXI')]
   section=next(n for limit,n in sections if int(code[:2])<=limit)
   section_label=byid.get('EIUIP'+section,{}).get('label','HS 第'+section+'部')
   parents=sorted([p for p in byid if p.startswith('EIUIP') and p[5:].isdigit() and sid.startswith(p) and p!=sid],key=len)
   path=[section_label]+[byid[p]['label'] for p in parents]
  elif sid in mapping:path=mapping[sid]['path']
  elif group in ('IR','IZ','IP') and code.isdigit():
   # BLS's BEA, NAICS and HS codes have nested numerical subcategories.
   parents=[p for p in byid if p.startswith(sid[:5]) and p[5:].isdigit() and sid.startswith(p) and p!=sid]
   parents.sort(key=len)
   if parents:
    first=parents[0];path=list(mapping.get(first,{}).get('path',[]))+[byid[p]['label'] for p in parents]
   elif group=='IR':path=[byid['EIUIR']['label']]
  elif group=='CO':
   # Origin names are explicit in BLS series_name; countries and regional groups are parallel.
   country=s['sourceName'].split('-',1)[0];path=[country]
   match=re.fullmatch(r'(EIUCO.+Z)(\d+)',sid)
   if match:
    parents=sorted([p for p in byid if p.startswith(match[1]) and p[len(match[1]):].isdigit() and sid.startswith(p) and p!=sid],key=len)
    path += [byid[p]['label'] for p in parents]
  elif group in ('IV','IC'):
   parents=sorted([p for p in byid if p.startswith(sid[:5]) and sid.startswith(p) and p!=sid],key=len)
   path=[byid[p]['label'] for p in parents]
  s['hierarchy']=path;s['depth']=len(path)
 return items

def update(offline=None):
 cache=e.CACHE/'import-prices';cache.mkdir(parents=True,exist_ok=True)
 state_path=cache/'fetch-state.json';state=json.loads(state_path.read_text()) if state_path.exists() else {}
 now=datetime.now(timezone.utc);cached=False
 if offline:
  blobs={name:(Path(offline)/name).read_bytes() for name in FILES}
 elif state.get('retryAfter') and now<datetime.fromisoformat(state['retryAfter']):
  raise ValueError('BLS一括取得の再試行は24時間後。保存済みの輸入物価を保持しています。')
 elif state.get('fetchedAt') and (now-datetime.fromisoformat(state['fetchedAt'])).total_seconds()<18*3600 and all((cache/name).exists() for name in FILES):
  blobs={name:(cache/name).read_bytes() for name in FILES};cached=True
 else:
  blobs={}
  try:
   for i,name in enumerate(FILES):
    if i:time.sleep(2)
    blobs[name]=e.get(BASE+name)
  except Exception as exc:
   e.write(state_path,dict(state,retryAfter=(now+timedelta(hours=24)).isoformat(),error=str(exc)))
   raise
 items=decorate(parse(blobs)) # Validate every group before saving any series.
 for name,blob in blobs.items():
  (cache/name).write_bytes(blob)
  digest=hashlib.sha256(blob).hexdigest();(e.RAW/digest).write_bytes(blob)
  e.write(e.RAW/(digest+'.json'),dict(url=BASE+name,sha256=digest,retrievedAt=now.isoformat()))
 e.write(state_path,dict(fetchedAt=state['fetchedAt'] if cached else now.isoformat(),files=len(blobs),series=len(items),apiCalls=0))
 return [e.save(s) for s in items]
