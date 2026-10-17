"""Update the existing base charts directly from official levels, without Excel."""
import csv,io,json,re,copy
from pathlib import Path
from collections import defaultdict
import openpyxl
import expansion as e

MAPPING=json.loads((Path(__file__).parent/'base-series.json').read_text())
BULK={'CU':'cu/cu.data.0.Current','CE':'ce/ce.data.0.AllCESSeries','LN':'ln/ln.data.1.AllData','WP':'wp/wp.data.22.FD-ID'}
def shift(d,k):
    n=int(d[:4])*12+int(d[5:7])-1+k
    return f'{n//12:04}-{n%12+1:02}'
def parse_bulk(blob,codes):
    result=defaultdict(list)
    # Stream rows rather than expanding all CES/CPS rows into dictionaries.
    lines=io.TextIOWrapper(io.BytesIO(blob),encoding='utf-8-sig')
    reader=csv.reader(lines,delimiter='\t');header=[v.strip() for v in next(reader)]
    if header[:4]!=['series_id','year','period','value']:raise ValueError('BLS一括データの列構成が変更')
    for row in reader:
        if len(row)<4:continue
        code,year,period,value=[x.strip() for x in row[:4]]
        if code in codes and re.fullmatch(r'M(?:0[1-9]|1[0-2])',period):
            result[code].append(e.obs(year+'-'+period[1:]+'-01',value,footnotes=row[4].strip() if len(row)>4 else ''))
    if not result:raise ValueError('要求したBLS系列がありません')
    for rows in result.values():e.valid_observations(rows)
    return result

def replace_bases(d,updates):
    """Preserve historical dates, align all arrays and recompute all chart metrics."""
    d=copy.deepcopy(d);dates=sorted(set(d['dates'])|{r['date'][:7] for rows in updates.values() for r in rows})
    for s in d['series']:
        bases={se:dict(zip(d['dates'],vs)) for se,vs in s['bases'].items()}
        for se,m in bases.items():
            new=updates.get(s['id']+'|'+se)
            if new is not None:
                old=[e.obs(dt+'-01',v) for dt,v in m.items()]
                m.update({r['date'][:7]:r['value'] for r in e.merge_observations(old,new)})
        def value(se,dt):return bases.get(se,{}).get(dt)
        def ratio(se,dt,k):
            a,b=value(se,dt),value(se,shift(dt,-k))
            return (a/b-1)*100 if a is not None and b not in (None,0) else None
        values={}
        for metric in d['metrics']:
            key=metric['id'];vs=[]
            for dt in dates:
                sa,ns=value('SA',dt),value('NSA',dt);prior=value('SA',shift(dt,-1))
                v=ratio('NSA' if d['id'] in ('cpi','cpi_detail','ppi') else 'SA',dt,12) if key=='yoy' else ratio('SA',dt,1) if key=='mom' else ns if key=='nsa' else sa-prior if key=='change' and sa is not None and prior is not None else None if key=='change' else sa
                vs.append(v)
            values[key]=vs
        s['bases']={se:[m.get(dt) for dt in dates] for se,m in bases.items()};s['values']=values
    d.update(dates=dates,latest=dates[-1],savedAt=e.now())
    return d

def bls(datasets,catalog,report):
    by={s['id']:s for s in catalog['series']};wanted=set(MAPPING.values())
    wanted.update(s['officialId'] for s in by.values() if s['id'].startswith(('local:','healthcare:')) and s.get('officialId'))
    found={}
    for prefix,file in BULK.items():
        codes={c for c in wanted if c.startswith(prefix)}
        try:
            found.update(parse_bulk(e.get('https://download.bls.gov/pub/time.series/'+file),codes))
            report.append(dict(source='BLS '+prefix,status='success',series=len(codes&found.keys())))
        except Exception as ex:report.append(dict(source='BLS '+prefix,status='failed',reason=str(ex)))
    for did in ('cpi','cpi_detail','ppi','employment','labor','wages','hours'):
        updates={k.split('|',1)[1]:found[code] for k,code in MAPPING.items() if k.startswith(did+'|') and code in found}
        if did=='labor':
            for se in ('SA','NSA'):
                ids=[s['officialId'] for s in by.values() if s['id'].startswith('local:CPS_Main_'+se+':') and s['label'] in ('Unemployed','Civilian labor force')]
                if len(ids)==2 and all(code in found for code in ids):
                    u=next(s['officialId'] for s in by.values() if s['id']=='local:CPS_Main_'+se+':Unemployed')
                    lf=next(code for code in ids if code!=u);a={o['date']:o for o in found[u]};b={o['date']:o for o in found[lf]}
                    sid=next(s['id'] for s in datasets[did]['series'] if s['name']=='Unemployment rate (recalculated)')
                    updates[sid+'|'+se]=[e.obs(dt,a[dt]['value']/b[dt]['value']*100,'derived') for dt in sorted(a.keys()&b.keys()) if a[dt]['value'] is not None and b[dt]['value'] not in (None,0)]
        if updates:
            try:datasets[did]=replace_bases(datasets[did],updates)
            except Exception as ex:report.append(dict(source=did,status='failed',reason=str(ex)))
    out=[]
    for sid,m in by.items():
        code=m.get('officialId')
        if not sid.startswith(('local:','healthcare:')):continue
        if code in found:
            try:out.append(e.save(dict(m,observations=found[code])))
            except Exception as ex:out.append(dict(m,status='fetch_failed',error=str(ex)))
        else:out.append(dict(m,status='fetch_failed',error='BLS公式系列を取得できなかったため保存値を保持'))
    return out

def pce(datasets):
    url='https://apps.bea.gov/national/Release/XLS/Survey/Section2All_xls.xlsx'
    w=openpyxl.load_workbook(io.BytesIO(e.get(url)),read_only=True,data_only=True)
    try:rows=list(w['T20804-M'].values)
    finally:w.close()
    if 'Table 2.8.4.' not in str(rows[0][0]) or 'seasonally adjusted' not in str(rows[1][0]):raise ValueError('PCE表定義が変更')
    cols={j:str(v).replace('M','-')+'-01' for j,v in enumerate(rows[7]) if re.fullmatch(r'\d{4}M\d{2}',str(v))}
    norm=lambda v:re.sub(r'[^a-z]','',re.sub(r'\\\d+\\','',str(v)).lower())
    source={norm(r[1]):r for r in rows[8:] if str(r[0]).isdigit()}
    updates={}
    for s in datasets['pce']['series']:
        r=source[norm(s['name'])];updates[s['id']+'|SA']=[e.obs(dt,r[j]) for j,dt in cols.items()]
    datasets['pce']=replace_bases(datasets['pce'],updates)

def cpi3(datasets):
    from cpi_release import parse_html
    p=e.RAW/'cpi3.html';p.write_bytes(e.get('https://www.bls.gov/news.release/cpi.t03.htm'))
    month,title,rows,_=parse_html(p);d=copy.deepcopy(datasets['cpi3']);old_dates=d['dates'];dates=sorted(set(old_dates)|{month})
    if month<d['latest']:raise ValueError('CPI Table 3の公表月が保存値より古い')
    rows={r['Item']:r for r in rows}
    if set(rows)!=set(s['name'] for s in d['series']):raise ValueError('CPI Table 3の品目構成が変更')
    for s in d['series']:
        for key,field in [('ri','Relative_Importance'),('yoy','NSA_YoY'),('nsa_mom','NSA_MoM'),('mom','SA_MoM')]:
            values=dict(zip(old_dates,s['values'][key]));v=rows[s['name']][field]
            if month in values and values[month]!=v:raise ValueError('CPI発表時点の保存値と最新表の値が異なるため要確認')
            values[month]=v;s['values'][key]=[values.get(dt) for dt in dates]
    d.update(dates=dates,latest=month,savedAt=e.now());datasets['cpi3']=d
