"""Public-only adapters copied from the local dashboard; maintained independently."""
import csv,io,json,zipfile,hashlib,time

from datetime import datetime

from decimal import Decimal

from urllib.request import Request,urlopen

from urllib.parse import urlencode,urljoin

from lxml import html,etree

import openpyxl

import expansion as e

def parse_claims(b):
 root=etree.fromstring(b,parser=etree.XMLParser(resolve_entities=False,no_network=True));groups={}
 for w in root.findall('week'):
  state=w.findtext('stateName')
  for field,datefield,unit in [('InitialClaims','weekEnded','人'),('ContinuedClaims','ReflectingWeekEnded','人'),('CoveredEmployment','ReflectingWeekEnded','人'),('InsuredUnemploymentRate','ReflectingWeekEnded','%')]:
   date=datetime.strptime(w.findtext(datefield),'%m/%d/%Y').strftime('%Y-%m-%d')
   groups.setdefault((state,field,unit),{})[date]=e.obs(date,w.findtext(field),status='published')
 return groups

def claims():
 url='https://oui.doleta.gov/unemploy/claims.asp';tree=html.fromstring(e.get(url));states=tree.xpath('//select[@id="states"]/option/@value');states=[s for s in states if len(s)==2]
 if len(states)<50:raise ValueError('州一覧の書式が変わりました')
 endpoint='https://oui.doleta.gov/unemploy/wkclaims/report.asp';params=[('level','state'),('strtdate','2006'),('enddate',str(datetime.now().year)),('filetype','xml')]+[('states[]',s) for s in states]
 body=urlencode(params).encode()
 for attempt in range(3):
  try:
   with urlopen(Request(endpoint,data=body,headers={'User-Agent':'Mozilla/5.0 (EconomicNote local research)'}),timeout=120) as r:b=r.read()
   if any(msg in b for msg in [b'Unable to connect!',b'SQLSTATE=',b'administrative user mode']):raise ValueError('DOL公式データベースが一時停止中です。保存値を保持します。')
   parsed=parse_claims(b)
   if len({state for state,field,unit in parsed})<50 or len(parsed)<200:raise ValueError('DOLの州別応答に必要な州・指標がそろっていません。保存値を保持します。')
   break
  except Exception:
   if attempt==2:raise
   time.sleep(2**attempt)
 digest=hashlib.sha256(b).hexdigest();(e.RAW/digest).write_bytes(b);e.write(e.RAW/(digest+'.json'),dict(url=endpoint,publicQuery=params,retrievedAt=e.now(),sha256=digest))
 out=[]
 for (state,field,unit),rows in parsed.items():
  out.append(e.save(dict(id=f'claims:{state}:{field}',label=state+' '+field,page='labor',category='州別・失業保険',provider='U.S. Department of Labor',source=url,frequency='Weekly',seasonal='NSA',unit=unit,definition='州別の公式週次値。InitialはweekEnded、Continued・IUR・Covered EmploymentはReflectingWeekEndedを観測日とします。国全体のSA値と区別。',observations=list(rows.values()))))
 return out

def derived(entries):
 catalog={'series':entries};by={s['id']:s for s in entries};out=[]
 def read(id):return {r['date'][:7]:r for r in e.load_series(id,catalog)['observations'] if r['raw'] is not None}
 unemployed=next((s['id'] for s in entries if s['id'].startswith('local:CPS_Main_SA:') and s['label'].lower()=='unemployed'),None)
 specs=[('hires_openings','採用数 ÷ 求人数','fred:JTSHIL','fred:JTSJOL','ratio','labor','求人・採用（JOLTS）')]
 if unemployed:specs.append(('openings_unemployed','求人件数 ÷ 失業者数','fred:JTSJOL',unemployed,'ratio','labor','求人・採用（JOLTS）'))
 for sector in ['Manufacturing','Services']:
  for right in (['Production','Inventories'] if sector=='Manufacturing' else ['Business Activity']):specs.append(('ism_'+sector+'_'+right,'ISM '+sector+' New Orders − '+right,'ism:'+sector+':New Orders','ism:'+sector+':'+right,'difference','ism',sector))
 for id,label,left,right,op,page,category in specs:
  if left not in by or right not in by or not by[left].get('count') or not by[right].get('count'):continue
  a,b=read(left),read(right);rs=[]
  for date in sorted(a.keys()&b.keys()):
   x,y=Decimal(a[date]['raw']),Decimal(b[date]['raw'])
   if op=='ratio' and not y:continue
   raw=x/y if op=='ratio' else x-y;rs.append(e.obs(date+'-01',str(raw),status='derived'))
  out.append(e.save(dict(id='derived:'+id,label=label,page=page,category=category,provider='公式系列から計算',source=by[left]['source'],frequency='Monthly',seasonal=by[left].get('seasonal'),unit='倍' if op=='ratio' else 'DIポイント',definition=f'{left} {"÷" if op=="ratio" else "−"} {right}。同じ観測月の公表値をDecimalで計算。欠損は補間しません。採用は月間フロー、求人は月末ストックです。',inputs=[left,right],observations=rs)))
 states=[x for x in entries if x['id'].startswith('claims:') and x['id'].endswith(':InitialClaims') and x.get('count')]
 if states:
  mappings=[{r['date']:r for r in e.load_series(x['id'],catalog)['observations'] if r['raw'] is not None} for x in states];dates=set.intersection(*(set(m) for m in mappings));rs=[e.obs(d,sum(Decimal(m[d]['raw']) for m in mappings),'derived',reportingRegions=len(states)) for d in sorted(dates)]
  out.append(e.save(dict(id='derived:claims_state_sum',label='州・地域別 Initial Claims の合計',page='labor',category='州別・失業保険',provider='DOL州別公式値から計算',source='https://oui.doleta.gov/unemploy/claims.asp',frequency='Weekly',seasonal='NSA',unit='人',definition=f'取得した{len(states)}州・地域の同じ対象週を合計。全地域の観測がある週のみ。全国公式値とは別系列で、完全一致を仮定しません。',observations=rs)))
  for state in states:
   root=state['id'].rsplit(':',1)[0];coveredid=root+':CoveredEmployment'
   if coveredid not in by:continue
   a={r['date']:r for r in e.load_series(state['id'],catalog)['observations'] if r['raw'] is not None};b={r['date']:r for r in e.load_series(coveredid,catalog)['observations'] if r['raw'] is not None}
   rs=[e.obs(d,Decimal(a[d]['raw'])/Decimal(b[d]['raw'])*100,'derived') for d in sorted(a.keys()&b.keys()) if Decimal(b[d]['raw'])>0]
   out.append(e.save(dict(id='derived:claims_ratio:'+root.split(':')[1],label=root.split(':')[1]+' Initial Claims / Covered Employment',page='labor',category='州別・失業保険',provider='DOL州別公式値から計算',source=state['source'],frequency='Weekly',seasonal='NSA',unit='%',definition='同じ対象週のInitial Claims÷Covered Employment×100。全国公式IURとは別指標。補完なし。',observations=rs)))
 wage='fred:A132RC1Q027SBEA';profit='fred:A463RC1Q027SBEA'
 if wage in by and profit in by:
  a,b=read(wage),read(profit);rs=[]
  for date in sorted(a.keys()&b.keys()):
   prior=str(int(date[:4])-1)+date[4:]
   if prior in a and prior in b and Decimal(a[prior]['raw']) and Decimal(b[prior]['raw']):
    value=((Decimal(a[date]['raw'])/Decimal(a[prior]['raw'])-1)-(Decimal(b[date]['raw'])/Decimal(b[prior]['raw'])-1))*100;rs.append(e.obs(date+'-01',value,'derived'))
  out.append(e.save(dict(id='derived:wage_profit_gap',label='民間賃金前年比 − 非金融企業利益前年比',page='labor',category='労働所得・企業利益',provider='BEA公式系列から計算',source=by[wage]['source'],frequency='Quarterly',seasonal='SA',unit='ポイント',definition='民間賃金と、IVA・CCAdj調整後の非金融企業利益の前年比差。両者は対象範囲が異なるため、利益率ではありません。同じ四半期で計算。',observations=rs)))

 return out

def revisions():
 import re,calendar
 snap=json.loads((e.HERE/'research/revision-snapshot.json').read_text());url=snap['source'];rows=snap['rows'];err=None
 try:
  tree=html.fromstring(e.get(url));parsed={}
  for tr in tree.xpath('//tr'):
   cells=[' '.join(c.text_content().split()) for c in tr.xpath('./th|./td')]
   mon=cells[0].replace('.','')[:3] if cells else ''
   if len(cells)<14 or mon not in calendar.month_abbr or not cells[1].isdigit():continue
   year=int(cells[1]);month=list(calendar.month_abbr).index(mon);date=f'{year:04}-{month:02}-01';parsed[date]=[e.dec(re.sub(r'\s*\([A-Za-z]\)','',v)) for v in cells[2:14]]
  if not parsed:raise ValueError('BLS改定表の形式を検証できません')
  rows=parsed;e.write(e.HERE/'research/revision-snapshot.json',dict(source=url,checkedAt=e.now(),rows=rows))
 except Exception as ex:err=str(ex)
 out=[]
 def store(code,label,rs,season):
  meta=e.save(dict(id='revisions:'+code,label='NFP '+label,page='labor',category='雇用・改定',provider='BLS',source=url,frequency='Monthly',seasonal=season,unit='千人',definition='BLS公表の各回の前月差。横軸は対象月。第3回も年次ベンチマーク前のsample-based値です。前2か月累計改定は当月発表に伴う前月の(第2−初回)＋前々月の(第3−第2)。未公表は空欄。',observations=rs))
  if err:meta.update(status='fetch_failed',error='自動取得不可。公式表で照合済みの保存値を表示：'+err)
  out.append(meta)
 for season,offset in [('SA',0),('NSA',6)]:
  for i,label in enumerate(['初回公表の前月差','第2回公表の前月差','第3回公表の前月差']):store(season+':'+str(i),label,[e.obs(d,v[offset+i],'published') for d,v in rows.items()],season)
  rs=[]
  for date in sorted(rows):
   y,m=map(int,date[:7].split('-'));n=y*12+m-1
   prev=lambda k:rows.get(f'{(n-k)//12:04}-{(n-k)%12+1:02}-01')
   a,b=prev(1),prev(2)
   if rows[date][offset] is None or not a or not b:continue
   vals=[a[offset],a[offset+1],b[offset+1],b[offset+2]]
   if all(v is not None for v in vals):rs.append(e.obs(date,Decimal(vals[1])-Decimal(vals[0])+Decimal(vals[3])-Decimal(vals[2]),'derived'))
  store(season+':net2','前2か月累計改定',rs,season)
 return out

def healthcare():
 out=[]
 for code,label in [('CES6562000003','Health care and social assistance'),('CES6562000103','Health care')]:
  id='healthcare:'+code;p=e.SERIES/e.key(id);old=json.loads(p.read_text()) if p.exists() else {};rows={r['date']:r for r in old.get('observations',[])};year=datetime.now().year
  for start,end in ([(2006,2015),(2016,year)] if not old else [(year-9,year)]):
   for a in range(start,end+1,10):
    b=min(a+9,end);url=f'https://api.bls.gov/publicAPI/v2/timeseries/data/{code}?startyear={a}&endyear={b}';res=json.loads(e.get(url))
    if res.get('status')!='REQUEST_SUCCEEDED':raise ValueError(str(res.get('message')))
    found=res['Results']['series'][0]
    if found['seriesID']!=code or not found['data']:raise ValueError('BLS APIの系列IDまたはデータを確認できません')
    for r in found['data']:
     if not r['period'].startswith('M') or r['period']=='M13':continue
     d=r['year']+'-'+r['period'][1:]+'-01';rows[d]=e.obs(d,r['value'],'preliminary' if any(f.get('code')=='P' for f in r['footnotes']) else 'latest')
  out.append(e.save(dict(id=id,officialId=code,label=label+' 平均時給',page='labor',category='賃金・労働時間',provider='BLS',source='https://data.bls.gov/timeseries/'+code,frequency='Monthly',seasonal='SA',unit='ドル',definition='CES全従業員の平均時給。産業コードは既存Series_Masterの同産業の雇用系列、data type 03は全従業員平均時給。医療と医療・社会扶助を区別。BLS APIのPフラグを保存。',observations=list(rows.values()))))
 return out

def diffusion():
 import re,calendar
 url='https://www.bls.gov/news.release/empsit.b.htm';dates=['2025-08-01','2026-06-01','2026-07-01','2026-08-01'];values={'Total private':['45.4','53.6','52.8','55.6'],'Manufacturing':['41.7','57.6','52.1','61.1']};err=None
 try:
  tree=html.fromstring(e.get(url));table=next(t for t in tree.xpath('//table') if 'DIFFUSION INDEX' in t.text_content());headers=table.xpath('.//thead//th');ds=[]
  for h in headers:
   text=' '.join(' '.join(h.itertext()).split());m=re.search(r'([A-Za-z]+)\.?\s*(20\d{2})',text)
   if m:
    month=next((i for i in range(1,13) if calendar.month_name[i].lower().startswith(m[1].lower())),None)
    if month:ds.append(f'{m[2]}-{month:02}-01')
  parsed={}
  for tr in table.xpath('.//tr'):
   cells=[' '.join(c.text_content().split()) for c in tr.xpath('./th|./td')]
   if cells and 'industries)' in cells[0]:
    for label in values:
     if cells[0].startswith(label):parsed[label]=[e.dec(re.sub(r'\(p\)','',v)) for v in cells[1:]]
  if len(ds)!=4 or len(parsed)!=2 or any(len(v)!=4 for v in parsed.values()):raise ValueError('Diffusionの公表列を検証できません')
  dates,values=ds,parsed
 except Exception as ex:err=str(ex)
 out=[]
 for label,vs in values.items():
  id='diffusion:'+label;p=e.SERIES/e.key(id);old=json.loads(p.read_text()) if p.exists() else {};rows={r['date']:r for r in old.get('observations',[])}
  for d,v in zip(dates,vs):rows[d]=e.obs(d,v,'published')
  meta=e.save(dict(id=id,label=label+' 雇用Diffusion Index（1か月幅）',page='labor',category='雇用・広がり',provider='BLS',source=url,frequency='Monthly',seasonal='SA',unit='DI',definition='増加業種の割合＋変化なし業種の半分。50が増減の均衡。BLS Summary Table Bから確認。初期収録は2025年8月および2026年6〜8月。長期履歴は未収録。3期平均は1か月幅DIの移動平均で、3か月幅DIとは異なります。',observations=list(rows.values())))
  if err:meta.update(status='fetch_failed',error='自動取得不可。公式表照合済みの保存値を表示：'+err)
  out.append(meta)
 return out
