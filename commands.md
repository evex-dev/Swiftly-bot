# command list

- /arima_growth target:予測したいメンバー数 show_graph:false or true | サーバーの成長をARIMAモデルで予測します。
    ユーザー権限: なし
    bot権限: なし
- /base64 action:decode or encode content:<コンテンツ> |  Base64エンコードまたはデコードします。
    ユーザー権限: なし
    bot権限: なし

- /regiser | サーバーを掲示板に登録します
    ユーザー権限: サーバー管理者
    bot権限: 招待作成

- /board-setting | サーバーの説明文を設定します。
    ユーザー権限: サーバー管理者
    bot権限: なし

- /up | サーバーの表示順位を上げます。
    ユーザー権限: なし
    bot権限: なし

- /botadmin (option) | Bot管理コマンド
    ユーザー権限: bot管理者のみ
    bot権限: なし

- /captcha difficulty:1~10 | CAPTCHA画像を生成し、解答を検証します。
    ユーザー権限: なし
    bot権限: なし

- /help-command | Swiftlyが提供するすべてのコマンドを表示します。
    ユーザー権限: なし
    bot権限: なし

- /first-comment | このチャンネルの最初のメッセージへのリンクを取得します。
    ユーザー権限: なし
    bot権限: なし

- /growth target:予測したいメンバー数 show_graph:false or true | サーバーの成長を予測します。全サーバー向きです。
    ユーザー権限: なし
    bot権限: なし

- /help | Swiftlyのヘルプを表示します。
    ユーザー権限: なし
    bot権限: なし

- /imagegen prompt:< prompt > | 与えられたプロンプトに基づいて画像を生成します
    ユーザー権限:　なし
    bot権限: なし

- /ip ip_addr:(ip) | IP情報を取得します。
    ユーザー権限: なし
    bot権限: なし
    備考: オプションは有効なIPアドレスである必要があります。

- /love-calculator user1: user2: | 2人のユーザーを選択して愛の相性を計算します。
    ユーザー権限: なし
    bot権限: なし

- /fantasy-status user: | 特定の人の装備品、攻撃力、守備力、体力を表示する。
    ユーザー権限: なし
    bot権限: なし

- /your-cpu-gpu user: | 特定の人をCPU、GPUで例えると...？
    ユーザー権限: なし
    bot権限: なし

- /versus user1: user2: | fantasy-statusのステータスをもとに対戦させます。ステータスは固定ですがそれ以外はランダム。
    ユーザー権限: なし
    bot権限: なし

- /skin username: | Minecraftのスキンを取得します。Java版のみ。
    ユーザー権限: なし
    bot権限: なし
    備考: 存在するJava版のユーザー名である必要があります。

- /minecraft address: | Minecraft サーバーのステータスを取得する。
    ユーザー権限: なし
    bot権限: なし
    備考: 存在するサーバーのアドレスである必要があります。取得には時間がかかる可能性があります。

- /moji-bake content: | 文字をわざと文字化けさせます。
    ユーザー権限: なし
    bot権限: なし

- /search_package manager:pip or npm package: | npmまたはpipのパッケージを検索します
    ユーザー権限: なし
    bot権限 : なし

- /ping | pingを返します
    ユーザー権限: なし
    bot権限: なし

- /poll action:create/end title:タイトル description:説明 duration:期間 options:選択肢 | 匿名投票を作成・管理します。
    ユーザー権限: なし
    bot権限: なし
    備考: createでは選択肢をカンマ区切りで指定。期間は30分/1時間/12時間/1日/3日/1週間から選択。投票は自動で終了し7日後に削除されます。

- /prophet_growth target:予測したいメンバー数 show_graph:false or true | サーバーの成長を予測します。Prophetは大規模サーバー向けです。
    ユーザー権限: なし
    bot権限: なし

- /pysandbox code: | Python コードをサンドボックスで実行し、結果を返します。
    ユーザー権限: なし
    bot権限: なし

- ?pysandbox (code) | Python コードをサンドボックスで実行し、結果を返します。
    ユーザー権限: なし
    bot権限: 発言　メッセージの読み取り　チャンネルを見る

- /sandbox code: | JavaScript コードをサンドボックスで実行し、結果を返します。
    ユーザー権限: なし
    bot権限: なし

- ?sandbox (code) | JavaScript コードをサンドボックスで実行し、結果を返します。
    ユーザー権限: なし
    bot権限: 発言　メッセージの読み取り　チャンネルを見る

- /status | ボットのステータスを確認します
    ユーザー権限: なし
    bot権限: なし

- /time | 現在の時間を取得します。
    ユーザー権限: なし
    bot権限: なし

- /time-signal channel: time: | 指定したチャンネルと時間に時報を設定します。
    ユーザー権限: サーバー管理者
    bot権限: 指定したチャンネルでの発言権
    備考: １チャンネルには3つまで時報を設定できます。

- /join | ボイスチャンネルに参加します。このコマンドを打ったチャンネルの読み上げが開始されます。
    ユーザー権限: なし
    bot権限: ボイスチャンネルへの接続
    備考: ユーザーがVCに参加している必要があります

- /leave | ボイスチャンネルから退出します
    ユーザー権限: なし
    bot権限: ボイスチャンネルへの接続
    備考: ユーザーがVCに参加している必要があります

- /vc-tts message: | メッセージを読み上げます
    ユーザー権限: なし
    bot権限: ボイスチャンネルへの接続　VCでの発言権
    備考: ユーザーがVCに参加している必要があります

- /whois domain: | ドメインのwhois情報を返します
    ユーザー権限: なし
    bot権限: なし
    備考: 有効なドメインである必要があります

- /youyaku channel: num_messages:~1000 | 指定したチャンネルのメッセージを要約します。
    ユーザー権限: なし
    bot権限: 指定したチャンネルを見る権限

- /welcome action:enable/disable increment:5~1000 | サーバーへの参加メッセージを設定します。
    ユーザー権限: サーバー管理者
    bot権限: メッセージ送信
    備考: incrementは何人ごとにお祝いメッセージを送信するか設定（デフォルト: 100人）。
         システムメッセージチャンネルまたは一般チャンネルに送信されます
