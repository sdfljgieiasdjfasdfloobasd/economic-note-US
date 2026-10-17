"""Offline regression checks for lossless cloud refresh and publication boundaries."""
import copy,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
import expansion as e,core,publication,refresh
class CloudTests(unittest.TestCase):
 def test_merge_revisions_and_history(self):
  old=[e.obs('2024-01-01','100.123456'),e.obs('2026-08-01','105'),e.obs('2026-09-01','106')]
  got=e.merge_observations(old,[e.obs('2026-08-01','105.5'),e.obs('2026-09-01',None),e.obs('2026-10-01','108.99')])
  self.assertEqual([x['raw'] for x in got],['100.123456','105.5',None,'108.99'])
 def test_stale_or_bad_response_rejected(self):
  old=[e.obs('2026-09-01','10')]
  for new in ([],[e.obs('2026-08-01','12')],[e.obs('2026-09-01','1')]*2,[e.obs('2026-09-01','NaN')]):
   with self.assertRaises(ValueError):e.merge_observations(old,new)
 def test_seasons_and_change_alignment(self):
  d=dict(id='cpi',dates=['2026-08','2026-09'],series=[dict(id='0',bases={'SA':[100,101],'NSA':[90,100]})],metrics=[{'id':'mom'},{'id':'nsa'}])
  got=core.replace_bases(d,{'0|SA':[e.obs('2026-09-01',102),e.obs('2026-10-01',103)]})
  s=got['series'][0];self.assertEqual(s['bases']['NSA'],[90,100,None]);self.assertAlmostEqual(s['values']['mom'][1],2)
  self.assertAlmostEqual(s['values']['mom'][2],100/102);self.assertEqual(d['dates'],['2026-08','2026-09'])
 def test_bad_identity_preserves_disk(self):
  meta=dict(id='test',provider='BLS',unit='%',frequency='Monthly',seasonal='SA',source='https://www.bls.gov/test',definition='official')
  with tempfile.TemporaryDirectory() as tmp:
   e.initialize(tmp,{'test':meta});s=dict(meta,observations=[e.obs('2026-09-01','4.1')]);e.save(s);p=e.SERIES/e.key('test');before=p.read_bytes()
   with self.assertRaises(ValueError):e.save(dict(s,unit='千人',observations=[e.obs('2026-10-01','8')]))
   self.assertEqual(before,p.read_bytes());e.save(dict(s,id='unreviewed'));self.assertFalse((e.SERIES/e.key('unreviewed')).exists())
 def test_bls_only_monthly_and_requested_codes(self):
  b=b'series_id\tyear\tperiod\tvalue\tfootnote_codes\nCES0000000001\t2026\tM09\t123.456\tP\nCES0000000001\t2026\tM13\t123\t\nOTHER\t2026\tM09\t900\t\n'
  got=core.parse_bulk(b,{'CES0000000001'});self.assertEqual(len(got),1);self.assertEqual(len(got['CES0000000001']),1);self.assertEqual(got['CES0000000001'][0]['raw'],'123.456')
 def test_failed_adapter_cannot_publish_fallback_values(self):
  old={'id':'diffusion:Manufacturing','observations':[e.obs('2026-09-01','50.1')]}
  candidate={'id':old['id'],'observations':[e.obs('2026-09-01','99.9')],'status':'fetch_failed','error':'download failed'}
  result=refresh.retained_failure(old,candidate)
  self.assertEqual(result['observations'],old['observations'])
  self.assertEqual(result['status'],'fetch_failed')
  self.assertNotEqual(result['observations'],candidate['observations'])
 def test_unresponsive_host_stops_repeated_requests(self):
  with tempfile.TemporaryDirectory() as tmp:
   e.initialize(tmp,{})
   with patch.object(e,'urlopen',side_effect=TimeoutError('timeout')) as request,patch.object(e.time,'sleep'):
    with self.assertRaises(TimeoutError):e.get('https://www.bea.gov/test1')
    with self.assertRaises(ValueError):e.get('https://www.bea.gov/test2')
    self.assertEqual(request.call_count,3)
 def test_api_quota_response_is_not_retried(self):
  import bls_api,io
  with tempfile.TemporaryDirectory() as tmp:
   state=Path(tmp)/'state.json'
   response=io.BytesIO(b'{"status":"REQUEST_NOT_PROCESSED","message":["daily quota"]}')
   with patch.object(bls_api,'urlopen',return_value=response) as fetch:
    bls_api.fetch(['CU1','CU2'],state,clock=lambda:1000000,opener=fetch,sleep=lambda _:None)
    bls_api.fetch(['CU3'],state,clock=lambda:1000010,opener=fetch,sleep=lambda _:None)
    self.assertEqual(fetch.call_count,1)
 def test_http_429_stops_host(self):
  from urllib.error import HTTPError
  with tempfile.TemporaryDirectory() as tmp:
   e.initialize(tmp,{})
   with patch.object(e,'urlopen',side_effect=HTTPError('https://www.bea.gov',429,'limit',{},None)) as fetch,patch.object(e.time,'sleep'):
    with self.assertRaises(HTTPError):e.get('https://www.bea.gov/test1')
    with self.assertRaises(ValueError):e.get('https://www.bea.gov/test2')
    self.assertEqual(fetch.call_count,1)
 def test_schedule_jst_and_no_private_paths(self):
  yml=(ROOT/'.github/workflows/pages.yml').read_text();self.assertIn("cron: '0 19 * * *'",yml)
  self.assertIn('python cloud/refresh.py',yml);self.assertIn('git push origin HEAD:main',yml)
  for p in (ROOT/'cloud').glob('*.py'):
   self.assertNotRegex(p.read_text(),r'/Users/[A-Za-z0-9_]');self.assertNotIn('manual_update/update.py',p.read_text())
if __name__=='__main__':unittest.main()
