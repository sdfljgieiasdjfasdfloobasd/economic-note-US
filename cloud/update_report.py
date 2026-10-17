"""Compare saved observations, independently of file timestamps or derived UI metrics."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import uuid
import struct

PAGES = {'gdp':'GDP','housing':'住宅建設','production':'鉱工業生産','pce-nonprice':'PCE・所得・貯蓄','consumption':'消費','expectations':'期待インフレ', 'sp':'S&P Global PMI', 'ism':'ISM PMI', 'labor':'労働市場・拡張'}
GROUPS = {'cpi':'CPI', 'pce':'PCE', 'ppi':'PPI', 'employment':'雇用統計'}


def now():
    return datetime.now().astimezone().isoformat()


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def dataset_snapshot(d):
    result = {}
    metrics = {m['id']:m for m in d.get('metrics', [])}
    for s in d['series']:
        for measure, values in s.get('bases' if d['kind']=='base' else 'values', {}).items():
            observations = {date:(v, '') for date,v in zip(d['dates'], values) if v is not None}
            if not observations: continue
            key = json.dumps([d['id'], s['name'], measure], ensure_ascii=False)
            result[key] = dict(label=s.get('label',s['name']), group=GROUPS.get(d['group'],d['group'])+' / '+d['label'],
                target=dict(dataset=d['id'],seriesId=s['id'],measure=measure),
                measure=measure if d['kind']=='base' else metrics.get(measure,{}).get('label',measure),
                unit=d.get('baseUnit','') if d['kind']=='base' else metrics.get(measure,{}).get('unit',''), observations=observations)
    return result


def explorer_snapshot(s):
    if s.get('alias'): return {}
    return {'explorer:'+s['id']: dict(label=s['label'],group=PAGES.get(s.get('page'),s.get('page','追加系列'))+' / '+s.get('category',''),
        measure=s.get('seasonal',''), unit=s.get('unit',''),
        observations={o['date']:(o['value'],o.get('status','')) for o in s.get('observations',[]) if o.get('value') is not None})}


def snapshot(cache):
    cache = Path(cache);result = {}
    for meta in read(cache/'manifest.json',{'datasets':[]})['datasets']:
        d=read(cache/(meta['id']+'.json'))
        if d:result.update(dataset_snapshot(d))
    for m in read(cache/'explorer/catalog.json',{'series':[]})['series']:
        if m.get('alias'):continue
        file=cache/'explorer/series'/(hashlib.sha256(m['id'].encode()).hexdigest()+'.json')
        result.update(explorer_snapshot({**m,**read(file,{})}))
    return result


def observation_hash(observations):
    digest=hashlib.sha256()
    for date,(value,_) in sorted(observations.items()):
        if value is None:continue
        date=date+'-01' if len(date)==7 else date
        digest.update(date.encode()+b'\0'+struct.pack('!d',float(value))+b'\n')
    return digest.hexdigest()


def revision_checks(after):
    checks={};lookup={}
    for key,s in after.items():
        checks[key]=observation_hash(s['observations'])
        if s.get('target'):
            t=s['target'];lookup[json.dumps([t['dataset'],str(t['seriesId']),t['measure']],ensure_ascii=False,separators=(',',':'))]=key
    return checks,lookup


def equal(a, b):
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return a == b


def compare(before, after):
    changed, unchanged = [], {}
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key,{}), after.get(key,{})
        a, b = old.get('observations',{}), new.get('observations',{})
        if not a and not b:
            continue
        details = []
        for date in sorted(a.keys() | b.keys(), reverse=True):
            av, bv = a.get(date), b.get(date)
            kind = ('added' if av is None else 'removed' if bv is None else
                    'revised' if not equal(av[0],bv[0]) else 'status' if av[1]!=bv[1] else None)
            if kind:
                details.append(dict(date=date, kind=kind, before=av[0] if av else None, after=bv[0] if bv else None,
                                    beforeStatus=av[1] if av else '', afterStatus=bv[1] if bv else '',
                                    additionType=('initial' if not a else 'new_period' if date>max(a) else 'backfill') if kind=='added' else None,
                                    delta=float(Decimal(str(bv[0]))-Decimal(str(av[0]))) if av and bv and kind=='revised' else None))
        meta = {k:v for k,v in (new or old).items() if k!='observations'}
        if details:
            changed.append(dict(id=key, **meta, comparable=not old or not new or all(old.get(k)==new.get(k) for k in ('unit','measure')), counts={kind:sum(d['kind']==kind for d in details) for kind in ['added','revised','removed','status']}, details=details))
        else:
            unchanged[meta['group']] = unchanged.get(meta['group'],0)+1
    return changed, unchanged


def make_report(before, after, *, started, mode, catalog=None, failures=(), finished=None):
    changed, unchanged = compare(before, after)
    errors = [dict(group='更新処理',label=label,error=error) for label,error in failures]
    if mode=='official':
        for s in (catalog or {}).get('series',[]):
            # Retained failures from an earlier run are not a new failed attempt.
            if s.get('status')=='fetch_failed' and s.get('checkedAt','')>=started:
                errors.append(dict(group=PAGES.get(s.get('page'), '追加系列'), label=s['label'], measure=s.get('seasonal',''), error=s.get('error','取得失敗')))
    checks,lookup=revision_checks(after)
    return dict(format=2,checks=checks,lookup=lookup,id=uuid.uuid4().hex, startedAt=started, finishedAt=finished or now(), mode=mode, changed=changed,
        unchanged=[dict(group=k,count=v) for k,v in sorted(unchanged.items())], failures=errors,
        counts=dict(changed=len(changed), unchanged=sum(unchanged.values()), failed=len(errors),
            **{kind:sum(bool(s['counts'][kind]) for s in changed) for kind in ['added','revised','removed','status']}))


def save(cache, report, log_dir=None):
    path = Path(cache)/'update-report.json'
    text = json.dumps(report,ensure_ascii=False,allow_nan=False)
    temp = path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(text)
    os.replace(temp,path)
    if log_dir:
        (Path(log_dir)/'update-report.json').write_text(text)
