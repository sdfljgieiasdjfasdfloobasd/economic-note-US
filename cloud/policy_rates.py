"""FOMC target range midpoint. One combined official CSV; no credentials."""
import csv
import io
import json
from datetime import date
from decimal import Decimal
import expansion as e

ID = 'policy:target-midpoint'
URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARL%2CDFEDTARU&cosd=2008-12-16'
LABEL = '米国政策金利（目標レンジ中央）'


def parse(blob):
    rows = csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
    if not {'DFEDTARL', 'DFEDTARU'}.issubset(rows.fieldnames or []):
        raise ValueError('政策金利CSVの上限・下限の列を確認できません')
    observations = []
    for row in rows:
        day = row.get('observation_date', row.get('DATE'))
        date.fromisoformat(day)
        lo, hi = e.dec(row['DFEDTARL']), e.dec(row['DFEDTARU'])
        for column in ['DFEDTARL', 'DFEDTARU']:
            if row[column] not in ('', '.', 'NA') and e.dec(row[column]) is None:
                raise ValueError('政策金利CSVに不正な値があります')
        value = None
        if lo is not None and hi is not None:
            if Decimal(lo) > Decimal(hi):
                raise ValueError('政策金利の上下限が逆転しています')
            value = (Decimal(lo) + Decimal(hi)) / 2
        observations.append(e.obs(day, value, 'calculated', lowerRaw=lo, upperRaw=hi))
    if len({r['date'] for r in observations}) != len(observations):
        raise ValueError('政策金利の観測日が重複しています')
    return dict(id=ID, label=LABEL, page='analysis', category='共通比較・政策金利',
                publicationId='fed-policy', publicationLabel='FRB / 政策金利（目標レンジ中央）',
                provider='Board of Governors of the Federal Reserve System / FRED',
                frequency='Daily', seasonal='非該当', unit='%', sourceMetric='政策金利',
                source='https://fred.stlouisfed.org/series/DFEDTARU', download=URL,
                sourceSeriesCodes=['DFEDTARL', 'DFEDTARU'],
                definition='同一日のFOMC目標レンジ下限と上限の単純平均。(DFEDTARL + DFEDTARU) / 2。日次・暦日。当日有効な金利。片側欠損は空欄。2008年12月16日より前の単一目標金利とは連結しません。実効FF金利やFOMC見通しの中央値とは別です。',
                attribution='Source: Board of Governors of the Federal Reserve System, Federal Funds Target Range [DFEDTARL, DFEDTARU], via FRED. Public Domain: Citation Requested. https://fred.stlouisfed.org/series/DFEDTARL https://fred.stlouisfed.org/series/DFEDTARU Midpoint calculated by this site.',
                observations=sorted(observations, key=lambda r:r['date']))


def update():
    try:
        series = parse(e.get(URL))
        path = e.SERIES / e.key(ID)
        if path.exists():
            old = json.loads(path.read_text())
            previous = {r['date'] for r in old['observations'] if r['value'] is not None}
            current = {r['date'] for r in series['observations'] if r['value'] is not None}
            if previous and (not current or min(current) > min(previous) or max(current) < max(previous)):
                raise ValueError('取得履歴が短くなったため保存値を保持します')
        return [e.save(series)]
    except Exception as error:
        return [e.failure(ID, LABEL, 'analysis', '共通比較・政策金利',
                          'https://fred.stlouisfed.org/series/DFEDTARU', error,
                          'Board of Governors of the Federal Reserve System / FRED')]
