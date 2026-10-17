"""Explicit publication review, independent of the private/local dashboard.
Unknown or changed series are withheld until individually reviewed. No online calls.
"""
from pathlib import Path
from urllib.parse import urlsplit
from collections import Counter
import hashlib
import html
import json

HERE = Path(__file__).resolve().parent
REVIEW_DATE = '2026-10-17'
RULES = {
 'nyfed_sce': {'name':'New York Fed / SCE', 'terms':'https://www.newyorkfed.org/medialibrary/interactives/sce/sce/downloads/data/frbny-sce-survey-housing-module-public-questionnaire.pdf', 'basis':'SCE公開データの利用・改変・再配布ライセンス。指定の出典・免責を画面と出力に記載。'},
 'philly_spf': {'name':'Philadelphia Fed / SPF', 'terms':'https://www.philadelphiafed.org/about-us/privacy-notice', 'basis':'情報・教育・研究目的の利用条件に基づくSPFの公表集計値。出典を表示し、本サイトの分析を同連銀の見解としない。'},
 'fred_citation': {'name':'St. Louis Fed / FRED inflation compensation', 'terms':'https://fred.stlouisfed.org/legal/', 'basis':'T5YIE・T10YIE・T5YIFRのCopyrighted: Citation Required区分。系列別出典とFRED経由であることを表示。'},

 'bls': {'name':'BLS', 'terms':'https://www.bls.gov/opub/copyright-information.htm', 'basis':'BLS公表統計のpublic-domain方針。出典を表示。写真・ロゴ等は対象外。'},
 'bea': {'name':'BEA', 'terms':'https://www.bea.gov/help/faq/145', 'basis':'BEA公表統計の再利用方針。出典を表示。第三者素材は対象外。'},
 'census': {'name':'U.S. Census Bureau / BEA / HUD', 'terms':'https://www2.census.gov/foia/ds_policies/ds027.pdf', 'basis':'Census作成の公表統計を対象。出典と元の定義・単位を保持。'},
 'board': {'name':'Federal Reserve Board', 'terms':'https://www.federalreserve.gov/disclaimer.htm', 'basis':'理事会作成の公表統計の再利用方針。地区連銀・第三者著作物を一括許可しない。'},
 'dol': {'name':'U.S. Department of Labor', 'terms':'https://www.dol.gov/general/aboutdol/copyright', 'basis':'DOLの公表統計のpublic-domain方針。出典を表示。'},
 'eia': {'name':'U.S. Energy Information Administration', 'terms':'https://www.eia.gov/about/copyrights_reuse.php', 'basis':'EIA作成データの利用・配布方針。出典と保存されている公表日・取得日を保持。ロゴ・第三者素材は対象外。'},
}
RESTRICTED = {
 'ism': 'https://www.ismworld.org/footer/terms-of-use/',
 'sp': 'https://www.pmi.spglobal.com/Public/Home/PressRelease/730109510e164e5489ff0a326463f6ab',
}


def signature(s):
    # Dates, revisions and observations may change; identity/ownership must not.
    identity={k:s.get(k) for k in ('id','provider','unit','frequency','seasonal','definition','inputs','alias')}
    identity['sourceHost']=urlsplit(s.get('source') or '').hostname
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def dataset_signature(d):
    schema={k:d.get(k) for k in ('id','source','kind','baseUnit','metrics')}
    schema['series']=[{k:s.get(k) for k in ('id','label','name','unit')} for s in d['series']]
    return hashlib.sha256(json.dumps(schema,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def registry():
    return json.loads((HERE/'publication-allowlist.json').read_text())


def select(catalog):
    approved=registry()['series']; allowed={}
    decisions=[]
    for s in catalog['series']:
        rule,digest=approved.get(s['id'],[None,None])
        if rule in RULES and digest==signature(s): allowed[s['id']]=rule
    # Removing an input must also remove its computed results.
    while True:
        remove={s['id'] for s in catalog['series'] if s['id'] in allowed and any(x not in allowed for x in s.get('inputs',[]))}
        if not remove:break
        for sid in remove:del allowed[sid]
    for s in catalog['series']:
        sid=s['id'];rule=allowed.get(sid)
        restricted='ism' if sid.startswith('ism:') or sid.startswith('derived:ism_') else 'sp' if sid.startswith('sp:') or s.get('page')=='sp' else None
        decisions.append({'id':sid,'label':s.get('label',''),'provider':s.get('provider') or '提供元未設定','page':s.get('page'),
          'decision':'included' if rule else 'permission_required' if restricted else 'held_for_review',
          'rule':rule,'terms':RULES[rule]['terms'] if rule else RESTRICTED.get(restricted,''),
          'reason':'確認した公開範囲に含む' if rule else '再配布の許諾を確認できないため公開版から除外' if restricted else '系列ごとの再配布条件・必要な権利表示の確認が未完了のため公開保留（禁止と断定するものではありません）'})
    rows=[clean(s,allowed) for s in catalog['series'] if s['id'] in allowed]
    return {**catalog,'series':rows,'failedSources':[], 'publicationPolicy':'reviewed-only',
            'publicationExcluded':len(decisions)-len(rows)}, decisions


def clean(value, allowed):
    if isinstance(value,list):return [clean(v,allowed) for v in value]
    if isinstance(value,dict):
        return {k:([clean(v,allowed) for v in val if v.get('id') in allowed] if k=='relatedSeries' and isinstance(val,list) else clean(val,allowed)) for k,val in value.items()}
    return value


def check_datasets(datasets):
    approved=registry()['datasets']
    for sid,d in datasets.items():
        if approved.get(sid)!=dataset_signature(d):
            raise ValueError('公開用の表定義が変わりました。再配布範囲の確認が必要です: '+sid)


def calendar_scope(c):
    # Only calendars from the agencies covered above; omit local refresh errors.
    hosts={'www.bls.gov','www.bea.gov','www.dol.gov'}
    c={**c,'events':[e for e in c['events'] if urlsplit(e.get('source','')).hostname in hosts],
       'sources':[s for s in c['sources'] if urlsplit(s.get('url','')).hostname in hosts],
       'exclusions':[{'label':'公開版のカレンダー','source':'publication-scope.html','reason':'再配布条件を確認したBLS・BEA・DOLの保存済み予定のみ。掲載していない統計の発表がないことを意味しません。'}]}
    return c


def write_report(stage, decisions, built_at):
    counts=Counter(d['decision'] for d in decisions)
    providers={}
    for d in decisions:
        row=providers.setdefault(d['provider'],Counter());row[d['decision']]+=1
    report={'reviewedAt':REVIEW_DATE,'builtAt':built_at,'policy':'reviewed-only','counts':dict(counts),
            'providers':{k:dict(v) for k,v in sorted(providers.items())},'rules':RULES,'series':decisions}
    e=html.escape
    table=''.join('<tr><th>'+e(p)+'</th>'+''.join('<td>'+str(n.get(k,0))+'</td>' for k in ('included','permission_required','held_for_review'))+'</tr>' for p,n in sorted(providers.items()))
    rules=''.join(f'<li><a href="{e(v["terms"])}">{e(v["name"])}</a>：{e(v["basis"])}</li>' for v in RULES.values())
    held=''.join(f'<tr><td>{e(d["provider"])}</td><td>{e(d["label"])}</td><td>{e(d["id"])}</td><td>{e(d["reason"])}</td></tr>' for d in decisions if d['decision']!='included')
    text=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>公開範囲・出典 | 経済データノート</title><style>body{{font:16px/1.7 system-ui;max-width:1100px;margin:auto;padding:24px;color:#244451}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;border-bottom:1px solid #ddd;padding:6px;overflow-wrap:anywhere}}a{{color:#007f75}}.scroll{{overflow:auto}}summary{{cursor:pointer}}</style><a href="./">← サイトへ</a><h1>公開範囲・出典</h1>
<p>確認日：{REVIEW_DATE}。この公開版では、確認した再配布範囲に含まれる統計だけを配信します。各系列の元の数値精度・出典・観測日・取得日は詳細に保持しています。元のMac用サイトは別に保存されています。</p>
<p>拡張カタログ {len(decisions):,} 系列中、公開対象 {counts['included']:,}、許諾確認が必要 {counts['permission_required']:,}、確認未完了で保留 {counts['held_for_review']:,}。未取得のカタログ項目も件数に含みます。これに加えてBLS・BEAの基本表10表を収録しています。</p>
<p>再配布条件が未確認の系列は公開保留です。再配布が禁止されていると断定したものではありません。新規系列や提供元・定義が変わった系列も、確認するまでは自動で公開しません。</p>
<h2>出典・利用方針</h2><ul>{rules}</ul>
<p>本サイトのグラフ、翻訳、比率や移動平均などの計算は公開者による加工です。公式機関による承認・推奨を示すものではありません。各提供元の原公表値と計算値を区別してください。出典：U.S. Bureau of Labor Statistics、U.S. Bureau of Economic Analysis、U.S. Census Bureau、U.S. Department of Labor、Board of Governors of the Federal Reserve System、U.S. Energy Information Administration。EIAデータの公表日が不明な場合は公表日不明とし、取得日で代用しません。</p>
<p>ISMは<a href="{RESTRICTED['ism']}">利用規約</a>、S&amp;P Global PMIは<a href="{RESTRICTED['sp']}">リリースの利用条件</a>に基づき、別途許諾を確認するまで数値とその派生系列を公開しません。</p>
<h2>提供元別</h2><div class="scroll"><table><tr><th>提供元</th><th>公開対象</th><th>許諾確認</th><th>確認保留</th></tr>{table}</table></div>
<details><summary>公開しない系列の一覧</summary><div class="scroll"><table><tr><th>提供元</th><th>系列名</th><th>ID</th><th>理由</th></tr>{held}</table></div></details></html>'''
    (stage/'publication-scope.html').write_text(text)
    return report
