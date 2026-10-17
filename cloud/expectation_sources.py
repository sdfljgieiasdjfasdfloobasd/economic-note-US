"""Reviewed SCE and SPF workbook adapters. Shared public downloader/cache only."""
import io
import openpyxl
from expansion import get,workbook_rows,xseries,obs,save
URLS={'nyfed': 'https://www.newyorkfed.org/medialibrary/interactives/sce/sce/downloads/data/frbny-sce-data.xlsx', 'spf_median': 'https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters/historical-data/medianLevel.xlsx'}
def official_excel(which):
    url = URLS[which]
    b = get(url)
    out = []
    if which == 'nyfed':
        w = openpyxl.load_workbook(io.BytesIO(b), read_only=True, data_only=True)
        try:
            names = w.sheetnames
        finally:
            w.close()
        legacy = next((n for n in names if n.lower().startswith('five-year ahead infl exp')), None)
        specs = [('Inflation expectations', 1, 'Inflation expectations', 1, '1年先期待インフレ・中央値', '1Y'), ('Inflation expectations', 2, 'Inflation expectations', 2, '3年先期待インフレ・中央値', '3Y'), ('Inflation uncertainty', 1, 'Inflation uncertainty', 1, '1年先インフレ不確実性', '1Y'), ('Inflation uncertainty', 2, 'Inflation uncertainty', 2, '3年先インフレ不確実性', '3Y'), ('Five-year ahead Infl Exp', 1, legacy or 'Inflation expectations', 1 if legacy else 10, '5年先期待インフレ・中央値', '5Y'), ('Five-year ahead Infl Exp', 5, legacy or 'Inflation uncertainty', 5 if legacy else 4, '5年先インフレ不確実性', '5Y')]
        sheets = {sn: workbook_rows(b, sn) for sn in dict.fromkeys((v[2] for v in specs))}
        parsed = []
        for (original, oldcol, sn, col, label, h) in specs:
            rows = sheets[sn]
            if not legacy and h == '5Y' and (not any((('five' in str(r[col]).lower() or '5' in str(r[col])) and ('year' in str(r[col]).lower() or 'yr' in str(r[col]).lower()) for r in rows[:4] if len(r) > col))):
                raise ValueError('SCEの5年先列を確認できません: ' + sn)
            item = xseries('nyfed:' + original + ':' + str(oldcol), 'NY Fed SCE ' + label, 'expectations', '家計', 'Federal Reserve Bank of New York', url, rows, col, horizon=h, note='3年先・5年先は、その時点での1年間のインフレ期待。期間全体の累積平均ではありません。© Federal Reserve Bank of New York. SCE data are used under the published license; FRBNY is not responsible for this analysis.', save_result=False)
            if not any((r['value'] is not None for r in item['observations'])):
                raise ValueError('SCE有効観測なし: ' + item['id'])
            if len({r['date'] for r in item['observations']}) != len(item['observations']):
                raise ValueError('SCE観測日重複')
            item.update(sourceTable=sn, sourceColumn=col)
            parsed.append(item)
        out = [save(item) for item in parsed]
    elif which == 'spf_median':
        for sn in ['CPI5YR', 'PCE5YR', 'CPI10', 'PCE10', 'CPI', 'CORECPI', 'PCE', 'COREPCE']:
            rows = workbook_rows(b, sn)
            header = rows[0]
            for (col, name) in enumerate(header[2:], 2):
                if not name:
                    continue
                code = str(name)
                suffix = code[len(sn):]
                horizon = {'1': '前四半期（既知値）', '2': '当四半期', '3': '1四半期先', '4': '2四半期先', '5': '3四半期先', '6': '4四半期先', 'A': '当年平均', 'B': '翌年平均', 'C': '翌々年平均'}.get(suffix, '5年平均' if '5YR' in sn else '10年平均')
                rs = [obs(f'{int(r[0])}-{(int(r[1]) - 1) * 3 + 1:02}-01', r[col]) for r in rows[1:] if len(r) > col and isinstance(r[0], (int, float)) and (1900 <= r[0] <= 2100) and isinstance(r[1], (int, float)) and (1 <= r[1] <= 4)]
                out.append(save(dict(id='spf:median:' + code, label='SPF ' + sn + ' ' + horizon, page='expectations', category='専門家', provider='Federal Reserve Bank of Philadelphia', source=url, unit='%', frequency='Quarterly', seasonal='未確認', horizon=horizon, definition='調査四半期を横軸に表示。四半期予測は前期比年率、年次予測は年平均前年比。系列コード: ' + code, observations=rs)))
    else:
        raise ValueError('Unsupported expectation source')
    return out
