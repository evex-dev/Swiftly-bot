import discord
from discord.ext import commands
from typing import Final, Optional
import logging
from datetime import datetime, timedelta
import platform
import psutil
import os

# 定数定義
RATE_LIMIT_SECONDS: Final[int] = 5
MS_PER_SECOND: Final[int] = 1000

LATENCY_THRESHOLDS: Final[dict] = {
    "excellent": 100,  # 100ms未満
    "good": 200,      # 200ms未満
    "fair": 500,      # 500ms未満
    "poor": float('inf')  # それ以上
}

LATENCY_COLORS: Final[dict] = {
    "excellent": discord.Color.green(),
    "good": discord.Color.blue(),
    "fair": discord.Color.orange(),
    "poor": discord.Color.red()
}

ERROR_MESSAGES: Final[dict] = {
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

logger = logging.getLogger(__name__)

class Ping(commands.Cog):
    """Pingコマンドを提供"""

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

    def _get_latency_info(
        self,
        latency: float
    ) -> tuple[str, discord.Color]:
        for status, threshold in LATENCY_THRESHOLDS.items():
            if latency < threshold:
                return status, LATENCY_COLORS[status]
        return "poor", LATENCY_COLORS["poor"]

    def _get_system_info(self) -> dict:
        return {
            "OS": platform.system(),
            "Python": platform.python_version(),
            "Discord.py": discord.__version__,
            "CPU使用率": f"{psutil.cpu_percent()}%",
            "メモリ使用率": f"{psutil.Process(os.getpid()).memory_percent():.1f}%"
        }

    def _create_ping_embed(
        self,
        latency: float
    ) -> discord.Embed:
        status, color = self._get_latency_info(latency)

        embed = discord.Embed(
            title="🏓 Pong!",
            color=color
        )

        # レイテンシー情報
        embed.add_field(
            name="レイテンシー",
            value=f"{latency:.2f}ms ({status})",
            inline=False
        )

        # システム情報
        system_info = self._get_system_info()
        for name, value in system_info.items():
            embed.add_field(
                name=name,
                value=value,
                inline=True
            )

        # シャード情報（シャーディングが有効な場合）
        if self.bot.shard_id is not None:
            embed.add_field(
                name="シャード情報",
                value=f"ID: {self.bot.shard_id}/{self.bot.shard_count}",
                inline=False
            )

        embed.set_footer(
            text="💚 excellent < 100ms | 💙 good < 200ms | "
                 "💛 fair < 500ms | ❤️ poor > 500ms"
        )

        return embed

    @discord.app_commands.command(
        name="ping",
        description="Botのレイテンシーと状態を表示します"
    )
    async def ping(
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

            # レイテンシーの計算
            latency = self.bot.latency * MS_PER_SECOND

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_ping_embed(latency)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in ping command: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ping(bot))
