"""Row-specific consumption definitions. Does not change observation values."""
def bea_income_metadata(s):
 if s.get('sourceTable')!='T20600-M':return s
 code=s.get('officialId','');unit=s['unit']
 s.setdefault('sourceHeader','[Millions of dollars; months are seasonally adjusted at annual rates]')
 s.update(annualized=True,statisticType='income_expenditure_flow',priceBasis='real' if 'chained' in unit else 'nominal',referenceYear=2017 if 'chained' in unit else None)
 note='月次の季節調整済み年率フロー。単位は各行の表示に従います。連鎖実質額の親子項目を単純加算しません。'
 if code=='B230RC':
  s.update(annualized=False,statisticType='population_stock',measure='人口',priceBasis='not_applicable',seasonal='未確認',seasonalVerification='表頭のSAARは金額フローの共通見出し。人口固有の季節調整の根拠は未確認。',sourceSeasonalHeader='SAAR')
  note='人口（千人）、月中人口ストック。月初と翌月初推計の平均。年率化しません。海外軍人・施設人口を含む総人口（公式脚注6）。人口に季節調整を行う根拠は原表で未確認のためSAと断定しません。'
 elif code=='A072RC':s.update(annualized=False,statisticType='saving_rate',priceBasis='not_applicable');note='個人貯蓄÷可処分個人所得×100。季節調整済み金額からの比率（%）。この比率自体は年率換算しません。'
 elif code in ('A067RCM','PF000969','A067RM'):s.update(annualized=False,statisticType='monthly_percent_change',priceBasis='not_applicable');note='季節調整済み系列の前月比（%）。前月比の年率換算値ではありません。'
 elif code in ('A229RC','A229RX'):s.update(statisticType='income_per_capita');note='1人当たり可処分個人所得、ドル／人・年率。総額（年率）を月中人口で除した値。月額とは異なります。'
 s['definition']=note;s['metadataSource']='https://apps.bea.gov/national/Release/XLS/Survey/Section2All_xls.xlsx#T20600-M';return s

SAVING_NOTE='保存原表（2026年5月URL）は各シート2000年からの値を含む一方、公式解説は2004年からと記載。開始年の説明が不一致で、2000〜2003年の比較可能性は未確認。原値を削除・補間せず、分析時はこの期間を区別してください。'
def complement_metadata(s):
 sid=s.get('id','')
 if sid.startswith('complement:qss:'):
  if s.get('sourceMeasure')=='INPAT':s.update(unit='千日',statisticType='inpatient_days',annualized=False,priceBasis='not_applicable')
  if s.get('sourceMeasure')=='DISC':s.update(unit='千件',statisticType='hospital_discharges',annualized=False,priceBasis='not_applicable')
 if sid.startswith('complement:saving:'):
  s.update(experimental=True,coverageDiscrepancy=SAVING_NOTE,unverifiedEarlyYears='2000–2003',metadataSource='https://www.bea.gov/data/special-topics/distribution-of-personal-income')
  if SAVING_NOTE not in s.get('definition',''):s['definition']=s.get('definition','')+' '+SAVING_NOTE
 if sid.startswith('complement:scf:'):
  s.update(priceBasis='nominal' if 'USD' in s.get('unit','') else 'not_applicable',annualized=False,sourceEdition='public nominal historical',displayDateRule='調査年の1月1日を代表ラベルとして表示。調査日・公表日ではない。所得は原則前年。')
 if sid.startswith('complement:dfa:'):
  s.update(classificationAxis='net_worth_rank',annualized=False,displayDateRule='四半期の初日を代表ラベルとして保存。残高の測定時点は四半期末。公表日ではない。',groupDefinition={'TopPt1':'上位0.1%','RemainingTop1':'上位0.1〜1%（上位0.1%を含まない）','Next9':'上位1〜10%','Next40':'50〜90百分位','Bottom50':'下位50%'}.get(s.get('sourceCategory'),s.get('sourceCategory')))
 return s
