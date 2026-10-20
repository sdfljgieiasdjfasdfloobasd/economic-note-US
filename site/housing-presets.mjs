// Same canonical IDs in both editions; show only complete comparisons.
export function housingPresets(series){
 const ids=new Set(series.filter(s=>s.count).map(s=>s.id));
 const usPrice=series.find(s=>s.id.startsWith('complement:fhfa:traditional:purchase-only:monthly:')&&s.sourceGeo==='USA'&&s.seasonal==='SA')?.id;
 return [
  ['着工・許可・完成（年率）',['housing:starts_cust:Seasonally Adjusted:1','housing:permits_cust:Seasonally Adjusted:1','housing:comps_cust:Seasonally Adjusted:1']],
  ['建設中・許可済み未着工（ストック）',['housing:under_cust:Seasonally Adjusted:1','housing:authnot_cust:Seasonally Adjusted:1']],
  ['新築販売と販売用在庫',['complement:ressales:ASOLD:TOTAL:US:SA','complement:ressales:FORSALE:TOTAL:US:SA']],
  ['新築在庫の消化月数',['complement:ressales:FORSALE:MONSUP:US:SA']],
  ['新築販売の中央値・平均価格',['complement:ressales:SOLD:MEDIAN:US:NSA','complement:ressales:SOLD:AVERAG:US:NSA']],
  ['住宅価格指数（FHFA・前年比）',[usPrice],'history','yoy'],
  ['賃貸・持ち家の空室率',['complement:hvs:賃貸空室率:1','complement:hvs:持ち家空室率:1']],
  ['地域別の持ち家率',['united-states','northeast','midwest','south','west'].map(r=>'complement:hvsdetail:14:Quarterly:'+r)],
  ['住宅ローンの需要・貸出基準',['sloos:SUBLPDHMDE_N.Q','sloos:SUBLPDHMSE_N.Q']],
  ['住宅ローン返済負担',['dsr:MORTGAGE_DSR_RATIO']],
  ['30年・15年住宅ローン金利',['complement:pmms:1','complement:pmms:3']],
 ].filter(p=>p[1].every(id=>ids.has(id)));
}
