import asyncpg
from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
from pathlib import Path
from typing import Final
import logging


load_dotenv()

DB_CONFIG: Final[dict] = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": "prohibited_channels"
}

CREATE_TABLE_SQL: Final[str] = """
    CREATE TABLE IF NOT EXISTS prohibited_channels (
        guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        PRIMARY KEY (guild_id, channel_id)
    )
"""

logger = logging.getLogger(__name__)

ERROR_MESSAGES: Final[dict] = {
    "no_permission": "Botにメッセージ削除の権限がありません。",
    "db_error": "データベースエラーが発生しました: {}"
}

SUCCESS_MESSAGES: Final[dict] = {
    "added": "{} を制限リストに追加しました。",
    "removed": "{} を制限リストから削除しました。"
}

class Prohibited(commands.Cog):
    """チャンネルごとのコマンド実行制限を管理"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            try:
                await conn.execute(CREATE_TABLE_SQL)
            finally:
                await conn.close()
        except Exception as e:
            logger.error("Error initializing database: %s", e, exc_info=True)
            raise

    async def is_channel_prohibited(
        self,
        guild_id: int,
        channel_id: int
    ) -> bool:
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            try:
                result = await conn.fetchval(
                    """
                    SELECT 1 FROM prohibited_channels
                    WHERE guild_id = $1 AND channel_id = $2
                    """,
                    str(guild_id), str(channel_id)
                )
                return result is not None
            finally:
                await conn.close()
        except Exception as e:
            logger.error(
                "Error checking prohibited channel: %s", e,
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

            conn = await asyncpg.connect(**DB_CONFIG)
            try:
                if not is_prohibited:
                    await conn.execute(
                        """
                        INSERT INTO prohibited_channels
                        (guild_id, channel_id) VALUES ($1, $2)
                        """,
                        str(guild_id), str(channel_id)
                    )
                else:
                    await conn.execute(
                        """
                        DELETE FROM prohibited_channels
                        WHERE guild_id = $1 AND channel_id = $2
                        """,
                        str(guild_id), str(channel_id)
                    )
                return not is_prohibited
            finally:
                await conn.close()
        except Exception as e:
            logger.error(
                "Error toggling channel prohibition: %s", e,
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
        description="特定のチャンネルでのコマンドの利用を禁止する。もう一度実行すると解除される。"
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
            logger.error("Error in set_mute_channel: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["db_error"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Prohibited(bot))
