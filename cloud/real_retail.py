"""Monthly SA real retail estimates. Offline derivation; two price inputs use one CSV.
No interpolation, no backfilling a broken chain, no mixing NSA with SA.
"""
from decimal import Decimal, localcontext
import csv, io, json
import expansion as e
D=Decimal
PREFIX='realretail:'
TOTAL='retail:total:SA'; RT='retail:retail:SA'; FS='retail:722:SA'
GOODS='realretailinput:CUSR0000SAC'; DINING='realretailinput:CUSR0000SEFV'
CORE='priceview:cpi:19:SA:level'
PCEG='bea:price:DGDSRG'; PCEF='bea:U20404-M:DFSERG'
URL='https://fred.stlouisfed.org/graph/fredgraph.csv?id=CUSR0000SAC,CUSR0000SEFV'
ENGLISH={'REAL_RETAIL_2CPI':'Real Retail — Goods + Dining CPI','REAL_RETAIL_DETAIL':'Real Retail — Category CPI','REAL_RETAIL_BEA':'Real Retail — PCE Price Estimate (Legacy BEA Unconnected)','REAL_CONTROL_CORE':'Real Control — Core Goods CPI'}
NAMES={'REAL_RETAIL_2CPI':'実質小売全体｜財CPI＋外食CPI','REAL_RETAIL_DETAIL':'実質小売全体｜業種別CPI','REAL_RETAIL_BEA':'実質小売全体｜PCE価格調整（旧BEA未接続・試算）','REAL_CONTROL_CORE':'実質Control Group｜コア財CPI'}
# Each 3-digit industry appears exactly once. Broad proxies are explicit, never hidden.
MAPPING=[
 ('441','自動車・部品','priceview:cpi_detail:184:SA:level','CUSR0000SATCLTB','輸送用財（燃料除く）','新車・中古車・部品を含む家計支出構成。店舗の販売構成とは異なる。',False),
 ('442','家具・インテリア','priceview:cpi_detail:136:SA:level','CUSR0000SAH31','家具・家庭用品','家庭用品も含む広めの代理指数。',True),
 ('443','家電・電子機器',CORE,'CUSR0000SACL1E','コア財','家電と電子機器を合わせたSA指数がないため広い財指数で代用。',True),
 ('444','建材・園芸',GOODS,'CUSR0000SAC','財全体','住宅修繕資材・業務用需要との品目対応が不完全。',True),
 ('445','食品・飲料店','priceview:cpi:2:SA:level','CUSR0000SAF11','家庭内食品','酒類や非食品の販売を含む店舗売上とは一致しない。',False),
 ('446','健康・パーソナルケア',CORE,'CUSR0000SACL1E','コア財','医薬品と日用品を合わせた店舗構成を再現できず広い財指数で代用。',True),
 ('447','ガソリンスタンド','priceview:cpi:14:SA:level','CUSR0000SETB01','ガソリン','店舗の非燃料品販売は分離できない。',False),
 ('448','衣料品','priceview:cpi:20:SA:level','CUSR0000SAA','衣料','店舗内の非衣料品と支出構成の違いが残る。',False),
 ('451','スポーツ・趣味・書籍','priceview:cpi_detail:199:SA:level','CUSR0000SARC','娯楽財','娯楽財の家計支出構成を代理使用。',True),
 ('452','総合小売',GOODS,'CUSR0000SAC','財全体','多品目業態。店舗の商品ライン構成を使っていない。',True),
 ('453','その他小売',GOODS,'CUSR0000SAC','財全体','多品目業態。店舗の商品ライン構成を使っていない。',True),
 ('454','無店舗小売',GOODS,'CUSR0000SAC','財全体','ネット通販等の品目構成・価格を直接測定した指数ではない。',True),
 ('722','飲食店・バー',DINING,'CUSR0000SEFV','外食','チップ等の調査対象・ウェイトの違いが残る。',False)]
NOTES={
 'REAL_RETAIL_2CPI':'野村近似。野村の正式な計算式は未確認。財小売と飲食サービスをそれぞれ前月価格に換算して集計。',
 'REAL_RETAIL_DETAIL':'13業種と集計残差を前月価格に換算する月次近似。BLS公式産出量ではありません。商品ライン別年次推計の完全再現ではありません。',
 'REAL_RETAIL_BEA':'旧BEA Table 5U・6U・7Uは2024-07-25に公表終了。公式月次アーカイブの旧小売表を取得できていないため、全期間が独立したPCE価格調整の試算。旧BEA公式値・接続・延長を再現した系列ではありません。',
 'REAL_CONTROL_CORE':'Control＝総合−自動車・部品−ガソリン−建材・園芸−飲食。食品店を含むControlを食品除外のコア財CPIで調整するため、完全な品目対応ではありません。'}

def shift(date,n):
 y,m=map(int,date[:7].split('-'));k=y*12+m-1+n;return f'{k//12:04d}-{k%12+1:02d}-01'
def raw(x):return format(x,'f') if x is not None else None

def ingest_prices(blob):
 rows=list(csv.DictReader(io.StringIO(blob.decode('utf-8-sig'))));out=[]
 if not rows or not {'observation_date','CUSR0000SAC','CUSR0000SEFV'}<=rows[0].keys():raise ValueError('CPI CSVの列が不正')
 for code,label in [('CUSR0000SAC','財CPI（全財・SA）'),('CUSR0000SEFV','外食CPI（SA）')]:
  obs=[e.obs(r['observation_date'],r[code],'published') for r in rows if r['observation_date']>='1992-01-01']
  if any(o['value'] is not None and o['value']<=0 for o in obs):raise ValueError('非正の価格指数')
  out.append(e.save(dict(id='realretailinput:'+code,label=label,officialId=code,provider='BLS（FRED経由）',source='https://fred.stlouisfed.org/series/'+code,download=URL,originalSource='https://www.bls.gov/cpi/',page='retail',category='実質小売 / 計算用価格指数',unit='指数（1982–84=100）',frequency='Monthly',seasonal='SA',definition='BLS CPI-Uの季節調整済み月次指数。FRED配布CSVの全履歴を取得し、最新改定値を保存。欠損は補完しない。',observations=obs)))
 return out

def update_prices():return ingest_prices(e.get(URL))

def quantity(previous,current,relatives):
 """Laspeyres quantity link and additive percentage-point contributions."""
 if any(v<=0 for v in relatives) or sum(previous)<=0:raise ValueError('Invalid prices or previous total')
 total=sum(previous);parts=[(n/p-b)/total*100 for b,n,p in zip(previous,current,relatives)]
 return sum(parts),parts

def enrich(records,levels=None):
 """Calendar-based rates. Missing intermediate links invalidate chained horizons.
 Direct single-deflator levels can compare observed endpoints without interpolation.
 """
 by={o['date']:o for o in records};growth={d:D(o['raw']) for d,o in by.items() if o['raw'] is not None}
 def link(d,n):
  if levels is not None:
   a,b=levels.get(d),levels.get(shift(d,-n));return (a/b-1)*100 if a is not None and b is not None and b>0 else None
  seq=[growth.get(shift(d,-i)) for i in range(n)]
  if any(x is None for x in seq):return None
  v=D(1)
  for x in seq:v*=1+x/100
  return (v-1)*100
 for o in records:
  d=o['date'];m=[growth.get(shift(d,-i)) for i in range(3)];g3=link(d,3)
  for k,v in [('mom',growth.get(d)),('yoy',link(d,12)),('growth3',g3),('avg3',sum(m)/3 if all(v is not None for v in m) else None),('annual3',((1+g3/100)**4-1)*100 if g3 is not None else None)]:o[k+'Raw']=raw(v)
  o['metricMissingReason']='必要な月の入力または連鎖倍率が欠損。補間していません。'
 for base,field in [('2019-12-01','index2019Raw'),('2025-11-01','indexRaw')]:
  values={}
  if levels is not None and levels.get(base):values={d:v/levels[base]*100 for d,v in levels.items()}
  elif base in by:
   # The reference is an index normalization, not a fabricated monthly growth rate.
   values[base]=D(100)
   d=shift(base,1)
   while d in growth:values[d]=values[shift(d,-1)]*(1+growth[d]/100);d=shift(d,1)
   d=base
   while d in growth:
    prev=shift(d,-1);values[prev]=values[d]/(1+growth[d]/100);d=prev
  for o in records:o[field]=raw(values.get(o['date']))
 return records

def compute(entries):
 metas={s['id']:s for s in entries};cache={};loaded={};maps={}
 def get(sid):
  if sid not in loaded:
   if sid not in metas:raise ValueError('計算用系列が未収録: '+sid)
   if metas[sid].get('seasonal')!='SA' or metas[sid].get('frequency')!='Monthly':raise ValueError('SA月次以外の入力メタデータ: '+sid)
   s=e.load_series(sid,{'series':entries})
   if s.get('seasonal')!='SA' or s.get('frequency')!='Monthly':raise ValueError('SA月次以外の入力: '+sid)
   loaded[sid]=s;maps[sid]={o['date']:D(str(o.get('raw') if o.get('raw') is not None else o['value'])) for o in s['observations'] if o.get('value') is not None}
  return maps[sid]
 all_dates=sorted(get(TOTAL));dates=[]
 d=max('1992-01-01',all_dates[0])
 while d<=all_dates[-1]:dates.append(d);d=shift(d,1)
 configs={
 'REAL_RETAIL_2CPI':[(RT,GOODS),(FS,DINING)],
 'REAL_RETAIL_DETAIL':[('retail:'+x[0]+':SA',x[2]) for x in MAPPING],
 'REAL_RETAIL_BEA':[(RT,PCEG),(FS,PCEF)],
 'REAL_CONTROL_CORE':[('macrocalc:retail_control:SA',CORE)]}
 results=[];diagnostics={'months':len(dates),'headlineMaxDifference':'0','categoryMaxResidual':'0','controlMaxDifference':'0'}
 for sid in {x for pairs in configs.values() for pair in pairs for x in pair}|{TOTAL,RT,FS,*['retail:'+c+':SA' for c in ['441','447','444']]}:get(sid)
 for sid in {p for pairs in configs.values() for _,p in pairs}:
  if any(v<=0 for v in get(sid).values()):raise ValueError('非正の物価指数: '+sid)
 # These identities must hold before any estimate is saved.
 for d in dates:
  if all(d in get(s) for s in [TOTAL,RT,FS]):
   gap=abs(get(TOTAL)[d]-get(RT)[d]-get(FS)[d]);diagnostics['headlineMaxDifference']=raw(max(D(diagnostics['headlineMaxDifference']),gap))
   if gap>2:raise ValueError('総合と小売＋飲食が不整合: '+d)
  ids=[TOTAL,'retail:441:SA','retail:447:SA','retail:444:SA',FS,'macrocalc:retail_control:SA']
  if all(d in get(s) for s in ids):
   gap=abs(get(TOTAL)[d]-sum(get(s)[d] for s in ids[1:5])-get(ids[-1])[d]);diagnostics['controlMaxDifference']=raw(max(D(diagnostics['controlMaxDifference']),gap))
   if gap>D('.000001'):raise ValueError('Controlの除外式が不一致: '+d)
 with localcontext() as ctx:
  ctx.prec=50
  for method,pairs in configs.items():
   inputs=list(dict.fromkeys([TOTAL]+[s for pair in pairs for s in pair]+([GOODS] if method=='REAL_RETAIL_DETAIL' else [])))
   rows=[];levels={} if method=='REAL_CONTROL_CORE' else None
   if levels is not None:
    n,p=pairs[0];levels={d:v/(get(p)[d]/100) for d,v in get(n).items() if d in get(p)}
   for d in dates:
    prev=shift(d,-1);missing=[f'{sid} @ {month}' for sid in inputs for month in [prev,d] if month not in get(sid)]
    if missing:rows.append(e.obs(d,None,'unavailable',missingReason='必要な入力が未収録・未公表',missingInputs=missing));continue
    before=[get(n)[prev] for n,p in pairs];current=[get(n)[d] for n,p in pairs];rel=[get(p)[d]/get(p)[prev] for n,p in pairs];parts=None
    if method=='REAL_RETAIL_DETAIL':
     residual=[get(TOTAL)[month]-sum(get(n)[month] for n,p in pairs) for month in [prev,d]]
     diagnostics['categoryMaxResidual']=raw(max(D(diagnostics['categoryMaxResidual']),*[abs(v) for v in residual]))
     # Up to 13 categories + total each rounded to $1m. Larger residual is a coverage failure.
     if any(abs(v)>14 for v in residual):raise ValueError('13業種と総合の集計差が丸め範囲外: '+d+' '+str(residual))
     before.append(residual[0]);current.append(residual[1]);rel.append(get(GOODS)[d]/get(GOODS)[prev])
    if method=='REAL_RETAIL_BEA':
     price=sum(b*r for b,r in zip(before,rel))/sum(before);growth=(sum(current)/sum(before)/price-1)*100
    else:growth,parts=quantity(before,current,rel)
    extra=dict(inputPreviousTotalRaw=raw(sum(before)),inputCurrentTotalRaw=raw(sum(current)),priceRelativesRaw=[raw(r) for r in rel],inputPreviousRaw=[raw(v) for v in before],inputCurrentRaw=[raw(v) for v in current])
    if method=='REAL_RETAIL_DETAIL':
     pa=sum(current)/sum(b*r for b,r in zip(before,rel));extra.update(contributionsRaw=[raw(v) for v in parts],residualRaw=raw(residual[1]),proxyShareRaw=raw(sum(b for b,m in zip(before,MAPPING) if m[6])/sum(before)*100),fisherMomRaw=raw(((1+growth/100)*pa).sqrt()*100-100))
    if levels is not None:extra['realLevelRaw']=raw(levels[d])
    rows.append(e.obs(d,growth,'estimate',**extra))
   enrich(rows,levels)
   provenance=[dict(id=sid,label=metas[sid]['label'],provider=metas[sid].get('provider'),source=metas[sid].get('source'),officialId=metas[sid].get('officialId'),retrievedAt=metas[sid].get('sourceCheckedAt') or metas[sid].get('retrievedAt'),releaseDate=metas[sid].get('sourceReleaseDate') or metas[sid].get('releaseDate'),latest=metas[sid].get('latest',{}).get('date'),sourceVintage=metas[sid].get('latest',{}).get('sourceVintage')) for sid in inputs]
   results.append(dict(id=PREFIX+method,methodId=method,label=NAMES[method],englishName=ENGLISH[method],provider='本サイト計算（Census・BLS・BEA）',page='retail',category='実質小売 / 4方式比較',publication={'id':'real-retail','label':'実質小売売上高・4方式比較（独自試算）'},frequency='Monthly',seasonal='SA',unit='%',valueType='growth',source='https://www.census.gov/retail/marts/www/timeseries.html',definition=NOTES[method]+' 保存値は実質前月比（%）。前年比・3か月比は月次連鎖倍率から計算（Controlは単一物価による実質水準の比）。欠損は補完しない。',inputs=inputs,inputProvenance=provenance,estimateType='independent_estimate',legacyStatus='unavailable_unconnected' if method=='REAL_RETAIL_BEA' else None,indexBase='2025-11=100',alternativeIndexBase='2019-12=100',mapping=[dict(code=x[0],label=x[1],priceId=x[2],officialId=x[3],priceLabel=x[4],limitation=x[5],proxy=x[6]) for x in MAPPING] if method=='REAL_RETAIL_DETAIL' else [],diagnostics=diagnostics,observations=rows))
 return results

def derive(entries):return [e.save(s) for s in compute(entries)]
