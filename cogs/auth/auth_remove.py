from dotenv import load_dotenv
import os
import asyncpg
import discord
from discord.ext import commands

load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = "authpanel"
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

class AuthRemove(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.app_commands.command(
        name="remove_auth_panel",
        description="認証パネルを削除します (管理者専用)"
    )
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(
        message_id="削除する認証パネルのメッセージID"
    )
    async def remove_auth_panel(self, interaction: discord.Interaction, message_id: int) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return

        conn = await asyncpg.connect(DATABASE_URL)
        try:
            row = await conn.fetchrow(
                "SELECT channel_id FROM panels WHERE message_id = $1", message_id
            )
            if not row:
                await interaction.response.send_message("指定されたメッセージIDの認証パネルが見つかりません。", ephemeral=True)
                return

            channel_id = row["channel_id"]
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                except discord.NotFound:
                    pass

            await conn.execute("DELETE FROM panels WHERE message_id = $1", message_id)
        finally:
            await conn.close()

        await interaction.response.send_message("認証パネルを削除しました。", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AuthRemove(bot))