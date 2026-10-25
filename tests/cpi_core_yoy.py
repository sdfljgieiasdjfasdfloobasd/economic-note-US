"""Offline cloud integration: public inputs, signature gate, revisions and missing inputs."""
import copy,gzip,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
import expansion as e
from cpi_nsa_contributions import build_series,update,PREFIX
rel=json.loads((ROOT/'site/release.json').read_text())
def load(p):return json.loads(gzip.decompress((ROOT/'site'/p).read_bytes()))
ds={k:load(p) for k,p in rel['datasets'].items()}
cat=load(rel['catalog']);expected={s['id']:s for s in cat['series'] if s['id'].startswith(PREFIX)}
assert len(expected)>100
# All observations agree with the packaged public inputs.
index=load(rel['seriesIndex']);generated=build_series(ds)
for s in generated:assert s['observations']==load(index[s['id']])['observations'],s['id']
with tempfile.TemporaryDirectory() as tmp:
 sid=PREFIX+'267'
 e.initialize(tmp,{sid:expected[sid]})
 def forbidden(*a,**kw):raise AssertionError('no network calls are allowed')
 e.get=forbidden
 result=update(ds);assert [s['id'] for s in result]==[sid]
 original=e.load_series(sid)['observations'][-1]['value'];assert original is not None
 changed=copy.deepcopy(ds)
 row=next(r for r in changed['cpi_detail']['series'] if r['id']=='267')
 row['bases']['NSA'][-1]+=1
 update(changed);assert e.load_series(sid)['observations'][-1]['value']!=original
 # Do not retain the old estimate when a required input disappears.
 row['bases']['NSA'][-1]=None
 update(changed);assert e.load_series(sid)['observations'][-1]['value'] is None
 # Never emit unapproved new series in a scheduled update.
 assert len(list(e.SERIES.glob('*.json')))==1
 expected_bad={**expected[sid],'definition':'different formula'}
 e.APPROVED={sid:expected_bad}
 try:update(ds)
 except ValueError:pass
 else:raise AssertionError('changed definition accepted')
print('PASS: public input parity, offline recomputation, revised/missing inputs and publication signature gate')
