import asyncio
import time
import platform
import psutil
from typing import Final, Optional, Dict
import logging
from datetime import datetime, timedelta

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


ROUTER_IP: Final[str] = "192.168.1.1"
STATUS_URL: Final[str] = "https://stats.sakana11.org/public-dashboards/a0034c728e9e427e928bdba6f23003f0"
TIMEOUT_SECONDS: Final[int] = 3
RATE_LIMIT_SECONDS: Final[int] = 30

ERROR_MESSAGES: Final[dict] = {
    "connection_error": "接続エラー",
    "timeout": "タイムアウト",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

EMBED_COLORS: Final[dict] = {
    "normal": discord.Color.blue(),
    "warning": discord.Color.orange(),
    "error": discord.Color.red()
}

logger = logging.getLogger(__name__)

class SystemStatus:
    """システムステータスを管理するクラス"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cleanup(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def get_discord_latency(self) -> float:
        return round(self.bot.latency * 1000, 2)

    async def get_router_latency(self) -> str:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            start_time = time.time()
            async with self._session.get(
                f"http://{ROUTER_IP}",
                timeout=TIMEOUT_SECONDS
            ):
                pass
            return f"{round((time.time() - start_time) * 1000, 2)}ms"

        except aiohttp.ClientError as e:
            logger.error("Router connection error: %s", e, exc_info=True)
            return ERROR_MESSAGES["connection_error"]
        except asyncio.TimeoutError:
            logger.warning("Router timeout after %ds", TIMEOUT_SECONDS)
            return ERROR_MESSAGES["timeout"]
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            return ERROR_MESSAGES["unexpected"].format(str(e))

    def get_system_info(self) -> Dict[str, str]:
        process = psutil.Process()
        return {
            "CPU使用率": f"{psutil.cpu_percent()}%",
            "メモリ使用率": f"{process.memory_percent():.1f}%",
            "起動時間": str(
                timedelta(seconds=int(time.time() - process.create_time()))
            )
        }

class Status(commands.Cog):
    """ステータス確認機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.system = SystemStatus(bot)
        self._last_uses = {}

    async def cog_load(self) -> None:
        await self.system.initialize()

    async def cog_unload(self) -> None:
        await self.system.cleanup()

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

    def _create_status_embed(
        self,
        discord_latency: float,
        router_latency: str,
        system_info: Dict[str, str]
    ) -> discord.Embed:
        # レイテンシーに基づいて色を決定
        color = EMBED_COLORS["normal"]
        if isinstance(router_latency, str) and "エラー" in router_latency:
            color = EMBED_COLORS["error"]
        elif discord_latency > 500:  # 500ms以上は警告
            color = EMBED_COLORS["warning"]

        embed = discord.Embed(
            title="Swiftly ステータス",
            color=color
        )

        # レイテンシー情報
        embed.add_field(
            name="APIレイテンシ",
            value=f"{discord_latency}ms",
            inline=True
        )
        embed.add_field(
            name="ネットワークレイテンシ",
            value=router_latency,
            inline=True
        )

        # システム情報
        for name, value in system_info.items():
            embed.add_field(
                name=name,
                value=value,
                inline=True
            )

        # ステータスページへのリンク
        embed.add_field(
            name="ステータス詳細",
            value=f"[こちらをご覧ください]({STATUS_URL})",
            inline=False
        )

        return embed

    @app_commands.command(
        name="status",
        description="ボットのステータスを確認します"
    )
    async def status(
        self,
        interaction: discord.Interaction
    ) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return

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

            # 各種情報の取得
            discord_latency = self.system.get_discord_latency()
            router_latency = await self.system.get_router_latency()
            system_info = self.system.get_system_info()

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_status_embed(
                discord_latency,
                router_latency,
                system_info
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Error in status command: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Status(bot))
