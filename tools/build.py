"""Build a standalone Pages snapshot, without editing the local dashboard.

Run from any directory with Python 3 (openpyxl/lxml are only needed to read
the existing dashboard's catalog helpers). Never uploads or calls providers.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
import zipfile
import publication
import version_assets

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_KEYS = {'localFile', 'localPath', 'token', 'access_token', 'password', 'api_key'}
LOCAL_PATH = re.compile(r'(?:/Users/|/private/var/|/var/folders/|/Applications/)[^\s\"\'<>]*')


def sanitize(value):
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if k not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return LOCAL_PATH.sub('[ローカルパス省略]', value)
    return value


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('元画面が変更されています。公開版の変換を確認してください: ' + old[:90])
    return text.replace(old, new, 1)


def patch_frontend(stage):
    p = stage / 'app.js'
    text = p.read_text()
    old = next(line for line in text.splitlines() if line.startswith('async function request('))
    text = replace_once(text, old, '')
    text = "import {request} from './static-api.mjs';\n" + text
    text = replace_once(text, "setInterval(getStatus,10000);", '')
    text = replace_once(text, "'↻ 公式データを更新'", "'↻ 公開データを再読込'")
    text = replace_once(text, '`公式確認 ${when(status.lastOfficial)}`', '`公開用データ作成 ${when(status.lastOfficial)}`')
    text = replace_once(text, "'economic-note-v2'", "'economic-note-pages-v2'") if text.count("'economic-note-v2'") == 1 else text.replace("'economic-note-v2'", "'economic-note-pages-v2'")
    p.write_text(text)
    p = stage / 'index.html'
    text = p.read_text().replace('href="/"', 'href="./"')
    text = text.replace('自分のMacで見る米国経済統計。', '米国経済統計の公開用スナップショット。')
    text = text.replace('このMacのみ', '公開用データ').replace('ローカル保存の統計データ', '端末内で比較・分析')
    text = text.replace('保存済みExcelの変更は自動で反映されます。', '公開データの作成時点の保存値です。更新には再公開が必要です。')
    text = text.replace('<main>', '<main><p class="notice pages-note">公開用スナップショット：元の統計データは公開者が更新・再公開します。お気に入りはこのブラウザ内に保存され、他の人とは共有されません。<a href="publication-scope.html">公開範囲・出典・除外理由</a></p>', 1)
    text = text.replace('id="workbook-link"', 'id="workbook-link" hidden').replace('class="automation"', 'class="automation" hidden')
    text = text.replace('</head>', '<link rel="stylesheet" href="pages.css"></head>')
    p.write_text(text)
    p = stage / 'explorer-ui.mjs'
    text = p.read_text()
    text = replace_once(text, "$('#ex-intro').textContent=descriptions[p];", "root.dataset.publicEmpty=String(!catalog.series.some(s=>belongsToPage(s,p)&&s.count));$('#ex-intro').textContent=descriptions[p]+' 公開版は確認済みの系列のみ収録しています。対象外の系列は上部の「公開範囲・出典・除外理由」を参照してください。';")
    text = replace_once(text, "$('#ex-presets').innerHTML=list.map", "$('#ex-presets').innerHTML=list.filter(p=>p[1].some(id=>catalog.series.some(s=>s.id===id&&s.count))).map")
    # Preserve original indexes after filtering preset buttons.
    text = text.replace('data-ex-preset="${i}"', 'data-ex-preset="${list.indexOf(p)}"')
    p.write_text(text)
    p = stage / 'update-report.mjs'
    text = p.read_text()
    text = replace_once(text, 'export function reportHTML(r){', "export function reportHTML(r){\n if(r?.mode==='snapshot')return '<p>公開者が保存したデータのスナップショットです。元のサイトの更新ログは掲載していません。公開範囲・出典はページ上部のリンクから確認できます。</p>';")
    text = text.replace('report?`今回の更新内容', "report?.mode==='snapshot'?'公開データについて':report?`今回の更新内容")
    p.write_text(text)
    p = stage / 'calendar-ui.mjs'
    text = p.read_text().replace('公式データを更新', '公開データを再読込').replace('発表予定を再取得', '公開済みの予定を再読込')
    text = text.replace('「公開済みの予定を再読込」で公式カレンダーを確認できます。取得失敗時は以前の予定を保持し、その確認日を表示します。自動更新の設定は変更しません。', '公開者が保存した予定を表示します。「公開済みの予定を再読込」はサイトの再読込です。最新の日程は各公式リンクで確認してください。')
    p.write_text(text)
    p = stage / 'analysis-ui.mjs'
    text = p.read_text().replace("'保存しました：'+r.name", "'このブラウザに保存しました：'+r.name").replace('をこのMacに保存します。', 'をこのブラウザ内に保存します。他の端末とは同期しません。')
    p.write_text(text)
    p = stage / 'chart-export.mjs'
    text = p.read_text()
    old = next(line for line in text.splitlines() if line.startswith('export async function downloadChart('))
    new = """export async function downloadChart(svg,format,getToken){
 await document.fonts.ready;const image=buildChartImage(svg);
 const blob=format==='svg'?new Blob([image.source],{type:'image/svg+xml;charset=utf-8'}):format==='pdf'?await chartPdf(image):await png(image);
 const name=filename(image.title,format),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),600000);return {url,name};
}"""
    p.write_text("import {chartPdf} from './static-pdf.mjs';\n" + replace_once(text, old, new))


def build(source):
    source = source.resolve()
    if source == ROOT or ROOT in source.parents or source in ROOT.parents:
        raise ValueError('元サイトと公開版は別フォルダにしてください。')
    if not (source / 'data/manifest.json').is_file():
        raise ValueError('元サイトの保存データが見つかりません。')
    state = json.loads((source / 'data/state.json').read_text())
    if state.get('running'):
        raise ValueError('公式データの更新中です。更新完了後に実行してください。')
    private = ROOT / '.private'
    private.mkdir(exist_ok=True)
    backup = private / 'original-source.zip'
    if not backup.exists():
        with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted([*source.glob('*.py'), *source.glob('dist/*'), source / 'data/analysis-favorites.json']):
                if p.is_file(): z.write(p, p.relative_to(source))
    stage = ROOT / '.build-next'
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir()
    seen = {}

    def read(path):
        raw = path.read_bytes()
        seen[path] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    for p in (source / 'dist').iterdir():
        if p.suffix in {'.html', '.js', '.mjs', '.css'}:
            raw = p.read_bytes()
            seen[p] = hashlib.sha256(raw).hexdigest()
            (stage / p.name).write_bytes(raw)
    patch_frontend(stage)
    for p in (ROOT / 'templates').iterdir():
        if p.is_file(): shutil.copy2(p, stage / p.name)
    (stage / '.nojekyll').touch()
    (stage / 'data').mkdir()
    compressed_bytes = uncompressed_bytes = observations = 0

    def emit(value):
        nonlocal compressed_bytes, uncompressed_bytes
        raw = encoded(sanitize(value))
        key = hashlib.sha256(raw).hexdigest()
        name = 'data/' + key + '.json.gz'
        path = stage / name
        if not path.exists():
            packed = gzip.compress(raw, compresslevel=6, mtime=0)
            path.write_bytes(packed)
            compressed_bytes += len(packed)
            uncompressed_bytes += len(raw)
        return name

    manifest = read(source / 'data/manifest.json')
    catalog = read(source / 'data/explorer/catalog.json')
    original_catalog = catalog
    catalog, decisions = publication.select(catalog)
    allowed = {s['id'] for s in catalog['series']}
    datasets = {d['id']: read(source / 'data' / (d['id'] + '.json')) for d in manifest['datasets']}
    publication.check_datasets(datasets)
    release = {'format': 1, 'builtAt': datetime.now(timezone.utc).isoformat(), 'datasets': {k: emit(v) for k, v in datasets.items()}}
    release['manifest'] = emit(manifest)
    release['catalog'] = emit(catalog)
    # Local update logs may contain excluded values, including old vintages.
    release['updateReport'] = emit({'id': 'public-snapshot', 'startedAt':release['builtAt'], 'finishedAt':release['builtAt'], 'mode':'snapshot', 'changed':[], 'unchanged':[], 'failures':[], 'counts':{}})
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source))
    import analysis_data
    import release_calendar
    analysis = analysis_data.catalog()
    analysis['series'] = [s for s in analysis['series'] if (s['id'].startswith('ex:') and s['id'][3:] in allowed) or (s['id'].startswith('wb:') and s['descriptor'][0] in datasets)]
    release['analysisCatalog'] = emit(publication.clean(analysis, allowed))
    # Also compute the after-scheduled-time status now, so the browser can
    # distinguish a future event from its actual cached coverage as time passes.
    calendar = release_calendar.payload(cache=source / 'data')
    future = release_calendar.payload(cache=source / 'data', current=datetime(2200, 1, 1, tzinfo=timezone.utc))
    after = {e['id']: e['reflection'] for e in future['events']}
    for event in calendar['events']: event['afterDue'] = after[event['id']]
    release['calendar'] = emit(publication.calendar_scope(calendar))
    read(source / 'data/calendar.json')
    index = {}
    for i, m in enumerate(catalog['series']):
        sid = m['id']
        if sid in index: raise ValueError('系列IDが重複しています: ' + sid)
        if m.get('alias'):
            a = m['alias']; d = datasets[a['dataset']]
            s = next(s for s in d['series'] if s['id'] == a['series'])
            from expansion import obs
            value = dict(m, observations=[obs(date + '-01', v) for date, v in zip(d['dates'], (s['values'][a['metric']] if a.get('metric','level')!='level' else s['bases'][a['season']]))])
        else:
            p = source / 'data/explorer/series' / (hashlib.sha256(sid.encode()).hexdigest() + '.json')
            value = dict(read(p), status=m['status'], error=m.get('error')) if p.exists() else dict(m, observations=[])
        value = publication.clean(value, allowed)
        observations += sum(o.get('value') is not None for o in value['observations'])
        index[sid] = emit(value)
        if (i + 1) % 5000 == 0: print(f'{i + 1:,} 系列を整理済み', flush=True)
    release['seriesIndex'] = emit(index)
    scope = publication.write_report(stage, decisions, release['builtAt'])
    # Keep the existing cloud schedule/status when rebuilding a manual snapshot.
    old_release_path=ROOT/'site/release.json'
    previous_release=json.loads(old_release_path.read_text()) if old_release_path.exists() else {}
    for key in ('cloudUpdate','numericalRepair'):
        if key in previous_release:release[key]=previous_release[key]
    if release.get('cloudUpdate'):
        status_page=ROOT/'site/update-status.html'
        if status_page.exists():shutil.copy2(status_page,stage/'update-status.html')
        page=stage/'index.html'
        page.write_text(page.read_text().replace('公開用スナップショット：元の統計データは公開者が更新・再公開します。','毎朝4時（日本時間）に公式データを自動取得し、検証後に公開します。').replace('公開データの作成時点の保存値です。更新には再公開が必要です。','公開データの作成時点の保存値です。毎朝4時（日本時間）に自動更新を開始します。').replace('<a href="publication-scope.html">','<a href="update-status.html">自動更新の結果</a> · <a href="publication-scope.html">'))
    release['publicationPolicy'] = 'reviewed-only'
    release['revision'] = hashlib.sha256(encoded(release)).hexdigest()
    (stage / 'release.json').write_bytes(encoded(release))
    frontend_version = version_assets.version_site(stage)
    report = {'builtAt': release['builtAt'], 'datasets': len(datasets), 'explorerSeries': len(index), 'observations': observations,
              'dataBytesBeforeCompression': uncompressed_bytes, 'dataBytesAfterCompression': compressed_bytes,
              'siteBytes': sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()),
              'sourceUnchanged': True, 'publicationCounts':scope['counts'], 'excluded': ['原Excel', '生の取得ファイル', '改定履歴の保管庫', '更新ログ', '個人のお気に入り', 'ローカル設定・トークン', '調査資料'],
              'mode': 'snapshot', 'automaticProviderUpdates': bool(release.get('cloudUpdate')), 'frontendVersion': frontend_version}
    # Fail rather than publish a mixed snapshot if a live update changed input.
    for p, digest in seen.items():
        if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError('作成中に元データが変わりました。元サイトは変更していません。再実行してください。')
    if report['siteBytes'] >= 950_000_000: raise ValueError('公開容量が950MBを超えました。公開する範囲を再確認してください。')
    (private / 'source-checksums.json').write_bytes(encoded({str(p): d for p, d in seen.items()}))
    previous = ROOT / '.site-previous'
    if previous.exists(): shutil.rmtree(previous)
    if (ROOT / 'site').exists(): (ROOT / 'site').rename(previous)
    stage.rename(ROOT / 'site')
    (ROOT / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'publication-report.json').write_text(json.dumps(scope, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent / 'economic-dashboard')
    build(parser.parse_args().source)
