"""BLS JOLTS bulk download: national industries, with verified classification metadata."""
import csv,io,json
import expansion as e
BASE='https://download.bls.gov/pub/time.series/jt/'
def table(blob):
 return [{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(io.StringIO(blob.decode('utf-8-sig')),delimiter='\t')]
def parse(files):
 industries={r['industry_code']:r for r in table(files['jt.industry'])}
 measures={r['dataelement_code']:r['dataelement_text'] for r in table(files['jt.dataelement'])}
 series={r['series_id']:r for r in table(files['jt.series']) if r['state_code']=='00' and r['area_code']=='00000' and r['sizeclass_code']=='00' and r['dataelement_code'] in ['JO','HI','TS','QU','LD','OS']}
 groups={id:[] for id in series}
 for r in table(files['jt.data.1.AllItems']):
  if r['series_id'] not in groups or r['period'] not in [f'M{i:02}' for i in range(1,13)]:continue
  if e.dec(r['value']) is None:continue
  groups[r['series_id']].append(e.obs(r['year']+'-'+r['period'][1:]+'-01',r['value'],'preliminary' if 'P' in r['footnote_codes'] else 'published',footnotes=r['footnote_codes']))
 out=[]
 for code,meta in series.items():
  if not groups[code]:raise ValueError('BLS JOLTSに観測がありません: '+code)
  ind=industries[meta['industry_code']];measure=meta['dataelement_code'];season='SA' if meta['seasonal']=='S' else 'NSA'
  out.append(dict(id='jolts:'+code,officialId=code,label='JOLTS '+measures[measure]+' · '+ind['industry_text'],page='labor',category='求人・採用（JOLTS）',provider='Bureau of Labor Statistics',source=BASE+'jt.data.1.AllItems',frequency='Monthly',unit='千人' if meta['ratelevel_code']=='L' else '%',seasonal=season,industryCode=meta['industry_code'],industryName=ind['industry_text'],depth=int(ind['display_level']),measure=measure,definition='BLS公式ファイルから直接取得。求人は月末ストック、採用・離職は月間フロー。率と人数は別系列。業種合計と総数の丸め・季節調整差は残差として表示します。',observations=groups[code],checkedAt=e.now()))
 return out

def update(files=None):
 files=files or {n:e.get(BASE+n) for n in ['jt.industry','jt.dataelement','jt.series','jt.data.1.AllItems']}
 items=parse(files);by={s['officialId']:s for s in items};out=[]
 # Preserve existing IDs/bookmarks while replacing the provider route.
 aliases={}
 for spec in e.FRED:
  code=spec['code']
  if not code.startswith(('JTS','JTU')):continue
  industry='100000' if code[3:-3]=='1000' else '000000'
  official=code[:3]+industry+'000000000'+code[-3:]
  if official not in by:raise ValueError('JOLTS公式系列と既存系列の対応が不明です: '+code)
  aliases[official]=spec
 for s in items:
  spec=aliases.get(s['officialId'])
  if spec:s=dict(s,id=spec['id'])
  out.append(e.save(s))
 return out
