"""Regression checks for the public/private data boundary."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import publication as p

class PublicationTests(unittest.TestCase):
 def setUp(self):
  self.base={'id':'bls:test','provider':'BLS','source':'https://www.bls.gov/test','definition':'test','unit':'thousands','inputs':[],'latest':{'value':123}}
  self.derived={**self.base,'id':'derived:test','inputs':['bls:test']}
  self.registry={'series':{s['id']:['bls',p.signature(s)] for s in (self.base,self.derived)}}
 def select(self,rows):
  with patch.object(p,'registry',return_value=self.registry):return p.select({'series':rows})
 def test_new_series_is_not_published_automatically(self):
  c,d=self.select([self.base,{**self.base,'id':'bls:new'}]);self.assertEqual([s['id'] for s in c['series']],['bls:test']);self.assertEqual(d[-1]['decision'],'held_for_review')
 def test_revisions_are_allowed_but_changed_ownership_is_not(self):
  c,_=self.select([{**self.base,'latest':{'value':456}}]);self.assertEqual(c['series'][0]['latest']['value'],456)
  for updates in ({'provider':'Other'},{'source':'https://private.example/data'},{'definition':'different series'},{'inputs':['ism:test']}):
   c,_=self.select([{**self.base,**updates}]);self.assertFalse(c['series'])
 def test_blocked_input_also_blocks_derived_values(self):
  c,_=self.select([{**self.base,'provider':'Other'},self.derived]);self.assertFalse(c['series'])
 def test_references_are_filtered_without_mutating_original(self):
  original={**self.base,'relatedSeries':[{'id':'ism:test','latest':{'value':999}},{'id':'bls:test'}]};before=copy.deepcopy(original)
  c,_=self.select([original]);self.assertEqual(c['series'][0]['relatedSeries'],[{'id':'bls:test'}]);self.assertEqual(original,before)
 def test_explicit_restrictions_and_pending_are_distinct(self):
  _,d=self.select([{'id':'ism:headline','page':'ism'},{'id':'sp:headline','page':'sp'},{'id':'adp:test','provider':'ADP'}]);self.assertEqual([x['decision'] for x in d],['permission_required','permission_required','held_for_review'])
 def test_calendar_does_not_keep_restricted_reflection(self):
  c={'events':[{'source':'https://www.bls.gov/schedule'},{'source':'https://www.ismworld.org/calendar','reflection':{'value':123}}],'sources':[]}
  self.assertEqual(len(p.calendar_scope(c)['events']),1)

if __name__=='__main__':unittest.main()
