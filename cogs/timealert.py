import discord
from discord.ext import commands, tasks
import aiosqlite
from datetime import datetime, timedelta, timezone
from typing import Final, Optional, List
import logging
from pathlib import Path

# 定数定義
JST: Final[timezone] = timezone(timedelta(hours=9))
DB_DIR: Final[Path] = Path("data")
DB_NAME: Final[str] = "timealerts.db"
MAX_ALERTS_PER_CHANNEL: Final[int] = 3
TIME_FORMAT: Final[str] = "%H:%M"
CHECK_INTERVAL: Final[int] = 1  # minutes
RATE_LIMIT_SECONDS: Final[int] = 30

CREATE_TABLE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS alerts (
    channel_id INTEGER,
    alert_time TEXT,
    PRIMARY KEY (channel_id, alert_time)
)
"""

ERROR_MESSAGES: Final[dict] = {
    "invalid_time": "時間のフォーマットが正しくありません。正しいフォーマットは HH:MM です。",
    "max_alerts": "このチャンネルにはすでに{}つの時報が設定されています。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "db_error": "データベースエラーが発生しました: {}",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

SUCCESS_MESSAGES: Final[dict] = {
    "alert_set": "{} に {} の時報を設定しました。/remove-time-signalで、登録を解除できます。",
    "alert_removed": "{} の {} の時報を解除しました。",
    "time_signal": "🕒 時報です！\n現在の時刻は {} です。"
}

logger = logging.getLogger(__name__)

class AlertDatabase:
    """時報データベースを管理するクラス"""

    def __init__(self) -> None:
        self._db: Optional[aiosqlite.Connection] = None
        DB_DIR.mkdir(exist_ok=True)

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(DB_DIR / DB_NAME)
        await self._db.execute(CREATE_TABLE_SQL)
        await self._db.commit()

    async def cleanup(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def get_alert_count(
        self,
        channel_id: int
    ) -> int:
        if not self._db:
            await self.initialize()

        async with self._db.execute(
            "SELECT COUNT(*) FROM alerts WHERE channel_id = ?",
            (channel_id,)
        ) as cursor:
            return (await cursor.fetchone())[0]

    async def add_alert(
        self,
        channel_id: int,
        alert_time: str
    ) -> None:
        """時報を追加"""
        if not self._db:
            await self.initialize()

        await self._db.execute(
            "INSERT INTO alerts (channel_id, alert_time) VALUES (?, ?)",
            (channel_id, alert_time)
        )
        await self._db.commit()

    async def remove_alert(
        self,
        channel_id: int,
        alert_time: str
    ) -> None:
        """時報を削除"""
        if not self._db:
            await self.initialize()

        await self._db.execute(
            "DELETE FROM alerts WHERE channel_id = ? AND alert_time = ?",
            (channel_id, alert_time)
        )
        await self._db.commit()

    async def get_channels_for_time(
        self,
        alert_time: str
    ) -> List[int]:
        if not self._db:
            await self.initialize()

        async with self._db.execute(
            "SELECT channel_id FROM alerts WHERE alert_time = ?",
            (alert_time,)
        ) as cursor:
            return [row[0] for row in await cursor.fetchall()]

class TimeAlert(commands.Cog):
    """時報機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = AlertDatabase()
        self._last_uses = {}
        self.check_alerts.start()

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

    def _validate_time(self, time_str: str) -> bool:
        try:
            datetime.strptime(time_str, TIME_FORMAT)
            return True
        except ValueError:
            return False

    def _create_alert_embed(
        self,
        channel: discord.TextChannel,
        time: str,
        is_set: bool = True
    ) -> discord.Embed:
        action = "設定" if is_set else "解除"
        return discord.Embed(
            title=f"時報{action}",
            description=SUCCESS_MESSAGES[
                "alert_set" if is_set else "alert_removed"
            ].format(channel.mention, time),
            color=discord.Color.green()
        ).add_field(
            name="チャンネル",
            value=channel.name,
            inline=True
        ).add_field(
            name="時刻",
            value=time,
            inline=True
        )

    @commands.has_permissions(administrator=True)
    @discord.app_commands.command(
        name="time-signal",
        description="指定したチャンネルと時間に時報を設定します"
    )
    @discord.app_commands.describe(
        channel="時報を設定するチャンネル",
        time="時報の時刻（HH:MM形式）"
    )
    async def time_signal(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        time: str
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

            # 時刻のバリデーション
            if not self._validate_time(time):
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_time"],
                    ephemeral=True
                )
                return

            # 時報数のチェック
            count = await self.db.get_alert_count(channel.id)
            if count >= MAX_ALERTS_PER_CHANNEL:
                await interaction.response.send_message(
                    ERROR_MESSAGES["max_alerts"].format(
                        MAX_ALERTS_PER_CHANNEL
                    ),
                    ephemeral=True
                )
                return

            # 時報の追加
            await self.db.add_alert(channel.id, time)

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_alert_embed(channel, time)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in time_signal: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )

    @commands.has_permissions(administrator=True)
    @discord.app_commands.command(
        name="remove-time-signal",
        description="指定したチャンネルの時報を解除します"
    )
    @discord.app_commands.describe(
        channel="時報を解除するチャンネル",
        time="解除する時報の時刻（HH:MM形式）"
    )
    async def remove_time_signal(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        time: str
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

            # 時刻のバリデーション
            if not self._validate_time(time):
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_time"],
                    ephemeral=True
                )
                return

            # 時報の削除
            await self.db.remove_alert(channel.id, time)

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_alert_embed(
                channel,
                time,
                is_set=False
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in remove_time_signal: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )

    @tasks.loop(minutes=CHECK_INTERVAL)
    async def check_alerts(self) -> None:
        """時報をチェックして送信"""
        try:
            now = datetime.now(JST).strftime(TIME_FORMAT)
            channel_ids = await self.db.get_channels_for_time(now)

            for channel_id in channel_ids:
                if channel := self.bot.get_channel(channel_id):
                    embed = discord.Embed(
                        description=SUCCESS_MESSAGES["time_signal"].format(now),
                        color=discord.Color.blue()
                    )
                    await channel.send(embed=embed)

        except Exception as e:
            logger.error("Error in check_alerts: %s", e, exc_info=True)

    @check_alerts.before_loop
    async def before_check_alerts(self) -> None:
        """時報チェック開始前の準備"""
        await self.bot.wait_until_ready()
        await self.db.initialize()

    async def cog_unload(self) -> None:
        """Cogのアンロード時の処理"""
        self.check_alerts.cancel()
        await self.db.cleanup()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TimeAlert(bot))
