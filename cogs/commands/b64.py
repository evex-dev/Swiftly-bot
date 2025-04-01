import base64
import re
from typing import Final, Literal, Optional
import logging

import discord
from discord.ext import commands


ACTIONS: Final[list[str]] = ["encode", "decode"]
INVALID_ACTION_MESSAGE: Final[str] = "アクションは 'encode' または 'decode' のいずれかでなければなりません。"
INVALID_BASE64_MESSAGE: Final[str] = "無効なBase64文字列です。正しい形式で入力してください。"
ERROR_MESSAGE: Final[str] = "エラーが発生しました: {}"
MENTION_DETECTED_MESSAGE: Final[str] = "デコード結果に、@everyone やメンション、役職メンションが含まれているため、デコードを拒否しました。"

# 正規表現パターン
MENTION_PATTERNS: Final[dict[str, str]] = {
    "user": r"<@!?(\d+)>",
    "role": r"<@&(\d+)>",
    "everyone": "@everyone"
}

# Embedの色
COLORS: Final[dict[str, int]] = {
    "encode": discord.Color.blue().value,
    "decode": discord.Color.green().value,
    "error": discord.Color.red().value
}

logger = logging.getLogger(__name__)

class Base64(commands.Cog):
    """Base64エンコード/デコード機能"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _create_response_embed(
        self,
        action: Literal["encode", "decode"],
        content: str
    ) -> discord.Embed:
        return discord.Embed(
            title=f"Base64 {action}結果",
            description=content,
            color=COLORS[action]
        )

    def _contains_mentions(self, text: str) -> bool:
        return any([
            MENTION_PATTERNS["everyone"] in text,
            re.search(MENTION_PATTERNS["user"], text) is not None,
            re.search(MENTION_PATTERNS["role"], text) is not None
        ])

    async def _encode_text(self, text: str) -> str:
        return base64.b64encode(text.encode("utf-8")).decode("utf-8")

    async def _decode_text(self, text: str) -> Optional[str]:
        decoded = base64.b64decode(text).decode("utf-8")
        if self._contains_mentions(decoded):
            return None
        return decoded

    @discord.app_commands.command(
        name="base64",
        description="Base64エンコードまたはデコードします。"
    )
    @discord.app_commands.describe(
        action="実行するアクション（encode/decode）",
        content="エンコード/デコードする内容"
    )
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name=a, value=a) for a in ACTIONS
    ])
    async def base64_command(
        self,
        interaction: discord.Interaction,
        action: str,
        content: str
    ) -> None:
        if action not in ACTIONS:
            await interaction.response.send_message(
                INVALID_ACTION_MESSAGE,
                ephemeral=True
            )
            return

        try:
            if action == "encode":
                result = await self._encode_text(content)
                embed = self._create_response_embed("encode", result)
                await interaction.response.send_message(embed=embed)
            else:  # decode
                result = await self._decode_text(content)
                if result is None:
                    await interaction.response.send_message(
                        MENTION_DETECTED_MESSAGE,
                        ephemeral=True
                    )
                    return

                embed = self._create_response_embed("decode", result)
                await interaction.response.send_message(embed=embed)

        except base64.binascii.Error as e:
            logger.warning("Invalid Base64 input: %s", e)
            await interaction.response.send_message(
                INVALID_BASE64_MESSAGE,
                ephemeral=True
            )
        except Exception as e:
            logger.error("Error in base64_command: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGE.format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Base64(bot))
