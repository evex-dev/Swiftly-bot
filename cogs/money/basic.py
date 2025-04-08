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
        
        # 手数料の計算
        fee = int(amount * self.transfer_fee_rate)
        if fee < 1:
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
                bonus = random.randint(100, 500)
                await self.update_balance(user_id, bonus)
                await db.execute('UPDATE user_balance SET last_daily = ? WHERE user_id = ?', (now.isoformat(), user_id))
                await db.commit()
                
                embed = discord.Embed(
                    title="デイリーボーナス",
                    description=f"{bonus} {self.currency_symbol} {self.currency_name}を獲得しました！",
                    color=discord.Color.gold()
                )
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

    async def event_generator(self):
        """経済イベントを定期的に生成"""
        events = [
            {"name": "税率引き下げ", "description": "税率が一時的に引き下げられます。", "effects": {"tax_rate": 0.05}},
            {"name": "手数料無料キャンペーン", "description": "送金手数料が無料になります。", "effects": {"transfer_fee_rate": 0.0}},
            {"name": "取引手数料割引", "description": "株式取引手数料が半額になります。", "effects": {"trade_fee_rate": 0.01}},
        ]
        while True:
            self.current_event = random.choice(events)
            await asyncio.sleep(3600)  # 1時間ごとにイベントを変更

async def setup(bot):
    await bot.add_cog(Economy(bot))