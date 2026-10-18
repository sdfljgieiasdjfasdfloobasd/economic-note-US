"""Read PPI release Tables 1 and 3 by explicit commodity IDs and date headers.
Keep published rates separate from index levels. Never infer a level from a rate.
"""
import re,calendar,json,csv,io
from datetime import datetime
from lxml import html
import expansion as e

URL='https://www.bls.gov/news.release/ppi.t{:02}.htm'

def parse(blob,number):
 root=html.fromstring(blob);tables=root.xpath('//table[caption]');table=next((t for t in tables if re.search(r'Table\s+'+str(number)+r'\.',t.xpath('string(./caption)'))),None)
 if table is None:raise ValueError('PPI公式表番号を確認できません')
 caption=' '.join(table.xpath('string(./caption)').split());m=re.search(r'\[([A-Za-z]+) (20\d{2})',caption)
 if not m:raise ValueError('PPI対象月の形式変更')
 month=datetime.strptime(m[1]+' '+m[2],'%B %Y').strftime('%Y-%m-01')
 rows=table.xpath('.//tr');heads=[''.join(c.itertext()).strip() for c in rows[1].xpath('./th|./td')]
 if number==3:
  dates=[]
  for h in heads[2:]:
   mt=re.search(r'([A-Za-z]+)\.?\s*(20\d{2})',h)
   if not mt:raise ValueError('PPI指数列の年月が不明')
   dates.append(datetime.strptime(mt[1][:3]+' '+mt[2],'%b %Y').strftime('%Y-%m-01'))
 else:
  if len(heads)!=8 or '12-month' not in caption+table.text_content():raise ValueError('PPI変化率の列構成が変更')
  # Monthly headings omit the year. Anchor their target months to release month.
  dates=[]
  for h in heads[3:]:
   target=re.search(r'to\s*([A-Za-z]+)',h)
   if not target:raise ValueError('PPI前月比の対象月が不明')
   mm=datetime.strptime(target[1][:3],'%b').month;year=int(month[:4])-(mm>int(month[5:7]));dates.append(f'{year}-{mm:02}-01')
 if not dates or dates[-1]!=month or dates!=sorted(set(dates)):raise ValueError('PPI列の年月と公表月が不一致')
 out=[];seen=set()
 # Official HTML headers name each row's parents, including alternate aggregates.
 row_labels={c.get("id"):re.sub(r"\(\d+\)",""," ".join(c.text_content().split())).strip() for c in table.xpath(".//th[@id]")}
 for pos,tr in enumerate(rows[2:]):
  cells=[' '.join(c.text_content().split()) for c in tr.xpath('./th|./td')]
  if len(cells)!=(4+len(dates) if number==3 else 5+len(dates)):continue
  start=2 if number==3 else 1;group,code=cells[start:start+2]
  if not group and not code:continue
  if not re.fullmatch(r'(?:FD|ID5|ID6)',group) or not re.fullmatch(r'[A-Z0-9]+',code):raise ValueError('未知のPPI商品コード: '+group+code)
  official='WPS'+group+code;name=re.sub(r'\(\d+\)','',cells[0]).strip()
  if official in seen:raise ValueError('同一表内で商品コード重複: '+official)
  seen.add(official)
  header=tr.xpath('./th|./td')[0]
  parents=[row_labels[k] for k in header.get('headers','').split() if '.r.' in k and k in row_labels]
  section={'FD':'最終需要','ID6':'中間需要：商品分類別','ID5':'中間需要：生産段階別'}[group]
  specs=[('level','指数','SA',list(zip(dates,cells[4:]))) ] if number==3 else [('mom','%','SA',list(zip(dates,cells[5:]))),('yoy','%','NSA',[(month,cells[4])])]
  for metric,unit,season,points in specs:
   sid='priceppi:'+group+code+':'+metric
   pub='BLS / PPI Table '+str(number)+' · '+('最終需要・中間需要の指数（SA）' if number==3 else '最終需要・中間需要の公表変化率')
   rs=[]
   for d,v in points:
    raw=re.sub(r'\([a-z0-9]+\)','',v).strip()
    if raw not in ['-','–','—',''] and e.dec(raw) is None:raise ValueError('PPI数値の形式が不明: '+v)
    rs.append(e.obs(d,raw,'published',source=URL.format(number)))
   out.append(dict(id=sid,label=name+(' / 前月比' if metric=='mom' else ' / 前年比' if metric=='yoy' else ''),matchLabel=name,page='ppi',category=pub,publicationId='ppi:table'+str(number),publicationLabel=pub,provider='Bureau of Labor Statistics',source=URL.format(number),officialId=official if season=='SA' else 'WPU'+group+code,frequency='Monthly',seasonal=season,unit=unit,sourceMetric={'level':'価格指数','mom':'公表前月比','yoy':'公表前年比'}[metric],sourceOrder=pos,definition=('BLS公表のSA指数。指数の基準は品目により異なります。' if number==3 else 'BLSが丸めて公表した変化率。指数から再計算した伸び率とは別の系列です。ウェイトは系列詳細のrelativeImportanceに公表基準時点とともに保持。'),relativeImportance=None if number==3 else dict(raw=cells[3],reference=re.search(r'Dec\.?\s*(20\d{2})',table.text_content()).group(0) if re.search(r'Dec\.?\s*(20\d{2})',table.text_content()) else '公式表見出し参照'),observations=rs))
  for s in out[-len(specs):]:
   s.update(depth=len(parents),hierarchy=parents,hierarchySection=section)
   s['publications']=[dict(id=s['publicationId'],label=s['publicationLabel'])]
   s['publicationViews']={s['publicationId']:dict(sourceOrder=pos,matchLabel=name,label=s['label'],hierarchy=parents,depth=len(parents),hierarchySection=section)}
 if not all(any(code.startswith(g) for code in seen) for g in ['WPSFD','WPSID5','WPSID6']):raise ValueError('PPIの需要分類が欠けています')
 if len(seen)<100:raise ValueError('PPI全品目を確認できません: '+str(len(seen)))
 return out

def store(items,bulk=None):
 out=[]
 for s in items:
  path=e.SERIES/e.key(s['id']);old=json.loads(path.read_text()) if path.exists() else None
  if old and old.get('alias'):s['alias']=old['alias']
  rs={r['date']:r for r in (old or {}).get('observations',[])}
  if bulk and s['id'].endswith(':level'):rs.update({r['date']:r for r in bulk.get(s['officialId'],[])})
  rs.update({r['date']:r for r in s['observations']});s['observations']=sorted(rs.values(),key=lambda r:r['date'])
  if any(r['value'] is not None for r in s['observations']):out.append(e.save(s))
 return out

def update():
 from price_extra_sources import parse_ppi2,parse_ppi_pdf,store as merge_store,url,retained
 # One release response supplies all three tables, rather than repeated requests.
 blob=e.get('https://www.bls.gov/news.release/ppi.htm')
 items=parse(blob,3)+parse(blob,1)+parse_ppi2(blob)
 # Reconcile canonical series before saving; Table 2 adds publication row views.
 combined={}
 for s in items:
  old=combined.get(s['id'])
  if old:
   old.setdefault('publications',[dict(id=old['publicationId'],label=old['publicationLabel'])]).extend(s['publications'])
   old.setdefault('publicationViews',{}).update(s['publicationViews'])
  else:combined[s['id']]=s
 result=merge_store(list(combined.values()));blocked=None
 for n in [9,11]:
  try:
   if blocked:raise ValueError('BLSがアクセスを拒否したため追加取得を停止。'+blocked)
   result.extend(merge_store(parse_ppi_pdf(e.get(url('ppi',n)),n)))
  except Exception as error:
   result.extend(retained('ppi',n,error))
   if getattr(error,'code',None) in [403,429]:blocked=str(error)
 return result
