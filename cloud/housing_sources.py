"""Housing supply, demand, prices and tenure: full official downloadable histories.
No extrapolation, credentials, PDF extraction or conversion of missing cells to zero.
"""
import csv,io,json,re,time
from datetime import datetime,timedelta
import expansion as e
from complementary_sources import sheets,make as base_make,observation,clean
from macro_sources import period

def make(*args,**kwargs):
 basis=kwargs.pop('priceBasis',None);s=base_make(*args,**kwargs)
 if basis is not None:s['priceBasis']=basis
 return s

e.ALLOWED=tuple(dict.fromkeys((*e.ALLOWED,'fhfa.gov')))
FHFA='https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv'
NRS='https://www.census.gov/construction/nrs/data/series.html'
HVS_TABLES=(3,4,7,8,9,10,11,14,'14a',16,17,18,19)
NRS_NAMES={'sold_cust':'新築販売戸数','fsale_cust':'販売用新築在庫','price_cust':'新築販売価格','pricerange_cust':'新築販売・価格帯別','pricereg_cust':'新築販売価格・地域別','soldfinc_cust':'新築販売・資金調達別','pricefinc_cust':'新築販売価格・資金調達別','usregsoldbyprice_2002_cust':'新築販売・旧価格帯別（2002–2019）','usregsoldbyprice_1999_cust':'新築販売・旧価格帯別（1999–2005）'}
HVS_NAMES={3:'賃貸空室率・建物戸数別',4:'持ち家空室率・建物戸数別',7:'住宅ストック・年次',8:'住宅ストック・四半期',9:'住宅ストック・地域別年次',10:'住宅ストック・地域別四半期',11:'募集家賃・売出価格',14:'持ち家率・全国と地域','14a':'持ち家率・季節調整済み',16:'持ち家率・人種／民族別',17:'持ち家率・所得階層別',18:'その他空室の理由',19:'持ち家率・年齢別'}

def slug(s):return re.sub(r'[^\w]+','-',s.lower()).strip('-')
def year(v):
 m=re.match(r'^((?:19|20)\d{2})(?:\D|\d|$)',clean(v))
 return int(m[1]) if m else None

def finish(rows):
 rows=list(rows);out=[]
 cutoff=max((o['date'] for s in rows for o in s['observations'] if o['raw'] is not None),default='')
 for s in rows:
  s['observations']=[o for o in s['observations'] if o['date']<=cutoff]
  obs=s['observations'];by={}
  for o in obs:
   if o['date'] in by and by[o['date']]['raw']!=o['raw']:raise ValueError('重複観測日: '+s['id']+' '+o['date'])
   by[o['date']]=o
  s['observations']=sorted(by.values(),key=lambda o:o['date'])
  if any(o['raw'] is not None for o in obs):out.append(s)
 if len({s['id'] for s in out})!=len(out):raise ValueError('住宅系列ID重複')
 return out

def fhfa_parse(b,url=FHFA):
 reader=csv.DictReader(io.StringIO(b.decode('utf-8-sig')));out={}
 if not {'hpi_type','hpi_flavor','frequency','level','place_name','place_id','yr','period','index_nsa','index_sa'}<=set(reader.fieldnames or []):raise ValueError('FHFA CSVの形式変更')
 flavors={'purchase-only':'購入取引のみ','all-transactions':'購入・借換鑑定を含む','expanded-data':'拡張取引データ'}
 for r in reader:
  f=r['frequency'];q=int(r['period']);y=int(r['yr'])
  if f not in ('monthly','quarterly') or not 1<=q<=(12 if f=='monthly' else 4):raise ValueError('FHFA頻度・年月不正')
  date=f'{y}-{q if f=="monthly" else 3*q-2:02d}-01'
  for season,col in [('NSA','index_nsa'),('SA','index_sa')]:
   if not r[col].strip():continue
   if e.dec(r[col]) is None:raise ValueError('FHFA非数値: '+r[col])
   key=':'.join(r[k] for k in ('hpi_type','hpi_flavor','frequency','level','place_id'))+':'+season
   if key not in out:
    pub='FHFA / 住宅価格指数 / '+flavors.get(r['hpi_flavor'],r['hpi_flavor'])+' / '+r['hpi_type']+' / '+r['level']+' · '+f.title()
    out[key]=make('fhfa',key,r['place_name']+' / '+flavors.get(r['hpi_flavor'],r['hpi_flavor']),url,pub,'指数（公式基準）',f.title(),season,'housing',note='同一住宅の再取引を用いた名目価格指数。指数の水準は住宅のドル価格ではなく、地域間の価格水準比較には使えません。購入のみ・借換鑑定を含む・拡張データを区別。基準時点は種類・地域ごとに公式仕様を参照。全公表履歴と改定を更新。',officialId=key,sourceType=r['hpi_type'],sourceFlavor=r['hpi_flavor'],sourceGeo=r['place_id'],sourceGeoLevel=r['level'],priceBasis='名目',experimental=r['hpi_type'] in ('developmental','distress-free','manufactured'),sourceDocumentation='https://www.fhfa.gov/document/d/hpi/hpi_specifications.xlsx')
   out[key]['observations'].append(observation(date,r[col],sourceNote=r.get('note',''),sourceStandardError=r.get('rstderr','')))
 return finish(out.values())

def nrs_parse(b,url):
 file=url.rsplit('/',1)[-1].rsplit('.',1)[0];out=[];legacy=url.endswith('.xls')
 for sn,rows in sheets(b):
  if sn=='Seasonal Factors':continue # Ancillary adjustment factors are not demand measures.
  text=' '.join(clean(r[0]) for r in rows[:6]).lower()
  freq='Quarterly' if ('quarterly' in text or 'qtr' in sn.lower()) and 'annual' not in text else 'Annual' if 'annual' in text else 'Monthly'
  if file in ('sold_cust','fsale_cust','price_cust') and freq=='Monthly':continue # Canonical RESSALES series already cover these cells.
  def date(v):
   if legacy and isinstance(v,(int,float)):
    if 1900<=v<=2100:return f'{int(v)}-01-01'
    if v>21000 and freq=='Monthly':return (datetime(1899,12,30)+timedelta(days=v)).strftime('%Y-%m-01')
   return period(v)
  first=next((i for i,r in enumerate(rows) if r and date(r[0])),None)
  if first is None:raise ValueError('NRS期間ヘッダー不明: '+sn)
  # Modern sheets have two levels; legacy layouts split price-band strings across rows.
  hs=next((i for i in range(first) if clean(rows[i][0]).lower() in ('year','month','monthly','quarter','period') or any(clean(v)=='Period' for v in rows[i])),None)
  if hs is None:raise ValueError('NRS列見出し不明: '+sn)
  carry=['']*(first-hs)
  for c in range(1,len(rows[first])):
   if any(clean(r[c])=='Period' for r in rows[hs:first] if c<len(r)):continue
   labels=[]
   for k,r in enumerate(rows[hs:first]):
    v=clean(r[c]) if c<len(r) else ''
    if v:
     carry[k]=v
     for j in range(k+1,len(carry)):carry[j]=''
    if carry[k]:labels.append(carry[k])
   if not labels:continue
   label=' / '.join(dict.fromkeys(labels));low=label.lower()
   season='NSA' if 'not seasonally' in low else 'SA' if 'seasonally adjusted' in low else 'NSA'
   unit='USD' if '(dollars)' in text else '%' if 'percent' in low or ('percent distribution' in text and legacy) else '千戸'
   if 'annual rate' in low:unit='千戸・年率'
   # Repeated annual US totals/prices are already covered by the simple annual files.
   if file=='pricereg_cust' and freq=='Annual' and ('united states' in low):continue
   if file=='pricefinc_cust' and freq=='Annual' and labels[-1]=='Total':continue
   if file=='soldfinc_cust' and freq=='Annual' and labels==['Total']:continue
   if file.startswith(('pricerange','usregsoldbyprice')) and 'total' in low and unit=='千戸':continue
   pub='Census / NRS '+NRS_NAMES[file]+' · '+freq
   key=file+':'+sn.strip()+':'+str(c)
   s=make('nrsdetail',key,NRS_NAMES[file]+' / '+label,url,pub,unit,freq,season,'housing',note='新築一戸建ての公式履歴。中古住宅は対象外。価格は土地を含む名目価格。販売は期間内の契約、販売用在庫は期末残高。価格帯の分類変更は旧区分と別系列。NA・S・Z等は原表記を残して空欄とし、ゼロ補完しません。',sourceTable=sn,sourceColumn=c,sourceOrder=c,priceBasis='名目' if unit=='USD' else '非該当')
   s['observations']=[observation(date(r[0]),r[c],sourceRow=i+1,sourceColumn=c+1) for i,r in enumerate(rows) if r and date(r[0]) and c<len(r)]
   out.append(s)
 return finish(out)

# Explicit inventory hierarchy; dots in Census workbooks are formatting, not labels.
INVENTORY={
 'All housing units':([],0), 'Vacant':(['All housing units'],1),
 'Year-round vacant':(['All housing units','Vacant'],2),
 'For rent':(['All housing units','Vacant','Year-round vacant'],3),
 'For sale only':(['All housing units','Vacant','Year-round vacant'],3),
 'Rented or sold':(['All housing units','Vacant','Year-round vacant'],3),
 'Held off market':(['All housing units','Vacant','Year-round vacant'],3),
 'Occasional use':(['All housing units','Vacant','Year-round vacant','Held off market'],4),
 'URE':(['All housing units','Vacant','Year-round vacant','Held off market'],4),
 'Other':(['All housing units','Vacant','Year-round vacant','Held off market'],4),
 'Seasonal':(['All housing units','Vacant'],2), 'Occupied':(['All housing units'],1),
 'Owner':(['All housing units','Occupied'],2),'Renter':(['All housing units','Occupied'],2)}
def rowlabel(v):
 s=re.sub(r'[.\u2026]+','',clean(v)).strip()
 return {'Total occupied':'Occupied',"Occ'l use":'Occasional use'}.get(s,s)

def hvs_detail_parse(b,url):
 rawnum=re.search(r'histtab(\d+a?)',url)[1];num=int(rawnum) if rawnum.isdigit() else rawnum
 rows=sheets(b)[0][1];out={};yr=None;heads={};columns={};region='United States';section='';title=HVS_NAMES[num]
 def put(label,d,v,unit='%',freq='Quarterly',col=0,row=0):
  key=f'{rawnum}:{freq}:'+slug(label);season='SA' if num=='14a' else 'NSA'
  if key not in out:
   s=make('hvsdetail',key,title+' / '+label,url,f'Census / HVS Table {rawnum} {title} · {freq}',unit,freq,season,'housing',note='CPS/HVS公式履歴。空室率は対象住宅の空室割合、持ち家率は居住世帯に占める持ち家世帯割合。住宅ストックは残高。標本・人口基準変更に伴う改定ブロックは原表の後掲値を採用。2025年第4四半期は10月欠測のため11・12月に基づく。募集家賃・売出価格は成約値ではありません。',sourceTable='Table '+rawnum,sourceOrder=len(out),priceBasis='名目' if unit=='USD' else '非該当')
   leaf=label.split(' / ')[-1]
   if leaf in INVENTORY:s.update(hierarchy=INVENTORY[leaf][0],depth=INVENTORY[leaf][1])
   out[key]=s
  # Same period occurs in explicitly revised Census benchmark blocks: later block wins.
  o=observation(d,v,sourceRow=row+1,sourceColumn=col+1)
  out[key].setdefault('_by',{})[d]=o
 for i,r in enumerate(rows):
  a=clean(r[0]);label=rowlabel(r[0]);y=year(a)
  if a.startswith(('Footnotes:','Source:')):yr=None;columns={};continue
  if num in (3,4,11,16,17,19):
   if a.startswith('Table 11'):section='募集家賃' if '11A' in a else '売出価格'
   if 'Year' in a and ('Quarter' in a or 'quarter' in a):
    heads={c:clean(h) for c,h in enumerate(r) if c and h}
    if num==16:heads.update({4:'All Other Races / Total',5:'Asian, Native Hawaiian and Pacific Islander Alone'})
    continue
   if y:yr=y;continue
   q=re.match(r'^([1-4])(?:st|nd|rd|th)',a)
   if yr and (q or (num==11 and a.startswith('Annual'))):
    freq='Quarterly' if q else 'Annual';d=f'{yr}-{3*int(q[1])-2 if q else 1:02d}-01'
    for c,h in heads.items():
     if num in (16,17,19) and c==1:continue # US total already in Table 14.
     put((section+' / ' if section else '')+h,d,r[c],unit='USD' if num==11 else '%',freq=freq,col=c,row=i)
  elif num in (14,'14a'):
   if y:yr=y
   if num=='14a' and y:label='United States'
   if yr and ((num=='14a' and y) or label in ('United States','Northeast','Midwest','South','West')):
    for c in range(1,5):put(label,f'{yr}-{3*c-2:02d}-01',r[c],col=c,row=i)
  elif num in (7,8,9,10,18):
   # Block date headers always have an empty/non-numeric row label.
   if num==9 and clean(r[1]) in ('Northeast','Midwest','South','West'):region=clean(r[1]);columns={};continue
   if num==10:
    m=re.match(r'(First|Second|Third|Fourth) quarter ((?:19|20)\d{2})',clean(r[1]),re.I)
    if m:
     q=['first','second','third','fourth'].index(m[1].lower())+1;columns={c:(f'{m[2]}-{3*q-2:02d}-01',reg) for c,reg in enumerate(['Northeast','Midwest','South','West'],1)};continue
   if num in (7,9) and not a and year(r[1]):
    columns={c:(f'{year(v)}-01-01',region) for c,v in enumerate(r) if c and year(v)};continue
   if num in (8,18) and year(r[1]) and (not a or a.startswith('Other Vacant')):
    yr=year(r[1]);columns={c:(f'{yr}-{3*c-2:02d}-01','United States') for c in range(1,5)};continue
   if columns and label and (label in INVENTORY or num==18) and any(e.dec(r[c]) is not None for c in columns if c<len(r)):
    for c,(d,reg) in columns.items():
     if c>=len(r):continue
     put(reg+' / '+label,d,r[c],unit='%' if num==18 and 'in thousands' not in label else '千戸',freq='Annual' if num in (7,9) else 'Quarterly',col=c,row=i)
 for s in out.values():s['observations']=list(s.pop('_by').values())
 return finish(out.values())

def jobs():
 yield 'fhfa',FHFA,fhfa_parse
 for n in HVS_TABLES:
  u=f'https://www.census.gov/housing/hvs/data/histtab{n}.xlsx';yield 'hvs:'+str(n),u,hvs_detail_parse
 # Fixed official history filenames do not require fetching a listing on every refresh.
 for name in NRS_NAMES:
  u='https://www.census.gov/construction/nrs/xls/'+name+('.xls' if name.startswith('usreg') else '.xlsx')
  yield 'nrs:'+name,u,nrs_parse

 for name in ('mhstabavgsls.xlsx','mhstabsplcstat.xlsx'):yield 'mhs:'+name,MHS_BASE+name,mhs_parse

def refresh_jobs(source_jobs):
 p=e.CACHE/'catalog.json';old=json.loads(p.read_text()).get('series',[]) if p.exists() else [];oldby={s['id']:s for s in old};out=[];blocked=set()
 for name,url,parse in source_jobs:
  host=url.split('/')[2]
  try:
   if host in blocked:raise RuntimeError('提供元のアクセス拒否後のため今回の取得を停止。保存値を保持。')
   time.sleep(1)
   rows=parse(e.get(url),url)
   if not rows:raise ValueError('公表データが空です。既存値を保持。')
   for s in rows:
    if not any(o.get('value') is not None for o in s.get('observations',[])):continue
    prior=oldby.get(s['id'],{})
    for field in ('pages','publications','publicationViews','hierarchy','depth'):
     if field not in s and field in prior:s[field]=prior[field]
    out.append(e.save(s))
  except Exception as ex:
   if any(x in str(ex) for x in ('403','429','Access Denied')):blocked.add(host)
   prior=[s for s in old if s.get('source')==url]
   out.extend(dict(s,status='fetch_failed',error=str(ex),checkedAt=e.now()) for s in prior)
   if not prior:out.append(dict(id='housingextra:source:'+name,label=name,page='housing',category='住宅・取得状況',source=url,status='fetch_failed',count=0,error=str(ex),checkedAt=e.now()))
 return out


def update():return refresh_jobs(jobs())

def decorate(entries):
 """Reuse canonical series in housing without copying observations or IDs."""
 for s in entries:
  sid=s['id'];label=s.get('label','');text=label+' '+s.get('definition','')
  related=(sid.startswith('sloos:') and bool(re.search(r'mortgage|residential',label,re.I))) or (sid.startswith('nydebt:') and bool(re.search(r'mortgage|home.equity|housing',label,re.I))) or (sid.startswith('dsr:') and 'MORTGAGE' in sid) or (sid.startswith('complement:c30:') and bool(re.search(r'\bresidential\b',label,re.I))) or (sid.startswith('gdp:') and bool(re.search(r'(?<![a-z])residential(?![a-z])',label,re.I)))
  if related:s['pages']=list(dict.fromkeys([*s.get('pages',[]),s.get('page',''),'housing']))
 return entries

MHS_BASE='https://www2.census.gov/programs-surveys/mhs/tables/time-series/'
def mhs_parse(b,url):
 import calendar
 file=url.rsplit('/',1)[-1];price=file=='mhstabavgsls.xlsx';book=sheets(b)
 name,rows=book[0];start=5 if price else 6;maxcol=15 if price else 24
 def dated(rows):
  yr=None;out={}
  for i,r in enumerate(rows):
   y=year(r[0])
   if y:yr=y;continue
   month=next((m for m in range(1,13) if clean(r[0]).startswith(calendar.month_name[m])),None)
   if yr and month:out[f'{yr}-{month:02d}-01']=(i,r)
  return out
 values=dated(rows);errors=dated(book[1][1]);out=[];carry=['']*(start-3)
 for c in range(1,maxcol+1):
  path=[]
  for k,r in enumerate(rows[3:start]):
   v=clean(r[c]);v=re.sub(r'(?<=[A-Za-z])\d+(?:\s+\d+)*$','',v).strip()
   if v:
    carry[k]=v
    for j in range(k+1,len(carry)):carry[j]=''
   if carry[k]:path.append(carry[k])
  label=' / '.join(path);unit='USD' if price else '戸';pub='Census / MHS 工場生産住宅・'+('平均販売価格' if price else '出荷月別の販売・設置状況')
  s=make('mhs',file+':'+str(c),label,url,pub,unit,'Monthly','NSA','housing',note='HUD支援のCensus Manufactured Housing Survey。通常の新築一戸建て調査とは対象が異なります。'+('土地代を含まない住宅本体の平均販売価格。販売済みと販売予定を含む推計。' if price else '日付は出荷対象月。その出荷分の販売・設置状況であり、当月の全国在庫残高ではありません。')+'相対標準誤差は各観測のsourceRelativeStandardErrorに保存。Z・Xなどの記号は空欄と原表記を保持。',sourceTable=name,sourceColumn=c,sourceOrder=c,priceBasis='名目' if price else '非該当')
  for d,(i,r) in values.items():
   err=errors.get(d,(None,[]))[1];s['observations'].append(observation(d,r[c],sourceRow=i+1,sourceColumn=c+1,sourceRelativeStandardError=(e.dec(err[c]) if e.dec(err[c]) is not None else clean(err[c])) if len(err)>c else None))
  out.append(s)
 return finish(out)
