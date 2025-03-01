# Swiftly-bot
Swiftly, a multi-function Discord bot

![swiftlyアイキャッチ](https://github.com/user-attachments/assets/2778b024-fa5a-4873-bec7-b75c45231365)

## Swiftlyのコマンド一覧
以下はSwiftlyが提供するコマンドとその説明です。

- `/wikipedia`
    Wikipediaで検索します。

- `/prophet_growth`
    サーバーの成長を予測します。Prophetは大規模サーバー向けです。

- `/arima_growth`
    サーバーの成長をARIMAモデルで予測します。

- `/help`
    Swiftlyのヘルプを表示します。

- `/captcha`
    Generate a CAPTCHA image.

- `/youyaku`
    指定したチャンネルのメッセージを要約します。

- `/ping`
    Replies with pong and latency.

- `/help-command`
    Swiftlyが提供するすべてのコマンドを表示します。

- `/time`
    現在の時間を取得します。

- `/moji-bake`
    文字をわざと文字化けさせます。

- `/first-comment`
    このチャンネルの最初のメッセージへのリンクを取得します。

- `/growth`
    サーバーの成長を予測します。全サーバー向きです。

- `/base64`
    Base64エンコードまたはデコードします。

- `/status`
    ボットのステータスを確認します。

- `/botadmin`
    Bot管理コマンド

- `/set_mute_channel`
    コマンド実行禁止チャンネルを設定します。管理者のみ実行可能です。

その他にも色々あります！

# LICENSE
- **edge-tts** - LGPL-3.0 License  
  - [some-lgpl-library GitHub リポジトリ]([https://github.com/someone/some-lgpl-library](https://github.com/rany2/edge-tts))
  - このライブラリは LGPL-3.0 ライセンスで配布されています。ソースコードは上記のリンクからアクセスできます。

## コントリビューターのみなさんへ

**お願い**
プルリクエストするとき、追加したコマンドがあるなら追加したコマンドを書いてくれるとありがたいです。
よろしくお願いします。

**Botのテスト方法**

1. リポジトリをクローン
```
git clone https://github.com/evex-dev/Swiftly-bot.git
```

2. Python仮想環境を作成

3. 仮想環境をアクティベート

4. 依存関係をインストール
```
pip install -r requirements.txt
```

5. tokenを.envファイルに記載
```env
DISCORD_TOKEN=<token>
```

6. bot.pyを実行
