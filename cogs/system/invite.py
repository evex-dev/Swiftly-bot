import discord
from discord.ext import commands

class InviteCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="invite",
        description="Botの招待リンクを送信します。"
    )
    async def invite(
        self,
        interaction: discord.Interaction
    ) -> None:
        """Botの招待リンクを送信するコマンド"""
        try:
            invite_url = "https://discord.com/oauth2/authorize?client_id=1310198598213963858"
            embed = discord.Embed(
                title="Swiftlyの招待リンク",
                description=f"[こちらをクリックしてBotを招待してください]({invite_url})",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(
                f"エラーが発生しました: {e}",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(InviteCommand(bot))