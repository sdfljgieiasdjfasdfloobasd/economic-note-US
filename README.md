# 経済データノート — GitHub Pages用

既存のMac用サイトとは独立した公開版です。
公開URL: https://sdfljgieiasdjfasdfloobasd.github.io/economic-note-US/

## 元のサイトに戻る

元の `economic-dashboard` フォルダ、Excel、起動用ファイルは変更しません。
これまでどおり親フォルダの「経済データノートを開く.command」を開き、
http://127.0.0.1:8765/ にアクセスしてください。
公開準備をやめても移行・復元作業は不要です。
公開版の試用は別ポート8766を使います。元サイトを停止しません。

`.private/original-source.zip` は準備開始時の元コードとお気に入りの控えです。
原Excel・履歴データは元フォルダに残っています。この控えはGitHubにも梱包ZIPにも含めません。

## 公開用の構成

- `site/`: Pagesに配置するHTML・CSS・JavaScript・圧縮JSONのみ。
- `templates/`: 公開版専用のデータ読み込み・PDF出力処理。
- `tools/build.py`: 元サイトの保存済みデータから再作成。公式サイトへの取得やアップロードはしません。
- `tools/verify.py`: 全データのハッシュ・参照整合・容量・ローカル情報混入を検査。
- `.github/workflows/pages.yml`: mainにpushした公開用ファイルを検証してPagesへ配置。
- `build-report.json`: 容量・系列数・観測数。
- `site/publication-scope.html`: 公開範囲・出典・除外理由。
- `publication-report.json`: 全カタログ項目の採否一覧。除外系列の数値は含みません。
- `tools/publication-allowlist.json`: 確認した系列のID・提供元・定義の照合情報。

数値や日付を丸めずJSONをgzip圧縮し、選択した系列だけダウンロードします。
原Excel、生の取得ファイル、改定履歴の保管庫、更新ログ、個人のお気に入り、
ローカル設定・トークン、調査資料は公開物から除外します。
公開対象の公式メタデータと、画面で必要な公表時点情報は保持します。
ローカル更新ログには除外系列の過去値が含まれる可能性があるため、公開版にはコピーしません。

## この版でできること

既存のグラフ、期間・指標切替、表・ヒートマップ、統計横断比較、回帰分析、
系列の一時非表示、軸指定、CSV・PNG・SVG・PDF保存をブラウザで処理します。
お気に入りは端末・ブラウザ・サイトごとのlocalStorageに保存します。
他人と共有されず、別端末には同期しません。ブラウザの保存データを消すと失われます。
元Excelのダウンロードは公開版には含めません。

Safari 16.4以降などDecompressionStreamに対応したブラウザが必要です。
公開後の閲覧にはMacの電源は不要です。

## 毎朝4時の自動更新（日本時間）

GitHub Actionsが毎日04:00 JST（UTCでは前日19:00）に起動し、公開対象の公式データを取得・検証してPagesに反映します。夏時間によるJSTの時刻変更はありません。混雑時は開始が遅れる場合があり、完了は取得時間の後になります。Macの起動・Codexの起動は不要で、AI APIは使いません。

- `cloud/refresh.py`: 公開スナップショットだけを入力に更新。Macのフォルダ・Excelを参照しません。
- `cloud/`: BLS・BEA・Census・FRB理事会・DOL・EIAと承認済みFRED系列の取得処理。
- `.github/workflows/pages.yml`: スケジュール実行・手動実行では取得→検証→GitHubに保存→Pagesへ配置。通常のpushは検証→配置のみ。
- サイト上の「自動更新の結果」で、直近の試行・取得処理ごとの失敗理由を確認できます。
- 閲覧者の再読込ボタンは、公開済みのデータを読み直すだけです。

取得失敗・古い応答・形式変更時は保存済みの値を保持します。定義・提供元・単位の変更や未承認の新規系列は自動公開しません。公式の改定は同じ対象期へ反映し、過去の保存履歴は維持します。元データが欠損を明示しているときは0に変換しません。

CPI Table 6の発表時点寄与度、雇用の年次ベンチマーク保存値は自動更新の対象外です。ISМ・S&P等の公開保留範囲も取得・公開対象になりません。これらが毎日最新になるという意味ではありません。

手動でクラウド更新するには、GitHubのActions → **Publish prepared economic dashboard** → **Run workflow**を選び、refreshを有効にします。falseは保存済みデータの再公開だけです。

公開用の画面を改良するときは、先にGitHub Desktopの **Fetch origin → Pull origin** で日次更新のコミットを取り込み、その後変更・Commit・Pushします。取り込まずに古い公開データで上書きしないでください。

停止はGitHubのActionsでこのworkflowをDisable workflow、またはschedule部分を削除します。元のMac用サイトはそのまま使えます。公開版だけを戻す場合はGitHub Desktopで対象コミットをRevertしてPushします（他の履歴を消すreset/force-pushは不要です）。公開リポジトリのスケジュールは60日間活動がないとGitHub側で無効になる場合があります。

元サイトのデータを手動で公開版へ作り直す旧手順も残しています。これはクラウド更新とは別で、実行するとその時点のMac保存値に置き換わるため、意図した場合だけ使ってください。

```sh
python3 tools/build.py
python3 tools/verify.py --source-unchanged
python3 tools/package.py
```

`build.py` はopenpyxlとlxmlを利用します。元サイトの隣にこのフォルダを置き、別の場所では `--source` を指定します。日次実行では使用しません。

## ローカルで試す

このMacでは「公開版をプレビュー.command」をダブルクリックできます。
「元のサイトを開く.command」で従来のサイトを開けます。
これらのMac用起動ファイルは配布ZIPには含めません。

```sh
python3 tools/preview.py --open
```

http://127.0.0.1:8766/economic-note/ が公開版のプレビューです。
プレビュー自体はこのMac専用です。これは将来の公開URLではありません。
GitHubのプロジェクト名付きURLを想定して、サブパス付きで動作検証できます。
公開物にPythonサーバーは必要ありません。

## GitHubアカウント作成後

1. GitHubで公開用の空のリポジトリを作ります。名前の例は `economic-note`。
2. GitHub Desktop等で、このフォルダの中身をmainブランチへ登録します。
   大量のファイルがあるためブラウザの手動アップロードは避けます。
   `.gitignore`を必ず含め、`.private`・`.site-previous`・ZIPを登録しないでください。
3. リポジトリの Settings → Pages → Build and deployment → Source を **GitHub Actions** にします。
4. Actionsの「Publish prepared economic dashboard」を実行します（以後mainへのpushでも実行）。
5. 成功後のPages URLをスマホ・友達と共有できます。

この無料構成ではサイトと登録したリポジトリの内容が一般公開されます。
ここに個人資料を追加しないでください。公開版はBLS・BEA・Census・FRB理事会・DOL・EIAの確認済み系列に限定しています。
ISM・S&Pは再配布の許諾未確認のため除外し、その他の未確認系列は公開保留としました。
保留は再配布禁止と断定したものではありません。詳しくは公開範囲ページを参照してください。
未確認の新規系列や定義・提供元が変わった系列は、再作成時も自動で公開しません。
BLS・BEAの基本表の構成変更時は作成を中止し、確認を求めます。
参照されない古い圧縮データが残っている場合も、検証で公開処理を止めます。
公開後に取りやめる場合はSettings → PagesのUnpublish siteで停止できますが、
公開済みのコピーやダウンロードまで回収することはできません。元のローカルサイトはそのまま使えます。

公式手順: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
容量制限: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits

## 検証

`python3 tests/cloud.py`、`python3 tests/publication.py`、`python3 tools/verify.py`。
ブラウザ用APIの検証は `node --test tests/static-api.mjs`。
公開範囲の承認リストは日次更新では変更しません。


### 期待インフレの公開比較（2026-10-17）

公開版はCIEに加え、NY連銀SCEの6系列、SPFの5年・10年CPI/PCE中央値4系列、FREDのT5YIE/T10YIE/T5YIFRを収録。NY連銀・市場・SPF・CIEの4種類を比較ボタンから選択できます。必要な系列が欠ける比較はボタンにせず、理由を折りたたみ欄に表示します。ミシガン大学の原系列は公開ダッシュボードの再配布条件を確認するまで非収録です。

SCE・SPFは公式Excelの既存パーサーを公開用に分離し、毎朝の更新に追加しました。許可リスト外の系列は配信しません。出典・SCE指定の免責はグラフ・表・CSV・画像出力にも含めます。追加前の28,601系列と基本表はバイト単位で変更なし。公開物全体の検証、保存済み公式Excelによる10系列の更新試験、4比較のブラウザ操作、SVG出典表示を確認しました。

条件確認元：
- https://www.newyorkfed.org/medialibrary/interactives/sce/sce/downloads/data/frbny-sce-survey-housing-module-public-questionnaire.pdf
- https://www.philadelphiafed.org/about-us/privacy-notice
- https://fred.stlouisfed.org/legal/ （3系列ともCitation Required区分）
- https://data.sca.isr.umich.edu/agreement.php
