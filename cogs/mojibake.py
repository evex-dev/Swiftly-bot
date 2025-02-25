import re
from typing import Final, List, Tuple, Optional
import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

# 定数定義
RATE_LIMIT_SECONDS: Final[int] = 10
MAX_CONTENT_LENGTH: Final[int] = 2000

MENTION_PATTERNS: Final[dict] = {
    "everyone": r"@(everyone|here)",
    "user": r"<@!?\d+>",
    "role": r"<@&\d+>"
}

MOJIBAKE_PATTERNS: Final[List[Tuple[str, str]]] = [
    ("utf-8", "iso-8859-1"),
    ("utf-8", "shift_jis"),
    ("utf-8", "euc-jp"),
    ("utf-8", "cp932")
]

ERROR_MESSAGES: Final[dict] = {
    "content_too_long": f"文字列は{MAX_CONTENT_LENGTH}文字以内で指定してください。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "decode_error": "文字化け処理中にエラーが発生しました: {}",
    "unexpected_error": "予期しないエラーが発生しました: {}"
}

logger = logging.getLogger(__name__)

class MojiBake(commands.Cog):
    """文字化け機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_uses = {}

    def _check_rate_limit(
        self,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    def _sanitize_input(self, content: str) -> str:
        # すべての@を全角に置き換え
        sanitized = content.replace("@", "＠")

        # 各種メンションパターンを無効化
        for pattern in MENTION_PATTERNS.values():
            sanitized = re.sub(
                pattern,
                lambda m: "＠" + m.group(0)[1:],
                sanitized
            )

        return sanitized

    def _create_mojibake(self, content: str) -> str:
        result = content
        for from_enc, to_enc in MOJIBAKE_PATTERNS:
            try:
                result = result.encode(from_enc).decode(
                    to_enc,
                    errors="ignore"
                )
            except UnicodeError:
                continue
        return result

    def _create_mojibake_embed(
        self,
        original: str,
        mojibake: str
    ) -> discord.Embed:
        return discord.Embed(
            title="文字化け結果",
            color=discord.Color.blue()
        ).add_field(
            name="元の文字列",
            value=original,
            inline=False
        ).add_field(
            name="文字化け後",
            value=mojibake,
            inline=False
        ).set_footer(
            text="使用エンコーディング: " +
                 ", ".join(f"{f}->{t}" for f, t in MOJIBAKE_PATTERNS)
        )

    @app_commands.command(
        name="moji-bake",
        description="文字をわざと文字化けさせます"
    )
    @app_commands.describe(
        content="文字化けさせる文字列"
    )
    async def moji_bake(
        self,
        interaction: discord.Interaction,
        content: str
    ) -> None:
        try:
            # 文字数制限チェック
            if len(content) > MAX_CONTENT_LENGTH:
                await interaction.response.send_message(
                    ERROR_MESSAGES["content_too_long"],
                    ephemeral=True
                )
                return

            # レート制限のチェック
            is_limited, remaining = self._check_rate_limit(
                interaction.user.id
            )
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            # メンションを無効化
            sanitized = self._sanitize_input(content)

            # 文字化け処理
            mojibake = self._create_mojibake(sanitized)

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_mojibake_embed(content, mojibake)
            await interaction.response.send_message(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none()
            )

        except UnicodeError as e:
            logger.error(f"Unicode error: {e}", exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["decode_error"].format(str(e)),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected_error"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MojiBake(bot))
