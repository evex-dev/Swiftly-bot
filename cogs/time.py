import asyncio
import aiohttp
import discord
from discord.ext import commands
from typing import Final, Optional, Dict, Any
import logging
from datetime import datetime, timedelta
import pytz

# 定数定義
API_BASE_URL: Final[str] = "https://api1.sakana11.org/api/ntp"
RATE_LIMIT_SECONDS: Final[int] = 10
REQUEST_TIMEOUT: Final[int] = 5

ERROR_MESSAGES: Final[dict] = {
    "api_error": "APIから時間を取得できませんでした。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "network_error": "ネットワークエラーが発生しました: {}",
    "timeout": "リクエストがタイムアウトしました。",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

EMBED_COLORS: Final[dict] = {
    "success": discord.Color.blue(),
    "error": discord.Color.red()
}

TIMEZONE: Final[str] = "Asia/Tokyo"

logger = logging.getLogger(__name__)

class TimeAPI:
    """時間取得APIを管理するクラス"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cleanup(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def get_current_time(self) -> Optional[Dict[str, Any]]:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            async with self._session.get(
                API_BASE_URL,
                timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(
                    "API error: %s - %s", response.status, await response.text()
                )
                return None

        except aiohttp.ClientError as e:
            logger.error("Network error: %s", e, exc_info=True)
            raise
        except asyncio.TimeoutError:
            logger.warning("Request timeout")
            raise
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            raise

class Time(commands.Cog):
    """時間取得機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.api = TimeAPI()
        self._last_uses = {}

    async def cog_load(self) -> None:
        """Cogのロード時にAPIを初期化"""
        await self.api.initialize()

    async def cog_unload(self) -> None:
        """Cogのアンロード時にAPIをクリーンアップ"""
        await self.api.cleanup()

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

    def _format_time(self, time_str: str) -> str:
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            jst = dt.astimezone(pytz.timezone(TIMEZONE))
            return jst.strftime("%Y年%m月%d日 %H:%M:%S")
        except Exception as e:
            logger.error("Error formatting time: %s", e, exc_info=True)
            return time_str

    def _create_time_embed(
        self,
        time_str: str,
        is_error: bool = False
    ) -> discord.Embed:
        if is_error:
            return discord.Embed(
                title="エラー",
                description=time_str,
                color=EMBED_COLORS["error"]
            )

        embed = discord.Embed(
            title="現在の時間",
            description=f"現在の時間は: {self._format_time(time_str)}",
            color=EMBED_COLORS["success"]
        )

        embed.add_field(
            name="タイムゾーン",
            value=TIMEZONE,
            inline=True
        )
        embed.add_field(
            name="APIエンドポイント",
            value=API_BASE_URL,
            inline=True
        )

        return embed

    @discord.app_commands.command(
        name="time",
        description="現在の時間を取得します。"
    )
    async def fetch_time(
        self,
        interaction: discord.Interaction
    ) -> None:
        try:
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

            # 時刻の取得
            data = await self.api.get_current_time()
            if not data or "time" not in data:
                await interaction.followup.send(
                    embed=self._create_time_embed(
                        ERROR_MESSAGES["api_error"],
                        is_error=True
                    )
                )
                return

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_time_embed(data["time"])
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as e:
            logger.error("Network error: %s", e, exc_info=True)
            await interaction.followup.send(
                embed=self._create_time_embed(
                    ERROR_MESSAGES["network_error"].format(str(e)),
                    is_error=True
                )
            )
        except asyncio.TimeoutError:
            logger.warning("Request timeout")
            await interaction.followup.send(
                embed=self._create_time_embed(
                    ERROR_MESSAGES["timeout"],
                    is_error=True
                )
            )
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            await interaction.followup.send(
                embed=self._create_time_embed(
                    ERROR_MESSAGES["unexpected"].format(str(e)),
                    is_error=True
                )
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Time(bot))
