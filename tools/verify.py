"""Offline verification of the complete Pages artifact (standard library only)."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import sys
import publication

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT, source=False):
    site = root / 'site'
    report = json.loads((root / 'build-report.json').read_text())
    release = json.loads((site / 'release.json').read_text())
    forbidden = re.compile(rb'/Users/|/private/var/|/var/folders/|"(?:localFile|localPath|access_token|api_key|password|token)"\s*:')
    files = [p for p in site.rglob('*') if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    assert total < 950_000_000, '公開容量が上限に近すぎます。'
    assert total == report['siteBytes'], '作成後に公開ファイルの容量が変わっています。'
    decoded = {}
    # Verify every data file, not just the charts selected by default.
    for p in files:
        assert not p.is_symlink(), '公開物にリンクが含まれています。'
        assert p.stat().st_size < 99_000_000, 'GitHubの単一ファイル上限に近すぎます。'
        raw = p.read_bytes()
        if p.suffix == '.gz':
            raw = gzip.decompress(raw)
            assert hashlib.sha256(raw).hexdigest() == p.name.removesuffix('.json.gz'), 'データのハッシュが一致しません。'
            assert not forbidden.search(raw), 'ローカル情報が含まれています。'
            obj = json.loads(raw, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
            if 'observations' in obj:
                assert isinstance(obj['observations'], list)
                assert all(o.get('value') is None or isinstance(o['value'], (int, float)) for o in obj['observations'])
            decoded[p.relative_to(site).as_posix()] = (obj.get('id'), sum(o.get('value') is not None for o in obj.get('observations', []))) if isinstance(obj, dict) else (None, 0)
        else:
            assert p.name in {'release.json','.nojekyll'} or p.suffix in {'.html','.js','.mjs','.css'}, '公開対象外のファイル: ' + p.name
            assert not forbidden.search(raw), 'ローカル情報が含まれています。'

    def load(path):
        assert re.fullmatch(r'data/[a-f0-9]{64}\.json\.gz', path), '不正な参照です。'
        assert path in decoded, '参照先がありません: ' + path
        return json.loads(gzip.decompress((site / path).read_bytes()))

    catalog = load(release['catalog'])
    index = load(release['seriesIndex'])
    assert release.get('publicationPolicy') == 'reviewed-only', '公開範囲の検査がありません。'
    selected, decisions = publication.select(catalog)
    assert len(selected['series']) == len(catalog['series']), '未承認系列が含まれています。'
    scope = json.loads((root/'publication-report.json').read_text())
    assert {d['id'] for d in scope['series'] if d['decision']=='included'} == set(index)
    assert scope['counts'] == report['publicationCounts']
    assert set(index) == {s['id'] for s in catalog['series']}
    assert len(index) == report['explorerSeries']
    observations = 0
    for sid, path in index.items():
        assert path in decoded and decoded[path][0] == sid, '系列とファイルの対応が不一致です。'
        observations += decoded[path][1]
    assert observations == report['observations']
    manifest = load(release['manifest'])
    assert set(release['datasets']) == {d['id'] for d in manifest['datasets']}
    for sid, path in release['datasets'].items(): assert load(path)['id'] == sid
    publication.check_datasets({sid:load(path) for sid,path in release['datasets'].items()})
    analysis = load(release['analysisCatalog'])
    for s in analysis['series']:
        if s['id'].startswith('ex:'): assert s['id'][3:] in index
        else: assert s['descriptor'][0] in release['datasets']
    calendar=load(release['calendar']); assert calendar == publication.calendar_scope(calendar)
    updates=load(release['updateReport'])
    if updates.get('format')==2:
        workbook_keys={json.dumps([d['id'],s['name'],m],ensure_ascii=False) for ds,path in release['datasets'].items() for d in [load(path)] for s in d['series'] for m in s.get('bases' if d['kind']=='base' else 'values',{})}
        def public_key(key):
            if key.startswith('explorer:'):return key[9:] in index
            return key in workbook_keys
        assert all(public_key(k) for k in updates['checks']), '非公開系列の改定チェック混入'
        assert all(public_key(s['id']) for s in updates['changed']), '非公開系列の改定混入'
        assert all(k in updates['checks'] for k in updates['lookup'].values())
        assert all(len(h)==64 for h in updates['checks'].values())
    else:assert not any(updates[k] for k in ('changed','unchanged','failures'))
    referenced=set(index.values()) | set(release['datasets'].values()) | {release[k] for k in ('manifest','catalog','analysisCatalog','calendar','updateReport','seriesIndex')}
    assert set(decoded)==referenced, '参照されない古いデータファイルが残っています。'
    if source:
        checks = json.loads((root / '.private/source-checksums.json').read_text())
        for name, digest in checks.items():
            assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, '元サイトの入力が作成後に変更されています: ' + name
    print(json.dumps({'result':'PASS','siteMB':round(total/1_000_000,2),'explorerSeries':len(index),
                      'analysisSeries':len(analysis['series']),'observations':observations,
                      'files':len(files),'sourceChecked':source},ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-unchanged',action='store_true')
    verify(source=parser.parse_args().source_unchanged)
