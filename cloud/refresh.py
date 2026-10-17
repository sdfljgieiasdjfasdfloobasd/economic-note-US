#!/usr/bin/env python3
"""Daily, deterministic refresh of the PUBLIC snapshot. No Mac files or AI APIs."""
from pathlib import Path
import argparse,copy,gzip,hashlib,html,json,os,shutil,sys,tempfile,time,traceback
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import publication,verify
import expansion as e
import core

def read(path):return json.loads(Path(path).read_text())
def load(site,path):return json.loads(gzip.decompress((site/path).read_bytes()))
def write(path,obj):e.write(path,obj)
def emit(site,obj):
    raw=json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    name='data/'+hashlib.sha256(raw).hexdigest()+'.json.gz';path=site/name
    if not path.exists():path.parent.mkdir(exist_ok=True);path.write_bytes(gzip.compress(raw,compresslevel=6,mtime=0))
    return name

def retained_failure(old, meta):
    reason=meta.get('error','取得失敗')
    if '/Users/' in reason or '/private/' in reason:reason='取得処理エラー。実行ログを確認してください。'
    return {**old,'status':'fetch_failed','error':reason,'checkedAt':e.now()}

def jobs(datasets,catalog,report):
    import activity_sources as a,macro_sources as m,complementary_sources as c,completion_sources as cs
    import additional_sources as ads,retail_source,jolts_source
    yield 'bls',lambda:core.bls(datasets,catalog,report)
    yield 'pce',lambda:core.pce(datasets)
    yield 'cpi3',lambda:core.cpi3(datasets)
    def revisions():
        rows={};source=None
        for season,offset in [('SA',0),('NSA',6)]:
            for i in range(3):
                sid=f'revisions:{season}:{i}'
                if sid not in e.APPROVED:continue
                data=e.load_series(sid);source=data['source']
                for o in data['observations']:rows.setdefault(o['date'],[None]*12)[offset+i]=o.get('raw')
        if not rows:raise ValueError('公表改定履歴の初期データがありません')
        write(e.HERE/'research/revision-snapshot.json',dict(source=source,rows=rows))
        return cs.revisions()
    yield 'revisions',revisions
    yield 'bea',m.bea
    yield 'gdp',a.gdp
    yield 'retail',retail_source.update
    yield 'jolts',jolts_source.update
    for name in ('g19','dsr','for','sloos'):yield name,lambda n=name:m.fed(n)
    for name,fn in [('housing',a.housing),('g17',a.g17),('vehicles',m.vehicles),('eia',m.eia),('cie',ads.cie),('claims',cs.claims),('diffusion',cs.diffusion)]:yield name,fn
    yield 'dfa',lambda:c.dfa_parse(e.get(c.DFA),c.DFA)
    def located(page,pattern,parser):
        u=c.get_file_link(page,pattern);return parser(e.get(u),u)
    yield 'income',lambda:located(c.BEA_DIST,r'/national/summary-file\.csv$',c.income_parse)
    yield 'saving',lambda:located(c.BEA_DIST,r'joint_dist_summary\.xlsx',c.saving_parse)
    yield 'scf',lambda:located('https://www.federalreserve.gov/econres/scfindex.htm',r'tables_public_nominal_historical\.xlsx',c.scf_parse)
    for program in ('QSS','M3','RESSALES'):
        yield program.lower(),lambda p=program:c.census_parse(e.get(c.BULK+p),p,c.BULK+p)
    def c30():
        import re
        us=list(dict.fromkeys(u for _,u in c.links('https://www.census.gov/construction/c30/historical_data.html') if re.search(r'/(?:tot|priv|pub|sl|fed)(?:sa)?time\.xlsx$',u)))
        if len(us)!=10:raise ValueError('C30公式ファイル構成が変更')
        return [s for u in us for s in c.c30_parse(e.get(u),u)]
    yield 'c30',c30
    url='https://www.eia.gov/opendata/bulk/STEO.zip'
    yield 'steo',lambda:c.steo_parse(e.get(url),url)
    yield 'hvs',lambda:[s for n in (1,2) for u in [f'https://www.census.gov/housing/hvs/data/histtab{n}.xlsx'] for s in c.hvs_parse(e.get(u),u)]
    def ft900():
        from complement_archives import ft_parse
        # Existing archive is preserved; each current exhibit includes prior months/revisions.
        return c.combine([[s for u in [f'https://www.census.gov/foreign-trade/Press-Release/current_press_release/exh{n}.xlsx'] for s in ft_parse(e.get(u),u,n)] for n in (7,8,10,16,17,18)])
    yield 'ft900',ft900
    specs=[s for s in e.FRED if not s['code'].startswith(('JTS','JTU'))]
    for spec in specs:yield spec['id'],lambda s=spec:[e.fred(s)]

def update_calendar(calendar,datasets,cat,report):
    import release_calendar as rc
    events=list(calendar['events']);sources=list(calendar['sources']);stamp=e.now()
    for key,parser in [('bls',rc.parse_bls_ics),('bea',rc.parse_bea)]:
        label,url=rc.SOURCES[key]
        try:
            parsed=parser(e.get(url),url)
            events=[ev for ev in events if ev['source']!=url]
            events.extend(dict(ev,label=rc.INDICATORS[ev['indicator']][0],group=rc.INDICATORS[ev['indicator']][1],nav=rc.INDICATORS[ev['indicator']][2],scheduleSource=label,scheduleCheckedAt=stamp,scheduleStatus='ok',japanTime=datetime.fromisoformat(ev['scheduledAt']).astimezone(rc.JST).isoformat()) for ev in parsed)
            sources=[s for s in sources if s.get('id')!=key]+[dict(id=key,label=label,url=url,status='ok',lastSuccessAt=stamp,count=len(parsed))]
        except Exception as ex:report.append(dict(source='calendar:'+key,status='failed',reason=str(ex)))
    for key,d in datasets.items():write(e.HERE/'data'/(key+'.json'),d)
    write(e.CACHE/'catalog.json',cat);entries=rc.observations(e.HERE/'data')
    for ev in events:
        ev['reflection']=rc.reflection(ev,entries.get(ev['indicator'],[]),datetime.now(timezone.utc))
        ev['afterDue']=rc.reflection(ev,entries.get(ev['indicator'],[]),datetime.fromisoformat(ev['scheduledAt'])+timedelta(seconds=1))
    return publication.calendar_scope(dict(calendar,updatedAt=stamp,now=stamp,events=sorted(events,key=lambda x:x['scheduledAt']),sources=sources))

def finalize(root,original,datasets,catalog,metas,report,started,only):
    site=root/'site';index=load(site,original['seriesIndex']);rows=[];changed=[];checked=0
    allowed=set(index)
    for meta in catalog['series']:
        sid=meta['id'];p=e.SERIES/e.key(sid);s=read(p)
        newmeta=metas.get(sid)
        if newmeta and newmeta.get('status')=='fetch_failed':
            # Failure is metadata only: never replace an existing series with an error blob.
            s=retained_failure(load(site,index[sid]),newmeta)
        elif sid not in e.ATTEMPTED:
            s={**s,'cloudUpdateStatus':'not_checked'}
        else:
            checked+=1;s.pop('cloudUpdateStatus',None)
            if s.get('status')=='fetch_failed':s.update(status='available');s.pop('error',None);s.pop('checkedAt',None)
        s=publication.clean(s,allowed)
        if load(site,index[sid]).get('observations')!=s.get('observations'):changed.append(sid)
        index[sid]=emit(site,s);rows.append(e.summary(s))
    cat={**catalog,'generatedAt':e.now(),'series':rows}
    publication.check_datasets(datasets)
    selected,_=publication.select(cat)
    if len(selected['series'])!=len(rows):raise ValueError('公開範囲の検証に失敗')
    # Totals are reconstructed from the same refreshed base datasets as the charts.
    manifest=load(site,original['manifest'])
    for m in manifest['datasets']:
        d=datasets[m['id']];m.update(latest=d['latest'],savedAt=d['savedAt'])
    for card in manifest['cards']:
        d=datasets[card['id']];s=next(s for s in d['series'] if s['name']==d['default']);vs=s['values'][d['metrics'][0]['id']]
        card.update(month=d['dates'][-1],value=vs[-1],previous=vs[-2] if len(vs)>1 else None,trend=vs[-36:])
    finished=e.now();manifest.update(generatedAt=finished,fingerprint=hashlib.sha256(finished.encode()).hexdigest())
    analysis=load(site,original['analysisCatalog']);by={s['id']:s for s in rows}
    for s in analysis['series']:
        if s['id'].startswith('ex:'):
            m=by[s['id'][3:]]
            for k in ('count','first','latest','status','error','retrievedAt','checkedAt'):
                if k in m:s[k]=m[k]
                else:s.pop(k,None)
        elif s.get('descriptor'):
            ds,si,se,metric=s['descriptor'];d=datasets[ds];row=next(v for v in d['series'] if v['id']==si);vs=row['bases'].get(se,[]) if d['kind']=='base' else row['values'].get(metric,[])
            observed=[e.obs(dt+'-01',v) for dt,v in zip(d['dates'],vs) if v is not None]
            s.update(count=len(observed),first=observed[0]['date'] if observed else None,latest=observed[-1] if observed else None)
    analysis['generatedAt']=finished
    calendar=load(site,original['calendar'])
    if not only:calendar=update_calendar(calendar,datasets,cat,report)
    for row in report:
        if '/Users/' in row.get('reason','') or '/private/' in row.get('reason',''):row['reason']='取得処理エラー。実行ログで詳細を確認してください。'
    failures=[v for v in report if v['status']=='failed'];held=[{'id':sid,'reason':reason} for sid,reason in e.REJECTED.items() if sid in allowed]
    changed_datasets=[key for key,d in datasets.items() if any(d.get(field)!=load(site,original['datasets'][key]).get(field) for field in ('dates','series'))]
    summary=dict(changedDatasets=changed_datasets,schedule='毎日04:00 JST（開始予定）',startedAt=started,finishedAt=e.now(),changedSeries=len(changed),checkedSeries=checked,failedSources=len(failures),mode='partial-test' if only else 'daily',sources=report,held=held,
                 limitations=['CPI Table 6（発表時点の寄与度）と年次ベンチマークの保存系列は自動更新対象外。保存済みの観測を表示します。','公式サイトのアクセス制限・定義変更時は保存値を保持。公開許諾未確認の系列は追加しません。'])
    release={**original,'builtAt':finished,'revision':'cloud-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),'cloudUpdate':summary}
    release['datasets']={k:emit(site,d) for k,d in datasets.items()}
    for k,v in [('catalog',cat),('manifest',manifest),('seriesIndex',index),('analysisCatalog',analysis),('calendar',calendar)]:release[k]=emit(site,v)
    write(site/'release.json',release)
    esc=html.escape
    table=''.join('<tr><td>'+esc(v['source'])+'</td><td>'+esc(v['status'])+'</td><td>'+esc(v.get('reason',''))+'</td></tr>' for v in report)
    (site/'update-status.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>自動更新の結果</title><style>body{font:16px/1.7 system-ui;max-width:1000px;margin:auto;padding:24px}td{padding:8px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}a{color:#087b72}</style><a href="./">← サイトへ</a><h1>自動更新の結果</h1><p>毎日04:00 JSTに開始予定。取得・検証後に反映。GitHub側の混雑で開始が遅れることがあります。</p><p>最終試行（UTC）: '+esc(summary['finishedAt'])+'</p><p>変更 '+str(len(changed))+'拡張系列 / 確認 '+str(checked)+'系列 / 失敗 '+str(len(failures))+'取得処理</p><p>基本表のデータ変更: '+esc(', '.join(changed_datasets) or 'なし')+'</p><p>'+esc(' '.join(summary['limitations']))+'</p><table><tr><th>取得処理</th><th>結果</th><th>理由</th></tr>'+table+'</table></html>')
    refs=set(index.values())|set(release['datasets'].values())|{release[k] for k in ('manifest','catalog','analysisCatalog','calendar','updateReport','seriesIndex')}
    for p in (site/'data').glob('*.json.gz'):
        if p.relative_to(site).as_posix() not in refs:p.unlink()
    br=read(root/'build-report.json');br.update(builtAt=finished,observations=sum(s['count'] for s in rows),mode='cloud',automaticProviderUpdates=True,siteBytes=sum(p.stat().st_size for p in site.rglob('*') if p.is_file()))
    br['dataBytesAfterCompression']=sum(p.stat().st_size for p in (site/'data').glob('*.json.gz'))
    br['dataBytesBeforeCompression']=sum(len(gzip.decompress(p.read_bytes())) for p in (site/'data').glob('*.json.gz'))
    write(root/'build-report.json',br)
    verify.verify(root)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('sources','held')},ensure_ascii=False),flush=True)
    return summary

def run(root=ROOT,only=None):
    root=Path(root).resolve();started=e.now();report=[]
    # Everything is staged. A parsing/verification failure cannot corrupt site/.
    with tempfile.TemporaryDirectory(prefix='.cloud-work-',dir=root) as tmp:
        tmp=Path(tmp);stage=tmp/'publish';stage.mkdir();shutil.copytree(root/'site',stage/'site')
        for name in ('build-report.json','publication-report.json'):shutil.copy2(root/name,stage/name)
        site=stage/'site';rel=read(site/'release.json');catalog=load(site,rel['catalog']);approved={s['id']:s for s in catalog['series']}
        e.initialize(tmp/'work',approved);index=load(site,rel['seriesIndex'])
        for sid,path in index.items():write(e.SERIES/e.key(sid),load(site,path))
        write(e.CACHE/'catalog.json',catalog)
        datasets={k:load(site,v) for k,v in rel['datasets'].items()}
        original_saved={k:d['savedAt'] for k,d in datasets.items()}
        for k,d in datasets.items():write(e.HERE/'data'/(k+'.json'),d)
        metas={}
        for name,fn in jobs(datasets,catalog,report):
            if only and name not in only:continue
            print('Refreshing',name,flush=True);before=set(e.ATTEMPTED)
            try:
                result=fn() or []
                for m in result:
                    if m['id'] not in approved:continue
                    if 'observations' in m:
                        if not any(o.get('value') is not None for o in m['observations']):continue
                        m=e.save(m)
                    metas[m['id']]=m
                if name in ('bls','pce','cpi3'):
                    for dk,dv in datasets.items():write(e.HERE/'data'/(dk+'.json'),dv)
                bad=[s for s in result if s.get('status')=='fetch_failed' and s['id'] in approved]
                report.append(dict(source=name,status='failed' if bad else 'success',series=len(e.ATTEMPTED-before),**({'reason':bad[0].get('error','取得失敗')} if bad else {})))
            except Exception as ex:
                print(name,type(ex).__name__,str(ex)[:300],flush=True)
                report.append(dict(source=name,status='failed',reason=str(ex)[:500]))
                for sid,meta in approved.items():
                    if sid==name or sid.startswith(name+':') or sid.startswith('complement:'+name+':'):
                        metas[sid]=dict(meta,status='fetch_failed',error=str(ex)[:500])
        # Roll back failed series before computing dependent measures.
        for sid,meta in metas.items():
            if meta.get('status')=='fetch_failed':write(e.SERIES/e.key(sid),load(site,index[sid]))
        # Materialize aliases after base data changes (e.g. PCE price indexes).
        for sid,meta in approved.items():
            alias=meta.get('alias')
            if not alias:continue
            d=datasets[alias['dataset']];s=next(v for v in d['series'] if v['id']==alias['series']);vs=s['bases'][alias['season']]
            old=e.load_series(sid);old.update(observations=[e.obs(dt+'-01',v) for dt,v in zip(d['dates'],vs)])
            if d['savedAt']!=original_saved[alias['dataset']]:
                try:metas[sid]=e.save(old)
                except Exception as ex:report.append(dict(source=sid,status='failed',reason=str(ex)))
        if not only:
            import completion_sources,macro_derived
            for name,fn in [('derived',completion_sources.derived),('macrocalc',macro_derived.derive)]:
                try:
                    entries=[metas.get(s['id'],s) for s in catalog['series']]
                    for m in fn(entries):
                        if m['id'] in approved:metas[m['id']]=m
                    report.append(dict(source=name,status='success'))
                except Exception as ex:report.append(dict(source=name,status='failed',reason=str(ex)))
        summary=finalize(stage,rel,datasets,catalog,metas,report,started,only)
        # The workflow commits only this validated public state, never raw downloads.
        old=root/'.cloud-previous'
        if old.exists():shutil.rmtree(old)
        (root/'site').rename(old)
        try:(stage/'site').rename(root/'site')
        except Exception:old.rename(root/'site');raise
        shutil.copy2(stage/'build-report.json',root/'build-report.json');shutil.rmtree(old)
        return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--only',help='Comma-separated adapter names for an isolated smoke test')
    a=p.parse_args();run(a.root,set(a.only.split(',')) if a.only else None)
