"""Public-only adapters copied from the local dashboard; maintained independently."""
from decimal import Decimal

import expansion as e

from macro_sources import item

def derive(entries):
 catalog={'series':entries};by={s['id']:s for s in entries};out=[];cache={}
 def read(id):
  if id not in cache:cache[id]={r['date'][:7]:Decimal(r['raw']) for r in e.load_series(id,catalog)['observations'] if r.get('raw') is not None}
  return cache[id]
 def calc(code,label,inputs,fn,page,unit,note,season='SA',pub='派生指標'):
  if not all(x in by and by[x].get('count') for x in inputs):return
  maps=[read(x) for x in inputs];ds=sorted(set.intersection(*(set(m) for m in maps)));rs=[]
  for d in ds:
   v=fn(d,maps)
   if v is not None:rs.append(e.obs(d+'-01',v,'derived'))
  if not rs:return
  s=item('macrocalc',code,label,by[inputs[0]]['source'],pub,unit,season=season,note=note,inputs=inputs);s.update(page=page,provider='公式公表値から計算',observations=rs);meta=e.save(s)
  bad=[by[x] for x in inputs if by[x].get('status')=='fetch_failed']
  if bad:meta.update(status='fetch_failed',error='元系列の取得失敗により保存値から計算。'+', '.join(x['label'] for x in bad),checkedAt=e.now())
  out.append(meta)
 def previous(d,k=1):
  n=int(d[:4])*12+int(d[5:])-1-k;return f'{n//12}-{n%12+1:02}'
 for season in ['SA','NSA']:
  calc('gasoline_share:'+season,'ガソリン販売額 / 小売・飲食売上高', ['retail:447:'+season,'retail:total:'+season],lambda d,ms:ms[0][d]/ms[1][d]*100 if ms[1][d] else None,'consumption','%','Census NAICS 447（Gasoline stations）÷Retail and food services total×100。数量・家計予算の割合ではなく小売売上金額の構成比。',season,'小売 / 派生指標')
  calc('retail_control:'+season,'Retail Control Group', ['retail:total:'+season]+['retail:'+n+':'+season for n in ['441','447','444','722']],lambda d,ms:ms[0][d]-sum(m[d] for m in ms[1:]),'consumption','million USD','Total retail and food services − Motor vehicle/parts (441) − Gasoline (447) − Building materials/garden (444) − Food services (722)。4つの互いに重複しない大分類を控除。自作計算。',season,'小売 / 派生指標')
  categories=['441','442','443','444','445','446','447','448','451','452','453','454','722'];ids=['retail:'+n+':'+season for n in categories]
  calc('retail_breadth:'+season,'Retail Sales Breadth（増加業種の割合）',ids,lambda d,ms:Decimal(sum(m[d]>m[previous(d)] for m in ms))/len(ms)*100 if all(previous(d) in m for m in ms) else None,'consumption','%','独自指標。非重複の13大分類 '+', '.join(categories)+' のうち前月から売上金額が増加した業種の割合。同じ13業種すべての当月・前月がある月のみ。売上額による加重はしません。',season,'小売 / 派生指標')
 a='bea:T20806-M:DPCERX';b='bea:T20600-M:A067RX'
 for k in [1,12]:
  calc('pce_dpi_gap:'+str(k),'実質PCE成長率 − 実質DPI成長率（'+('前月比' if k==1 else '前年比')+'）',[a,b],lambda d,ms:((ms[0][d]/ms[0][previous(d,k)]-1)-(ms[1][d]/ms[1][previous(d,k)]-1))*100 if all(previous(d,k) in m and m[previous(d,k)]>0 for m in ms) else None,'pce-nonprice','ポイント','同じ月・同じ比較期間の実質PCEと実質可処分所得の伸び率の差。連鎖額の成分は合算しません。',pub='PCE / 消費と所得の伸び')
 for pay in ['base','gross']:
  calc('adp_pay_gap:'+pay,'ADP Job Changer − Job Stayer（'+pay+'）',[f'adppay:worker_type:Job-changers:{pay}',f'adppay:worker_type:Job-stayers:{pay}'],lambda d,ms:ms[0][d]-ms[1][d],'labor','ポイント','同一公表月のJob Changerの賃金上昇率中央値 − Job Stayerの中央値。Base/Grossを分離。',season='非該当',pub='ADP / 派生指標')
 for group,exclude in [('Industry',{'Goods-producing','Service-providing'}),('Establishment Size',set())]:
  ids=[s['id'] for s in entries if s['id'].startswith('adp:M:'+group+':') and s['id'].endswith(':SA') and s['label'].removeprefix('ADP ') not in exclude]
  if not ids:continue
  calc('adp_breadth:'+group,'ADP 雇用増加の広がり（'+group+'）',ids,lambda d,ms:Decimal(sum(m[d]>m[previous(d)] for m in ms))/len(ms)*100 if all(previous(d) in m for m in ms) else None,'labor','%','独自指標。非重複の公式区分のうち、SA雇用者数が前月から増えた区分の割合。対象: '+', '.join(by[x]['label'] for x in ids)+'。欠損月は計算しません。',pub='ADP / 派生指標')
 return out

def references(entries):
 # One catalog entry and one saved series, shown on more than one page.
 for s in entries:
  if s['id'].startswith(('nyfed:','michigan:','conference:')):
   s['pages']=list(dict.fromkeys(s.get('pages',[])+['consumption']))
  if s['id'].startswith('nyfed:'):
   tab=s['id'].split(':')[1];s.update(publicationId='sceall:NY Fed / SCE '+tab,publicationLabel='NY Fed / SCE '+tab)
  if s['id'].startswith('michigan:'):s.update(publicationId='michigancons:Michigan / 消費者心理',publicationLabel='Michigan / 消費者心理')
  if s['id'].startswith('conference:'):s.update(publicationId='conferencecons:Conference Board / 消費者信頼感',publicationLabel='Conference Board / 消費者信頼感')
 return entries
