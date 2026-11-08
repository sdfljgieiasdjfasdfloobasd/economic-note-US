import unittest,sys,json,math
from pathlib import Path
from decimal import Decimal as D
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
import real_retail as r,expansion as e
class RealRetail(unittest.TestCase):
 def test_quantity(self):
  g,c=r.quantity([D(10),D(20)],[D(12),D(21)],[D(1),D(1)]);self.assertEqual(g,D(10));self.assertEqual(sum(c),g)
  g,_=r.quantity([D(10)],[D(10)],[D('1.1')]);self.assertLess(g,0)
 def test_gap(self):
  a=[e.obs('2025-09-01',1),e.obs('2025-10-01',None),e.obs('2025-11-01',None),e.obs('2025-12-01',2),e.obs('2026-01-01',3),e.obs('2026-02-01',4)]
  r.enrich(a);self.assertIsNone(a[3]['growth3Raw']);self.assertEqual(D(a[-1]['avg3Raw']),D(3));self.assertIsNone(a[-1]['yoyRaw']);self.assertEqual(D(a[3]['indexRaw']),D(102));self.assertIsNone(a[0]['indexRaw'])
 def test_positive_prices(self):
  with self.assertRaises(ValueError):r.quantity([D(10)],[D(10)],[D(0)])
 def test_mapping(self):
  codes=[x[0] for x in r.MAPPING];self.assertEqual(len(codes),13);self.assertEqual(len(set(codes)),13);self.assertTrue(all(len(x)==3 for x in codes))
 def test_actual(self):
  c=json.loads((e.CACHE/'catalog.json').read_text());results=r.compute(c['series'])
  for s in results:
   self.assertEqual(s['seasonal'],'SA');self.assertEqual(s['frequency'],'Monthly')
   self.assertLessEqual(D(s['diagnostics']['headlineMaxDifference']),D(2));self.assertLessEqual(D(s['diagnostics']['controlMaxDifference']),D('.000001'))
   obs=s['observations'];by={o['date']:o for o in obs}
   for o in obs:
    if o['value'] is None:continue
    prev=list(map(float,o['inputPreviousRaw']));cur=list(map(float,o['inputCurrentRaw']));p=list(map(float,o['priceRelativesRaw']))
    independent=(sum(cur)/sum(b*q for b,q in zip(prev,p))-1)*100 if s['methodId']=='REAL_RETAIL_BEA' else (sum(n/q for n,q in zip(cur,p))/sum(prev)-1)*100
    self.assertAlmostEqual(independent,o['value'],places=10)
    if 'contributionsRaw' in o:
     self.assertAlmostEqual(sum(map(float,o['contributionsRaw'])),o['value'],places=11)
     fisher=(math.sqrt((1+o['value']/100)*(sum(cur)/sum(b*q for b,q in zip(prev,p))))-1)*100
     self.assertAlmostEqual(fisher,float(o['fisherMomRaw']),places=10)
    old=by.get(r.shift(o['date'],-1),{})
    for f in ['indexRaw','index2019Raw']:
     if o.get(f) and old.get(f):self.assertAlmostEqual((float(o[f])/float(old[f])-1)*100,o['value'],places=10)
   if s['methodId']=='REAL_RETAIL_BEA':self.assertEqual(s['legacyStatus'],'unavailable_unconnected');self.assertTrue(all(o['status']!='published' for o in obs))
  # Reject mixing frequency/adjustment before calculating.
  entries=[dict(s,seasonal='NSA') if s['id']==r.GOODS else s for s in c['series']]
  with self.assertRaisesRegex(ValueError,'SA月次'):r.compute(entries)
if __name__=='__main__':
 import tempfile,gzip
 site=ROOT/'site';release=json.loads((site/'release.json').read_text());load=lambda k:json.loads(gzip.decompress((site/release[k]).read_bytes()))
 c=load('catalog');index=load('seriesIndex');approved={s['id']:s for s in c['series']}
 ids=set(x for s in c['series'] if s['id'].startswith('realretail:') for x in s['inputs'])|{'retail:441:SA','retail:444:SA','retail:447:SA','retail:retail:SA','retail:722:SA'}
 with tempfile.TemporaryDirectory() as work:
  e.initialize(work,approved);e.write(e.CACHE/'catalog.json',c)
  for sid in ids:e.write(e.SERIES/e.key(sid),json.loads(gzip.decompress((site/index[sid]).read_bytes())))
  result=unittest.main(exit=False).result
  sys.exit(not result.wasSuccessful())
