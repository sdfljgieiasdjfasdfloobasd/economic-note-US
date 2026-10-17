// Curated comparisons based on the official analyses linked below; not a popularity ranking.
const fed='https://www.federalreserve.gov/monetarypolicy/2025-06-mpr-part1.htm';
const speech='https://www.federalreserve.gov/newsevents/speech/kugler20250402a.htm';
const sce='https://www.newyorkfed.org/microeconomics/sce/sce-faq';
const spf='https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters';
export const expectationPresets=[
 {id:'household-short',group:'短期',title:'家計の1年先を比較',series:['michigan:PX_MD','nyfed:Inflation expectations:1'],summary:'ミシガン大学 × NY連銀 · 1年先・中央値',purpose:'短期の物価不安が両調査で広がっているかを確認します。',note:'どちらも家計の1年先予想ですが、質問文・調査方法・回答者が違います。水準の差をそのまま予測精度の差とは解釈しません。',sources:[['FRB：短期・長期の期待',fed],['NY連銀：設問の定義',sce]]},
 {id:'michigan-horizons',group:'年限別',title:'ミシガン大学：短期と長期',series:['michigan:PX_MD','michigan:PX5_MD'],summary:'1年先 × 5〜10年先 · 家計・中央値',purpose:'短期の上昇が長期の期待にも波及しているかを見ます。FRBの講演でも使われる比較です。',note:'同じ調査内の比較です。長期は5〜10年先について尋ねた年平均の物価上昇予想で、5年先の単年予想ではありません。',sources:[['FRB：図1と年限の説明',speech]]},
 {id:'nyfed-horizons',group:'年限別',title:'NY連銀：1年・3年・5年先',series:['nyfed:Inflation expectations:1','nyfed:Inflation expectations:2','nyfed:Five-year ahead Infl Exp:1'],summary:'短期・中期・長期 · 家計・中央値',purpose:'同じ調査の予測期間を並べ、物価上昇が長く続くと考えられているかを見ます。',note:'3年先は今から2〜3年後の1年間、5年先は4〜5年後の1年間の予想です。3年平均・5年平均ではありません。5年先系列の開始前は補完しません。',sources:[['NY連銀：予測期間の定義',sce]]},
 {id:'long-surveys',group:'長期',title:'長期：家計と専門家',series:['michigan:PX5_MD','spf:median:CPI10','spf:median:PCE10'],summary:'ミシガン5〜10年 × SPF CPI・PCE 10年',purpose:'長期の期待が安定しているか、家計と専門家の方向が揃っているかを確認します。',note:'年限・物価の定義は一致しません。SPFは今後10年間の年平均予測で、CPIとPCEも別の物価指数です。月次の家計調査と四半期の専門家調査を元の観測頻度で重ねています。',sources:[['FRB：家計・専門家の長期期待',fed],['Philadelphia連銀：SPF',spf]]},
 {id:'market',group:'市場',title:'市場：5年・10年・5年先5年',series:['fred:T5YIE','fred:T10YIE','fred:T5YIFR'],summary:'5年BEI × 10年BEI × 5年先5年フォワード',purpose:'市場が織り込む物価上昇の変化を、近い期間と遠い期間に分けて追います。',note:'5年BEI・10年BEIは今後各期間、5年先5年は今から5〜10年後の平均的なインフレ補償です。純粋な予想だけでなくリスクプレミアムや流動性の影響も含みます。日次値を表示します。',sources:[['FRB：インフレ補償の分析',fed],['FRED：5年先5年の定義','https://fred.stlouisfed.org/series/T5YIFR']]},
 {id:'household-business',group:'主体別',title:'1年先：家計と企業',series:['michigan:PX_MD','nyfed:Inflation expectations:1','bie:1y'],summary:'ミシガン・NY連銀 × Atlanta BIE',purpose:'家計の物価不安と企業のコスト見通しの方向を比較する、補助的な組み合わせです。',note:'家計の中央値に対し、BIEは米南東部の企業が予想する自社の単位コスト変化率の平均です。BIEはCPI・PCE予測ではなく、対象も集計方法も異なります。',sources:[['FRB：家計・企業の期待',speech],['Atlanta連銀：BIE','https://www.atlantafed.org/research-and-data/surveys/business-inflation-expectations']]},
 {id:'spf-horizons',group:'専門家',title:'SPF：CPI・PCEの5年と10年',series:['spf:median:CPI5YR','spf:median:CPI10','spf:median:PCE5YR','spf:median:PCE10'],summary:'CPI 5年・10年 × PCE 5年・10年',purpose:'専門家の長期予測を、物価指数と予測期間ごとに確認します。',note:'どれも期間内の年平均インフレ率の予測中央値です。CPI5YRは5年平均で、別コードCPI5（3四半期先）とは異なります。調査四半期を横軸にしています。',sources:[['Philadelphia連銀：SPFのデータと資料',spf]]},
 {id:'cie',group:'総合',title:'CIE：期待の共通した動き',series:['cie:CIE_spf','cie:CIE_mich'],summary:'SPF長期PCE尺度 × ミシガン長期尺度',purpose:'複数指標に共通する期待インフレの動きを確認します。',note:'同じ共通因子を異なる尺度に投影した2系列です。独立した2つの調査ではなく、SPF・ミシガンの元の予測値でもありません。研究統計であり、尺度間の差に経済的な意味を持たせません。',sources:[['FRB：CIEの定義','https://www.federalreserve.gov/econres/notes/feds-notes/research-data-series-index-of-common-inflation-expectations-20210305.html']]},
];
export function presetAvailability(preset,series){
 const available=new Set(series.filter(s=>s.count>0).map(s=>s.id));
 const missing=preset.series.filter(id=>!available.has(id));
 return {complete:missing.length===0,missing,count:preset.series.length-missing.length};
}

export const sceAttribution='Source: Survey of Consumer Expectations, © 2013–2026 Federal Reserve Bank of New York (FRBNY). The SCE data are available without charge at https://www.newyorkfed.org/microeconomics/sce and may be used subject to license terms posted there. FRBNY disclaims any responsibility for this analysis and interpretation of Survey of Consumer Expectations data.';
export function seriesAttribution(s){
 const id=(s.id||'').replace(/^ex:/,''),label=s.label||'';
 if(id.startsWith('nyfed:')||label.startsWith('NY Fed SCE '))return sceAttribution;
 if(id.startsWith('spf:')||label.startsWith('SPF '))return 'Source: Survey of Professional Forecasters, Federal Reserve Bank of Philadelphia. https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters';
 const code=['T5YIE','T10YIE','T5YIFR'].find(c=>id==='fred:'+c)||(/5-Year, 5-Year Forward Inflation/.test(label)?'T5YIFR':/10-Year Breakeven/.test(label)?'T10YIE':/5-Year Breakeven/.test(label)?'T5YIE':null);
 return code?'Source: Federal Reserve Bank of St. Louis, '+code+', retrieved from FRED. https://fred.stlouisfed.org/series/'+code:'';
}
export function seriesAttributions(series){return [...new Set(series.map(seriesAttribution).filter(Boolean))]}
