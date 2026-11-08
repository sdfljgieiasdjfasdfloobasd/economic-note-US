"""Offline integration check: one official CSV, four approved series, safe failures."""
from pathlib import Path
import sys,tempfile,copy
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
import expansion as e,indeed_source as src,refresh,publication
head='date,jobcountry,indeed_job_postings_index_SA,indeed_job_postings_index_NSA,variable\n'
blob=(head+'2020-02-01,US,100,100,total postings\n2020-02-01,US,100,100,new postings\n2026-10-30,US,103.79,109.16,total postings\n2026-10-30,US,99.03,97.29,new postings\n').encode()
records=src.parse(blob);approved={s['id']:s for s in records}
assert all(publication.registry()['series'][s['id']]==['indeed',publication.signature(s)] for s in records)
with tempfile.TemporaryDirectory() as tmp:
 e.initialize(tmp,approved)
 for s in records:e.write(e.SERIES/e.key(s['id']),s)
 with patch.object(e,'get',return_value=blob) as get:
  assert len(src.update())==4;assert get.call_count==1
 before={p.name:p.read_bytes() for p in e.SERIES.iterdir()}
 with patch.object(e,'get',side_effect=RuntimeError('HTTP 429')) as get:
  try:src.update();raise AssertionError('failure swallowed')
  except RuntimeError:pass
  assert get.call_count==1
 assert before=={p.name:p.read_bytes() for p in e.SERIES.iterdir()}
 with patch.object(e,'get',return_value=blob.replace(b'103.79',b'103.80')):
  src.update()
 assert e.load_series('indeed:total:SA')['observations'][-1]['raw']=='103.80'
 assert 'indeed' in dict(refresh.jobs({}, {'series':list(approved.values())}, []))
print('PASS Indeed: approval signatures, one fetch, revisions, safe failure, cloud schedule integration')
