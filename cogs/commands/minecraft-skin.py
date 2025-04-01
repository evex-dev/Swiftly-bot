import discord
from discord.ext import commands
import aiohttp
import re
from typing import Final, Optional
import logging
from datetime import datetime, timedelta


SKIN_BASE_URL: Final[str] = "https://mineskin.eu"
MOJANG_API_URL: Final[str] = "https://api.mojang.com/users/profiles/minecraft"
RATE_LIMIT_SECONDS: Final[int] = 30
USERNAME_PATTERN: Final[str] = r"^[a-zA-Z0-9_]{2,16}$"

SKIN_VIEWS: Final[dict] = {
    "armor": f"{SKIN_BASE_URL}/armor/body",
    "body": f"{SKIN_BASE_URL}/body",
    "face": f"{SKIN_BASE_URL}/helm",
    "bust": f"{SKIN_BASE_URL}/bust"
}

ERROR_MESSAGES: Final[dict] = {
    "invalid_username": "無効なユーザー名です。英数字とアンダースコアのみ使用可能で、2-16文字である必要があります。",
    "user_not_found": "指定されたユーザーが見つかりません。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "api_error": "APIエラーが発生しました: {}",
    "network_error": "ネットワークエラーが発生しました: {}"
}

logger = logging.getLogger(__name__)

class MinecraftSkin(commands.Cog):
    """Minecraftのスキンを取得する機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_uses = {}

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _validate_username(self, username: str) -> bool:
        return bool(re.match(USERNAME_PATTERN, username))

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

    async def _verify_minecraft_user(
        self,
        username: str
    ) -> bool:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            async with self._session.get(
                f"{MOJANG_API_URL}/{username}"
            ) as response:
                return response.status == 200
        except Exception as e:
            logger.error(
                "Error verifying Minecraft user: %s",
                e,
                exc_info=True
            )
            return False

    def _create_skin_embed(
        self,
        username: str,
        view_type: str = "armor"
    ) -> discord.Embed:
        skin_url = f"{SKIN_VIEWS[view_type]}/{username}/100.png"

        embed = discord.Embed(
            title=f"{username}のMinecraftスキン",
            description=(
                f"表示タイプ: {view_type}\n"
                "他の表示タイプ: armor, body, face, bust"
            ),
            color=discord.Color.blue()
        )
        embed.set_image(url=skin_url)
        embed.set_footer(
            text="Powered by MineSkin.eu"
        )

        return embed

    @discord.app_commands.command(
        name="skin",
        description="Minecraftのスキンを取得します。Java版のみ。"
    )
    @discord.app_commands.describe(
        username="Minecraftのユーザー名",
        view_type="表示タイプ（armor/body/face/bust）"
    )
    @discord.app_commands.choices(view_type=[
        discord.app_commands.Choice(name=k, value=k)
        for k in SKIN_VIEWS
    ])
    async def skin(
        self,
        interaction: discord.Interaction,
        username: str,
        view_type: str = "armor"
    ) -> None:
        try:
            # ユーザー名のバリデーション
            if not self._validate_username(username):
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_username"],
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

            await interaction.response.defer()

            # ユーザーの存在確認
            if not await self._verify_minecraft_user(username):
                await interaction.followup.send(
                    ERROR_MESSAGES["user_not_found"],
                    ephemeral=True
                )
                return

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_skin_embed(username, view_type)
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as e:
            logger.error("Network error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["network_error"].format(str(e)),
                ephemeral=True
            )
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["api_error"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MinecraftSkin(bot))
