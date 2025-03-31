import aiosqlite
from discord.ext import commands
import discord

DB_PATH = "data/authpanel.db"

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
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                "SELECT channel_id, guild_id FROM panels WHERE message_id = ?", (message_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await interaction.response.send_message("指定されたメッセージIDの認証パネルが見つかりません。", ephemeral=True)
                    return

                channel_id, guild_id = row
                if guild_id != interaction.guild.id:
                    await interaction.response.send_message("指定されたメッセージIDはこのサーバーのものではありません。", ephemeral=True)
                    return

                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                    except discord.NotFound:
                        pass

            await conn.execute("DELETE FROM panels WHERE message_id = ?", (message_id,))
            await conn.commit()

        await interaction.response.send_message("認証パネルを削除しました。", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AuthRemove(bot))