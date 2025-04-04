# 経済システムコマンド

## 基本コマンド
- `/balance` - 現在の所持金を確認します
- `/transfer` - 指定したユーザーに所持金を送金します (botには送金できません)
- `/daily` - デイリーボーナスを受け取ります (24時間に1回)

## 仕事・収入コマンド
- `/work` - 働いてお金を稼ぎます (30分に1回)
- `/tasks` - 小さなタスクをこなしてお金を稼ぎます (15分に1回)
- `/parttime` - アルバイトをしてお金を稼ぎます (60分に1回)

## 投資コマンド
- `/stocks` - 株式市場の一覧を表示します
- `/buystock` - 株式を購入します
- `/sellstock` - 保有している株式を売却します
- `/portfolio` - 保有している株式ポートフォリオを表示します
- `/stockinfo` - 特定の株式の詳細情報を表示します

## 経済システムについて
- 通貨名: スイフト (🪙)
- データベース: aiosqliteを使用した複数のDBファイル
  - `data/economy.db` - 基本的な残高・取引履歴
  - `data/work.db` - 労働記録
  - `data/investment.db` - 株式・投資情報