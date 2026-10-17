"""Public-only adapters copied from the local dashboard; maintained independently."""
import io,json,re,zipfile

from datetime import datetime

from concurrent.futures import ThreadPoolExecutor

from urllib.parse import urljoin

from lxml import html,etree

import openpyxl

import expansion as e

from macro_sources import item,store,period,fed_zip

GDP='https://apps.bea.gov/national/Release/XLS/Survey/Section1All_xls.xlsx'

def gdp_parse(b,url=GDP,tables=None):
 w=openpyxl.load_workbook(io.BytesIO(b),read_only=True,data_only=True);out=[]
 for sheet in w:
  if not sheet.title.endswith(('-Q','-A')):continue
  if tables is not None and sheet.title.split('-')[0] not in tables:continue
  rows=list(sheet.values);title=str(rows[0][0]);unit=str(rows[1][0] or '').strip('[]');freq='Quarterly' if sheet.title.endswith('-Q') else 'Annual';cols={i:period(v) for i,v in enumerate(rows[7]) if i>=3 and period(v)}
  if not cols:raise ValueError('GDPの対象期間を確認できません: '+sheet.title)
  seen=set();release=datetime.strptime(str(rows[4][0]).replace('Data published ',''),'%B %d, %Y').strftime('%Y-%m-%d');parents=[]
  for r in rows[8:]:
   if len(r)<3 or not r[1]:continue
   label=str(r[1]);depth=len(label)-len(label.lstrip());name=re.sub(r'\\\d+\\','',label.strip())
   while parents and parents[-1][0]>=depth:parents.pop()
   path=[x[1] for x in parents];parents.append((depth,name))
   if not r[2]:continue
   un=('%' if str(r[0])=='1' else 'ポイント') if 'Contributions to Percent Change' in title else '%' if 'Percent' in unit else unit
   # Per-capita tables explicitly distinguish dollars, population and indexes in row labels.
   if 'as a percentage' in name.lower():un='%'
   if sheet.title.startswith('T107') and 'Population' in name:un='千人'
   un=un.replace('] Seasonally adjusted at annual rates','・年率').replace('] Seasonally adjusted','')
   code=str(r[2]);key=sheet.title+':'+code;key+=(':line'+str(r[0])) if key in seen or code=='ZZZZZZ' else '';seen.add(key)
   s=item('gdp',key,' / '.join(path+[name]),url,'BEA / '+title+' · '+freq,un,freq,'SA' if freq=='Quarterly' else '非該当',note='公表表の見出し: '+unit+'。四半期伸び率は公式表の年率。連鎖実質額の内訳は加算しません。公表改定を含む最新値。',officialId=str(r[2]),sourceTable=sheet.title,depth=len(path),matchLabel=name)
   s.update(page='gdp',provider='Bureau of Economic Analysis',observations=[dict(e.obs(d,r[c],'published'),releaseDate=release) for c,d in cols.items()])
   if tables is not None:
    # Standard and underlying detail have different unit-header conventions.
    header=str(rows[1][0] or '');match=re.search(r'\[([^]]+)\]',header)
    base=(match[1] if match else header).split(';')[0].strip()
    contribution='Contributions to Percent Change' in title
    growth=title.startswith('Table ') and 'Percent Change From Preceding Period' in title
    s['unit']=('%' if str(r[0])=='1' else 'ポイント') if contribution else '%' if growth else base
    is_annualized=freq=='Quarterly' and 'annual rates' in header
    if is_annualized and not (contribution or growth):s['unit']+='・年率'
    s['hierarchy']=path;s['sourceLine']=str(r[0]);s['releaseDate']=release
    s['tableNumber']=re.search(r'Table ([0-9.]+U?)\.',title)[1]
    s['definition']='BEA公式表 '+s['tableNumber']+'。'+('四半期' if freq=='Quarterly' else '年次')+'。'
    if growth:s['definition']+=('前期比年率（%）。' if freq=='Quarterly' else '前年に対する実質成長率（%）。')
    elif contribution:s['definition']+='総額行は成長率（%）、内訳行はその成長率への寄与度（ポイント）。'+('四半期は年率。' if freq=='Quarterly' else '年次。')
    else:s['definition']+='公表単位: '+s['unit']+'。'
    if 'Chained' in title or 'chained' in title:s['definition']+='連鎖実質額の内訳は単純加算できません。'
    s['definition']+='全公表履歴と改定を反映。未公表・非公表の値は補完しません。'
    if sheet.title.startswith('T2'):s['pages']=['pce-nonprice']
    for o,(c,d) in zip(s['observations'],cols.items()):
     o['sourcePeriod']=rows[7][c]
     if o['raw'] is None:o.update(status='not_published',sourceMarker=str(r[c]) if r[c] is not None else None)
   out.append(s)
 w.close();return out

GDP_DETAILS=[
 ('個人消費', 'https://apps.bea.gov/national/Release/XLS/Survey/Section2All_xls.xlsx',
  frozenset(['T20301','T20302','T20401','T20404','T20405','T20406'])),
 ('民間固定投資', 'https://apps.bea.gov/national/Release/XLS/Survey/Section5All_xls.xlsx',
  frozenset(['T50301','T50302','T50401','T50402','T50501','T50502','T50601','T50602'])),
 ('投資・Underlying Detail', 'https://apps.bea.gov/national/Release/XLS/Underlying/Section5All_xls.xlsx',
  frozenset(['U50406','U50506'])),
]

def gdp_group_update(label,url,tables,previous):
 try:
  parsed=gdp_parse(e.get(url),url,tables)
  if tables is not None and {s['sourceTable'].split('-')[0] for s in parsed}!=set(tables):
   raise ValueError('指定表が公式ファイルに見つかりません。既存値を保持します。')
  if len({s['id'] for s in parsed})!=len(parsed):raise ValueError('BEA系列IDが重複しています')
  result=[]
  for s in parsed:
   if any(o['raw'] is not None for o in s['observations']):result.append(e.save(s))
   else:
    s.update(status='pending',error='公式表に行はありますが公表数値はありません（算出対象外の純額項目等を含む）。ゼロや推計値で補完しません。',retrievedAt=e.now())
    p=e.SERIES/e.key(s['id'])
    if p.exists():
     old=json.loads(p.read_text())
     if any(o.get('value') is not None for o in old.get('observations',[])):raise ValueError('保存済み観測の全欠損化を検出: '+s['id'])
    result.append(e.summary(s))
  return result
 except Exception as error:
  old=[s for s in previous if s['id'].startswith('gdp:') and
       (s.get('sourceTable','').startswith('T1') if tables is None else s.get('sourceTable','').split('-')[0] in tables)]
  return [dict(s,status='fetch_failed',error=str(error),checkedAt=e.now()) for s in old] or [dict(id='gdp:source:'+label,label=label,page='gdp',category='BEA / 取得状況',source=url,status='fetch_failed',count=0,error=str(error))]

def gdp():
 # Failure of a detail download does not mark unrelated GDP files as failed.
 path=e.CACHE/'catalog.json';previous=json.loads(path.read_text())['series'] if path.exists() else []
 result=gdp_group_update('GDP',GDP,None,previous)
 for label,url,tables in GDP_DETAILS:result.extend(gdp_group_update(label,url,tables,previous))
 return result

def housing():
 page='https://www.census.gov/construction/nrc/data/series.html';t=html.fromstring(e.get(page));urls=list(dict.fromkeys(urljoin(page,a.get('href')) for a in t.xpath('//a[@href]') if a.get('href').endswith('.xlsx')))
 if len(urls)<8:raise ValueError('住宅建設の公式履歴リンクを確認できません')
 with ThreadPoolExecutor(max_workers=3) as pool:blocks=list(pool.map(lambda u:housing_parse(e.get(u),u),urls))
 return store([s for block in blocks for s in block])

def g17():
 b,url=fed_zip('g17','https://www.federalreserve.gov/datadownload/Choose.aspx?rel=G17')
 return store(g17_parse(b,url))


def housing_parse(b,url):
 w=openpyxl.load_workbook(io.BytesIO(b),read_only=True,data_only=True);out=[];file=url.rsplit('/',1)[-1].replace('.xlsx','')
 for sheet in w:
  rows=list(sheet.values);first=next((i for i,r in enumerate(rows) if r and period(r[0])),None)
  if first is None:raise ValueError('住宅表の対象期間を確認できません: '+sheet.title)
  title=str(rows[0][0]);heads=rows[4:first];carry=['']*len(heads);freq='Annual' if 'Annual' in sheet.title else 'Quarterly' if 'Quarterly' in sheet.title else 'Monthly';season='SA' if sheet.title=='Seasonally Adjusted' else '非該当' if sheet.title=='Seasonal Factors' else 'NSA';note=' '.join(str(r[0]) for r in rows[:4] if r[0]);unit='季節調整係数' if sheet.title=='Seasonal Factors' else '千戸・年率' if 'annual rate' in note.lower() else '千戸'
  for c in range(1,len(rows[first])):
   labels=[]
   for i,h in enumerate(heads):
    if c<len(h) and h[c] is not None:
     carry[i]=' '.join(str(h[c]).split())
     for k in range(i+1,len(carry)):carry[k]=''
    if carry[i]:labels.append(carry[i])
   if not labels:continue
   label=' / '.join(dict.fromkeys(labels));un='平方フィート' if 'Square feet' in label else unit
   measure={'permits_cust':'建築許可','authnot_cust':'許可済み・未着工','starts_cust':'住宅着工','under_cust':'建設中','comps_cust':'住宅完成','starts_permits_cust':'住宅着工（許可地域）','under_permits_cust':'建設中（許可地域）','comps_permits_cust':'住宅完成（許可地域）','starts_quarterly_cust':'着工・用途／設計','comps_quarterly_cust':'完成・用途／設計'}.get(file,title)
   s=item('housing',file+':'+sheet.title+':'+str(c),measure+' / '+label,url,'Census / '+title+' · '+sheet.title,un,freq,season,note=note+'。公表ファイルの全地域・戸数区分。建設中・未着工は期末ストック。年率・実数・係数を区別。',sourceTable=sheet.title)
   s.update(page='housing',provider='U.S. Census Bureau / HUD',observations=[e.obs(period(r[0]),r[c],'published') for r in rows[first:] if r and period(r[0]) and c<len(r)]);out.append(s)
 w.close();return out

def g17_parse(b,url):
 z=zipfile.ZipFile(io.BytesIO(b));root=etree.fromstring(z.read('G17_data.xml'),etree.XMLParser(resolve_entities=False,no_network=True));structure=etree.fromstring(z.read('G17_struct.xml'));codes={c.get('id'):{n.get('value'):''.join(n.itertext()).strip() for n in c if n.get('value')} for c in structure.xpath('//*[local-name()="CodeList"]')};out=[];seen={}
 for series in root.xpath('//*[local-name()="Series"]'):
  a=dict(series.attrib);code=a['SERIES_NAME']
  if code in seen:
   existing=seen[code];pub='FRB / G.17 '+series.getparent().get('id');members=existing.setdefault('publications',[{'id':existing['publicationId'],'label':existing['publicationLabel']}]);member={'id':'g17:'+pub,'label':pub}
   if member not in members:members.append(member)
   continue
  annotations={n.xpath('string(./*[local-name()="AnnotationType"])'):n.xpath('string(./*[local-name()="AnnotationText"])') for n in series.xpath('.//*[local-name()="Annotation"]')};label=annotations.get('Short Description',code);group=series.getparent().get('id');unit=a['UNIT'].replace('_',' ');unit='%' if unit=='Percentage' else unit;mult=e.dec(a.get('UNIT_MULT','1'));unit=({'1000000':'million ','1000000000':'billion ','1000':'thousand '}.get(mult,'')+unit) if mult in ['1','1000','1000000','1000000000'] else unit+' (source multiplier '+mult+')';freq=codes['CL_FREQ'][a['FREQ']]
  s=item('g17',code,label,url,'FRB / G.17 '+group,unit,freq,a.get('SA','非該当'),note=annotations.get('Long Description',label)+'。公式SDMXの単位と産業分類を保持。指数・設備稼働率・能力・ウェイトは別系列。',officialId=code,dimensions=a)
  s.update(page='production',provider='Federal Reserve Board',observations=[e.obs(o.get('TIME_PERIOD'),o.get('OBS_VALUE'),o.get('OBS_STATUS','published')) for o in series.xpath('./*[local-name()="Obs"]')]);out.append(s);seen[code]=s
 return out
