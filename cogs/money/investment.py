import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import random
import asyncio
from datetime import datetime, timedelta
import math

class Investment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'data/investment.db'
        self.economy_cog = None
        self.currency_name = "スイフト"  # デフォルト値
        self.currency_symbol = "🪙"  # デフォルト値
        self.stock_update_task = None
        self.stocks = {}
        self.bank_user_id = 0  # システム/銀行のユーザーID
        self.trade_fee_rate = 0.02  # 取引手数料率 (2%)
        self.dynamic_trade_fee_rate = self.trade_fee_rate  # イベントによる動的な取引手数料率
        self.market_events = []  # 市場イベントのリスト
        self.last_market_event = None
        bot.loop.create_task(self.setup_database())
        bot.loop.create_task(self.load_economy_cog())
        bot.loop.create_task(self.event_listener())
    
    async def load_economy_cog(self):
        """Economy cogを読み込む（利用可能になったタイミングで）"""
        for _ in range(10):  # 10回までリトライ
            self.economy_cog = self.bot.get_cog("Economy")
            if self.economy_cog:
                self.currency_name = self.economy_cog.currency_name
                self.currency_symbol = self.economy_cog.currency_symbol
                break
            await asyncio.sleep(5)  # 5秒待機
        
        # 株価更新タスクの開始（Economy cogがなくても開始）
        self.stock_update_task = self.bot.loop.create_task(self.update_stocks_loop())
        
        # 初期株価の読み込み
        await self.load_stocks()
    
    async def get_currency_info(self):
        """通貨情報の取得 (Economy cogがない場合はデフォルト値を使用)"""
        if self.economy_cog:
            return self.economy_cog.currency_symbol, self.economy_cog.currency_name
        return self.currency_symbol, self.currency_name
    
    async def update_balance(self, user_id, amount):
        """残高更新 (Economy cogがない場合はFalseを返す)"""
        if not self.economy_cog:
            return False
        await self.economy_cog.update_balance(user_id, amount)
        return True
    
    async def get_balance(self, user_id):
        """残高取得 (Economy cogがない場合は0を返す)"""
        if not self.economy_cog:
            return 0
        return await self.economy_cog.get_balance(user_id)
    
    async def add_transaction(self, sender_id, receiver_id, amount, description):
        """取引記録 (Economy cogがない場合は何もしない)"""
        if not self.economy_cog:
            return
        await self.economy_cog.add_transaction(sender_id, receiver_id, amount, description)
    
    async def cog_unload(self):
        # タスクのキャンセル
        if self.stock_update_task:
            self.stock_update_task.cancel()
    
    async def setup_database(self):
        # データディレクトリの確認
        os.makedirs('data', exist_ok=True)
        
        # データベース接続
        async with aiosqlite.connect(self.db_path) as db:
            # 株式テーブル
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    prev_price REAL NOT NULL,
                    volatility REAL NOT NULL,
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ユーザー株式保有テーブル
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_stocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stock_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    purchase_price REAL NOT NULL,
                    purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (stock_id) REFERENCES stocks (id)
                )
            ''')
            
            # 投資ログテーブル
            await db.execute('''
                CREATE TABLE IF NOT EXISTS investment_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stock_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (stock_id) REFERENCES stocks (id)
                )
            ''')
            
            # サンプル株の追加（初回のみ）
            cursor = await db.execute('SELECT COUNT(*) FROM stocks')
            count = await cursor.fetchone()
            
            if count[0] == 0:
                sample_stocks = [
                    ("SWFT", "スイフトテック", 1000.0, 1000.0, 0.15),
                    ("DIGI", "デジタルコーポレーション", 750.0, 750.0, 0.12),
                    ("GAME", "ゲームエンターテイメント", 500.0, 500.0, 0.20),
                    ("FOOD", "フードチェーン", 350.0, 350.0, 0.10),
                    ("ENER", "エネルギー産業", 1200.0, 1200.0, 0.18),
                    ("MEDC", "メディカルサイエンス", 900.0, 900.0, 0.25),
                    ("BANK", "バンキング財団", 1500.0, 1500.0, 0.08),
                    ("LUXR", "ラグジュアリーブランド", 2000.0, 2000.0, 0.22)
                ]
                
                now = datetime.now().isoformat()
                
                for stock in sample_stocks:
                    await db.execute(
                        'INSERT INTO stocks (symbol, name, price, prev_price, volatility, last_update) VALUES (?, ?, ?, ?, ?, ?)',
                        (stock[0], stock[1], stock[2], stock[3], stock[4], now)
                    )
            
            await db.commit()
    
    async def load_stocks(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM stocks')
            stocks = await cursor.fetchall()
            
            # メモリに株価情報を読み込む
            self.stocks = {stock['symbol']: dict(stock) for stock in stocks}
    
    async def update_stocks_loop(self):
        """定期的に株価を更新するループ"""
        try:
            while True:
                # 市場イベントの更新（20%の確率）
                if random.random() < 0.2:
                    await self.generate_market_event()
                
                await self.update_stock_prices()
                await asyncio.sleep(3600)  # 1時間ごとに更新
        except asyncio.CancelledError:
            pass
    
    async def generate_market_event(self):
        """市場イベントの生成"""
        events = [
            {"name": "市場好調", "description": "市場全体が好調に推移しています。", "effect": (0.05, 0.15), "emoji": "📈"},
            {"name": "市場低迷", "description": "市場全体が低迷しています。", "effect": (-0.15, -0.05), "emoji": "📉"},
            {"name": "テクノロジーブーム", "description": "テクノロジー関連企業の株価が急上昇しています。", "effect": (0.1, 0.2), "emoji": "💻", "sectors": ["SWFT", "DIGI", "GAME"]},
            {"name": "医療業界の躍進", "description": "医療関連企業の株価が上昇しています。", "effect": (0.1, 0.2), "emoji": "🏥", "sectors": ["MEDC"]},
            {"name": "エネルギー危機", "description": "エネルギー関連企業の株価が下落しています。", "effect": (-0.2, -0.1), "emoji": "⚡", "sectors": ["ENER"]},
            {"name": "消費者需要増加", "description": "小売業とフード関連企業の株価が上昇しています。", "effect": (0.05, 0.15), "emoji": "🛒", "sectors": ["FOOD", "LUXR"]},
            {"name": "金融不安", "description": "銀行と金融関連企業の株価が下落しています。", "effect": (-0.15, -0.05), "emoji": "🏦", "sectors": ["BANK"]}
        ]
        
        # ランダムにイベントを選択
        event = random.choice(events)
        self.last_market_event = event
        self.market_events.append({
            "event": event,
            "timestamp": datetime.now()
        })
        
        # イベントに基づいて、関連する株式のボラティリティを一時的に変更
        if "sectors" in event:
            for symbol in event["sectors"]:
                if symbol in self.stocks:
                    stock = self.stocks[symbol]
                    effect_min, effect_max = event["effect"]
                    # 影響を与える（実際の更新は次のupdate_stock_pricesで行われる）
                    stock["event_effect"] = random.uniform(effect_min, effect_max)
    
    async def update_stock_prices(self):
        """株価の更新処理"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM stocks')
            stocks = await cursor.fetchall()
            
            now = datetime.now().isoformat()
            
            for stock in stocks:
                # 価格変動のシミュレーション
                volatility = stock['volatility']
                
                # 市場イベントの影響を加味
                event_effect = 0
                if stock["symbol"] in self.stocks and "event_effect" in self.stocks[stock["symbol"]]:
                    event_effect = self.stocks[stock["symbol"]]["event_effect"]
                    # イベント効果はこの更新後にリセット
                    del self.stocks[stock["symbol"]]["event_effect"]
                
                # 基本変動 + イベント効果
                change_percent = random.uniform(-volatility, volatility) + event_effect
                old_price = stock['price']
                new_price = max(1, old_price * (1 + change_percent))
                new_price = round(new_price, 2)
                
                # データベース更新
                await db.execute(
                    'UPDATE stocks SET prev_price = price, price = ?, last_update = ? WHERE id = ?',
                    (new_price, now, stock['id'])
                )
                
                # メモリ内の株価情報も更新
                symbol = stock['symbol']
                if symbol in self.stocks:
                    self.stocks[symbol]['prev_price'] = old_price
                    self.stocks[symbol]['price'] = new_price
                    self.stocks[symbol]['last_update'] = now
            
            await db.commit()
    
    async def get_stock(self, symbol):
        """シンボルから株式情報を取得"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM stocks WHERE symbol = ?', (symbol,))
            stock = await cursor.fetchone()
            return stock
    
    async def get_stock_by_id(self, stock_id):
        """IDから株式情報を取得"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM stocks WHERE id = ?', (stock_id,))
            stock = await cursor.fetchone()
            return stock
    
    async def get_user_stocks(self, user_id):
        """ユーザーの保有株式一覧を取得"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT us.id, us.stock_id, us.quantity, us.purchase_price, us.purchase_date,
                       s.symbol, s.name, s.price
                FROM user_stocks us
                JOIN stocks s ON us.stock_id = s.id
                WHERE us.user_id = ?
                ORDER BY us.purchase_date DESC
            ''', (user_id,))
            stocks = await cursor.fetchall()
            return stocks
    
    async def buy_stock(self, user_id, stock_id, quantity, current_price):
        """株式の購入処理"""
        total_cost = quantity * current_price
        
        # まず所持金をチェック
        balance = await self.get_balance(user_id)
        if balance < total_cost:
            return False, "残高不足です"
        
        # 所持金から購入金額を差し引く
        await self.update_balance(user_id, -total_cost)
        await self.add_transaction(user_id, 0, total_cost, f"株式購入: {quantity}株")
        
        # 株式購入記録
        async with aiosqlite.connect(self.db_path) as db:
            # すでに同じ株を保有しているか確認
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM user_stocks WHERE user_id = ? AND stock_id = ?',
                (user_id, stock_id)
            )
            existing = await cursor.fetchone()
            
            if existing:
                # 既存の株式に追加
                new_quantity = existing['quantity'] + quantity
                avg_price = (existing['purchase_price'] * existing['quantity'] + current_price * quantity) / new_quantity
                
                await db.execute(
                    'UPDATE user_stocks SET quantity = ?, purchase_price = ? WHERE id = ?',
                    (new_quantity, avg_price, existing['id'])
                )
            else:
                # 新規購入
                await db.execute(
                    'INSERT INTO user_stocks (user_id, stock_id, quantity, purchase_price) VALUES (?, ?, ?, ?)',
                    (user_id, stock_id, quantity, current_price)
                )
            
            # 投資ログに記録
            await db.execute(
                'INSERT INTO investment_logs (user_id, stock_id, quantity, price, action) VALUES (?, ?, ?, ?, ?)',
                (user_id, stock_id, quantity, current_price, 'buy')
            )
            
            await db.commit()
        
        return True, "株式購入が完了しました"
    
    async def sell_stock(self, user_id, holding_id, quantity, current_price):
        """株式の売却処理"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # 保有株式の確認
            cursor = await db.execute(
                'SELECT * FROM user_stocks WHERE id = ? AND user_id = ?',
                (holding_id, user_id)
            )
            holding = await cursor.fetchone()
            
            if not holding:
                return False, "指定された株式が見つかりません"
            
            if holding['quantity'] < quantity:
                return False, f"保有数量が不足しています (保有: {holding['quantity']}株)"
            
            # 株式情報の取得
            stock = await self.get_stock_by_id(holding['stock_id'])
            if not stock:
                return False, "株式情報が見つかりません"
            
            # 売却金額の計算
            total_earning = quantity * current_price
            
            # 売却処理
            if holding['quantity'] == quantity:
                # すべての株を売却
                await db.execute('DELETE FROM user_stocks WHERE id = ?', (holding_id,))
            else:
                # 一部売却
                new_quantity = holding['quantity'] - quantity
                await db.execute(
                    'UPDATE user_stocks SET quantity = ? WHERE id = ?',
                    (new_quantity, holding_id)
                )
            
            # 投資ログに記録
            await db.execute(
                'INSERT INTO investment_logs (user_id, stock_id, quantity, price, action) VALUES (?, ?, ?, ?, ?)',
                (user_id, stock['id'], quantity, current_price, 'sell')
            )
            
            await db.commit()
        
        # 売却金額を所持金に追加
        await self.update_balance(user_id, total_earning)
        await self.add_transaction(0, user_id, total_earning, f"株式売却: {quantity}株")
        
        return True, "株式売却が完了しました"
    
    async def event_listener(self):
        """経済イベントの影響を受けるリスナー"""
        while True:
            if self.economy_cog and hasattr(self.economy_cog, "current_event"):
                event = self.economy_cog.current_event
                if event and "trade_fee_rate" in event["effects"]:
                    self.dynamic_trade_fee_rate = event["effects"]["trade_fee_rate"]
                else:
                    self.dynamic_trade_fee_rate = self.trade_fee_rate
            await asyncio.sleep(60)  # 1分ごとにチェック
    
    @app_commands.command(name="stocks", description="株式市場の一覧を表示します")
    async def stocks(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM stocks ORDER BY symbol')
            stocks = await cursor.fetchall()
        
        if not stocks:
            await interaction.response.send_message("現在、株式市場にデータがありません。", ephemeral=True)
            return
        
        symbol, name = await self.get_currency_info()
        
        embed = discord.Embed(
            title="📈 株式市場",
            description="現在の株価情報です。購入には `/buystock` コマンドを使用してください。",
            color=discord.Color.blue()
        )
        
        for stock in stocks:
            price_change = stock['price'] - stock['prev_price']
            change_percent = (price_change / stock['prev_price']) * 100 if stock['prev_price'] > 0 else 0
            
            # 上昇・下落の矢印と色
            if price_change > 0:
                change_emoji = "🟢 ↗️"
                change_text = f"+{price_change:.2f} (+{change_percent:.2f}%)"
            elif price_change < 0:
                change_emoji = "🔴 ↘️"
                change_text = f"{price_change:.2f} ({change_percent:.2f}%)"
            else:
                change_emoji = "⚪ →"
                change_text = "0.00 (0.00%)"
            
            embed.add_field(
                name=f"{change_emoji} {stock['symbol']} - {stock['name']}",
                value=f"価格: **{stock['price']:.2f}** {symbol}\n変動: {change_text}",
                inline=True
            )
        
        last_update = datetime.fromisoformat(stocks[0]['last_update']).strftime('%Y-%m-%d %H:%M:%S')
        embed.set_footer(text=f"最終更新: {last_update} | 株価は1時間ごとに更新されます")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="buystock", description="株式を購入します")
    @app_commands.describe(
        symbol="購入する株式のシンボル",
        quantity="購入する株数"
    )
    async def buystock(self, interaction: discord.Interaction, symbol: str, quantity: int):
        if not self.economy_cog:
            await interaction.response.send_message("経済システムが現在利用できません。しばらく経ってから再度お試しください。", ephemeral=True)
            return
        
        if quantity <= 0:
            await interaction.response.send_message("購入数量は1以上で指定してください。", ephemeral=True)
            return
        
        user_id = interaction.user.id
        stock = await self.get_stock(symbol.upper())
        
        if not stock:
            await interaction.response.send_message(f"シンボル '{symbol}' の株式は見つかりませんでした。", ephemeral=True)
            return
        
        current_price = stock['price']
        # 株式の価値
        stock_value = current_price * quantity
        # 取引手数料の計算
        fee = int(stock_value * self.dynamic_trade_fee_rate)  # 動的手数料率を使用
        if fee < 1:
            fee = 1  # 最低手数料
        
        total_cost = stock_value + fee
        
        # 残高確認
        balance = await self.get_balance(user_id)
        if balance < total_cost:
            await interaction.response.send_message(
                f"残高不足です。必要金額: {total_cost:.2f} {self.currency_symbol} (株式: {stock_value:.2f} + 手数料: {fee:.2f}), "
                f"現在の残高: {balance:.2f} {self.currency_symbol}",
                ephemeral=True
            )
            return
        
        # 購入処理
        # まず手数料をシステムに支払う
        await self.update_balance(user_id, -fee)
        await self.update_balance(self.bank_user_id, fee)
        await self.add_transaction(user_id, self.bank_user_id, fee, f"Stock purchase fee: {stock['symbol']}")
        
        # 次に株を購入
        success, message = await self.buy_stock(user_id, stock['id'], quantity, current_price)
        
        if success:
            embed = discord.Embed(
                title="🛒 株式購入",
                description=f"{stock['symbol']} - {stock['name']} の株式を購入しました！",
                color=discord.Color.green()
            )
            
            embed.add_field(name="購入数量", value=f"{quantity}株", inline=True)
            embed.add_field(name="株価", value=f"{current_price:.2f} {self.currency_symbol}/株", inline=True)
            embed.add_field(name="株式価値", value=f"{stock_value:.2f} {self.currency_symbol}", inline=True)
            embed.add_field(name="取引手数料", value=f"{fee:.2f} {self.currency_symbol} (2%)", inline=True)
            embed.add_field(name="合計支払額", value=f"{total_cost:.2f} {self.currency_symbol}", inline=True)
            
            new_balance = await self.get_balance(user_id)
            embed.add_field(name="残高", value=f"{new_balance:.2f} {self.currency_symbol}", inline=False)
            
            # 市場イベント情報があれば表示
            if self.last_market_event:
                embed.add_field(
                    name=f"📊 市場情報: {self.last_market_event['emoji']} {self.last_market_event['name']}",
                    value=self.last_market_event['description'],
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"購入に失敗しました: {message}", ephemeral=True)
    
    @app_commands.command(name="sellstock", description="保有している株式を売却します")
    @app_commands.describe(
        holding_id="売却する株式のID (portfolioコマンドで確認できます)",
        quantity="売却する株数"
    )
    async def sellstock(self, interaction: discord.Interaction, holding_id: int, quantity: int):
        if quantity <= 0:
            await interaction.response.send_message("売却数量は1以上で指定してください。", ephemeral=True)
            return
        
        user_id = interaction.user.id
        
        # 保有株の確認
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT us.*, s.symbol, s.name, s.price
                FROM user_stocks us
                JOIN stocks s ON us.stock_id = s.id
                WHERE us.id = ? AND us.user_id = ?
            ''', (holding_id, user_id))
            holding = await cursor.fetchone()
        
        if not holding:
            await interaction.response.send_message("指定されたIDの株式が見つからないか、あなたの保有ではありません。", ephemeral=True)
            return
        
        if holding['quantity'] < quantity:
            await interaction.response.send_message(f"保有数量が不足しています。現在の保有数: {holding['quantity']}株", ephemeral=True)
            return
        
        current_price = holding['price']
        # 株式の価値
        stock_value = current_price * quantity
        # 取引手数料の計算
        fee = int(stock_value * self.trade_fee_rate)
        if fee < 1:
            fee = 1  # 最低手数料
        
        net_earning = stock_value - fee
        
        # まず手数料をシステムに支払う（売却額から差し引く）
        await self.update_balance(self.bank_user_id, fee)
        await self.add_transaction(user_id, self.bank_user_id, fee, f"Stock selling fee: {holding['symbol']}")
        
        # 売却処理
        success, message = await self.sell_stock(user_id, holding_id, quantity, current_price)
        
        if success:
            # 購入時との差額計算
            purchase_price = holding['purchase_price']
            profit_per_share = current_price - purchase_price
            total_profit = profit_per_share * quantity
            profit_percent = (profit_per_share / purchase_price) * 100 if purchase_price > 0 else 0
            
            if profit_per_share > 0:
                profit_text = f"+{total_profit:.2f} (+{profit_percent:.2f}%)"
                color = discord.Color.green()
            elif profit_per_share < 0:
                profit_text = f"{total_profit:.2f} ({profit_percent:.2f}%)"
                color = discord.Color.red()
            else:
                profit_text = "0.00 (0.00%)"
                color = discord.Color.blue()
            
            embed = discord.Embed(
                title="💹 株式売却",
                description=f"{holding['symbol']} - {holding['name']} の株式を売却しました！",
                color=color
            )
            
            embed.add_field(name="売却数量", value=f"{quantity}株", inline=True)
            embed.add_field(name="売却価格", value=f"{current_price:.2f} {self.currency_symbol}/株", inline=True)
            embed.add_field(name="株式価値", value=f"{stock_value:.2f} {self.currency_symbol}", inline=True)
            embed.add_field(name="取引手数料", value=f"{fee:.2f} {self.currency_symbol} (2%)", inline=True)
            embed.add_field(name="純受取額", value=f"{net_earning:.2f} {self.currency_symbol}", inline=True)
            embed.add_field(name="損益", value=profit_text, inline=True)
            
            new_balance = await self.get_balance(user_id)
            embed.add_field(name="残高", value=f"{new_balance:.2f} {self.currency_symbol}", inline=False)
            
            if holding['quantity'] == quantity:
                embed.set_footer(text="すべての株式を売却しました")
            else:
                embed.set_footer(text=f"残り保有数: {holding['quantity'] - quantity}株")
            
            # 市場イベント情報があれば表示
            if self.last_market_event:
                embed.add_field(
                    name=f"📊 市場情報: {self.last_market_event['emoji']} {self.last_market_event['name']}",
                    value=self.last_market_event['description'],
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"売却に失敗しました: {message}", ephemeral=True)
    
    @app_commands.command(name="stockinfo", description="特定の株式の詳細情報を表示します")
    @app_commands.describe(symbol="調べたい株式のシンボル")
    async def stockinfo(self, interaction: discord.Interaction, symbol: str):
        stock = await self.get_stock(symbol.upper())
        
        if not stock:
            await interaction.response.send_message(f"シンボル '{symbol}' の株式は見つかりませんでした。", ephemeral=True)
            return
        
        # 価格変動の計算
        price_change = stock['price'] - stock['prev_price']
        change_percent = (price_change / stock['prev_price']) * 100 if stock['prev_price'] > 0 else 0
        
        if price_change > 0:
            change_emoji = "🟢 ↗️"
            change_text = f"+{price_change:.2f} (+{change_percent:.2f}%)"
            color = discord.Color.green()
        elif price_change < 0:
            change_emoji = "🔴 ↘️"
            change_text = f"{price_change:.2f} ({change_percent:.2f}%)"
            color = discord.Color.red()
        else:
            change_emoji = "⚪ →"
            change_text = "0.00 (0.00%)"
            color = discord.Color.blue()
        
        embed = discord.Embed(
            title=f"{stock['symbol']} - {stock['name']}",
            description=f"{change_emoji} 現在の株価: **{stock['price']:.2f}** {self.currency_symbol}",
            color=color
        )
        
        embed.add_field(name="前回価格", value=f"{stock['prev_price']:.2f} {self.currency_symbol}", inline=True)
        embed.add_field(name="変動", value=change_text, inline=True)
        embed.add_field(name="ボラティリティ", value=f"{stock['volatility'] * 100:.2f}%", inline=True)
        
        # ユーザーの保有状況
        user_id = interaction.user.id
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT SUM(quantity) as total_quantity, AVG(purchase_price) as avg_purchase_price
                FROM user_stocks
                WHERE user_id = ? AND stock_id = ?
            ''', (user_id, stock['id']))
            user_holding = await cursor.fetchone()
        
        if user_holding and user_holding['total_quantity'] and user_holding['total_quantity'] > 0:
            quantity = user_holding['total_quantity']
            avg_price = user_holding['avg_purchase_price']
            current_value = quantity * stock['price']
            purchase_value = quantity * avg_price
            profit = current_value - purchase_value
            profit_percent = (profit / purchase_value) * 100 if purchase_value > 0 else 0
            
            if profit > 0:
                profit_text = f"+{profit:.2f} (+{profit_percent:.2f}%)"
            elif profit < 0:
                profit_text = f"{profit:.2f} ({profit_percent:.2f}%)"
            else:
                profit_text = "0.00 (0.00%)"
            
            embed.add_field(
                name="あなたの保有状況",
                value=f"保有数: **{quantity}**株\n"
                      f"平均購入価格: {avg_price:.2f} {self.currency_symbol}\n"
                      f"現在価値: {current_value:.2f} {self.currency_symbol}\n"
                      f"損益: {profit_text}",
                inline=False
            )
        
        last_update = datetime.fromisoformat(stock['last_update']).strftime('%Y-%m-%d %H:%M:%S')
        embed.set_footer(text=f"最終更新: {last_update}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="portfolio", description="保有している株式ポートフォリオを表示します")
    async def portfolio(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_stocks = await self.get_user_stocks(user_id)
        
        if not user_stocks:
            await interaction.response.send_message("現在、株式を保有していません。`/buystock` コマンドで株式を購入できます。", ephemeral=True)
            return
        
        symbol, currency_name = await self.get_currency_info()
        
        embed = discord.Embed(
            title="📊 株式ポートフォリオ",
            description=f"{interaction.user.display_name} さんの保有株式一覧です",
            color=discord.Color.gold()
        )
        
        total_value = 0
        total_cost = 0
        
        for stock in user_stocks:
            current_price = stock['price']
            quantity = stock['quantity']
            purchase_price = stock['purchase_price']
            
            current_value_stock = current_price * quantity
            purchase_value = purchase_price * quantity
            profit = current_value_stock - purchase_value
            profit_percent = (profit / purchase_value) * 100 if purchase_value > 0 else 0
            
            total_value += current_value_stock
            total_cost += purchase_value
            
            if profit > 0:
                profit_text = f"+{profit:.2f} {symbol} (+{profit_percent:.2f}%)"
                profit_emoji = "🟢"
            elif profit < 0:
                profit_text = f"{profit:.2f} {symbol} ({profit_percent:.2f}%)"
                profit_emoji = "🔴"
            else:
                profit_text = f"0.00 {symbol} (0.00%)"
                profit_emoji = "⚪"
            
            purchase_date = datetime.fromisoformat(stock['purchase_date']).strftime('%Y-%m-%d')
            
            embed.add_field(
                name=f"ID: {stock['id']} | {profit_emoji} {stock['symbol']} - {stock['name']}",
                value=f"🔢 保有数: **{quantity}**株\n"
                      f"💰 購入価格: {purchase_price:.2f} {symbol}/株\n"
                      f"📈 現在価格: {current_price:.2f} {symbol}/株\n"
                      f"📅 購入日: {purchase_date}\n"
                      f"💵 評価額: {current_value_stock:.2f} {symbol}\n"
                      f"📊 損益: {profit_text}",
                inline=False
            )
        
        # 合計の損益情報
        total_profit = total_value - total_cost
        total_profit_percent = (total_profit / total_cost) * 100 if total_cost > 0 else 0
        
        if total_profit > 0:
            total_profit_text = f"+{total_profit:.2f} {symbol} (+{total_profit_percent:.2f}%)"
            footer_emoji = "🟢 総合収益"
        elif total_profit < 0:
            total_profit_text = f"{total_profit:.2f} {symbol} ({total_profit_percent:.2f}%)"
            footer_emoji = "🔴 総合損失"
        else:
            total_profit_text = f"0.00 {symbol} (0.00%)"
            footer_emoji = "⚪ 収支なし"
        
        embed.add_field(
            name="💼 ポートフォリオ合計",
            value=f"投資額: {total_cost:.2f} {symbol}\n"
                  f"評価額: {total_value:.2f} {symbol}\n"
                  f"損益: {total_profit_text}",
            inline=False
        )
        
        embed.set_footer(text=f"{footer_emoji} | 株式を売却するには /sellstock コマンドを使用してください")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="market", description="現在の市場動向と最新のイベントを表示します")
    async def market_trends(self, interaction: discord.Interaction):
        # 現在のイベント情報
        if self.last_market_event:
            event = self.last_market_event
            event_description = f"{event['emoji']} **{event['name']}**: {event['description']}"
        else:
            event_description = "現在、特筆すべき市場イベントはありません。"
        
        # 各セクターの動向
        sectors = {
            "テクノロジー": ["SWFT", "DIGI", "GAME"],
            "金融": ["BANK"],
            "エネルギー": ["ENER"],
            "医療": ["MEDC"],
            "消費財": ["FOOD", "LUXR"]
        }
        
        sector_trends = {}
        
        for sector_name, symbols in sectors.items():
            total_change = 0
            count = 0
            
            for symbol in symbols:
                if symbol in self.stocks:
                    stock = self.stocks[symbol]
                    price_change = (stock['price'] - stock['prev_price']) / stock['prev_price']
                    total_change += price_change
                    count += 1
            
            if count > 0:
                avg_change = total_change / count
                
                if avg_change > 0.05:
                    trend = "🟢 急上昇"
                elif avg_change > 0:
                    trend = "🟢 上昇"
                elif avg_change < -0.05:
                    trend = "🔴 急下落"
                elif avg_change < 0:
                    trend = "🔴 下落"
                else:
                    trend = "⚪ 横ばい"
                
                sector_trends[sector_name] = {
                    "trend": trend,
                    "change": avg_change * 100  # パーセンテージに変換
                }
        
        # 過去のイベント履歴（最新5件）
        recent_events = self.market_events[-5:] if len(self.market_events) > 0 else []
        
        embed = discord.Embed(
            title="📊 市場概況",
            description=f"現在の市場動向と最新のイベント情報です\n\n{event_description}",
            color=discord.Color.gold()
        )
        
        # セクター動向
        sectors_text = ""
        for sector_name, data in sector_trends.items():
            sectors_text += f"{data['trend']} **{sector_name}** セクター: {data['change']:.2f}%\n"
        
        if sectors_text:
            embed.add_field(name="セクター動向", value=sectors_text, inline=False)
        
        # 過去のイベント
        if recent_events:
            events_text = ""
            for idx, event_data in enumerate(reversed(recent_events), 1):
                event = event_data["event"]
                timestamp = event_data["timestamp"].strftime("%Y-%m-%d %H:%M")
                events_text += f"{idx}. {timestamp} - {event['emoji']} **{event['name']}**\n"
            
            embed.add_field(name="最近の市場イベント", value=events_text, inline=False)
        
        # 取引ヒント
        trading_tips = [
            "上昇トレンドのセクターの株を買うことを検討しましょう。",
            "下落トレンドのセクターでも、底値で買うチャンスがあるかもしれません。",
            "分散投資が重要です。複数のセクターに投資しましょう。",
            "長期的な視点で投資することでリスクを軽減できます。",
            "市場イベントは一時的な株価変動を引き起こすことがあります。"
        ]
        
        embed.add_field(
            name="💡 取引ヒント",
            value=random.choice(trading_tips),
            inline=False
        )
        
        last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        embed.set_footer(text=f"情報更新: {last_update}")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Investment(bot))