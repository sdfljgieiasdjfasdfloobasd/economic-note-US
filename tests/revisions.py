"""Offline end-to-end public update: revisions, rollback and publication checks."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
import refresh as r,expansion as e,publication
class PublicRevisions(unittest.TestCase):
 def test_finalized_revision_report_uses_only_committed_public_values(self):
  source=ROOT/'site';release=r.read(source/'release.json');cat=r.load(source,release['catalog']);idx=r.load(source,release['seriesIndex'])
  metadata=[s for s in cat['series'] if s['id'].startswith('nyfed:')][:2]
  self.assertEqual(len(metadata),2)
  originals=[r.load(source,idx[s['id']]) for s in metadata]
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);site=root/'site';site.mkdir();catalog={'series':metadata};_,decisions=publication.select(catalog)
   scope=publication.write_report(site,decisions,e.now());r.write(root/'publication-report.json',scope)
   old={'publicationPolicy':'reviewed-only','datasets':{}}
   values={'catalog':catalog,'seriesIndex':{s['id']:r.emit(site,s) for s in originals},'manifest':{'datasets':[],'cards':[]},'analysisCatalog':{'series':[]},'calendar':publication.calendar_scope({'events':[],'sources':[]}), 'updateReport':{'changed':[],'unchanged':[],'failures':[]}}
   for key,value in values.items():old[key]=r.emit(site,value)
   r.write(root/'build-report.json',{'publicationCounts':scope['counts'],'explorerSeries':2})
   e.initialize(root/'work',{m['id']:m for m in metadata})
   revised=copy.deepcopy(originals[0]);row=revised['observations'][-1];before=row['value'];row.update(value=before+.125,raw=str(before+.125))
   # A rejected download's candidate value must not appear in the report.
   failed=copy.deepcopy(originals[1]);failed['observations'][-1]['value']=999
   for s in [revised,failed]:e.write(e.SERIES/e.key(s['id']),s)
   e.ATTEMPTED.add(revised['id'])
   failures={failed['id']:{**metadata[1],'status':'fetch_failed','error':'fixture download failure'}}
   r.finalize(root,old,{},catalog,failures,[{'source':'fixture','status':'failed','reason':'fixture download failure'}],e.now(),['fixture'])
   new=r.read(site/'release.json');report=r.load(site,new['updateReport'])
   self.assertEqual(report['format'],2);self.assertEqual(report['counts']['revised'],1);self.assertEqual(report['counts']['failed'],1)
   self.assertEqual(report['changed'][0]['details'][0]['before'],before)
   self.assertEqual(report['changed'][0]['details'][0]['after'],before+.125)
   self.assertEqual(set(report['checks']),{'explorer:'+s['id'] for s in originals})
   self.assertNotIn('explorer:'+failed['id'],[c['id'] for c in report['changed']])
   saved_idx=r.load(site,new['seriesIndex']);self.assertEqual(r.load(site,saved_idx[failed['id']])['observations'],originals[1]['observations'])
if __name__=='__main__':unittest.main()
