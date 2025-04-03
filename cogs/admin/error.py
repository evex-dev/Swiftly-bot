import discord
from discord import app_commands
from discord.ext import commands

class AdminErrorCog(commands.Cog):
    """管理者用のエラー発生テストコマンドを提供するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="raise_error", description="わざとエラーを発生させるコマンド")
    async def raise_error(self, interaction: discord.Interaction) -> None:
        """わざとエラーを発生させるコマンド"""
        if interaction.user.id != 1241397634095120438:
            await interaction.response.send_message("❌ このコマンドを実行する権限がありません。", ephemeral=True)
            return

        try:
            # 意図的にエラーを発生させる
            raise RuntimeError("これはテスト用の意図的なエラーです。")
        except Exception as e:
            raise  # エラーを再スローしてエラー追跡システムにキャプチャさせる

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminErrorCog(bot))