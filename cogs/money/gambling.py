import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy_cog = None
        self.currency_name = "スイフト"  # デフォルト値
        self.currency_symbol = "🪙"  # デフォルト値
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
    
    @app_commands.command(name="coinflip", description="コインフリップで賭けます")
    @app_commands.describe(
        bet="賭ける金額",
        choice="表か裏を選択"
    )
    @app_commands.choices(choice=[
        app_commands.Choice(name="表", value="heads"),
        app_commands.Choice(name="裏", value="tails")
    ])
    async def coinflip(self, interaction: discord.Interaction, bet: int, choice: str):
        if not self.economy_cog:
            await interaction.response.send_message("経済システムが現在利用できません。しばらく経ってから再度お試しください。", ephemeral=True)
            return
        
        # ...existing code...
    
    # 他のコマンドも同様に修正