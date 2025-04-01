import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import random
from datetime import datetime, timedelta

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'data/economy.db'
        self.currency_name = "スイフト"  # 架空の通貨名
        self.currency_symbol = "🪙"  # 通貨記号
        bot.loop.create_task(self.setup_database())
        
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
                await db.execute('INSERT INTO user_balance (user_id, balance) VALUES (?, ?)', (user_id, 0))
                await db.commit()
                return 0
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
        
        if sender_balance < amount:
            await interaction.response.send_message(f"残高不足です！現在の残高: {sender_balance} {self.currency_symbol}", ephemeral=True)
            return
        
        # 送金処理
        await self.update_balance(sender_id, -amount)
        await self.update_balance(receiver_id, amount)
        await self.add_transaction(sender_id, receiver_id, amount, "User transfer")
        
        embed = discord.Embed(
            title="送金完了",
            description=f"{amount} {self.currency_symbol} {self.currency_name}を{user.mention}に送金しました",
            color=discord.Color.green()
        )
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

async def setup(bot):
    await bot.add_cog(Economy(bot))