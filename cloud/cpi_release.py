from pathlib import Path
import re,json,calendar
from lxml import html
MONTHS={m.lower():i for i,m in enumerate(calendar.month_name) if m}

def text(v):return ' '.join(str(v if v is not None else '').replace('\xa0',' ').split())

def clean(v):return text(re.sub(r'\(\s*\d+(?:\s*,\s*\d+)*\s*\)|[¹²³⁴⁵⁶⁷⁸⁹⁰*†‡]','',text(v)))

def month_from(v):return [f'{y}-{MONTHS[m.lower()]:02}' for m,y in re.findall(r'\b([A-Za-z]+)\.?\s+(20\d\d)\b',text(v)) if m.lower() in MONTHS]

def shift(m,delta):
    y,mo=map(int,m.split('-'));n=y*12+mo-1+delta;return f'{n//12:04}-{n%12+1:02}'

def number(v):
    v=text(v)
    if v.lower() in ['', '-', '–','—','not available','na']:return None
    v=re.sub(r'^\(\s*[rRpP]\s*\)\s*','',v)
    return float(v.replace(',','').replace('−','-'))

def parse_html(path):
    tree=html.fromstring(Path(path).read_bytes());tables=[]
    for t in tree.xpath('//table'):
        title=text(' '.join(t.xpath('./caption//text()')))
        stub=text(' '.join(t.xpath('./thead/tr[1]/*[1]//text()')))
        if re.match(r'Table\s+3\.',title) and 'All Urban Consumers' in title and stub.lower()=='special aggregate indexes':tables.append((t,title))
    if len(tables)!=1:raise ValueError('No unique CPI-U Special Aggregates Table 3')
    t,title=tables[0];ms=month_from(title)
    if len(ms)!=1:raise ValueError('Cannot identify one CPI month from table title')
    month=ms[0];occ={}
    for i,tr in enumerate(t.xpath('./thead/tr')):
        col=0
        for c in tr.xpath('./th|./td'):
            while (i,col) in occ:col+=1
            value=text(' '.join(c.itertext()))
            for rr in range(i,i+int(c.get('rowspan','1'))):
                for cc in range(col,col+int(c.get('colspan','1'))):occ[rr,cc]=value
            col+=int(c.get('colspan','1'))
    width=max(c for r,c in occ)+1
    headers={c:list(dict.fromkeys(occ[r,c] for r in range(max(r for r,c in occ)+1) if (r,c) in occ)) for c in range(width)}
    columns={};intervals={}
    for field,label,expected in [('Relative_Importance','Relative importance',[shift(month,-1)]),('NSA_YoY','Unadjusted percent change',[shift(month,-12),month]),('NSA_MoM','Unadjusted percent change',[shift(month,-1),month]),('SA_MoM','Seasonally adjusted percent change',[shift(month,-1),month])]:
        hits=[]
        for c,parts in headers.items():
            if any(v.startswith(label) for v in parts) and month_from(' '.join(parts))==expected:hits.append(c)
        if len(hits)!=1:raise ValueError(f'{field} header interval not unique: {expected}; {headers}')
        columns[field]=hits[0];intervals[field]=expected
    rows=[]
    for tr in t.xpath('./tbody/tr'):
        if not tr.xpath('./th/p'):continue
        cells=tr.xpath('./th|./td');raw=text(' '.join(cells[0].itertext()));item=clean(raw)
        if not item:continue
        if len(cells)!=width:raise ValueError('Data row/header width differs: '+item)
        row={'Date':month+'-01','Item':item,'Raw_Item_Name':raw,'Display_Order':len(rows)+1,'Source_Row_ID':cells[0].get('id')}
        marks=[]
        for key,c in columns.items():
            rawvalue=text(' '.join(cells[c].itertext()));row[key]=number(rawvalue)
            if re.search(r'\(\s*[rRpP]\s*\)',rawvalue):marks.append(key+': '+rawvalue)
        row['Published_Revision_Marker']='; '.join(marks) or None
        row['RI_Reference_Month']=intervals['Relative_Importance'][0]
        for key in ['NSA_YoY','NSA_MoM','SA_MoM']:
            row[key+'_Start']=intervals[key][0];row[key+'_End']=intervals[key][1]
        rows.append(row)
    signature=json.dumps(headers,sort_keys=True)
    return month,title,rows,signature
MONTHS.update({m.lower():i for i,m in enumerate(calendar.month_abbr) if m})
