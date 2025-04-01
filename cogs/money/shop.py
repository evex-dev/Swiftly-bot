import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import asyncio
from typing import List, Optional

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'data/shop.db'
        self.economy_cog = None
        self.currency_name = "スイフト"  # デフォルト値
        self.currency_symbol = "🪙"  # デフォルト値
        bot.loop.create_task(self.setup_database())
        bot.loop.create_task(self.load_economy_cog())
    
    async def load_economy_cog(self):
        """Economy cogを読み込む（利用可能になったタイミングで）"""
        for _ in range(10):  # 10回までリトライ
            self.economy_cog = self.bot.get_cog("Economy")
            if self.economy_cog:
                self.currency_name = self.economy_cog.currency_name
                self.currency_symbol = self.economy_cog.currency_symbol
                break
            await asyncio.sleep(5)  # 5秒待機
    
    async def setup_database(self):
        """データベースのセットアップ"""
        if not os.path.exists(self.db_path):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    CREATE TABLE items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        price INTEGER NOT NULL,
                        emoji TEXT NOT NULL
                    )
                ''')
                await db.commit()
    
    async def get_all_items(self):
        """全アイテムの取得"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM items') as cursor:
                items = await cursor.fetchall()
                return [{'id': row[0], 'name': row[1], 'description': row[2], 'price': row[3], 'emoji': row[4]} for row in items]
    
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
    
    @app_commands.command(name="shop", description="ショップのアイテム一覧を表示します")
    async def shop(self, interaction: discord.Interaction):
        items = await self.get_all_items()
        
        if not items:
            await interaction.response.send_message("現在、ショップにはアイテムがありません。", ephemeral=True)
            return
        
        symbol, name = await self.get_currency_info()
        
        embed = discord.Embed(
            title="🛒 ショップ",
            description="以下のアイテムが購入可能です。購入するには `/buy <アイテムID>` コマンドを使用してください。",
            color=discord.Color.blue()
        )
        
        for item in items:
            embed.add_field(
                name=f"{item['emoji']} {item['name']} (ID: {item['id']})",
                value=f"```{item['description']}```\n価格: **{item['price']}** {symbol} {name}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="buy", description="ショップからアイテムを購入します")
    async def buy(self, interaction: discord.Interaction, item_id: int):
        if not self.economy_cog:
            await interaction.response.send_message("経済システムが現在利用できません。しばらく経ってから再度お試しください。", ephemeral=True)
            return
        
        # ...existing code...