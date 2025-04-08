import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import random
from datetime import datetime, timedelta
import asyncio

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'data/economy.db'
        self.currency_name = "スイフト"  # 架空の通貨名
        self.currency_symbol = "🪙"  # 通貨記号
        self.initial_balance = 1000  # 新規ユーザーへの初期付与額
        self.transfer_fee_rate = 0.05  # 送金手数料率 (5%)
        self.bank_user_id = 0  # システム/銀行のユーザーID
        self.current_event = None
        self.event_start_time = None
        self.event_duration = 3600  # デフォルトイベント期間 (1時間)
        self.base_daily_min = 100  # デイリーボーナスの基本最小値
        self.base_daily_max = 500  # デイリーボーナスの基本最大値
        bot.loop.create_task(self.setup_database())
        bot.loop.create_task(self.event_generator())
        
    async def setup_database(self):
        # データディレクトリの確認
        os.makedirs('data', exist_ok=True)
        
        # データベース接続
        async with aiosqlite.connect(self.db_path) as db:
            # ユーザー残高テーブル
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_balance (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    last_daily TIMESTAMP
                )
            ''')
            
            # 取引履歴テーブル
            await db.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    amount INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            ''')
            await db.commit()
    
    async def get_balance(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT balance FROM user_balance WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            
            if row is None:
                # 新規ユーザーには初期資金を付与
                await db.execute('INSERT INTO user_balance (user_id, balance) VALUES (?, ?)', (user_id, self.initial_balance))
                await db.commit()
                
                # 取引履歴に初期付与を記録
                await self.add_transaction(0, user_id, self.initial_balance, "Initial balance")
                
                return self.initial_balance
            return row['balance']
    
    async def update_balance(self, user_id, amount):
        current_balance = await self.get_balance(user_id)
        new_balance = current_balance + amount
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE user_balance SET balance = ? WHERE user_id = ?', (new_balance, user_id))
            await db.commit()
        
        return new_balance
    
    async def add_transaction(self, sender_id, receiver_id, amount, description):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES (?, ?, ?, ?)',
                (sender_id, receiver_id, amount, description)
            )
            await db.commit()
    
    @app_commands.command(name="balance", description="あなたの所持金を確認します")
    async def balance(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        balance = await self.get_balance(user_id)
        
        embed = discord.Embed(
            title="残高確認",
            description=f"{interaction.user.mention}の残高",
            color=discord.Color.green()
        )
        embed.add_field(name="所持金", value=f"{balance} {self.currency_symbol} {self.currency_name}")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="transfer", description="他のユーザーにお金を送ります")
    async def transfer(self, interaction: discord.Interaction, user: discord.User, amount: int):
        sender_id = interaction.user.id
        receiver_id = user.id
        
        if sender_id == receiver_id:
            await interaction.response.send_message("自分自身にお金を送ることはできません！", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("送金額は1以上にしてください！", ephemeral=True)
            return
        
        sender_balance = await self.get_balance(sender_id)
        
        # 現在のイベントによる手数料率の調整
        fee_rate = self.transfer_fee_rate
        if self.current_event and 'transfer_fee_rate' in self.current_event['effects']:
            fee_rate = self.current_event['effects']['transfer_fee_rate']
            
        # 手数料の計算
        fee = int(amount * fee_rate)
        if fee < 1 and fee_rate > 0:
            fee = 1  # 最低手数料
        
        total_cost = amount + fee
        
        if sender_balance < total_cost:
            await interaction.response.send_message(
                f"残高不足です！必要金額: {total_cost} {self.currency_symbol} (送金額: {amount} + 手数料: {fee})\n"
                f"現在の残高: {sender_balance} {self.currency_symbol}", 
                ephemeral=True
            )
            return
        
        # 送金処理
        await self.update_balance(sender_id, -total_cost)
        await self.update_balance(receiver_id, amount)
        await self.update_balance(self.bank_user_id, fee)  # 手数料はシステム/銀行へ
        
        # 取引履歴に記録
        await self.add_transaction(sender_id, receiver_id, amount, "User transfer")
        await self.add_transaction(sender_id, self.bank_user_id, fee, "Transfer fee")
        
        embed = discord.Embed(
            title="送金完了",
            description=f"{amount} {self.currency_symbol} {self.currency_name}を{user.mention}に送金しました",
            color=discord.Color.green()
        )
        embed.add_field(name="手数料", value=f"{fee} {self.currency_symbol}")
        embed.add_field(name="合計引き落とし額", value=f"{total_cost} {self.currency_symbol}")
        
        new_balance = await self.get_balance(sender_id)
        embed.add_field(name="あなたの残高", value=f"{new_balance} {self.currency_symbol}", inline=False)
        
        # イベント情報があれば追加
        if self.current_event and 'transfer_fee_rate' in self.current_event['effects']:
            embed.add_field(name="特別イベント", value=f"🎉 {self.current_event['name']}: {self.current_event['description']}", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="daily", description="デイリーボーナスを受け取ります")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT last_daily FROM user_balance WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            
            now = datetime.now()
            can_claim = True
            time_left = None
            
            if row and row['last_daily']:
                last_daily = datetime.fromisoformat(row['last_daily'])
                next_daily = last_daily + timedelta(days=1)
                if now < next_daily:
                    can_claim = False
                    time_left = next_daily - now
            
            if can_claim:
                # イベントによるボーナス調整
                min_bonus = self.base_daily_min
                max_bonus = self.base_daily_max
                bonus_multiplier = 1.0
                
                if self.current_event:
                    if 'daily_min' in self.current_event['effects']:
                        min_bonus = self.current_event['effects']['daily_min']
                    if 'daily_max' in self.current_event['effects']:
                        max_bonus = self.current_event['effects']['daily_max']
                    if 'daily_multiplier' in self.current_event['effects']:
                        bonus_multiplier = self.current_event['effects']['daily_multiplier']
                
                base_bonus = random.randint(min_bonus, max_bonus)
                bonus = int(base_bonus * bonus_multiplier)
                
                await self.update_balance(user_id, bonus)
                await db.execute('UPDATE user_balance SET last_daily = ? WHERE user_id = ?', (now.isoformat(), user_id))
                await db.commit()
                
                embed = discord.Embed(
                    title="デイリーボーナス",
                    description=f"{bonus} {self.currency_symbol} {self.currency_name}を獲得しました！",
                    color=discord.Color.gold()
                )
                
                # イベント情報があれば追加
                if self.current_event and (
                    'daily_min' in self.current_event['effects'] or 
                    'daily_max' in self.current_event['effects'] or 
                    'daily_multiplier' in self.current_event['effects']):
                    embed.add_field(name="特別イベント", value=f"🎉 {self.current_event['name']}: {self.current_event['description']}", inline=False)
                    if bonus_multiplier != 1.0:
                        embed.add_field(name="ボーナス倍率", value=f"{bonus_multiplier}倍", inline=True)
                
                await interaction.response.send_message(embed=embed)
            else:
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{hours}時間 {minutes}分 {seconds}秒"
                
                embed = discord.Embed(
                    title="デイリーボーナス",
                    description=f"次のボーナスまで待ってください: {time_str}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="economy", description="サーバー経済の統計情報を表示します")
    async def economy_stats(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # 全体の通貨量
            cursor = await db.execute('SELECT SUM(balance) as total_currency FROM user_balance')
            row = await cursor.fetchone()
            total_currency = row['total_currency'] if row and row['total_currency'] else 0
            
            # ユーザー数
            cursor = await db.execute('SELECT COUNT(*) as user_count FROM user_balance WHERE user_id != 0')
            row = await cursor.fetchone()
            user_count = row['user_count'] if row else 0
            
            # 銀行の残高（手数料等の蓄積）
            cursor = await db.execute('SELECT balance FROM user_balance WHERE user_id = 0')
            row = await cursor.fetchone()
            bank_balance = row['balance'] if row and row['balance'] else 0
            
            # 平均所持金
            avg_balance = total_currency / user_count if user_count > 0 else 0
            
            # 最も資産のあるユーザー
            cursor = await db.execute('''
                SELECT user_id, balance 
                FROM user_balance 
                WHERE user_id != 0 
                ORDER BY balance DESC 
                LIMIT 5
            ''')
            top_users = await cursor.fetchall()
            
            # 取引量
            cursor = await db.execute('''
                SELECT SUM(amount) as total_transactions 
                FROM transactions 
                WHERE description = 'User transfer'
            ''')
            row = await cursor.fetchone()
            total_transactions = row['total_transactions'] if row and row['total_transactions'] else 0
            
        embed = discord.Embed(
            title="📊 サーバー経済統計",
            description=f"サーバー全体の経済状況",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="通貨総量", value=f"{total_currency} {self.currency_symbol}", inline=True)
        embed.add_field(name="ユーザー数", value=f"{user_count}人", inline=True)
        embed.add_field(name="平均所持金", value=f"{avg_balance:.2f} {self.currency_symbol}", inline=True)
        embed.add_field(name="銀行残高", value=f"{bank_balance} {self.currency_symbol}", inline=True)
        embed.add_field(name="総取引量", value=f"{total_transactions} {self.currency_symbol}", inline=True)
        
        if top_users:
            top_users_text = ""
            for i, user in enumerate(top_users, 1):
                member = interaction.guild.get_member(user['user_id'])
                name = member.display_name if member else f"ID: {user['user_id']}"
                top_users_text += f"{i}. {name}: {user['balance']} {self.currency_symbol}\n"
            
            embed.add_field(name="資産トップ5", value=top_users_text, inline=False)
        
        embed.set_footer(text=f"経済システムはユーザー間の取引で回っています")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="event", description="現在進行中の経済イベントを確認します")
    async def check_event(self, interaction: discord.Interaction):
        if not self.current_event or not self.event_start_time:
            embed = discord.Embed(
                title="経済イベント",
                description="現在、特別な経済イベントは開催されていません。",
                color=discord.Color.light_grey()
            )
            await interaction.response.send_message(embed=embed)
            return
            
        now = datetime.now()
        elapsed = now - self.event_start_time
        remaining = timedelta(seconds=self.event_duration) - elapsed
        
        if remaining.total_seconds() <= 0:
            embed = discord.Embed(
                title="経済イベント",
                description="イベントが終了間近です。まもなく新しいイベントが始まります。",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            return
            
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed = discord.Embed(
            title=f"🎉 {self.current_event['name']}",
            description=self.current_event['description'],
            color=discord.Color.gold()
        )
        
        # イベント効果の詳細を表示
        effects_details = []
        for key, value in self.current_event['effects'].items():
            if key == 'transfer_fee_rate':
                effects_details.append(f"送金手数料率: {value * 100}%")
            elif key == 'daily_multiplier':
                effects_details.append(f"デイリーボーナス倍率: {value}倍")
            elif key == 'daily_min':
                effects_details.append(f"デイリー最小額: {value}")
            elif key == 'daily_max':
                effects_details.append(f"デイリー最大額: {value}")
            elif key == 'price_multiplier':
                effects_details.append(f"市場価格変動: {value}倍")
            elif key == 'lottery_odds':
                effects_details.append(f"宝くじ当選確率: {value}倍")
            
        if effects_details:
            embed.add_field(name="効果", value="\n".join(effects_details), inline=False)
            
        embed.add_field(name="残り時間", value=f"{hours}時間 {minutes}分 {seconds}秒", inline=False)
        embed.set_footer(text="イベント中はさまざまな特典や変更があります。有効活用しましょう！")
        
        await interaction.response.send_message(embed=embed)

    async def event_generator(self):
        """経済イベントを定期的に生成"""
        await self.bot.wait_until_ready()
        
        events = [
            # 基本的な経済イベント
            {
                "name": "送金手数料無料キャンペーン", 
                "description": "期間中、送金手数料が無料になります！", 
                "effects": {"transfer_fee_rate": 0.0},
                "duration": 3600,  # 1時間
                "weight": 10
            },
            {
                "name": "送金手数料半額キャンペーン", 
                "description": "期間中、送金手数料が半額になります！", 
                "effects": {"transfer_fee_rate": 0.025},
                "duration": 7200,  # 2時間
                "weight": 15
            },
            {
                "name": "富の恵み", 
                "description": "デイリーボーナスが通常より多くなります！", 
                "effects": {"daily_multiplier": 2.0},
                "duration": 3600,  # 1時間
                "weight": 10
            },
            {
                "name": "大富豪の祝福", 
                "description": "デイリーボーナスが大幅に増加します！", 
                "effects": {"daily_multiplier": 3.0},
                "duration": 1800,  # 30分
                "weight": 5
            },
            {
                "name": "保証付きデイリー", 
                "description": "デイリーボーナスの最低額が増加します！", 
                "effects": {"daily_min": 300, "daily_max": 700},
                "duration": 3600,  # 1時間
                "weight": 10
            },
            {
                "name": "豊穣の時代", 
                "description": "全てのお金の獲得量が増加します！", 
                "effects": {"daily_multiplier": 1.5, "transfer_fee_rate": 0.03},
                "duration": 5400,  # 1時間30分
                "weight": 8
            },
            {
                "name": "不景気", 
                "description": "経済が停滞し、デイリーボーナスが減少します...", 
                "effects": {"daily_multiplier": 0.7},
                "duration": 3600,  # 1時間
                "weight": 7
            },
            {
                "name": "増税期間", 
                "description": "送金手数料が一時的に増加します。", 
                "effects": {"transfer_fee_rate": 0.08},
                "duration": 2700,  # 45分
                "weight": 7
            },
            {
                "name": "市場バブル", 
                "description": "株式や商品の価格が急上昇しています！", 
                "effects": {"price_multiplier": 1.5},
                "duration": 2700,  # 45分
                "weight": 8
            },
            {
                "name": "市場暴落", 
                "description": "株式や商品の価格が大幅に下落しています...", 
                "effects": {"price_multiplier": 0.6},
                "duration": 2700,  # 45分
                "weight": 8
            },
            {
                "name": "インフレーション", 
                "description": "物価が上昇し、デイリーボーナスが増加する代わりに手数料も上昇します。", 
                "effects": {"daily_multiplier": 1.3, "transfer_fee_rate": 0.07},
                "duration": 3600,  # 1時間
                "weight": 6
            },
            {
                "name": "デフレーション", 
                "description": "物価が下落し、デイリーボーナスが減少する代わりに手数料も下がります。", 
                "effects": {"daily_multiplier": 0.8, "transfer_fee_rate": 0.03},
                "duration": 3600,  # 1時間
                "weight": 6
            },
            {
                "name": "短期豊作", 
                "description": "一時的な好景気！すべての経済活動が活発化します。", 
                "effects": {"daily_multiplier": 1.4, "transfer_fee_rate": 0.02},
                "duration": 1800,  # 30分
                "weight": 4
            }
        ]
        
        while True:
            # イベントをランダムに選択（重み付け）
            weights = [event.get("weight", 10) for event in events]
            selected_event = random.choices(events, weights=weights, k=1)[0]
            
            self.current_event = selected_event
            self.event_start_time = datetime.now()
            self.event_duration = selected_event.get("duration", 3600)
            
            # イベント期間が終了するまで待機
            await asyncio.sleep(self.event_duration)

async def setup(bot):
    await bot.add_cog(Economy(bot))