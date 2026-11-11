"""Reviewed row-specific units and seasonal definitions; no new sources or series."""
import re
from consumption_metadata import bea_income_metadata, complement_metadata
def seasonal_basis(label, explicit=None):
 """Interpret negation before the substring 'seasonally adjusted'."""
 value=str(explicit or '').strip().upper()
 if value in ('SA','NSA'):return value
 text=' '.join(str(label).lower().split())
 if re.search(r'\b(?:not|non[- ]?)\s*seasonally adjusted\b|\bunadjusted\b',text):return 'NSA'
 if 'seasonally adjusted' in text or re.search(r'\bsaar\b',text):return 'SA'
 return '非該当'

def fed_metadata(release,label,attrs):
 result={'seasonal':seasonal_basis(label,attrs.get('SA'))}
 if release=='sloos' and attrs.get('UNIT')=='Number' and label.lower().startswith('net percentage'):
  result.update(unit='%',sourceUnit='Number',unitNote='公式系列名のNet percentage（回答割合の差、パーセントポイント）に基づく表示。SDMXのUNIT=Numberはdimensionsに保持し、銀行数として扱いません。')
 return result

def vehicle_metadata(label):
 text=str(label).lower()
 annualized=bool(re.search(r'annual rates?|\bsaar\b',text))
 factor='factor' in text
 unit='季節・営業日調整係数' if factor else ('百万台・年率' if annualized else '百万台') if 'millions' in text else '千台・年率' if annualized and 'thousands' in text else '千台' if 'thousands' in text else None
 if unit is None:raise ValueError('BEA自動車の単位を確認できません: '+str(label))
 return dict(seasonal='非該当' if factor else seasonal_basis(label),unit=unit,annualized=annualized,sourceHeader=label,measure='adjustment_factor' if factor else 'sales_volume')

SLOOS_JULY_2026 = {
 'sourcePeriod':'2026-09-30', 'ddpPeriod':'2026:3', 'surveyMonth':'2026-07', 'sourceReleaseMonth':'2026-08',
 'releaseDate':'2026-08-03',
 'periodSource':'https://www.federalreserve.gov/data/sloos/sloos-202607.htm',
 'periodDefinition':'保存日付2026-09-30はDDPのTIME_PERIOD。2026年7月調査・8月3日公表。通常の変化設問は概ね4〜6月の変化、特別設問は原設問の時点・期間に従います。9月調査を意味しません。'}

def annotate_sloos_period(series):
 # Only this independently verified survey is mapped; never infer historical dates.
 if series.get('frequency') != 'Quarterly' and series.get('dimensions',{}).get('FREQ') != 'Q':return series
 found=False
 for observation in series.get('observations',[]):
  if observation['date']=='2026-09-30':
   observation.update(SLOOS_JULY_2026)
   found=True
 if found:
  series['verifiedSurveyPeriods']={'2026-09-30':dict(SLOOS_JULY_2026)}
  note=SLOOS_JULY_2026['periodDefinition']
  if note not in series.get('definition',''):series['definition']=series.get('definition','')+' '+note
 return series

G19_MISSING_STATUS={'ND':'データなし','NA':'利用できない値','NC':'計算不能'}

def normalize_g19_missing(series):
 # FRB CL_OBS_STATUS defines these as missing, regardless of OBS_VALUE.
 # Keep the original raw token/status; do not reject negative normal values.
 if not series.get('id','').startswith('g19:'):return series
 for observation in series.get('observations',[]):
  status=observation.get('status')
  if status in G19_MISSING_STATUS:
   observation.update(value=None,sourceMissingCode=status,
    missingReason='FRB G.19の公表状態 '+status+'（'+G19_MISSING_STATUS[status]+'）。原表コードを保持し、数値として計算しません。')
 return series

def normalize(s):
 sid=s.get('id','')
 if sid.startswith('bea:'):bea_income_metadata(s)
 if sid.startswith('complement:'):complement_metadata(s)
 if sid.startswith(('g19:','sloos:')):
  s.update(fed_metadata(sid.split(':')[0],s.get('label',''),s.get('dimensions',{})))
  if sid.startswith('g19:'):normalize_g19_missing(s)
  else:annotate_sloos_period(s)
 if sid.startswith('vehicles:'):s.update(vehicle_metadata(s.get('sourceHeader') or s.get('label','')))
 return s
