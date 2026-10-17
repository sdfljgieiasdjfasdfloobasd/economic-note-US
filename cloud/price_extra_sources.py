"""Official release tables. Parse explicit columns, retain published rates and missing cells.
No API calls or inferred values. HTML/PDF snapshots can be imported offline.
"""
import re,hashlib,io,json
from datetime import datetime
from lxml import html
import expansion as e

LABELS={('cpi',4):'地域別・総合の公表変化率',('cpi',5):'C-CPI-UとCPI-Uの公表変化率',('cpi',7):'12か月の分析表',('ppi',2):'需要区分別の商品グループ・公表変化率',('ppi',9):'商品・サービス分類と詳細品目の指数（NSA）',('ppi',11):'産業別・製品別の指数（NSA）'}
def url(page,n):return f'https://www.bls.gov/web/ppi/ppitable{n:02}.pdf' if n in [9,11] else f'https://www.bls.gov/news.release/{page}.t{n:02}.htm'
def text(el):return ' '.join(el.text_content().split())
def clean(el):
 el=html.fromstring(html.tostring(el))
 for x in el.xpath('.//*[contains(@class,"footnoteRefs")]'):x.drop_tree()
 return text(el)
def date(s):
 m=re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)\.?\s*(20\d{2})',s)
 if not m:raise ValueError('公式表の年月が不明: '+s)
 return datetime.strptime(m[1][:3]+' '+m[2],'%b %Y').strftime('%Y-%m-01')
def val(s):
 s=re.sub(r'\([a-z0-9]+\)','',s).strip()
 if s in ['', '-', '–','—']:return None
 if e.dec(s) is None:raise ValueError('公式表の数値形式が不明: '+s)
 return s

def base(page,n,code,name,metric,season,unit,order,definition):
 pub=f'{page}:table{n}';label=f'BLS / {page.upper()} Table {n} · {LABELS[page,n]}'
 return dict(id=f'price{page}:{n}:{code}:{metric}',label=name+' / '+metric,matchLabel=name,page=page,provider='Bureau of Labor Statistics',source=url(page,n),publicationId=pub,publicationLabel=label,publications=[dict(id=pub,label=label)],sourceMetric=metric,frequency='Monthly',seasonal=season,unit=unit,sourceOrder=order,definition=definition,observations=[])

def table(blob,page,n):
 root=html.fromstring(blob);ts=root.xpath('//table[caption]');t=next((t for t in ts if re.match(r'Table\s+'+str(n)+r'\.',text(t.find('caption')))),None)
 if t is None:raise ValueError('公式表番号を確認できません')
 return t,date(text(t.find('caption')))

def parse_cpi(blob,n):
 t,month=table(blob,'cpi',n);trs=t.xpath('.//tr');out={};stack=[]
 if n==4:
  targets=[date(clean(x)) for x in trs[0].xpath('./th')[2:]]
  starts=[date(clean(x)) for x in trs[1].xpath('./th')]
  if len(targets)!=2 or len(starts)!=6:raise ValueError('CPI4列構成変更')
  specs=[]
  for i,start in enumerate(starts):
   target=targets[i//3];lag=(int(target[:4])-int(start[:4]))*12+int(target[5:7])-int(start[5:7])
   if lag not in [1,2,12]:raise ValueError('CPI4比較期間変更')
   specs.append((target,{1:'公表前月比',2:'公表2か月前比',12:'公表前年比'}[lag]))
 elif n==7:
  if not all(s in text(t) for s in ['Unadjusted percent change','Unadjusted effect','Relative','Standard error']):raise ValueError('CPI7列構成変更')
  ref=date(clean(trs[0].xpath('./th')[1]));specs=[(1,'相対的重要度','%'),(2,'公表前年比','%'),(3,'前年比寄与度','ポイント'),(4,'標準誤差','ポイント')]
 else:
  if 'Unadjusted 1-month' not in text(t) or 'Unadjusted 12-month' not in text(t):raise ValueError('CPI5列構成変更')
  specs=[('C-CPI-U','公表前月比'),('CPI-U','公表前月比'),('C-CPI-U','公表前年比'),('CPI-U','公表前年比')]
 for order,tr in enumerate(trs):
  cells=tr.xpath('./th|./td');header=tr.xpath('./th[@scope="row"]')
  if not header:continue
  name=clean(header[0]);dep=re.search(r'sub(\d+)',html.tostring(header[0],encoding='unicode'));depth=int(dep[1]) if dep else 0
  if n!=5:
   while stack and stack[-1][0]>=depth:stack.pop()
   hierarchy=[x[1] for x in stack];stack.append((depth,name))
  if len(cells)!={4:8,5:5,7:7}[n]:continue
  code=hashlib.sha256(name.encode()).hexdigest()[:16]
  if n==4:
   schedule=text(cells[1])
   if schedule not in ['M','1','2']:raise ValueError('CPI4公表頻度不明')
   for i,(d,metric) in enumerate(specs):
    sid=code+':'+metric
    if sid not in out:
     s=base('cpi',n,code,name,metric,'NSA','%',order,'BLS公表変化率。地域系列は季節調整前。M＝毎月、1＝奇数月、2＝偶数月の公表。公表されない月・比較期間は欠損として保持。最新公表表に載る期間のみ収録。');s.update(pricingSchedule=schedule,depth=depth,hierarchy=hierarchy);out[sid]=s
    out[sid]['observations'].append(e.obs(d,val(clean(cells[i+2])),'published',source=url('cpi',n),pricingSchedule=schedule))
  elif n==5:
   d=date(name)
   for i,(label,metric) in enumerate(specs):
    sid=label+':'+metric
    if sid not in out:out[sid]=base('cpi',n,label,label,metric,'NSA','%',i,'公式表に掲載される公表変化率。古い年は12月だけ掲載されるため月次欠損を補間しません。C-CPI-Uは初期推計の後、四半期ごとに改定されます。')
    out[sid]['observations'].append(e.obs(d,val(clean(cells[i+1])),'published',source=url('cpi',n)))
  else:
   for i,metric,unit in specs:
    sid=code+':'+metric
    s=base('cpi',n,code,name,metric,'NSA',unit,order,'12か月の公表分析表。前年比、総合への寄与度、相対的重要度、標準誤差を区別。相対的重要度は観測月の前月時点（詳細のreferenceMonth参照）。過去最大・最小との比較情報は観測詳細に保持。')
    s.update(depth=depth,hierarchy=hierarchy)
    s['observations']=[e.obs(month,val(clean(cells[i])),'published',source=url('cpi',n),referenceMonth=ref if i==1 else month,comparisonSince=clean(cells[5]),comparisonPercent=val(clean(cells[6])))]
    if sid in out:
     if out[sid]['observations']!=s['observations']:raise ValueError('CPI7重複項目の数値不一致')
     out[sid].setdefault('publicationViews',{s['publicationId']:[dict(sourceOrder=out[sid]['sourceOrder'],hierarchy=out[sid]['hierarchy'],depth=out[sid]['depth'],matchLabel=name)]})[s['publicationId']].append(dict(sourceOrder=order,hierarchy=hierarchy,depth=depth,matchLabel=name))
    else:out[sid]=s
 if len(out)<{4:100,5:4,7:1000}[n]:raise ValueError('CPI表の品目数が少なすぎます')
 return list(out.values())

def parse_ppi2(blob):
 t,month=table(blob,'ppi',2);trs=t.xpath('.//tr');heads=[clean(x) for x in trs[1].xpath('./th')]
 if len(heads)!=8 or 'Unadjusted' not in text(t):raise ValueError('PPI2列構成変更')
 dates=[]
 for h in heads[3:]:
  m=re.search(r'to\s*([A-Za-z]+)',h)
  if not m:raise ValueError('PPI2年月不明')
  mm=datetime.strptime(m[1][:3],'%b').month;dates.append(f'{int(month[:4])-(mm>int(month[5:7]))}-{mm:02}-01')
 if dates[-1]!=month:raise ValueError('PPI2公表月不一致')
 out={};stack=[]
 for order,tr in enumerate(trs[2:]):
  cs=tr.xpath('./th|./td');rh=tr.xpath('./th[@scope="row"]')
  if not rh:continue
  name=clean(rh[0]);dep=re.search(r'sub(\d+)',html.tostring(rh[0],encoding='unicode'));depth=int(dep[1]) if dep else 0
  while stack and stack[-1][0]>=depth:stack.pop()
  hierarchy=[x[1] for x in stack];stack.append((depth,name))
  if len(cs)!=9:continue
  group,code=map(clean,cs[1:3]);code=group+('' if code in ['-','–'] else code)
  if not re.fullmatch(r'[A-Z0-9]+',code):raise ValueError('PPI2商品コード不明')
  nsa=bool(rh[0].xpath('.//a[contains(@href,".f.2")]'))
  for metric,season,points in [('公表前月比','NSA' if nsa else 'SA',list(zip(dates,cs[4:]))),('公表前年比','NSA',[(month,cs[3])])]:
   s=base('ppi',2,code,name,metric,season,'%',order,'BLS公表の丸め済み変化率。前月比は原則SA、脚注2の品目は季節性が認められないためNSA。前年比はNSA。複数の需要区分に登場する同一商品は一つの系列を参照。')
   s['id']='priceppi:'+code+':'+('yoy' if metric=='公表前年比' else 'mom_nsa' if nsa else 'mom')
   s.update(officialId=('WPS' if season=='SA' else 'WPU')+code,depth=depth,hierarchy=hierarchy)
   s['observations']=[e.obs(d,val(clean(c)),'published',source=url('ppi',2)) for d,c in points]
   view=dict(sourceOrder=order,depth=depth,hierarchy=hierarchy,matchLabel=name)
   if s['id'] in out:
    if [r['raw'] for r in out[s['id']]['observations']]!=[r['raw'] for r in s['observations']]:raise ValueError('PPI2重複コードの数値不一致: '+code)
    out[s['id']]['publicationViews']['ppi:table2'].append(view)
   else:s['publicationViews']={'ppi:table2':[view]};out[s['id']]=s
 if len(out)<500:raise ValueError('PPI2品目不足')
 return list(out.values())

def store(items):
 out=[]
 for s in items:
  p=e.SERIES/e.key(s['id']);old=json.loads(p.read_text()) if p.exists() else {}
  rs={r['date']:r for r in old.get('observations',[])};rs.update({r['date']:r for r in s['observations']})
  # An existing canonical PPI series can belong to Table 1 and Table 2.
  merged={**old,**s,'observations':sorted(rs.values(),key=lambda r:r['date'])}
  pubs={x['id']:x for x in old.get('publications',[])}
  if old.get('publicationId'):pubs[old['publicationId']]={'id':old['publicationId'],'label':old['publicationLabel']}
  pubs.update({x['id']:x for x in s.get('publications',[])})
  merged.pop('error',None);merged.pop('checkedAt',None)
  merged['publications']=list(pubs.values());merged['publicationViews']={**old.get('publicationViews',{}),**s.get('publicationViews',{})}
  if old.get('publicationId') and old['publicationId']!=s['publicationId']:
   for k in ['publicationId','publicationLabel','label','definition','source','sourceOrder','hierarchy','depth']:merged[k]=old.get(k,s.get(k))
  if any(r['value'] is not None for r in merged['observations']):out.append(e.save(merged))
  elif hasattr(e,'APPROVED'):
   # No numeric value was published. Leave the approved empty blob intact.
   merged.update(status='published_missing',error='公式表に数値が公表されていません。0ではありません。');out.append(e.summary(merged))
  else:
   merged.update(status='published_missing',error='公式表に行はありますが、掲載期間の数値は非公表です。0ではありません。',retrievedAt=e.now());e.write(p,merged);out.append(e.summary(merged))
 return out

def update_cpi():
 blob=e.get('https://www.bls.gov/news.release/cpi.htm')
 return store([s for n in [4,5,7] for s in parse_cpi(blob,n)])

def pdf_rows(blob,n):
 """Read text positions, keeping empty numeric columns and wrapped titles.
 Column boundaries are checked against each page's printed month/year header.
 """
 import pdfplumber
 result=[]
 bounds=([0,274,298,357,380,419,458,497,536,580] if n==9 else [0,292,323,378,401,436,470,505,540,580])
 with pdfplumber.open(io.BytesIO(blob)) as pdf:
  month=date(pdf.pages[0].extract_text(x_tolerance=.7))
  for page_no,page in enumerate(pdf.pages):
   words=page.extract_words(x_tolerance=.7,y_tolerance=2)
   lines={}
   for w in words:lines.setdefault(round(w['top'],1),[]).append(w)
   years=[w for w in words if w['top']<105 and w['x0']>bounds[4] and re.fullmatch(r'20\d{2}p?',w['text'])]
   if len(years)!=5:raise ValueError(f'PPI{n} p{page_no+1}: 年見出しを確認できません')
   years.sort(key=lambda w:w['x0'])
   for i,w in enumerate(years):
    if not bounds[4+i]<w['x0']<bounds[5+i]:raise ValueError('PPI PDF列位置が変更')
   # Each numeric column's month appears immediately above its year.
   months=[]
   for i,w in enumerate(years):
    candidates=[a for a in words if bounds[4+i]<a['x0']<bounds[5+i] and w['top']-13<a['top']<w['top'] and re.fullmatch(r'[A-Za-z]+\.?',a['text'])]
    if len(candidates)!=1:raise ValueError('PDF月見出しが不明')
    months.append(date(candidates[0]['text']+' '+w['text'][:4]))
   if months[-1]!=month or months!=sorted(set(months)):raise ValueError('PDF年月が不一致')
   pending=[]
   for top,ws in sorted(lines.items()):
    if top<=years[0]['top']+3 or top>716:continue
    if re.match(r'^(?:[123]\s*)?(?:All indexes|Industry and product|The special index)', ' '.join(w['text'] for w in ws)):break
    cells=[' '.join(w['text'] for w in ws if bounds[i]<=w['x0']<bounds[i+1]) for i in range(9)]
    label=re.sub(r'(?:\.\s*){2,}.*$','',cells[0]).rstrip('. ').strip()
    coded=bool(cells[1] or cells[2]);numeric=any(cells[4:])
    if not coded and not numeric:
     if label and any(w['x0']<100 for w in ws):pending.append(label)
     else:pending=[]
     continue
    if not label:raise ValueError('PDF行名がありません')
    label=' '.join(pending+[label]);pending=[]
    nums=[val(c) for c in cells[4:]]
    code=(cells[1]+('' if cells[2]=='–' else cells[2]))
    if code and not re.fullmatch(r'[A-Z0-9-]+',code):raise ValueError('PDFコード形式: '+code)
    if not code:code='aggregate-'+hashlib.sha256(label.encode()).hexdigest()[:12]
    result.append(dict(code=code,label=label,base=cells[3] or ('1982=100' if n==9 else None),raw=nums,dates=months,depth=max(0,round((min(w['x0'] for w in ws)-37.9)/6.4)),pdfPage=page_no+1))
   page.close()
 return result

def parse_ppi_pdf(blob,n):
 rows=pdf_rows(blob,n);out={};stack=[]
 for order,row in enumerate(rows):
  name=row['label'];depth=row['depth']
  while stack and stack[-1][0]>=depth:stack.pop()
  hierarchy=[v[1] for v in stack];stack.append((depth,name))
  # Product-group headings have a code but neither an index base nor numeric cells.
  if n==11 and row['base'] is None and all(v is None for v in row['raw']):continue
  s=base('ppi',n,row['code'],name,'価格指数','NSA','指数',order,'BLS公式PDFに掲載された季節調整前の価格指数。掲載5か月分を保持。品目ごとの指数基準はindexBaseに保持。非公表・季節商品の欠損は補完しません。')
  s.update(label=name,depth=depth,hierarchy=hierarchy,officialCode=row['code'],indexBase=row['base'])
  s['observations']=[e.obs(d,v,'published',source=url('ppi',n),pdfPage=row['pdfPage'],indexBase=row['base']) for d,v in zip(row['dates'],row['raw'])]
  if s['id'] in out:raise ValueError('PDF同一コードが重複: '+s['id'])
  out[s['id']]=s
 if len(out)<1000:raise ValueError('PDF詳細品目数が少なすぎます')
 return list(out.values())

def retained(page,n,error):
 p=e.CACHE/'catalog.json'
 catalog=json.loads(p.read_text()) if p.exists() else {'series':[]}
 pub=f'{page}:table{n}'
 rows=[s for s in catalog['series'] if s.get('publicationId')==pub or any(x['id']==pub for x in s.get('publications',[]))]
 return [dict(s,status='fetch_failed',error=str(error),checkedAt=e.now()) for s in rows]
