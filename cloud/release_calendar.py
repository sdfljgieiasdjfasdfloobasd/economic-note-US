"""Public-only adapters copied from the local dashboard; maintained independently."""
from pathlib import Path

from datetime import datetime, date, timedelta, timezone

from zoneinfo import ZoneInfo

from urllib.request import Request, urlopen

from urllib.parse import urljoin, urlparse

from concurrent.futures import ThreadPoolExecutor

from lxml import html

import re, json, hashlib, os, uuid, threading

HERE=Path(__file__).resolve().parent

CACHE=HERE/'data/calendar.json'

SEED=HERE/'calendar_seed.json'

ET=ZoneInfo('America/New_York')

JST=ZoneInfo('Asia/Tokyo')

MONTHS={name:i+1 for i,name in enumerate('January February March April May June July August September October November December'.split())}

LOCK=threading.Lock()

RUNNING=False

SOURCES={
 'bls':('BLS 発表予定','https://www.bls.gov/schedule/news_release/bls.ics'),
 'bea':('BEA 発表予定','https://www.bea.gov/news/schedule/full'),
 'ism':('ISM 発表予定','https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/'),
 'nyfed':('NY連銀 経済指標カレンダー','https://www.newyorkfed.org/research/calendars/nationalecon_cal'),
 'michigan':('Michigan 次回発表','https://www.sca.isr.umich.edu/'),
}

INDICATORS={
 'cpi':('CPI 消費者物価','物価','cpi',[('cpi','NSA')],[]),
 'ppi':('PPI 生産者物価','物価','ppi',[('ppi','NSA')],[]),
 'pce':('PCE 物価・個人所得／支出','物価','pce',[('pce','SA')],[]),
 'employment':('雇用統計','雇用','employment',[(x,'SA') for x in ['employment','labor','wages','hours']],[]),
 'jolts':('JOLTS 求人・労働異動','雇用','labor-market',[],['fred:JTSJOL','fred:JTSHIR','fred:JTSQUR','fred:JTSLDR']),
 'eci':('雇用コスト指数 ECI','雇用','labor-market',[],['fred:CIS1020000000000I']),
 'productivity':('労働生産性・単位労働コスト','雇用','labor-market',[],['fred:OPHNFB','fred:ULCNFB']),
 'ism-mfg':('ISM 製造業 PMI','PMI','ism',[],['ism:Manufacturing:Headline PMI']),
 'ism-svc':('ISM サービス業 PMI','PMI','ism',[],['ism:Services:Headline PMI']),
 'michigan':('Michigan インフレ期待','期待インフレ','expectations',[],['michigan:PX_MD','michigan:PX5_MD']),
 'nyfed':('NY連銀 消費者期待調査','期待インフレ','expectations',[],['nyfed:Inflation expectations:1','nyfed:Inflation expectations:2']),
 'adp':('ADP 民間雇用','雇用','labor-market',[],[]),
 'claims':('新規失業保険申請','雇用','labor-market',[],['fred:ICSA','fred:CCSA']),
 'conference':('消費者信頼感・雇用判断','雇用','labor-market',[],['conference:plentiful','conference:hard']),
}

def now():return datetime.now(timezone.utc)

def read(path, default):return json.loads(path.read_text()) if path.exists() else default

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 p=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');p.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False));os.replace(p,path)

def text(node):return ' '.join(node.text_content().split())

def previous_month(d):return (d.replace(day=1)-timedelta(days=1)).strftime('%Y-%m')

def event(indicator, when, target=None, stage='', source='', note=''):
 if when.tzinfo is None:raise ValueError('タイムゾーンが必要です')
 return dict(id=f'{indicator}:{when.date()}:{stage}',indicator=indicator,scheduledAt=when.astimezone(timezone.utc).isoformat(),targetPeriod=target,stage=stage,source=source,note=note)

def period(title):
 q=re.search(r'(First|Second|Third|Fourth|[1-4](?:st|nd|rd|th)) Quarter (20\d\d)',title,re.I)
 if q:
  n={'first':1,'second':2,'third':3,'fourth':4}.get(q[1].lower()) or int(q[1][0]);return f'{q[2]}-Q{n}'
 m=re.search(r'('+'|'.join(MONTHS)+r') (20\d\d)',title)
 return f'{m[2]}-{MONTHS[m[1]]:02}' if m else None

def bls_kind(title):
 for prefix,key in [('Consumer Price Index','cpi'),('Producer Price Index','ppi'),('Employment Situation','employment'),('Job Openings and Labor Turnover','jolts'),('Employment Cost Index','eci'),('Productivity and Costs','productivity')]:
  if title.startswith(prefix) and 'by Industry' not in title:return key

def parse_bls_ics(blob,url):
 raw=re.sub(r'\r?\n[ \t]','',blob.decode('utf-8-sig'))
 if 'BEGIN:VCALENDAR' not in raw:raise ValueError('BLS iCalendarの形式を確認できません')
 out=[]
 for block in raw.split('BEGIN:VEVENT')[1:]:
  props={}
  for line in block.splitlines():
   if ':' in line:
    name,value=line.split(':',1);props[name.split(';')[0]]=(name,value.replace('\\,',',').replace('\\n',' '))
  title=props.get('SUMMARY',('', ''))[1];key=bls_kind(title)
  if not key or 'DTSTART' not in props:continue
  header,value=props['DTSTART'];zone=timezone.utc if value.endswith('Z') else ET
  tz=re.search('TZID=([^;:]+)',header)
  if tz:zone=ZoneInfo('America/New_York' if tz[1]=='Eastern Standard Time' else tz[1])
  dt=datetime.strptime(value.rstrip('Z'),'%Y%m%dT%H%M%S').replace(tzinfo=zone)
  target=period(title+' '+props.get('DESCRIPTION',('', ''))[1]);stage='改定' if '(R)' in title else '速報' if '(P)' in title else ''
  if props.get('STATUS',('', ''))[1]=='CANCELLED':continue
  out.append(event(key,dt,target,stage,url))
 if not out:raise ValueError('BLSの対象指標が見つかりません')
 return out

def parse_bea(blob,url):
 tree=html.fromstring(blob);out=[]
 for table in tree.xpath('//table'):
  m=re.search(r'Year (20\d\d)',text(table))
  if not m:continue
  for row in table.xpath('.//tr[td]'):
   cells=row.xpath('./td')
   if len(cells)<3:continue
   title=text(cells[2])
   if not title.startswith('Personal Income and Outlays'):continue
   dt=datetime.strptime(text(cells[0])+' '+m[1],'%B %d %I:%M %p %Y').replace(tzinfo=ET)
   out.append(event('pce',dt,period(title),source=url))
 if not out:raise ValueError('BEAのPCE発表予定を確認できません')
 return out

NYFED_NAMES={'ADP National Employment Report':'adp','Initial Claims':'claims','Survey of Consumer Expectations':'nyfed','Michigan Consumer Survey (Preliminary)':'michigan','Michigan Consumer Survey (Final)':'michigan','Consumer Confidence':'conference'}

def observations(cache):
 """Load only the named representative series; do not trust a dataset-wide latest date."""
 catalog={s['id']:s for s in read(cache/'explorer/catalog.json',{'series':[]})['series']}
 out={};datasets={}
 for key,(_,_,_,local,external) in INDICATORS.items():
  entries=[]
  for dataset,season in local:
   if dataset not in datasets:datasets[dataset]=read(cache/(dataset+'.json'),{})
   d=datasets[dataset];s=next((s for s in d.get('series',[]) if s['name']==d.get('default')),None)
   vals=s.get('bases',{}).get(season,[]) if s else []
   rs={dt:(v,'') for dt,v in zip(d.get('dates',[]),vals) if v is not None}
   entries.append(dict(label=d.get('title',dataset)+' / '+season,values=rs,latest=max(rs,default=None),fetched=d.get('savedAt'),error=None))
  for id in external:
   m=catalog.get(id,{});s=read(cache/'explorer/series'/(hashlib.sha256(id.encode()).hexdigest()+'.json'),{})
   rs={r['date']:(r['value'],r.get('status','')) for r in s.get('observations',[]) if r.get('value') is not None}
   entries.append(dict(label=m.get('label',id),values=rs,latest=max(rs,default=None),fetched=s.get('retrievedAt'),error=m.get('error') if m.get('status')=='fetch_failed' else None))
  out[key]=entries
 return out

def matches(observation_date,target):
 if not target:return False
 if '-Q' in target:return observation_date[:4]==target[:4] and (int(observation_date[5:7])-1)//3+1==int(target[-1])
 return observation_date[:7]==target

def reflection(e,entries,current):
 due=datetime.fromisoformat(e['scheduledAt'])<=current
 found=[any(matches(d,e['targetPeriod']) for d in s['values']) for s in entries]
 details=[dict(label=s['label'],latest=s['latest'],covered=found[i],error=s.get('error')) for i,s in enumerate(entries)]
 if not due:return dict(code='upcoming',label='発表予定',details=details)
 if not e['targetPeriod'] or not entries:return dict(code='unknown',label='対象期未確認',details=details)
 if not any(found):return dict(code='pending',label='予定時刻経過・未反映',details=details)
 if not all(found):return dict(code='partial',label='一部反映',details=details)
 # Latest-only caches cannot prove a specific preliminary/final/revision vintage.
 if e.get('stage') in ['確報','改定','速報']:
  return dict(code='period',label='対象期あり・公表版は要確認',details=details)
 return dict(code='reflected',label='反映済み（対象期）',details=details)

def payload(cache=HERE/'data',current=None):
 current=current or now();raw=read(cache/'calendar.json',{'sources':{}});entries=observations(cache);merged={}
 for source_id,s in raw['sources'].items():
  for e in s.get('events',[]):
   # Direct Michigan next-release information takes precedence over the Fed calendar.
   item=dict(e,scheduleSource=s['label'],scheduleCheckedAt=s.get('lastSuccessAt'),scheduleStatus=s['status'])
   k=(e['indicator'],e['scheduledAt'],e.get('stage',''))
   if k not in merged or source_id=='michigan':merged[k]=item
 events=[]
 for e in merged.values():
  label,group,nav,_,_=INDICATORS[e['indicator']]
  e.update(label=label,group=group,nav=nav,japanTime=datetime.fromisoformat(e['scheduledAt']).astimezone(JST).isoformat(),reflection=reflection(e,entries[e['indicator']],current))
  events.append(e)
 sources=[dict(id=k,**{a:b for a,b in v.items() if a!='events'},count=len(v.get('events',[])),through=max((e['scheduledAt'] for e in v.get('events',[])),default=None)) for k,v in raw['sources'].items()]
 return dict(now=current.isoformat(),updatedAt=raw.get('updatedAt'),running=RUNNING,events=sorted(events,key=lambda e:e['scheduledAt']),sources=sources,
  exclusions=[dict(label='S&P Global PMI',source='https://pmi.spglobal.com/Public/Release/ReleaseDates?language=en&os=0',reason='公式カレンダーの自動取得が制限されているため、予定は未収録です。'),dict(label='その他の期待インフレ・労働市場系列',source='',reason='このカレンダーは掲載指標のみが対象です。市場データ等の全系列の更新日は網羅していません。')])
