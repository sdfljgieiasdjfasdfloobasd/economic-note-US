# 経済データノート — GitHub Pages用

既存のローカルサイトとは独立した、保存データの公開用スナップショットです。
まだGitHubへのアップロード・インターネット公開は行っていません。

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

## データ更新の範囲

この段階では**スナップショット公開**です。クラウドで公式データを自動取得する処理は未導入です。
閲覧画面の「公開データを再読込」は再公開済みファイルを読み直す操作で、公式統計の取得ではありません。
更新する場合は元のローカルサイトでデータ更新を完了し、以下で再作成してGitHubへpushします。
取得失敗・未取得の状態も元の保存状態を保持し、公開準備が公式確認の成功を意味することはありません。
発表予定は保存分を表示し、予定時刻経過の判定のみブラウザの現在時刻に合わせます。

```sh
python3 tools/build.py
python3 tools/verify.py --source-unchanged
python3 tools/package.py
```

`build.py` は元サイトの読み込み用にopenpyxlとlxmlを利用します。
元サイトの隣にこのフォルダを置いて実行してください。別の場所なら `--source` で指定できます。
実行中に元データが変わった場合は作成を中止し、前の公開版を保持します。
直前の公開用ファイルは `.site-previous/` に保持します（GitHubには含めません）。

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

## 2026-10-17 公開前の整理

元のローカルサイト・Excelを変更せず、公開用コピーだけを絞り込みました。
未公開のGitHub Desktopリポジトリには除外前データを含む履歴があったため、
復元用の控えを公開フォルダの外に保存したうえで、公開用の履歴を作り直しました。
GitHubへの送信は別操作です。Desktopで公開用リポジトリを選んでPublish repositoryを使います。
無料のGitHub Pagesで一般公開する場合はKeep this code privateのチェックを外します。
元サイトや私用バックアップのフォルダを追加しないでください。

検証は `python3 tests/publication.py`、`python3 tools/verify.py`、
ブラウザ用の検証は `node --test tests/static-api.mjs` で行えます。
