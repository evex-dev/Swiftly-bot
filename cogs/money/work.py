import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import random
import asyncio
from datetime import datetime, timedelta

class Work(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'data/work.db'
        self.economy_cog = None
        self.cooldowns = {}
        bot.loop.create_task(self.setup_database())
    
    async def cog_load(self):
        # Economy cogが読み込まれるまで待機
        while self.economy_cog is None:
            try:
                self.economy_cog = self.bot.get_cog("Economy")
                if self.economy_cog:
                    break
            except:
                pass
            await asyncio.sleep(1)
    
    async def setup_database(self):
        # データディレクトリの確認
        os.makedirs('data', exist_ok=True)
        
        # データベース接続
        async with aiosqlite.connect(self.db_path) as db:
            # ワークログテーブル
            await db.execute('''
                CREATE TABLE IF NOT EXISTS work_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    work_type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
    
    async def log_work(self, user_id, work_type, amount):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO work_logs (user_id, work_type, amount) VALUES (?, ?, ?)',
                (user_id, work_type, amount)
            )
            await db.commit()
    
    def get_cooldown_remaining(self, user_id, command_name):
        if user_id not in self.cooldowns:
            return None
        
        if command_name not in self.cooldowns[user_id]:
            return None
        
        expiration_time = self.cooldowns[user_id][command_name]
        now = datetime.now()
        
        if now >= expiration_time:
            del self.cooldowns[user_id][command_name]
            return None
        
        return expiration_time - now
    
    def set_cooldown(self, user_id, command_name, seconds):
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
        
        expiration = datetime.now() + timedelta(seconds=seconds)
        self.cooldowns[user_id][command_name] = expiration
    
    @app_commands.command(name="work", description="働いてお金を稼ぎます")
    async def work(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        # クールダウンチェック
        cooldown = self.get_cooldown_remaining(user_id, "work")
        if cooldown:
            minutes, seconds = divmod(int(cooldown.total_seconds()), 60)
            await interaction.response.send_message(
                f"あなたはまだ疲れています。**{minutes}分{seconds}秒**後にもう一度試してください。",
                ephemeral=True
            )
            return
        
        # 仕事のリスト
        jobs = [
            {"name": "プログラミング", "description": "コードを書いて報酬を得ました。", "min": 50, "max": 150, "emoji": "💻"},
            {"name": "デザイン", "description": "素敵なデザインを作成しました。", "min": 40, "max": 160, "emoji": "🎨"},
            {"name": "翻訳", "description": "文書を翻訳しました。", "min": 30, "max": 120, "emoji": "📝"},
            {"name": "配達", "description": "荷物を配達しました。", "min": 20, "max": 100, "emoji": "📦"},
            {"name": "動画編集", "description": "動画を編集しました。", "min": 60, "max": 180, "emoji": "🎬"},
            {"name": "記事執筆", "description": "記事を書きました。", "min": 40, "max": 140, "emoji": "📰"},
            {"name": "料理", "description": "おいしい料理を作りました。", "min": 30, "max": 110, "emoji": "🍳"},
            {"name": "家庭教師", "description": "生徒に勉強を教えました。", "min": 50, "max": 170, "emoji": "📚"},
            {"name": "デリバリー", "description": "食事を配達しました。", "min": 40, "max": 120, "emoji": "🛵"},
            {"name": "カスタマーサポート", "description": "お客様の問題を解決しました。", "min": 45, "max": 130, "emoji": "🎧"},
            {"name": "イラスト作成", "description": "イラストを描きました。", "min": 55, "max": 165, "emoji": "🖌️"},
            {"name": "ガーデニング", "description": "庭の手入れをしました。", "min": 35, "max": 105, "emoji": "🌱"}
        ]
        
        # ランダムな仕事を選択
        job = random.choice(jobs)
        amount = random.randint(job["min"], job["max"])
        
        # 報酬を与える
        await self.economy_cog.update_balance(user_id, amount)
        await self.economy_cog.add_transaction(0, user_id, amount, f"Work: {job['name']}")
        await self.log_work(user_id, job["name"], amount)
        
        # クールダウンを設定（30分）
        self.set_cooldown(user_id, "work", 1800)
        
        embed = discord.Embed(
            title=f"{job['emoji']} {job['name']}",
            description=f"{job['description']}\n\n**+{amount}** {self.economy_cog.currency_symbol} {self.economy_cog.currency_name}を獲得しました！",
            color=discord.Color.green()
        )
        
        new_balance = await self.economy_cog.get_balance(user_id)
        embed.add_field(name="残高", value=f"{new_balance} {self.economy_cog.currency_symbol}")
        embed.set_footer(text="次の仕事まで30分待つ必要があります")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="tasks", description="タスクをこなしてお金を稼ぎます")
    async def tasks(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        # クールダウンチェック
        cooldown = self.get_cooldown_remaining(user_id, "tasks")
        if cooldown:
            minutes, seconds = divmod(int(cooldown.total_seconds()), 60)
            await interaction.response.send_message(
                f"タスクを完了するためのエネルギーがまだ回復していません。**{minutes}分{seconds}秒**後にもう一度試してください。",
                ephemeral=True
            )
            return
        
        # タスクのリスト
        tasks = [
            {"name": "アンケート回答", "description": "アンケートに回答しました。", "min": 20, "max": 80, "emoji": "📋"},
            {"name": "写真撮影", "description": "写真を撮影しました。", "min": 30, "max": 100, "emoji": "📸"},
            {"name": "データ入力", "description": "データを入力しました。", "min": 25, "max": 90, "emoji": "📊"},
            {"name": "商品レビュー", "description": "商品のレビューを書きました。", "min": 35, "max": 110, "emoji": "⭐"},
            {"name": "テスト参加", "description": "新機能のテストに参加しました。", "min": 40, "max": 120, "emoji": "🧪"},
            {"name": "情報収集", "description": "情報を収集しました。", "min": 25, "max": 85, "emoji": "🔍"},
            {"name": "資料整理", "description": "資料を整理しました。", "min": 30, "max": 95, "emoji": "📁"},
            {"name": "SNS運用", "description": "SNSの投稿を作成しました。", "min": 35, "max": 105, "emoji": "📱"},
            {"name": "宣伝活動", "description": "商品の宣伝を行いました。", "min": 40, "max": 115, "emoji": "📢"},
            {"name": "会議参加", "description": "会議に参加しました。", "min": 45, "max": 125, "emoji": "👥"}
        ]
        
        # ランダムなタスクを選択
        task = random.choice(tasks)
        amount = random.randint(task["min"], task["max"])
        
        # 報酬を与える
        await self.economy_cog.update_balance(user_id, amount)
        await self.economy_cog.add_transaction(0, user_id, amount, f"Task: {task['name']}")
        await self.log_work(user_id, task["name"], amount)
        
        # クールダウンを設定（15分）
        self.set_cooldown(user_id, "tasks", 900)
        
        embed = discord.Embed(
            title=f"{task['emoji']} {task['name']}",
            description=f"{task['description']}\n\n**+{amount}** {self.economy_cog.currency_symbol} {self.economy_cog.currency_name}を獲得しました！",
            color=discord.Color.blue()
        )
        
        new_balance = await self.economy_cog.get_balance(user_id)
        embed.add_field(name="残高", value=f"{new_balance} {self.economy_cog.currency_symbol}")
        embed.set_footer(text="次のタスクまで15分待つ必要があります")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="parttime", description="アルバイトをしてお金を稼ぎます")
    async def parttime(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        # クールダウンチェック
        cooldown = self.get_cooldown_remaining(user_id, "parttime")
        if cooldown:
            minutes, seconds = divmod(int(cooldown.total_seconds()), 60)
            await interaction.response.send_message(
                f"アルバイトのシフトはまだ始まっていません。**{minutes}分{seconds}秒**後に再度確認してください。",
                ephemeral=True
            )
            return
        
        # アルバイトのリスト
        part_time_jobs = [
            {"name": "カフェスタッフ", "description": "カフェでドリンクを提供しました。", "min": 100, "max": 250, "emoji": "☕"},
            {"name": "コンビニ店員", "description": "コンビニで接客しました。", "min": 90, "max": 220, "emoji": "🏪"},
            {"name": "ファストフード店員", "description": "ファストフード店で料理を提供しました。", "min": 80, "max": 200, "emoji": "🍔"},
            {"name": "書店スタッフ", "description": "書店で本を整理しました。", "min": 95, "max": 230, "emoji": "📚"},
            {"name": "映画館スタッフ", "description": "映画館でチケットをチェックしました。", "min": 110, "max": 260, "emoji": "🎬"},
            {"name": "ホテルスタッフ", "description": "ホテルでチェックイン対応をしました。", "min": 120, "max": 280, "emoji": "🏨"},
            {"name": "フードデリバリー", "description": "食事の配達をしました。", "min": 100, "max": 240, "emoji": "🛵"},
            {"name": "家庭教師", "description": "生徒に勉強を教えました。", "min": 130, "max": 300, "emoji": "✏️"}
        ]
        
        # ランダムなアルバイトを選択
        job = random.choice(part_time_jobs)
        amount = random.randint(job["min"], job["max"])
        
        # 報酬を与える
        await self.economy_cog.update_balance(user_id, amount)
        await self.economy_cog.add_transaction(0, user_id, amount, f"Part-time: {job['name']}")
        await self.log_work(user_id, f"PartTime:{job['name']}", amount)
        
        # クールダウンを設定（60分）
        self.set_cooldown(user_id, "parttime", 3600)
        
        embed = discord.Embed(
            title=f"{job['emoji']} {job['name']}",
            description=f"{job['description']}\n\n**+{amount}** {self.economy_cog.currency_symbol} {self.economy_cog.currency_name}を獲得しました！",
            color=discord.Color.gold()
        )
        
        new_balance = await self.economy_cog.get_balance(user_id)
        embed.add_field(name="残高", value=f"{new_balance} {self.economy_cog.currency_symbol}")
        embed.set_footer(text="次のアルバイトまで60分待つ必要があります")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Work(bot))