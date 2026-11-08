"""Indeed Hiring Lab's public national CSV. One request per refresh; no API key."""
import csv,io
from datetime import date
import expansion as e
URL='https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/aggregate_job_postings_US.csv'
SOURCE='https://github.com/hiring-lab/job_postings_tracker'
LICENSE='https://creativecommons.org/licenses/by/4.0/'

def parse(blob):
 reader=csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
 required={'date','jobcountry','indeed_job_postings_index_SA','indeed_job_postings_index_NSA','variable'}
 if not required.issubset(reader.fieldnames or []):raise ValueError('Indeed CSVの列構成が変更されました')
 groups={};seen=set()
 for r in reader:
  if r['jobcountry']!='US':raise ValueError('Indeed CSVに米国以外の行があります')
  kind={'total postings':'total','new postings':'new'}.get(r['variable'])
  if not kind:raise ValueError('未知のIndeed求人区分: '+r['variable'])
  dt=date.fromisoformat(r['date']).isoformat()
  for season in ('SA','NSA'):
   key=(kind,season);identity=(*key,dt)
   if identity in seen:raise ValueError('Indeed観測が重複しています')
   seen.add(identity);raw=r['indeed_job_postings_index_'+season].strip();value=e.dec(raw)
   if raw and value is None:raise ValueError('Indeed指数が数値ではありません')
   if value is not None and float(value)<0:raise ValueError('Indeed指数が負です')
   groups.setdefault(key,[]).append(e.obs(dt,value))
 if set(groups)!={(k,s) for k in ('total','new') for s in ('SA','NSA')}:raise ValueError('Indeed全国4系列が揃っていません')
 result=[]
 for (kind,season),observations in groups.items():
  observations.sort(key=lambda r:r['date'])
  if not any(r['value'] is not None for r in observations):raise ValueError('Indeedの有効な値がありません')
  baseline=next((r for r in observations if r['date']=='2020-02-01'),None)
  if not baseline or baseline['value']!=100:raise ValueError('Indeed指数の基準が変わりました')
  result.append(dict(id=f'indeed:{kind}:{season}',label='Indeed 米国 '+('総求人指数' if kind=='total' else '新規求人指数（掲載7日以内）'),page='labor',category='Indeed / 全国求人指数',provider='Indeed Hiring Lab',source=SOURCE,download=URL,license='CC BY 4.0',licenseUrl=LICENSE,publicationId='indeed:national',publicationLabel='Indeed Hiring Lab / 米国全国求人指数',unit='指数（2020-02-01=100）',frequency='Daily',seasonal=season,definition='Indeed米国全国求人指数。2020年2月1日=100。7日移動平均、日次観測・週次公表更新。新規求人は掲載7日以内。人数ではない。公式CSVの指数水準をそのまま保存し、改定は最新配布ファイルで置換。Indeed Hiring Lab / CC BY 4.0 https://creativecommons.org/licenses/by/4.0/ 。',observations=observations))
 return result

def update():
 records=parse(e.get(URL)) # Validate all four before saving anything.
 return [e.save(s) for s in records]
