"""Public-only adapters copied from the local dashboard; maintained independently."""
import io,csv,json,re,zipfile,calendar

from datetime import datetime

from decimal import Decimal

from urllib.parse import urljoin

from lxml import html

import openpyxl

import expansion as e

def cie():
 url='https://www.federalreserve.gov/econres/notes/feds-notes/FEDS-Note-2873-cie-data.csv';rows=list(csv.DictReader(io.StringIO(e.get(url).decode('utf-8-sig'))));out=[]
 for code,label in [('CIE_spf','SPF 10年PCEに投影'),('CIE_mich','Michigan長期に投影')]:
  rs=[e.obs(datetime.strptime(r['period'],'%Y-%m-%d' if '-' in r['period'] else '%m/%d/%Y').strftime('%Y-%m-%d'),r[code]) for r in rows]
  out.append(e.save(dict(id='cie:'+code,label='FRB CIE '+label,page='expectations',category='総合・モデル',provider='Federal Reserve Board',source=url,frequency='Quarterly',seasonal='非該当',unit='%',definition='動学因子モデルによる複数の期待インフレ指標の共通変動。四半期末を横軸に表示。SPFの予測値そのものとは異なります。',observations=rs)))
 return out

SP_INDEX={'Composite PMI Output Index':('Composite','Output'),'Services PMI Business Activity Index':('Services','Business Activity / Headline PMI'),'Manufacturing Output Index':('Manufacturing','Output'),'Manufacturing PMI':('Manufacturing','Headline PMI')}
