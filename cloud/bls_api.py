"""Small, bounded BLS API fallback. No API key, no retries after rejection.
Persist the rolling request budget and response cache across runs. At most 20
requests per 24 hours, 20 series/request; old history is merged by callers.
"""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from urllib.request import Request,urlopen
import json,time,os,re
URL='https://api.bls.gov/publicAPI/v2/timeseries/data/'
LIMIT=20

def parse(payload,wanted):
 if payload.get('status')!='REQUEST_SUCCEEDED':raise ValueError('BLS API: '+'; '.join(payload.get('message',[]) or ['取得失敗']))
 result={}
 for s in payload.get('Results',{}).get('series',[]):
  code=s.get('seriesID')
  if code not in wanted:continue
  rows=[]
  for r in s.get('data',[]):
   if not re.fullmatch(r'M(?:0[1-9]|1[0-2])',r.get('period','')):continue
   raw=str(r.get('value','')).replace(',','');v=None if raw in ('-','', 'None') else Decimal(raw)
   if v is not None and not v.is_finite():raise ValueError('BLS APIの非数')
   date=r['year']+'-'+r['period'][1:]+'-01';datetime.strptime(date,'%Y-%m-%d')
   rows.append(dict(date=date,raw=None if v is None else raw,value=None if v is None else float(v),status='not_published' if v is None else 'published',releaseDate=None,source=URL,footnotes=r.get('footnotes',[])))
  if len({r['date'] for r in rows})!=len(rows):raise ValueError('BLS APIの重複観測')
  if rows:result[code]=sorted(rows,key=lambda r:r['date'])
 return result

def fetch(codes,path,clock=time.time,opener=urlopen,sleep=time.sleep):
 path=Path(path);state=json.loads(path.read_text()) if path.exists() else {};now=clock()
 state.setdefault('cache',{});state['attempts']=[t for t in state.get('attempts',[]) if now-t<86400]
 def persist():
  path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,separators=(',',':')));os.replace(tmp,path)
 # Oldest checked first so a quota-limited run does not starve the last series.
 needed=sorted(set(codes),key=lambda c:(state['cache'].get(c,{}).get('checkedAt',0),c));errors=[]
 for i in range(0,len(needed),20):
  batch=[c for c in needed[i:i+20] if now-state['cache'].get(c,{}).get('checkedAt',0)>=86400]
  if not batch:continue
  if len(state['attempts'])>=LIMIT or state.get('blockedUntil',0)>now:
   errors.append('BLS APIの取得上限を保護するため残りは次回へ。保存値を保持。');break
  state['attempts'].append(clock());persist();sleep(1)
  year=datetime.fromtimestamp(now,timezone.utc).year
  req=Request(URL,data=json.dumps(dict(seriesid=batch,startyear=str(year-9),endyear=str(year))).encode(),headers={'Content-Type':'application/json','User-Agent':'EconomicNote/1.0 (official statistical data)'})
  try:
   with opener(req,timeout=45) as response:payload=json.load(response)
   parsed=parse(payload,set(batch))
   for c,rows in parsed.items():state['cache'][c]=dict(checkedAt=clock(),rows=rows)
   for c in set(batch)-parsed.keys():errors.append('BLS APIに有効な観測がありません: '+c)
   persist()
  except Exception as ex:
   # A rejected or malformed response is not retried in this run or the next 24h.
   state['blockedUntil']=clock()+86400;persist();errors.append(str(ex));break
 result={c:state['cache'][c]['rows'] for c in codes if c in state['cache']}
 return result,errors
