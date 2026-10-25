"""Offline estimates of contributions to 12-month NSA core CPI inflation.

Relative importance in a Table 6 release refers to the preceding month.
Within a weight regime RI_i(p)/RI_core(p) identifies relative cost weights.
Split at December and bridge each segment to the original core index level;
never multiply a full-year price change by the latest month's weight.
Published (rounded) indices and RI imply estimates, not BLS published effects.
"""
from decimal import Decimal, localcontext

PREFIX = 'cpiderived:core_yoy:'
CORE = 'All items less food and energy'
PUBLICATION = 'CPI コア前年比への寄与度（NSA・推計値）'
SOURCE = 'https://www.bls.gov/cpi/factsheets/contributions-effects.htm'
DEFINITION = ('季節調整前（NSA）のコアCPI前年比への寄与度（ポイント）の推計値。'
 '保存済みのNSA指数とTable 6の相対的重要度を使用。相対的重要度の基準月は表の対象月の前月。'
 '12か月を12月のウェイト切替点で区切り、各区間の寄与を前年同月のコア指数に接続して合算。'
 '公表済みの丸められた指数・ウェイトによる計算で、BLSが直接公表したコア寄与度ではありません。'
 '最新保存指数と各月資料のウェイトを使用し、当時の発表値の完全再現ではありません。'
 '必要な指数・ウェイトが欠ける月は空欄。食品・エネルギーなどコア対象外は除外。'
 '親項目と内訳は重複するため全行を足さないでください。原指数・ウェイトの更新後に再計算します。')


def shift(month, n):
    y, m = map(int, month.split('-'))
    y, m = divmod(y * 12 + m - 1 + n, 12)
    return f'{y:04}-{m+1:02}'


def number(v):
    if v is None:
        return None
    x = Decimal(str(v))
    return x if x.is_finite() else None


def effect(end, item, aggregate, weights, aggregate_weights):
    """Return decimal effect and auditable segment inputs, or a missing reason.

    Index maps use reference months; weight maps use release target months.
    For segment s..e and anchor p: 100 * RI_i(p)/RI_c(p) *
    (I_i(e)-I_i(s))/I_i(p) * I_c(p)/I_c(t-12).
    Splitting also in unchanged-weight years is algebraically equivalent.
    """
    start = shift(end, -12)
    for month in (start, end):
        if aggregate.get(month) is None or aggregate[month] <= 0:
            return None, [], f'{month}のコアNSA指数がありません'
    pivots = [f'{y}-12' for y in range(int(start[:4]), int(end[:4])+1)
              if start < f'{y}-12' < end]
    edges = [start, *pivots, end]
    segments = []
    with localcontext() as ctx:
        ctx.prec = 28
        total = Decimal(0)
        for s, e in zip(edges, edges[1:]):
            if item.get(s) is None or item.get(e) is None:
                return None, segments, f'{s}または{e}の品目NSA指数がありません'
            year = int(s[:4]) + (s[5:] == '12')
            anchor = None
            for release in sorted(weights):
                if int(release[:4]) != year:
                    continue
                p = shift(release, -1)
                wi, wc = weights[release], aggregate_weights.get(release)
                ip, cp = item.get(p), aggregate.get(p)
                if wi is not None and wi >= 0 and wc is not None and wc > 0 and ip is not None and ip > 0 and cp is not None and cp > 0:
                    anchor = (release, p, wi, wc, ip, cp)
                    break
            if anchor is None:
                return None, segments, f'{year}年のウェイト区間に必要な相対的重要度・NSA指数がありません'
            release, p, wi, wc, ip, cp = anchor
            value = 100 * wi / wc * (item[e]-item[s]) / ip * cp / aggregate[start]
            total += value
            segments.append(dict(start=s, end=e, weightReleaseMonth=release,
                                 weightReferenceMonth=p, itemWeight=str(wi), coreWeight=str(wc),
                                 itemStartIndex=str(item[s]), itemEndIndex=str(item[e]),
                                 itemAnchorIndex=str(ip), coreAnchorIndex=str(cp), effect=str(value)))
        return total, segments, None


def build_series(datasets):
    """No network or writes. Works identically on the Mac and in daily refresh."""
    import expansion as ex
    d, w = datasets['cpi_detail'], datasets['cpi6']
    indexes = {r['name']: r for r in d['series']}
    weight_rows = {r['name']: r for r in w['series']}
    if CORE not in indexes or CORE not in weight_rows:
        raise ValueError('コアの指数またはウェイトがありません')
    def levels(r):
        return {dt: number(v) for dt, v in zip(d['dates'], r.get('bases', {}).get('NSA', []))}
    def weights(r):
        return {dt: number(v) for dt, v in zip(w['dates'], r['values']['ri'])}
    core_index, core_weights = levels(indexes[CORE]), weights(weight_rows[CORE])
    # First possible full annual window starts at the first available weight regime.
    first = f'{w["dates"][0][:4]}-12'
    dates = [dt for dt in d['dates'] if dt >= first]
    result = []
    for order, row in enumerate(d['series']):
        wr = weight_rows.get(row['name'])
        if wr is None or not (wr.get('coreApplicable') is True or row['name'] == CORE):
            continue
        observations = []
        indices, ri = levels(row), weights(wr)
        for dt in dates:
            value, segments, reason = effect(dt, indices, core_index, ri, core_weights)
            observations.append(ex.obs(dt+'-01', value, 'estimated' if value is not None else 'missing_inputs',
                                       missingReason=reason, calculationSegments=segments))
        h = row.get('hierarchy', {})
        result.append(dict(id=PREFIX+row['id'], label=row['label'], matchLabel=row['label'],
            page='cpi', category=PUBLICATION, publicationId='cpi:core-yoy', publicationLabel=PUBLICATION,
            provider='Bureau of Labor Statistics', source=SOURCE, frequency='Monthly', seasonal='NSA',
            unit='ポイント', sourceMetric='コア前年比への寄与（推計値）', definition=DEFINITION,
            calculation='cpi_core_yoy_chain_v1', coreApplicable=True, sourceOrder=order,
            hierarchy=h.get('path', []), depth=h.get('depth', 0),
            inputDatasets=['cpi_detail', 'cpi6'],
            inputSavedAt={k: datasets[k].get('savedAt') for k in ['cpi_detail', 'cpi6']},
            inputLatest={k: datasets[k].get('latest') for k in ['cpi_detail', 'cpi6']},
            observations=observations))
    return result


def update(datasets):
    import expansion as ex
    result = []
    for s in build_series(datasets):
        if hasattr(ex, 'APPROVED'):
            # Cloud estimates are complete recomputations. A newly missing input
            # must remove a stale estimate, not be merged back from an older run.
            import publication
            sid = s['id']
            if sid not in ex.APPROVED:
                continue
            if publication.signature(s) != publication.signature(ex.APPROVED[sid]):
                raise ValueError('寄与度推計の定義が公開承認済みの定義と一致しません')
            if any(o['value'] is not None for o in s['observations']):
                ex.valid_observations(s['observations'])
                s['status'] = 'available'
            else:
                s.update(status='missing_inputs', error='必要なNSA指数・ウェイトが揃う期間がありません')
            s['retrievedAt'] = ex.now()
            ex.ATTEMPTED.add(sid)
            ex.write(ex.SERIES/ex.key(sid), s)
            result.append(ex.summary(s))
            continue
        if any(o['value'] is not None for o in s['observations']):
            result.append(ex.save(s))
        else:
            # Preserve defined but uncomputable items, never substitute a zero.
            s.update(status='missing_inputs', error='必要なNSA指数・ウェイトが揃う期間がありません')
            ex.write(ex.SERIES/ex.key(s['id']), s)
            result.append(ex.summary(s))
    return result
