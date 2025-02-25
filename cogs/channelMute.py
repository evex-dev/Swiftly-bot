import aiosqlite
import discord
from discord.ext import commands
from pathlib import Path
from typing import Final, Optional
import logging

# 定数定義
DB_PATH: Final[Path] = Path("prohibited_channels.db")
TABLE_NAME: Final[str] = "prohibited_channels"

ERROR_MESSAGES: Final[dict] = {
    "no_permission": "このコマンドはサーバー管理者のみ実行可能です。",
    "db_error": "データベースエラーが発生しました: {}"
}

SUCCESS_MESSAGES: Final[dict] = {
    "added": "{} をコマンド実行禁止チャンネルに追加しました。",
    "removed": "{} をコマンド実行禁止チャンネルから削除しました。"
}

CREATE_TABLE_SQL: Final[str] = """
    CREATE TABLE IF NOT EXISTS prohibited_channels (
        guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        PRIMARY KEY (guild_id, channel_id)
    )
"""

logger = logging.getLogger(__name__)

class Prohibited(commands.Cog):
    """チャンネルごとのコマンド実行制限を管理"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(CREATE_TABLE_SQL)
                await db.commit()
        except Exception as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
            raise

    async def is_channel_prohibited(
        self,
        guild_id: int,
        channel_id: int
    ) -> bool:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    """
                    SELECT 1 FROM prohibited_channels
                    WHERE guild_id = ? AND channel_id = ?
                    """,
                    (str(guild_id), str(channel_id))
                ) as cursor:
                    return await cursor.fetchone() is not None
        except Exception as e:
            logger.error(
                f"Error checking prohibited channel: {e}",
                exc_info=True
            )
            return False

    async def toggle_channel_prohibition(
        self,
        guild_id: int,
        channel_id: int
    ) -> bool:
        try:
            is_prohibited = await self.is_channel_prohibited(
                guild_id,
                channel_id
            )

            async with aiosqlite.connect(DB_PATH) as db:
                if not is_prohibited:
                    await db.execute(
                        """
                        INSERT INTO prohibited_channels
                        (guild_id, channel_id) VALUES (?, ?)
                        """,
                        (str(guild_id), str(channel_id))
                    )
                else:
                    await db.execute(
                        """
                        DELETE FROM prohibited_channels
                        WHERE guild_id = ? AND channel_id = ?
                        """,
                        (str(guild_id), str(channel_id))
                    )
                await db.commit()
                return not is_prohibited
        except Exception as e:
            logger.error(
                f"Error toggling channel prohibition: {e}",
                exc_info=True
            )
            raise

    def _create_response_embed(
        self,
        channel: discord.TextChannel,
        is_added: bool
    ) -> discord.Embed:
        action = "追加" if is_added else "削除"
        return discord.Embed(
            title=f"チャンネル制限{action}",
            description=SUCCESS_MESSAGES["added" if is_added else "removed"].format(
                channel.mention
            ),
            color=discord.Color.green() if is_added else discord.Color.red()
        ).add_field(
            name="チャンネル情報",
            value=f"名前: {channel.name}\nID: {channel.id}"
        )

    @discord.app_commands.command(
        name="set_mute_channel",
        description="特定のチャンネルでのコマンドの利用を禁止する"
    )
    @discord.app_commands.describe(
        channel="制限を設定するチャンネル"
    )
    async def set_mute_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                ERROR_MESSAGES["no_permission"],
                ephemeral=True
            )
            return

        try:
            is_added = await self.toggle_channel_prohibition(
                interaction.guild_id,
                channel.id
            )
            embed = self._create_response_embed(channel, is_added)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in set_mute_channel: {e}", exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["db_error"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Prohibited(bot))
