"""Refresh known FRED identities through the official CSV export, without scraping HTML.
Only existing verified metadata is reused; unknown identities use the metadata adapter.
"""
import csv,io,re
from datetime import date

def refresh(e,spec):
 p=e.SERIES/e.key(spec['id'])
 if not p.exists():return None
 import json
 old=json.loads(p.read_text());code=spec['code']
 if old.get('source')!='https://fred.stlouisfed.org/series/'+code or not all(old.get(k) for k in ('originalUnit','frequency','seasonal','unit')) or not old.get('observations'):return None
 url='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+code
 reader=csv.DictReader(io.StringIO(e.get(url).decode('utf-8-sig')))
 if reader.fieldnames not in (['observation_date',code],['DATE',code]):raise ValueError('FRED CSVの系列ID・日付列が不一致')
 observations=[];seen=set()
 for row in reader:
  d=row[reader.fieldnames[0]];date.fromisoformat(d)
  if d in seen:raise ValueError('FRED CSVの観測日が重複')
  seen.add(d);value=row[code]
  if value not in ('','.','NA') and e.dec(value) is None:raise ValueError('FRED CSV非数値')
  observations.append(e.obs(d,value))
 if not any(o['value'] is not None for o in observations):raise ValueError('FRED CSVに数値なし')
 old_dates=[o['date'] for o in old['observations'] if o.get('value') is not None]
 new_dates=[o['date'] for o in observations if o['value'] is not None]
 if old_dates and (min(new_dates)>min(old_dates) or max(new_dates)<max(old_dates)):raise ValueError('FRED履歴が短くなったため既存値を保持')
 result={k:v for k,v in old.items() if k not in ('error','checkedAt','cloudUpdateStatus')}
 result.update(observations=observations,download=url,metadataVerifiedFrom='保存済み公式系列定義（CSVヘッダーで系列IDを照合）')
 return e.save(result)
