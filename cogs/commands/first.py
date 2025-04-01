import discord
from discord.ext import commands
from typing import Final, Dict, Optional
import logging
from datetime import datetime, timedelta


EMBED_COLORS: Final[dict] = {
    "success": discord.Color.blue(),
    "error": discord.Color.red()
}

ERROR_MESSAGES: Final[dict] = {
    "no_message": "このチャンネルにはメッセージが見つかりませんでした。",
    "no_permission": "このチャンネルのメッセージ履歴を読む権限がありません。",
    "unexpected": "エラーが発生しました: {}"
}

CACHE_EXPIRY: Final[int] = 3600  # キャッシュの有効期限（秒）

logger = logging.getLogger(__name__)

class CachedMessage:
    """キャッシュされたメッセージ情報を管理するクラス"""

    def __init__(
        self,
        message: discord.Message,
        timestamp: datetime = None
    ) -> None:
        self.message = message
        self.timestamp = timestamp or datetime.now()

    def is_expired(self) -> bool:
        return (
            datetime.now() - self.timestamp >
            timedelta(seconds=CACHE_EXPIRY)
        )

class FirstComment(commands.Cog):
    """チャンネルの最初のメッセージを取得する機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.message_cache: Dict[int, CachedMessage] = {}

    def _create_message_embed(
        self,
        message: discord.Message
    ) -> discord.Embed:
        embed = discord.Embed(
            title="最初のメッセージ",
            description=(
                f"[こちら]({message.jump_url}) "
                "をクリックして最初のメッセージに移動します。"
            ),
            color=EMBED_COLORS["success"]
        )

        # メッセージの詳細情報を追加
        embed.add_field(
            name="作成日時",
            value=discord.utils.format_dt(message.created_at, "F"),
            inline=False
        )
        if message.author:
            embed.add_field(
                name="作成者",
                value=message.author.mention,
                inline=True
            )
        if message.content:
            # 長すぎる場合は省略
            content = (
                message.content[:500] + "..."
                if len(message.content) > 500
                else message.content
            )
            embed.add_field(
                name="内容",
                value=content,
                inline=False
            )

        return embed

    async def _get_first_message(
        self,
        channel: discord.TextChannel
    ) -> Optional[discord.Message]:
        try:
            # キャッシュをチェック
            if channel.id in self.message_cache:
                cached = self.message_cache[channel.id]
                if not cached.is_expired():
                    return cached.message
                # 期限切れの場合はキャッシュを削除
                del self.message_cache[channel.id]

            # 新しいメッセージを取得
            async for message in channel.history(
                limit=1,
                oldest_first=True
            ):
                self.message_cache[channel.id] = CachedMessage(message)
                return message

        except discord.Forbidden:
            logger.warning(
                "No permission to read message history in channel %d", channel.id
            )
            raise
        except Exception as e:
            logger.error(
                "Error fetching first message in channel %d: %s", channel.id, e,
                exc_info=True
            )
            raise

        return None

    @discord.app_commands.command(
        name="first-comment",
        description="このチャンネルの最初のメッセージへのリンクを取得します。"
    )
    async def first_comment(
        self,
        interaction: discord.Interaction
    ) -> None:
        try:
            # 権限チェック
            if not interaction.channel.permissions_for(
                interaction.guild.me
            ).read_message_history:
                await interaction.response.send_message(
                    ERROR_MESSAGES["no_permission"],
                    ephemeral=True
                )
                return

            first_message = await self._get_first_message(
                interaction.channel
            )

            if first_message:
                embed = self._create_message_embed(first_message)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    ERROR_MESSAGES["no_message"],
                    ephemeral=True
                )

        except discord.Forbidden:
            await interaction.response.send_message(
                ERROR_MESSAGES["no_permission"],
                ephemeral=True
            )
        except Exception as e:
            logger.error(
                "Error in first_comment command: %s", e,
                exc_info=True
            )
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FirstComment(bot))
