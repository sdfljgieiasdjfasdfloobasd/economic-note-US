"""Public-only adapters copied from the local dashboard; maintained independently."""
import re,zipfile,io,json,calendar

from datetime import datetime

from concurrent.futures import ThreadPoolExecutor

import complementary_sources as c

import expansion as e

MONTHS={n.lower():i for i,n in enumerate(calendar.month_name) if n}

def name(v):return re.sub(r'\s*\(\d+\)','',c.clean(v)).strip().lower()

def month(v):
 t=c.clean(v).lower();m=re.match(r'^([a-z]+)(?:\s*\(r\))?$',t)
 return MONTHS.get(m[1]) if m else None

def ft_parse(b,url,exhibit):
 sn,rows=c.sheets(b)[0];out={};title=' '.join(c.clean(v) for r in rows[:5] for v in r if v)
 sa='SA' if exhibit in [7,8,10] else 'NSA';base=re.search(r'(?:Chained\s*\((\d{4})\)|(\d{4})\s*Chain)',title,re.I)
 unit='million chained ('+next(v for v in base.groups() if v)+') USD' if base else 'million USD'
 if exhibit==10 and not base:raise ValueError('実質貿易の基準年が見つかりません')
 def add(label,date,value,u=unit):
  key=c.sid(exhibit,name(label),u);s=out.setdefault(key,c.make('ft900',key,c.clean(label),url,f'Census/BEA / FT900 Exhibit {exhibit}',u,'Monthly',sa,'gdp',note='公式月次表。年累計・月次変化列を水準として混ぜません。過去公表分は観測ごとの出典URLで改定時点を保持し、後の公表に同月値がある場合は上書き。実質額の基準年が異なる履歴は接続しません。(-)はゼロまたは表示単位未満を表すため数値を推定せず空欄。',sourceTable='Exhibit '+str(exhibit)))
  s['observations'].append(c.observation(date,value,source=url))
 if exhibit in [7,8]:
  def header_month(v):
   m=re.match(r'^([A-Za-z]+)\b',c.clean(v));return MONTHS.get(m[1].lower()) if m else None
  h=next(i for i,r in enumerate(rows) if len(r)>2 and header_month(r[1]) and header_month(r[2]));cols=[];split_year=False
  for j in [1,2]:
   y=re.search(r'(19|20)\d{2}',str(rows[h][j]))
   if not y:y=re.search(r'(19|20)\d{2}',str(rows[h+1][j]));split_year=True
   assert y;cols.append((j,f'{y[0]}-{header_month(rows[h][j]):02d}-01'))
  for r in rows[h+1+int(split_year):]:
   label=c.clean(r[0])
   if not label or not any(e.dec(r[j]) is not None or c.clean(r[j])=='(-)' for j,d in cols):continue
   for j,d in cols:add(label,d,r[j])
 elif exhibit==18:
  cols=[];flow=None;release=re.search(r'_(\d{2})(\d{2})\.zip',url)
  for i,r in enumerate(rows):
   if len(r)>1 and c.clean(r[1]) in ['Exports','Imports']:flow=c.clean(r[1]);continue
   if name(r[0])=='country':
    # Early files place month headings on the Country row; later files below it.
    old=bool(re.match(r'^(?:'+ '|'.join(MONTHS) +r')\b',c.clean(r[1]).lower()));heads=rows[i-1] if old else r;dates=r if old else rows[i+1]
    cols=[];parent=''
    for j in range(1,len(heads)):
     if heads[j]:parent=c.clean(heads[j])
     d=c.clean(dates[j]);m=re.fullmatch(r'([A-Za-z]+) (\d{4})(?: \(R\))?',d)
     if m and m[1].lower() in MONTHS:date=f'{m[2]}-{MONTHS[m[1].lower()]:02d}-01'
     elif month(d) and release:
      year=int(release[1])+(1900 if int(release[1])>80 else 2000);year-=month(d)>int(release[2]);date=f'{year}-{month(d):02d}-01'
     else:continue
     cols.append((j,parent,date))
    continue
   label=c.clean(r[0])
   if not flow or not label or not any(e.dec(r[j]) is not None for j,_,_ in cols):continue
   for j,p,d in cols:add(flow+' / '+label+' / '+p,d,r[j])
 else:
  header=next(i for i,r in enumerate(rows) if name(r[0])=='period');flow='Imports' if exhibit==17 and 'Imports of' in title else '';year=None
  if exhibit==10:
   names=['Total Census Basis','Foods, Feeds, & Beverages','Industrial Supplies','Capital Goods','Automotive Vehicles etc.','Consumer Goods','Other Goods','Residual'];units=[unit]*8
  elif exhibit==16:names=['Balance','Exports','Imports'];units=[unit]*3
  else:names=['Petroleum / Quantity','Petroleum / Value','Crude oil / Quantity','Crude oil / Daily quantity','Crude oil / Value','Crude oil / Unit price'];units=['thousand barrels','thousand USD','thousand barrels','thousand barrels/day','thousand USD','USD/barrel']
  for r in rows[header+1:]:
   if c.clean(r[1]) in ['Exports','Imports']:flow=c.clean(r[1]);continue
   a=c.clean(r[0]);ym=re.fullmatch(r'((?:19|20)\d{2})(?:\s*\(R\))?',a)
   if ym:year=ym[1];continue
   mm=month(a)
   if not mm or not year:continue
   if exhibit in [10,17] and not flow:raise ValueError('輸出入区分不明')
   for j,(n,u) in enumerate(zip(names,units),1):add((flow+' / ' if flow else '')+n,f'{year}-{mm:02d}-01',r[j],u)
 if not out:raise ValueError('FT900表の数値形式を確認できません')
 return list(out.values())
