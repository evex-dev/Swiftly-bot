import discord
from discord.ext import commands
from discord import app_commands
import numpy as np

class Calculator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="calculator", description="数式を計算します")
    @app_commands.describe(expression="計算したい数式を入力してください")
    async def calculator(self, interaction: discord.Interaction, expression: str):
        try:
            allowed_names = {k: v for k, v in np.__dict__.items() if not k.startswith("__")}
            allowed_names.update({"abs": abs, "round": round})
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            await interaction.response.send_message(f"結果: `{result}`")
        except Exception as e:
            await interaction.response.send_message(f"エラー: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Calculator(bot))
