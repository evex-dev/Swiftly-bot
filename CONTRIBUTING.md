# コントリビューションガイド

まずはこのプロジェクトに関心を持ってくださりありがとうございます。

Swiftly-botはオープンソースとして公開されていますが、品質と安定性を保つために、以下のルールを守ってコントリビュートしていただけると助かります。

## 🛠 Issue・Pull Request の前に

- バグ報告・機能提案・質問は **必ず GitHub の [Issue](https://github.com/evex-dev/Swiftly-bot/issues) を通じて行ってください**。
- Discord や DM、メール等でのご連絡には**対応しておりません**（記録の一元化と管理のため）。


## 🔧 開発環境の構築方法

1. リポジトリをクローンします。

   ```bash
   git clone https://github.com/evex-dev/Swiftly-bot.git
   cd Swiftly-bot
   ```

2. Python仮想環境を作成します。

   ```bash
   python -m venv venv
   ```

3. 仮想環境をアクティベートします。

   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`

4. 依存関係をインストールします。

   ```bash
   pip install -r requirements.txt
   ```

5. `.env` ファイルを作成し、Discordトークンを設定します。

   ```env
   DISCORD_TOKEN=<your_token_here>
   ```

6. Botを実行します。

   ```bash
   python bot.py
   ```

## 📌 PR（プルリクエスト）の際のお願い

- **追加・変更したコマンドがある場合、その内容をPRの説明欄に必ず明記してください。**
- 意図が伝わるように、できるだけ詳しく書いてください（何を・なぜ追加/変更したか）。
- コーディング規約やフォーマットの統一にご協力ください（可能であれば `black` や `ruff` 等で整形してください）。

## 🔐 ライセンスについて

このプロジェクトは **AGPL-3.0** に基づいて公開されています。  
ネットワーク越しに提供されるBotであるため、コードを改変して提供する場合は、その改変を含む全コードの公開義務があります。  
詳細は [LICENSE](./LICENSE) をご参照ください。

## 🙏 最後に

Swiftly-botは個人で開発・運用されているプロジェクトです。  
すべてのIssue・PRに即時対応できるわけではないことをご了承ください。  
建設的で前向きなコントリビューションを心より歓迎します。