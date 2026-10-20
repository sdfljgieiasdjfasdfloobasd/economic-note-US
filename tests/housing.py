import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'cloud'),str(Path(__file__).resolve().parents[1]/'tools')]
import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import housing_sources as h
import fred_history
class HousingTests(unittest.TestCase):
 def test_housing_membership_excludes_nonresidential(self):
  rows=[dict(id='gdp:a',label='Nonresidential',page='gdp'),dict(id='gdp:b',label='Residential',page='gdp'),dict(id='complement:c30:a',label='Total nonresidential',page='production'),dict(id='complement:c30:b',label='Public residential',page='production')]
  h.decorate(rows)
  self.assertEqual([s['id'] for s in rows if 'housing' in s.get('pages',[])],['gdp:b','complement:c30:b'])
 def test_blocked_provider_is_not_retried_and_old_values_retained(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);old=dict(id='old',source='https://www.census.gov/a',count=2,latest={'date':'2026-08-01','value':1})
   (p/'catalog.json').write_text(json.dumps({'series':[old]}));calls=[]
   def get(u):calls.append(u);raise RuntimeError('HTTP 403')
   with patch.object(h.e,'CACHE',p),patch.object(h.e,'get',get),patch.object(h.time,'sleep'):
    result=h.refresh_jobs([('a',old['source'],lambda b,u:[]),('b','https://www.census.gov/b',lambda b,u:[])])
   self.assertEqual(calls,[old['source']]);self.assertEqual(result[0]['count'],2);self.assertEqual(result[0]['latest'],old['latest']);self.assertEqual(result[0]['status'],'fetch_failed')
 def test_fhfa_no_sa_fabrication(self):
  b=b'hpi_type,hpi_flavor,frequency,level,place_name,place_id,yr,period,index_nsa,index_sa\ntraditional,purchase-only,monthly,USA,USA,USA,2026,7,123.4567,\n'
  r=h.fhfa_parse(b);self.assertEqual(len(r),1);self.assertEqual(r[0]['seasonal'],'NSA');self.assertEqual(r[0]['observations'][0]['raw'],'123.4567')
 def test_mortgage_net_percentage_is_not_a_bank_count(self):
  import io,zipfile,macro_sources as m
  for label,expected in [('Net percentage of large banks reporting stronger demand for mortgage loans','%'),('Number of banks reporting mortgage loans','Number')]:
   buffer=io.BytesIO()
   with zipfile.ZipFile(buffer,'w') as z:
    z.writestr('SLOOS_struct.xml','<Root><CodeList id="CL_FREQ"><Code value="Q">Quarterly</Code></CodeList></Root>')
    z.writestr('SLOOS_data.xml','<Root><Series SERIES_NAME="TEST" FREQ="Q" UNIT="Number" UNIT_MULT="1"><Annotation><AnnotationType>Short Description</AnnotationType><AnnotationText>'+label+'</AnnotationText></Annotation><Obs TIME_PERIOD="2026-06-30" OBS_VALUE="17.6" OBS_STATUS="A"/></Series></Root>')
   s=m.fed_parse(buffer.getvalue(),'sloos','https://www.federalreserve.gov/test.zip')[0]
   self.assertEqual(s['unit'],expected);self.assertEqual(s['dimensions']['UNIT'],'Number');self.assertEqual(s['observations'][0]['raw'],'17.6')
 def test_fred_rejects_wrong_series_and_shortened_history(self):
  import expansion as e
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);old=dict(id='fred:TEST',source='https://fred.stlouisfed.org/series/TEST',originalUnit='Percent',unit='%',frequency='Monthly',seasonal='NSA',observations=[e.obs('2020-01-01',1),e.obs('2026-09-01',2)])
   (p/e.key(old['id'])).write_text(json.dumps(old))
   for body in (b'observation_date,OTHER\n2026-09-01,2',b'observation_date,TEST\n2026-09-01,2'):
    with patch.object(e,'SERIES',p),patch.object(e,'get',return_value=body),patch.object(e,'save') as save:
     with self.assertRaises(ValueError):fred_history.refresh(e,{'id':'fred:TEST','code':'TEST'})
     save.assert_not_called()
if __name__=='__main__':unittest.main()
