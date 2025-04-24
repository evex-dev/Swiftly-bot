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
            await interaction.response.defer(thinking=True)
            allowed_names = {k: v for k, v in np.__dict__.items() if not k.startswith("__")}
            allowed_names.update({"abs": abs, "round": round})
            result = eval(expression, {"__builtins__": {}}, allowed_names)

            embed = discord.Embed(
                title="計算結果",
                description=f"数式: `{expression}`",
                color=discord.Color.green()
            )
            embed.add_field(name="結果", value=f"`{result}`", inline=False)
            embed.set_footer(text="計算完了 🎉")
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Calculator(bot))
