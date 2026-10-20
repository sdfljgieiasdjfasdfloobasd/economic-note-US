"""Public-only adapters copied from the local dashboard; maintained independently."""
import csv,io,json,re,zipfile,hashlib,sys,time

from urllib.error import HTTPError

from datetime import datetime

from decimal import Decimal

from urllib.parse import urljoin

from pathlib import Path

from lxml import html

import openpyxl

import expansion as e

import xlrd

BEA_DIST='https://www.bea.gov/data/special-topics/distribution-of-personal-income'

DFA='https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip'

BULK='https://www.census.gov/econ_getzippedfile/?programCode='

def clean(x):return re.sub(r'\s+',' ',str(x or '').replace('_x000D_',' ')).strip()

def sid(*parts):return hashlib.sha256('\x1f'.join(map(str,parts)).encode()).hexdigest()[:24]

def make(group,key,label,url,pub,unit,freq,season='NSA',page='consumption',note='',**meta):
 return dict(id='complement:'+group+':'+key,label=label,page=page,provider=pub.split(' / ')[0],category=pub,publicationId='complement:'+group+':'+pub,publicationLabel=pub,source=url,unit=unit,frequency=freq,seasonal=season,definition=note,priceBasis='実質' if re.search(r'real|2017|chained',unit,re.I) else '名目' if re.search(r'dollar|USD',unit,re.I) else '非該当',observations=[],**meta)

def observation(date,v,**kw):
 o=e.obs(date,v,'published',**kw)
 if o['raw'] is None:o.update(status='not_available',sourceMarker=clean(v))
 return o

def sheets(b):
 if b[:2]==b'PK':
  w=openpyxl.load_workbook(io.BytesIO(b),read_only=True,data_only=True)
  try:return [(s.title,list(s.values)) for s in w]
  finally:w.close()
 w=xlrd.open_workbook(file_contents=b)
 return [(s.name,[s.row_values(i) for i in range(s.nrows)]) for s in w.sheets()]

def links(url):
 return [(clean(a.text_content()),urljoin(url,a.get('href'))) for a in html.fromstring(e.get(url)).xpath('//a[@href]')]

def get_file_link(url,pattern):
 candidates=[u for t,u in links(url) if re.search(pattern,u,re.I)]
 if not candidates:raise ValueError('公式ダウンロードリンクが見つかりません: '+pattern)
 return candidates[0]

def census_parse(b,program,url):
 z=zipfile.ZipFile(io.BytesIO(b));text=z.read(program+'-mf.csv').decode('utf-8-sig')
 parts={p.splitlines()[0]:p.splitlines()[1:] for p in re.split(r'\n\s*\n',text.replace('\r\n','\n')) if p.strip()}
 def table(name,key):return {r[key]:r for r in csv.DictReader(parts[name])}
 cats=table('CATEGORIES','cat_idx');types=table('DATA TYPES','dt_idx');geos=table('GEO LEVELS','geo_idx');dates={}
 for k,r in table('TIME PERIODS','per_idx').items():
  v=r['per_name'];m=re.fullmatch(r'Q([1-4])-(\d{4})',v)
  dates[k]=f'{m[2]}-{(int(m[1])-1)*3+1:02d}-01' if m else datetime.strptime(v,'%b-%Y').strftime('%Y-%m-01')
 freq='Quarterly' if program=='QSS' else 'Monthly';page={'QSS':'consumption','M3':'production','RESSALES':'housing'}[program]
 pub={'QSS':'Census / QSS 業種別サービス売上・支出','M3':'Census / M3 製造業受注・出荷・在庫','RESSALES':'Census / 新築住宅販売'}[program]
 out={};vintage=parts['DATA UPDATED ON'][0]
 for r in csv.DictReader(parts['DATA']):
  if r.get('et_idx','0')!='0':continue
  c,t,g=cats[r['cat_idx']],types[r['dt_idx']],geos[r['geo_idx']]
  # Levels only; percentage changes are supplied by the existing dashboard.
  if t['dt_unit']=='PCT':continue
  assert r['is_adj'] in ['0','1'];sa='SA' if r['is_adj']=='1' else 'NSA'
  key=':'.join([c['cat_code'],t['dt_code'],g['geo_code'],sa])
  unit={'MLN$':'million USD','DOL':'USD','K':'千','MO':'月','RATIO':'比率'}[t['dt_unit']]
  if program=='RESSALES' and unit=='千':unit='千戸'+('・年率' if sa=='SA' and c['cat_code'] in ('SOLD','ASOLD') else '')
  if program=='QSS' and unit=='千':unit='千件 / 千日（'+t['dt_desc']+'）'
  s=out.setdefault(key,make(program.lower(),key,' / '.join([c['cat_desc'],t['dt_desc'],g['geo_desc']]),url,pub, freq=freq,unit=unit,season=sa,page=page,note='公式一括履歴。名目金額・実数・比率を区別。改定を含む全履歴。非公表は空欄。'+('QSSは消費者向けだけでなく企業・政府向け売上も含みます。' if program=='QSS' else ''),officialId=key,sourceVintage=vintage,sourceCategory=c['cat_code'],sourceMeasure=t['dt_code'],sourceGeo=g['geo_code']))
  s['observations'].append(observation(dates[r['per_idx']],r['val'],sourceVintage=vintage))
 return list(out.values())

def dfa_parse(b,url):
 out={};z=zipfile.ZipFile(io.BytesIO(b))
 for kind in ['levels','shares']:
  name='dfa-networth-'+kind+'-detail.csv'
  for r in csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))):
   m=re.fullmatch(r'(\d{4}):Q([1-4])',r['Date']);assert m
   date=f'{m[1]}-{(int(m[2])-1)*3+1:02d}-01'
   for metric,v in r.items():
    if metric in ['Date','Category']:continue
    category={'TopPt1':'純資産 上位0.1%','RemainingTop1':'純資産 上位0.1〜1%','Next9':'純資産 上位1〜10%','Next40':'純資産 50〜90百分位','Bottom50':'純資産 下位50%'}.get(r['Category'],r['Category'])
    key=sid(kind,r['Category'],metric);unit='million USD' if kind=='levels' else '%'
    if metric=='Household count':unit='世帯'
    if metric=='Minimum Wealth Cutoff':unit='USD'
    s=out.setdefault(key,make('dfa',key,category+' / '+metric,url,'FRB / DFA 純資産階層別 '+('保有額' if kind=='levels' else '構成比'),unit,'Quarterly',note='純資産階層別の推計。四半期末残高。金融資産・負債の内訳は重複加算しない。SCFとFinancial Accountsを組み合わせた分配推計。',sourceFile=name,sourceCategory=r['Category'],sourceMeasure=metric))
    s['observations'].append(observation(date,v))
 return list(out.values())

def distribution_unit(metric):
 if 'Billions' in metric or 'Billions' in metric.replace(' ',''):return 'billion USD'
 if metric=='Total':return '比率（1=全体）'
 if '2017' in metric:return '2017 USD'
 if 'Nominal' in metric:return 'USD'
 return '比率（1=100%）' if '%' in metric else '比率'

def income_parse(b,url):
 out={}
 for r in csv.DictReader(io.StringIO(b.decode('utf-8-sig'))):
  keys=[r['Ranking'],r['Income Concept'],r['Quantile or Summary Metric']];key=sid(*keys);metric=keys[-1]
  s=out.setdefault(key,make('income',key,' / '.join(keys),url,'BEA / 所得分布（年次）',distribution_unit(metric),'Annual','非該当',note='公表CSVの精度を保持。階層別シェアは比率（0.1=10%）。所得階層の順位付け概念、名目額・実質額を区別。最新2024年は暫定推計。Nowcastを混在させません。',sourceMeasure=r['Income Concept'],sourceCategory=r['Ranking'],sourceMetric=metric))
  o=observation(r['Year']+'-01-01',r['Value']);o['status']='provisional' if r['Year']=='2024' else 'published';s['observations'].append(o)
 return list(out.values())

def saving_parse(b,url):
 out={}
 for sn,rows in sheets(b):
  heads=rows[0]
  for r in rows[1:]:
   if not isinstance(r[0],(int,float)):continue
   if sn=='shares of NIPA totals':items=[(list(map(clean,[r[1],r[2],r[4]])),r[5],distribution_unit(clean(r[4])))]
   elif sn=='joint shares':items=[([clean(r[1]),clean(r[2]),heads[c]],r[c],'比率（1=100%）') for c in range(3,len(heads))]
   elif sn=='savings rates':items=[([clean(heads[c])],r[c],'比率（1=100%）') for c in range(1,len(heads)) if heads[c]]
   else:raise ValueError('Unexpected BEA saving sheet '+sn)
   for keys,v,unit in items:
    key=sid(sn,*keys);s=out.setdefault(key,make('saving',key,' / '.join(keys),url,'BEA / 個人貯蓄分布【研究統計】 / '+sn,unit,'Annual','非該当',note='研究統計。所得・消費の共同分布による推計。比率は公式小数を保持（0.1=10%）。負の貯蓄率も公表値通り。',experimental=True,sourceTable=sn))
    s['observations'].append(observation(f'{int(r[0])}-01-01',v))
 return list(out.values())

def c30_parse(b,url):
 sn,rows=sheets(b)[0];heads=rows[3];sa='NSA' if 'not seasonally adjusted' in clean(rows[0][0]).lower() else 'SA' if 'seasonally adjusted' in clean(rows[0][0]).lower() else None;out=[]
 assert sa is not None,'Unknown C30 seasonal adjustment'
 dates=[]
 for r in rows[4:]:
  m=re.fullmatch(r'([A-Za-z]{3})-(\d{2})([pr]?)',clean(r[0]))
  if not m:continue
  year=int(m[2])+(1900 if int(m[2])>=70 else 2000);d=datetime.strptime(f'{m[1]}-{year}','%b-%Y').strftime('%Y-%m-01');dates.append((d,r,m[3]))
 assert dates
 ownership=sn.replace(' NSA','').replace(' SA','').replace('State','State and Local');file=url.rsplit('/',1)[-1]
 for c,h in enumerate(heads[1:],1):
  if not h:continue
  name=clean(h);s=make('c30',file+':'+str(c),ownership+' / '+name,url,'Census / C30 建設支出 / '+ownership,'million USD'+('・年率' if sa=='SA' else ''),'Monthly',sa,'production',note='建設工事の名目出来高。データセンターは建物の建設費でありサーバー機器を含みません。公共は連邦・州地方を含むため重複加算しない。',sourceTable=sn,sourceColumn=c,sourceMeasure=name)
  for d,r,flag in dates:
   o=observation(d,r[c],revisionFlag=flag);o['status']='preliminary' if flag=='p' else 'revised' if flag=='r' else o['status'];s['observations'].append(o)
  out.append(s)
 return out

def hvs_parse(b,url):
 rows=sheets(b)[0][1];heads=rows[3];out={};year=None;title=clean(rows[1][0]);kind='賃貸空室率' if 'Rental' in title else '持ち家空室率'
 for r in rows[4:]:
  a=clean(r[0]);m=re.match(r'^((?:19|20)\d{2})',a)
  if m:year=m[1];continue
  q=re.match(r'^([1-4])(?:st|nd|rd|th)',a)
  if not q or not year:continue
  d=f'{year}-{(int(q[1])-1)*3+1:02d}-01'
  for c,h in enumerate(heads[1:10],1):
   key=kind+':'+str(c);s=out.setdefault(key,make('hvs',key,kind+' / '+clean(h),url,'Census / HVS 住宅空室率','%','Quarterly',page='housing',note='公表表の非季節調整率。地域定義・標本の変更は公式脚注を参照。',sourceTable=title))
   s['observations'].append(observation(d,r[c]))
 # Repeated benchmark years marked r are revised estimates; later block is canonical.
 for s in out.values():s['observations']=list({o['date']:o for o in s['observations']}.values())
 return list(out.values())

def scf_parse(b,url):
 out={}
 def add(table,group,label,measure,year,value,unit):
  key=sid(table,group,label,measure);s=out.setdefault(key,make('scf',key,' / '.join([group,label,measure]),url,'FRB / SCF Table '+table+'（3年ごと）',unit,'Triennial','非該当',note='公開ミクロデータに基づく公式集計。調査年で表示（所得は原則前年）。名目ドル。保有額平均・中央値は保有世帯についての条件付き統計。3年ごとで欠測年は補間しない。少数標本の*は空欄。',sourceTable=table,sourceCategory=group,sourceMeasure=measure))
  s['observations'].append(observation(str(year)+'-01-01',value))
 for sn,rows in sheets(b):
  # Income and net worth across survey years, mean/median and savings shares.
  if sn.startswith('Table 1 ') or sn=='Table 4':
   group='All families';year=None;cols=[]
   for c in range(1,len(rows[2])):
    v=rows[2][c]
    if isinstance(v,(int,float)) and 1989<=v<=2100:year=int(v)
    if year is None:continue
    if sn=='Table 4':measure='Net worth / '+clean(rows[3][c]);unit='thousand USD'
    else:
     desc=clean(rows[3][c])
     if desc:base=desc
     measure=base+' / '+clean(rows[4][c]);unit='%' if 'Percentage' in base else 'thousand USD'
    if not clean(rows[3][c]) and not clean(rows[4][c] if sn!='Table 4' else None):continue
    cols.append((c,year,measure,unit))
   for r in rows[5:]:
    name=clean(r[0])
    if not name:continue
    if name.startswith('Percentile of') or (not any(e.dec(v) is not None for v in r[1:]) and not name.startswith('NOTE')):group=name;continue
    if name!='All families' and group not in ['Percentile of income','Percentile of net worth']:continue
    for c,y,m,u in cols:add('1' if sn.startswith('Table 1 ') else '4',group,name,m,y,r[c],u)
  # Published financial assets, nonfinancial assets and liabilities by family group.
  m=re.match(r'Table (6|9|13) (\d{2}) (?!Alt)',sn)
  if not m:continue
  table=m[1];year=int(m[2])+(1900 if int(m[2])>=80 else 2000);headers=[];measure=None;group='All families'
  for i,r in enumerate(rows[2:],2):
   name=clean(r[0])
   if name=='Family characteristic':
    headers=[clean(v) for v in r];
    if table=='13':
     parent=''
     for c in range(1,len(headers)):
      if headers[c]:parent=headers[c]
      sub=clean(rows[i+1][c]);headers[c]=parent+' / '+sub if sub else headers[c]
    continue
   hint=clean(r[1]) if len(r)>1 else ''
   if hint.startswith('Percentage of families'):measure='保有世帯割合';unit='%';group='All families';continue
   if hint.startswith('Median value'):measure='保有世帯の中央値';unit='thousand USD';group='All families';continue
   if hint.startswith('Mean value'):measure='保有世帯の平均値';unit='thousand USD';group='All families';continue
   if not name or not measure or not headers:continue
   if name.startswith('Percentile of'):group=name;continue
   if name!='All families' and not any(e.dec(v) is not None or v=='*' for v in r[1:]):group=name;continue
   if name!='All families' and group not in ['Percentile of income','Percentile of net worth']:continue
   for c,h in enumerate(headers[1:],1):
    if h:add(table,group,name,h+' / '+measure,year,r[c],unit)
 return list(out.values())

def steo_parse(b,url):
 out=[];z=zipfile.ZipFile(io.BytesIO(b))
 with z.open('STEO.txt') as f:
  for line in f:
   r=json.loads(line,parse_float=Decimal);code=r.get('series_id','');name=r.get('name','')
   if not code.endswith('.M') or not re.search(r'electric|power generation',name,re.I) or r.get('geography')!='USA':continue
   if r.get('copyright') not in [None,'None','']:continue
   s=make('steo',code,name,url,'EIA / STEO 電力【実績・予測】',r['units'],'Monthly','NSA','production',note='STEOの月次実績と予測。観測ごとのstatusとlastHistoricalPeriodで区別。予測は毎回改定されます。電源別発電量は実数、構成比は必要に応じ同じ定義の総量で計算。',officialId=code,lastHistoricalPeriod=r.get('lastHistoricalPeriod'),releaseDate=r.get('last_updated'),sourceMeasure=name)
   s['observations']=[]
   for d,v in r['data']:
    o=observation(d[:4]+'-'+d[4:6]+'-01',v);o['status']='forecast' if d>r['lastHistoricalPeriod'] else 'historical';o['releaseDate']=r.get('last_updated');s['observations'].append(o)
   out.append(s)
 # EIA also ships legacy/alternate codes for the same quantities. Keep a single
 # canonical series only after comparing every month, allowing source rounding.
 aliases={'ESCMU_US':'ESCMUUS','ESICU_US':'ESICUUS',
  'ELACP_US':'ELACTWH','ELCCP_US':'ELCCTWH','ELICP_US':'ELICTWH','ELRCP_US':'ELRCTWH','ELTCP_US':'ELTCTWH',
  'EXACPUS':'EXACP_US','EXCCPUS':'EXCCP_US','EXICPUS':'EXICP_US','EXRCPUS':'EXRCP_US','EXTCPUS':'EXTCP_US'}
 by={s['officialId'].split('.')[1]:s for s in out};drop=set()
 for alias,canonical in aliases.items():
  if alias not in by or canonical not in by:continue
  a,b=by[alias],by[canonical]
  def normalized(s):
   scale=Decimal('0.001') if s['unit'].startswith('million kilowatthours') else Decimal(1)
   return {o['date']:None if o['raw'] is None else Decimal(o['raw'])*scale for o in s['observations']}
  av,bv=normalized(a),normalized(b)
  same=a['label']==b['label'] and av.keys()==bv.keys() and all((av[d] is None and bv[d] is None) or (av[d] is not None and bv[d] is not None and abs(av[d]-bv[d])<=Decimal('0.00001')) for d in av)
  if same:b.setdefault('officialAliases',[]).append(a['officialId']);drop.add(a['id'])
  else:
   # A future definition change must never silently discard a genuinely different series.
   a['label']+=' ['+a['officialId']+']';a['definition']+=' 互換コードとの差異を検出したため別系列として保持。'
 return [s for s in out if s['id'] not in drop]

def combine(blocks):
 out={}
 for block in blocks:
  for s in block:
   if s['id'] not in out:out[s['id']]=dict(s,observations={})
   else:out[s['id']].update({k:v for k,v in s.items() if k!='observations'})
   out[s['id']]['observations'].update({o['date']:o for o in s['observations']})
 return [dict(s,observations=list(s['observations'].values())) for s in out.values()]

PAGES={'dfa':'consumption','income':'consumption','saving':'consumption','scf':'consumption','qss':'consumption','c30':'production','m3':'production','steo':'production','dallas':'production','nrs':'housing','ressales':'housing','nahb':'housing','fannie':'housing','pmms':'housing','hvs':'housing','slfrf':'gdp','ft900':'gdp'}
