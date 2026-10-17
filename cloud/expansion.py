from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from lxml import html
import csv, io, json, hashlib, os, re, time, math
import openpyxl
def dec(v):
 try:
  d=Decimal(str(v).strip().replace(',',''));return format(d,'f') if d.is_finite() else None
 except (InvalidOperation,ValueError):return None

def obs(date,value,status='latest',**more):
 v=dec(value)
 return dict(date=date,value=float(v) if v is not None else None,raw=v,status=status,releaseDate=None,**more)

def key(id):return hashlib.sha256(id.encode()).hexdigest()+'.json'

def summary(s):
 out={k:v for k,v in s.items() if k!='observations'};rs=[r for r in s.get('observations',[]) if r['value'] is not None]
 out.update(count=len(rs),first=rs[0]['date'] if rs else None,latest=rs[-1] if rs else None);return out

def fred(spec):
 id=spec['code'];source='https://fred.stlouisfed.org/series/'+id
 try:
  t=html.fromstring(get(source));title=t.xpath('string(//meta[@name="citation_title"]/@content)') or t.xpath('string(//title)').split(' | ')[0]
  units=t.xpath('string(//*[contains(@class,"series-meta-value-units")])').strip()
  freq=t.xpath('string(//*[contains(@class,"series-meta-value-frequency")])').strip()
  body=' '.join(t.text_content().split())
  if not freq:
   m=re.search(r'Frequency:\s*(Daily|Weekly[^\n]*?|Monthly|Quarterly|Annual)(?:\s+Notes:|\s+Suggested|\s+\w+:)',body);freq=m.group(1) if m else ''
  if not freq:
   els=t.xpath('//*[contains(@class,"meta-col")][.//*[normalize-space(text())="Frequency:"]]')
   freq=' '.join(els[0].text_content().split()).replace('Frequency:','').strip() if els else ''
  if not title or not units or not freq:raise ValueError('系列の名称・単位・頻度を検証できません')
  unit_nodes=t.xpath('//*[contains(@class,"meta-col")][.//*[normalize-space(text())="Units:"]]')
  seasonal_text=' '.join(unit_nodes[0].text_content().split()) if unit_nodes else ''
  if not seasonal_text:raise ValueError('季節調整メタデータを検証できません')
  season='NSA' if 'Not Seasonally Adjusted' in seasonal_text else 'SA' if 'Seasonally Adjusted' in seasonal_text else '非該当'
  rows=list(csv.DictReader(io.StringIO(get('https://fred.stlouisfed.org/graph/fredgraph.csv?id='+id).decode('utf-8-sig'))))
  if not rows or id not in rows[0]:raise ValueError('CSV系列IDが不一致')
  original_units=units;units={'Percent':'%','Number':'人','Persons':'人','Thousands of Persons':'千人','Level in Thousands':'千人','Weeks':'週','Dollars per Hour':'ドル'}.get(units,units)
  if id.startswith(('JTS','JTU')) and units=='Rate':units='%'
  rs=[obs(r.get('observation_date',r.get('DATE')),r[id]) for r in rows]
  return save(dict(spec,originalUnit=original_units,label=title,source=source,download='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+id,unit=units,frequency=freq,seasonal=season,observations=rs))
 except Exception as e:return failure(spec['id'],id,spec['page'],spec['category'],source,e,spec['provider'])

def workbook_rows(b,name):
 w=openpyxl.load_workbook(io.BytesIO(b),read_only=True,data_only=True);s=w[name];s.reset_dimensions();rows=list(s.values);w.close();return rows

def dt(v):
 if isinstance(v,datetime):return v.strftime('%Y-%m-%d')
 if isinstance(v,(int,float)) and 190001<=v<=210012:return str(int(v))[:4]+'-'+str(int(v))[4:]+'-01'
 if isinstance(v,str) and re.match(r'^\d{4}-\d\d-\d\d',v):return v[:10]
 return None

def xseries(id,label,page,category,provider,source,rows,col,datecol=0,scale=1,frequency='Monthly',note='',season='非該当',horizon=None):
 rs=[]
 for r in rows:
  date=dt(r[datecol]) if len(r)>datecol else None
  if not date:continue
  raw=dec(r[col]) if len(r)>col else None
  value=format(Decimal(raw)*Decimal(str(scale)),'f') if raw is not None else None
  rs.append(obs(date,value,sourceRaw=raw))
 return save(dict(id=id,label=label,page=page,category=category,provider=provider,source=source,unit='%',frequency=frequency,seasonal=season,horizon=horizon,definition=note,observations=rs))

# The cloud worker is rooted in a TemporaryDirectory supplied by the caller.
# It cannot discover or write the Mac dashboard or Excel files.
HERE = CACHE = RAW = SERIES = None
ALLOWED = ('bea.gov','bls.gov','census.gov','federalreserve.gov','eia.gov','dol.gov','doleta.gov','stlouisfed.org')
FRED = json.loads((Path(__file__).parent/'fred-specs.json').read_text())
APPROVED = {}; ATTEMPTED = set(); REJECTED = {}; CANDIDATES = None
_downloads = {}; _blocked = set()
def now(): return datetime.now(timezone.utc).isoformat()
def write(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':')));os.replace(tmp,path)
def initialize(work, approved):
    global HERE,CACHE,RAW,SERIES,APPROVED,ATTEMPTED,REJECTED
    HERE=Path(work);CACHE=HERE/'data/explorer';RAW=CACHE/'raw';SERIES=CACHE/'series'
    for p in (CACHE,RAW,SERIES):p.mkdir(parents=True,exist_ok=True)
    APPROVED=approved;ATTEMPTED=set();REJECTED={};_downloads.clear();_blocked.clear()
def get(url):
    host=urlparse(url).hostname or ''
    if not any(host==h or host.endswith('.'+h) for h in ALLOWED):raise ValueError('取得対象外の提供元')
    if url in _downloads:return _downloads[url].read_bytes()
    if host in _blocked:raise ValueError('この提供元はアクセスを拒否したため、今回の残りの取得を停止')
    for attempt in range(3):
        try:
            time.sleep(1 if host.endswith('stlouisfed.org') else .2)
            req=Request(url,headers={'User-Agent':'Mozilla/5.0 (EconomicNote public statistical research)','Referer':'https://www.bls.gov/' if host.endswith('bls.gov') else 'https://'+host+'/'})
            with urlopen(req,timeout=60) as response:
                # Reject an unexpected redirect outside the public source allowlist.
                final=urlparse(response.url).hostname or ''
                if not any(final==h or final.endswith('.'+h) for h in ALLOWED):raise ValueError('取得対象外へのリダイレクト')
                blob=response.read()
            if not blob:raise ValueError('空の応答')
            if any(s in blob[:100000] for s in (b'Access Denied',b'captcha_form',b'The application is temporarily unavailable',b'Unable to connect!',b'SQLSTATE=')):raise ValueError('配布サービスが一時停止、または自動取得を制限')
            path=RAW/hashlib.sha256(url.encode()).hexdigest();path.write_bytes(blob);_downloads[url]=path
            return blob
        except HTTPError as ex:
            if ex.code in (401,403):_blocked.add(host)
            if ex.code not in (429,500,502,503,504):raise
            if attempt==2:
                _blocked.add(host);raise
        except (URLError,TimeoutError,ConnectionError):
            if attempt==2:
                _blocked.add(host);raise
        time.sleep(2**attempt)
def valid_observations(rows):
    if not rows or not any(r.get('value') is not None for r in rows):raise ValueError('有効な観測がありません')
    if len({r['date'] for r in rows})!=len(rows):raise ValueError('観測日が重複')
    for r in rows:
        datetime.strptime(r['date'],'%Y-%m-%d')
        if r.get('value') is not None:
            if isinstance(r['value'],bool) or not math.isfinite(r['value']):raise ValueError('非数・無限大の観測')
            if dec(r.get('raw')) is None or float(r['raw'])!=r['value']:raise ValueError('数値と元の精度表記が不一致')
def merge_observations(old, new):
    valid_observations(new)
    # A stale upstream file must not overwrite more recent revisions.
    latest=lambda rs:max((r['date'] for r in rs if r.get('value') is not None),default='')
    if latest(new)<latest(old):raise ValueError('取得元の最新観測が保存値より古いため保持')
    merged={r['date']:r for r in old};merged.update({r['date']:r for r in new})
    return [merged[d] for d in sorted(merged)]
def save(s):
    import publication
    sid=s['id'];oldmeta=APPROVED.get(sid)
    if oldmeta is None:
        REJECTED[sid]='新規系列は公開範囲の確認待ち'
        return summary(s)
    ATTEMPTED.add(sid)
    if publication.signature(s)!=publication.signature(oldmeta):
        REJECTED[sid]='提供元・単位・頻度・定義の変更を検出。保存値を保持'
        raise ValueError(REJECTED[sid]+': '+sid)
    p=SERIES/key(sid);old=json.loads(p.read_text()) if p.exists() else dict(oldmeta,observations=[])
    s=dict(s,observations=merge_observations(old.get('observations',[]),s.get('observations',[])),retrievedAt=now(),status='available')
    s.pop('error',None);s.pop('checkedAt',None)
    # Keep the saved blob byte-identical on a successful no-change check.
    if s['observations']==old.get('observations'):
        s=old
        if s.get('status')=='fetch_failed':
            s=dict(s,status='available');s.pop('error',None);s.pop('checkedAt',None)
    write(p,s);return summary(s)
def failure(id,label,page,category,source,error,provider=''):
    ATTEMPTED.add(id)
    p=SERIES/key(id);s=summary(json.loads(p.read_text())) if p.exists() else dict(id=id,label=label,page=page,category=category,source=source,provider=provider,count=0,latest=None)
    return dict(s,status='fetch_failed',error=str(error),checkedAt=now())
def load_series(id,catalog=None):return json.loads((SERIES/key(id)).read_text())
