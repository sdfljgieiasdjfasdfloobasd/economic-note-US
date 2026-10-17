"""Census retail sales: defined monthly levels, coherent vintages, audited changes.

Bulk metadata is the series universe. Release-table columns are never series IDs.
MRTS is canonical for the detail history. MARTS only extends it when *all*
overlapping levels agree; incompatible releases are never spliced together.
"""
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from datetime import datetime
from decimal import Decimal, localcontext
from urllib.parse import urljoin

from lxml import html
import expansion as e

PAGE = 'https://www.census.gov/retail/sales.html'
BULK = 'https://www.census.gov/econ_getzippedfile/?programCode='
EXAUTO = 'https://www.census.gov/retail/marts/www/adv4400A.txt'
# Preserve existing stable IDs (favorites, comparisons and derived series).
CODES = {'44X72':'total', '44Y72':'exauto', '44Z72':'exgas', '44W72':'exautogas',
         '44000':'retail', '4400A':'Retail sales, total (excl. motor vehicle and parts dealers)',
         '4400C':'GAFO(1)', '441X':'4411,4412', '4423X':'442,443',
         '72251X':'722513, 722514, 722515'}
SUPPRESSION = 'Censusの公表基準による非公表（S）。標本誤差・回答品質等の基準によるもので、取得失敗やゼロではありません。'


def previous(date):
    year, month = map(int, date[:7].split('-'))
    return f'{year - (month == 1)}-{12 if month == 1 else month - 1:02d}-01'


def change(current, prior):
    if current is None or prior is None or Decimal(prior) == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 50
        return format((Decimal(current) - Decimal(prior)) * 100 / Decimal(prior), 'f')


def bulk_parse(blob, program):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        text = archive.read(program + '-mf.csv').decode('utf-8-sig')
    parts = {p.splitlines()[0]:p.splitlines()[1:] for p in re.split(r'\n\s*\n', text.replace('\r\n','\n')) if p.strip()}
    def table(name, key):
        return {r[key]:r for r in csv.DictReader(parts[name])}
    cats = table('CATEGORIES', 'cat_idx')
    types = table('DATA TYPES', 'dt_idx')
    geos = table('GEO LEVELS', 'geo_idx')
    dates = {k:datetime.strptime(v['per_name'], '%b-%Y').strftime('%Y-%m-01') for k,v in table('TIME PERIODS','per_idx').items()}
    vintage = parts['DATA UPDATED ON'][0].strip()
    digest = hashlib.sha256(blob).hexdigest()
    series, rates = {}, {}
    for row in csv.DictReader(parts['DATA']):
        if row['et_idx'] != '0' or geos[row['geo_idx']]['geo_code'] != 'US':
            continue  # Sampling errors and non-US geography are not sales levels.
        typ = types[row['dt_idx']]
        if typ['dt_code'] not in ('SM','MPCSM'):
            continue  # MRTS also contains inventories and inventory/sales ratios.
        if row['is_adj'] not in ('0','1'):
            raise ValueError('Census seasonal flag changed')
        cat = cats[row['cat_idx']]
        code = cat['cat_code']
        sid = 'retail:' + CODES.get(code, code) + (':SA' if row['is_adj']=='1' else ':NSA')
        date, raw = dates[row['per_idx']], e.dec(row['val'])
        if typ['dt_code']=='MPCSM':
            if raw is not None: rates.setdefault(sid,{})[date] = raw
            continue
        if typ['dt_unit'] != 'MLN$':
            raise ValueError('Census sales units changed: '+typ['dt_unit'])
        if row['val'] not in ('(S)','NA','(NA)','') and raw is None:
            raise ValueError('Unknown Census value marker: '+row['val'])
        s = series.setdefault(sid, dict(id=sid, officialId=code, label=cat['cat_desc'].split(': ',1)[-1],
            seasonal='SA' if row['is_adj']=='1' else 'NSA', observations={}))
        if date in s['observations']:
            raise ValueError('Duplicate Census series/month: '+sid+' '+date)
        reason = 'suppressed' if row['val']=='(S)' else 'not_available' if raw is None else None
        s['observations'][date] = e.obs(date,raw,'suppressed' if reason=='suppressed' else 'published',
            source=BULK+program, sourceVintage=vintage, sourceSha256=digest,
            sourceMarker=row['val'] if raw is None else None, missingReason=reason)
    if not series or not rates:
        raise ValueError('Census bulk format contains no sales/changes')
    return dict(series=series, rates=rates, vintage=vintage, sha256=digest)


def text_parse(blob):
    """Only first (sales) table; never read the second seasonal-factor table."""
    result, in_table = {}, False
    for line in blob.decode('utf-8-sig').splitlines():
        if re.match(r'^YEAR\s+JAN\s+FEB', line):
            if in_table: break
            in_table = True
            continue
        if not in_table: continue
        if re.match(r'^\d{4}\s', line):
            # Fixed-width cells preserve internal missing months.
            year = int(line[:4])
            for month in range(1,13):
                cell = line[4+(month-1)*10:4+month*10].strip()
                if cell:
                    raw = e.dec(cell)
                    if raw is None: raise ValueError('Invalid Census text sales cell: '+cell)
                    result[f'{year}-{month:02d}-01'] = raw
    if not result: raise ValueError('Census text sales table not found')
    return result


def verify_rates(series, official, source):
    comparisons, warnings, per_series = 0, [], {}
    for sid,s in series.items():
        checks=[]
        for date,row in sorted(s['observations'].items()):
            rate = change(row['raw'],s['observations'].get(previous(date),{}).get('raw'))
            published = official.get(sid,{}).get(date)
            if rate is None or published is None: continue
            diff = abs(Decimal(rate)-Decimal(published))
            checks.append(date); comparisons += 1
            if diff >= Decimal('0.05'):
                # Exact half-tenths can round either way in Census's 1dp field.
                reason = '公式の小数第1位への丸め境界（差がちょうど0.05ポイント）' if abs(diff-Decimal('.05')) < Decimal('1e-40') else '公式前月比との不一致。公表精度・定義・改定時点の確認が必要'
                warnings.append(dict(series=sid,date=date,calculated=rate,official=published,difference=str(diff),reason=reason,source=source))
        if checks:
            per_series[sid] = dict(count=len(checks),first=checks[0],last=checks[-1],recentChecks=checks[-25:])
    return dict(comparisons=comparisons,seriesCount=len(per_series),perSeries=per_series,warnings=warnings)


def assemble(mrts_blob, marts_blob, workbook, workbook_url, extra_blob):
    from macro_sources import item, retail_parse
    mrts, marts = bulk_parse(mrts_blob,'MRTS'), bulk_parse(marts_blob,'MARTS')
    series = mrts['series']
    detail_month = max(d for s in series.values() for d in s['observations'])
    # Independently parse Excel and compare every numeric cell to bulk series.
    excel = retail_parse(workbook,workbook_url)
    excel_checks=0
    if {s['id'] for s in excel} != set(series):
        raise ValueError('MRTS Excel/bulk series definitions differ; publication held for review')
    for s in excel:
        for row in s['observations']:
            if row['raw'] is None: continue
            other=series[s['id']]['observations'].get(row['date'],{}).get('raw')
            if other is None or Decimal(row['raw']) != Decimal(other):
                raise ValueError('MRTS Excel/bulk vintage or value mismatch: '+s['id']+' '+row['date'])
            excel_checks += 1
    validations=[verify_rates(series,mrts['rates'],BULK+'MRTS'),verify_rates(marts['series'],marts['rates'],BULK+'MARTS')]
    # Validate the complete overlap before mutating anything or saving files.
    overlap=0
    for sid,s in marts['series'].items():
        if sid not in series: raise ValueError('New MARTS category absent from MRTS: '+sid)
        for date,row in s['observations'].items():
            old=series[sid]['observations'].get(date)
            if old is not None:
                if old['raw'] != row['raw']:
                    raise ValueError('MRTS/MARTS改定時点が一致しません。混在を防ぐため保存値を保持: '+sid+' '+date)
                overlap+=1
    extra = text_parse(extra_blob)
    extra_id = 'retail:'+CODES['4400A']+':SA'
    for date,raw in extra.items():
        old=series[extra_id]['observations'].get(date)
        if old and old['raw']!=raw: raise ValueError('Retail ex-auto text/MRTS vintage mismatch: '+date)
    for sid,s in marts['series'].items():
        for date,row in s['observations'].items():
            if date>detail_month:
                series[sid]['observations'][date]=dict(row,status='advance')
    for date,raw in extra.items():
        if date>detail_month:
            # Also reconcile the official aggregate to its underlying published levels.
            retail=series['retail:retail:SA']['observations'].get(date,{}).get('raw')
            auto=series['retail:441:SA']['observations'].get(date,{}).get('raw')
            if retail is None or auto is None or Decimal(retail)-Decimal(auto)!=Decimal(raw):
                raise ValueError('Official retail ex-auto does not reconcile: '+date)
            series[extra_id]['observations'][date]=e.obs(date,raw,'advance',source=EXAUTO,sourceSha256=hashlib.sha256(extra_blob).hexdigest())
    latest = max(d for s in series.values() for d in s['observations'])
    output=[]
    for sid,s in series.items():
        rows=s['observations']
        last=max(rows)
        detail_coverage=rows.get(detail_month,{}).get('missingReason') or 'published'
        if latest not in rows:
            rows[latest]=e.obs(latest,None,'not_yet_published',
                missingReason='not_yet_published',source=BULK+'MRTS')
        coverage=rows[latest].get('missingReason') or 'published'
        note='Census公式の月次売上高水準（百万ドル、物価調整なし）。SA・NSAは別系列。前月比は同一系列の当月÷前月−1で計算。毎回全履歴の改定を反映。親項目と内訳を重複加算しません。'
        if detail_coverage=='suppressed':note+=' 直近の詳細公表月は'+SUPPRESSION
        if coverage=='not_yet_published':note+=f' {latest[:7]}の詳細値は未公表。MRTSは{detail_month[:7]}まで、MARTS速報の対象外です。'
        definition=item('retail',sid[len('retail:'):],s['label'],BULK+'MRTS','Census / Monthly Retail Trade・全業種','million USD',season=s['seasonal'],note=note,officialId=s['officialId'],latestCoverage=coverage,detailCoverage=detail_coverage,latestTargetMonth=latest,detailLatestMonth=detail_month,depth=max(0,len(s['officialId'])-3) if s['officialId'].isdigit() else 0)
        for date,row in sorted(rows.items()):
            row['momRaw']=change(row['raw'],rows.get(previous(date),{}).get('raw'))
            published=(marts['rates'] if date>detail_month else mrts['rates']).get(sid,{}).get(date)
            row['officialMomRaw']=published
            if row['raw'] is not None:row['status']='advance' if date>detail_month else 'published'
            definition['observations'].append(row)
        output.append(definition)
    audit=dict(validSeries=len(output),targetSeries=len(series),detailLatestMonth=detail_month,latestMonth=latest,
        latestCoverage=dict(Counter(s['latestCoverage'] for s in output)),detailCoverage=dict(Counter(s['detailCoverage'] for s in output)),excelLevelComparisons=excel_checks,
        coherentOverlapComparisons=overlap,validations=validations,
        sources={'MRTS':{'url':BULK+'MRTS','vintage':mrts['vintage'],'sha256':mrts['sha256']},'MARTS':{'url':BULK+'MARTS','vintage':marts['vintage'],'sha256':marts['sha256']},'Excel':{'url':workbook_url,'sha256':hashlib.sha256(workbook).hexdigest()},'exAuto':{'url':EXAUTO,'sha256':hashlib.sha256(extra_blob).hexdigest()}},
        missingSeries=[dict(id=s['id'],label=s['label'],reason=s['latestCoverage'],detailReason=s['detailCoverage']) for s in output if s['latestCoverage']!='published'])
    return output,audit


def update():
    """Called by the existing official-update button, without an API key."""
    import time
    page=html.fromstring(e.get(PAGE))
    workbook_url=next(urljoin(PAGE,a.get('href')) for a in page.xpath('//a[@href]') if 'mrtssales' in a.get('href') and a.get('href').endswith('.xlsx'))
    blobs=[]
    for url in (BULK+'MRTS',BULK+'MARTS',workbook_url,EXAUTO):
        time.sleep(1)  # Respect Census's request-rate guidance.
        blobs.append(e.get(url))
    try:
        items,audit=assemble(blobs[0],blobs[1],blobs[2],workbook_url,blobs[3])
    except Exception as error:
        e.write(e.CACHE/'retail-validation-failure.json',dict(checkedAt=e.now(),error=str(error)))
        raise
    warnings=[w for v in audit['validations'] for w in v['warnings']]
    audit.update(checkedAt=e.now(),warningCount=len(warnings))
    e.write(e.CACHE/'retail-validation.json',audit)
    unresolved=[w for w in warnings if '丸め境界' not in w['reason']]
    if unresolved:
        # User requested alerts at >= 0.05 pp; do not silently publish inconsistent data.
        raise ValueError(f'Census公式前月比と0.05ポイント以上の不一致が{len(unresolved)}件。retail-validation.jsonを参照。保存値を保持しました。')
    if warnings:print('retail validation: '+str(len(warnings))+' rounding-boundary warnings; details in retail-validation.json',flush=True)
    return [e.save(s) for s in items]
