import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, Literal, Optional, Tuple
import logging

import discord
from discord import app_commands
from discord.ext import commands

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

async def get_welcome_conn():
    return await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="welcome"
    )

async def get_leave_conn():
    return await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="leave"
    )

DEFAULT_INCREMENT: Final[int] = 100
MIN_INCREMENT: Final[int] = 5
MAX_INCREMENT: Final[int] = 1000
JOIN_COOLDOWN: Final[int] = 3  # seconds

ERROR_MESSAGES: Final[dict] = {
    "no_permission": "コマンドを使用するにはサーバーの管理権限が必要です。",
    "invalid_action": "enableまたはdisableを指定してください。",
    "invalid_increment": f"{MIN_INCREMENT}～{MAX_INCREMENT}人の間で指定してください。",
    "no_channel": "ONにする場合はチャンネルを指定してください。"
}

SUCCESS_MESSAGES: Final[dict] = {
    "enabled": "参加メッセージをONにしました!\n{increment}人ごとに{channel}でお祝いメッセージを送信します",
    "disabled": "参加メッセージを無効にしました!"
}

WELCOME_MESSAGES: Final[dict] = {
    "milestone": (
        "🎉🎉🎉 お祝い 🎉🎉🎉\n"
        "{mention} さん、ようこそ！\n"
        "{member_count}人達成！\n"
        "{guild_name}のメンバーが{member_count}人になりました！皆さんありがとうございます！"
    ),
    "normal": (
        "{mention} さん、ようこそ！\n"
        "現在のメンバー数: {member_count}人\n"
        "あと {remaining} 人で {next_milestone}人達成です！"
    )
}

LEAVE_MESSAGES: Final[dict] = {
    "leave": (
        "{mention} さんがサーバーを退室しました。\n"
        "現在のメンバー数: {member_count}人"
    )
}

CREATE_TABLE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS welcome_settings (
    guild_id INTEGER PRIMARY KEY,
    is_enabled INTEGER DEFAULT 0,
    member_increment INTEGER DEFAULT 100,
    channel_id INTEGER DEFAULT NULL,
    UNIQUE (guild_id) -- 一意制約を追加
)
"""

CREATE_LEAVE_TABLE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS leave_settings (
    guild_id INTEGER PRIMARY KEY,
    is_enabled INTEGER DEFAULT 0,
    channel_id INTEGER DEFAULT NULL,
    UNIQUE (guild_id) -- 一意制約を追加
)
"""

logger = logging.getLogger(__name__)

class WelcomeDatabase:
    """ウェルカムメッセージの設定を管理するDB"""

    @staticmethod
    async def init_database() -> None:
        conn = await get_welcome_conn()
        await conn.execute(CREATE_TABLE_SQL)
        await conn.close()

    @staticmethod
    async def get_settings(guild_id: int) -> Tuple[bool, int, Optional[int]]:
        conn = await get_welcome_conn()
        result = await conn.fetchrow(
            """
            SELECT is_enabled, member_increment, channel_id
            FROM welcome_settings WHERE guild_id = $1
            """,
            guild_id
        )
        await conn.close()
        return (
            bool(result[0]),
            result[1],
            result[2]
        ) if result else (False, DEFAULT_INCREMENT, None)

    @staticmethod
    async def update_settings(guild_id: int, is_enabled: bool,
                              member_increment: Optional[int] = None,
                              channel_id: Optional[int] = None) -> None:
        conn = await get_welcome_conn()
        await conn.execute(
            """
            INSERT INTO welcome_settings
            (guild_id, is_enabled, member_increment, channel_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT(guild_id) DO UPDATE SET
                is_enabled = EXCLUDED.is_enabled,
                member_increment = COALESCE($5, welcome_settings.member_increment),
                channel_id = COALESCE($6, welcome_settings.channel_id)
            """,
            guild_id, is_enabled, member_increment, channel_id,
            member_increment, channel_id
        )
        await conn.close()

class LeaveDatabase:
    """退室メッセージの設定を管理するDB"""

    @staticmethod
    async def init_database() -> None:
        conn = await get_leave_conn()
        await conn.execute(CREATE_LEAVE_TABLE_SQL)
        await conn.close()

    @staticmethod
    async def get_settings(guild_id: int) -> Tuple[bool, Optional[int]]:
        conn = await get_leave_conn()
        result = await conn.fetchrow(
            """
            SELECT is_enabled, channel_id
            FROM leave_settings WHERE guild_id = $1
            """,
            guild_id
        )
        await conn.close()
        return (
            bool(result[0]),
            result[1]
        ) if result else (False, None)

    @staticmethod
    async def update_settings(guild_id: int, is_enabled: bool,
                              channel_id: Optional[int] = None) -> None:
        conn = await get_leave_conn()
        await conn.execute(
            """
            INSERT INTO leave_settings
            (guild_id, is_enabled, channel_id)
            VALUES ($1, $2, $3)
            ON CONFLICT(guild_id) DO UPDATE SET
                is_enabled = EXCLUDED.is_enabled,
                channel_id = COALESCE($4, leave_settings.channel_id)
            """,
            guild_id, is_enabled, channel_id, channel_id
        )
        await conn.close()

class MemberWelcomeCog(commands.Cog):
    """メンバー参加時のウェルカムメッセージを管理"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.last_welcome_time = {}

    async def cog_load(self) -> None:
        """Cogのロード時にDBを初期化"""
        await WelcomeDatabase.init_database()
        await LeaveDatabase.init_database()

    @app_commands.command(
        name="welcome",
        description="参加メッセージの設定"
    )
    @app_commands.describe(
        action="参加メッセージをON/OFFにします",
        increment="何人ごとにお祝いメッセージを送信するか設定 (デフォルト: 100)",
        channel="メッセージを送信するチャンネル"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable")
    ])
    async def welcome_command(
        self,
        interaction: discord.Interaction,
        action: Literal["enable", "disable"],
        increment: Optional[int] = None,
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        """ウェルカムメッセージの設定を行うコマンド"""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                ERROR_MESSAGES["no_permission"],
                ephemeral=True
            )
            return

        try:
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    ERROR_MESSAGES["no_permission"],
                    ephemeral=True
                )
                return

            is_enabled = action == "enable"
            increment = increment or DEFAULT_INCREMENT

            if increment < MIN_INCREMENT or increment > MAX_INCREMENT:
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_increment"],
                    ephemeral=True
                )
                return

            if is_enabled and not channel:
                await interaction.response.send_message(
                    ERROR_MESSAGES["no_channel"],
                    ephemeral=True
                )
                return

            channel_id = channel.id if channel else None
            await WelcomeDatabase.update_settings(
                interaction.guild_id,
                is_enabled,
                increment,
                channel_id
            )

            if is_enabled:
                await interaction.response.send_message(
                    SUCCESS_MESSAGES["enabled"].format(
                        increment=increment,
                        channel=channel.mention
                    ),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    SUCCESS_MESSAGES["disabled"],
                    ephemeral=True
                )

        except Exception as e:
            logger.error("Error in welcome command: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"エラーが発生しました: {e}",
                ephemeral=True
            )

    @app_commands.command(
        name="leave-message",
        description="退室メッセージの設定"
    )
    @app_commands.describe(
        action="退室メッセージをON/OFFにします",
        channel="メッセージを送信するチャンネル"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable")
    ])
    async def leave_command(
        self,
        interaction: discord.Interaction,
        action: Literal["enable", "disable"],
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        """退室メッセージの設定を行うコマンド"""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                ERROR_MESSAGES["no_permission"],
                ephemeral=True
            )
            return

        try:
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    ERROR_MESSAGES["no_permission"],
                    ephemeral=True
                )
                return

            is_enabled = action == "enable"

            if is_enabled and not channel:
                await interaction.response.send_message(
                    ERROR_MESSAGES["no_channel"],
                    ephemeral=True
                )
                return

            channel_id = channel.id if channel else None
            await LeaveDatabase.update_settings(
                interaction.guild_id,
                is_enabled,
                channel_id
            )

            if is_enabled:
                await interaction.response.send_message(
                    f"退室メッセージをONにしました! チャンネル: {channel.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "退室メッセージを無効にしました!",
                    ephemeral=True
                )

        except Exception as e:
            logger.error("Error in leave command: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"エラーが発生しました: {e}",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """メンバー参加時のイベントハンドラ"""
        if member.bot:
            return

        try:
            is_enabled, increment, channel_id = await WelcomeDatabase.get_settings(
                member.guild.id
            )
            if not is_enabled:
                return

            # 参加マクロ対策
            now = datetime.now()
            last_time = self.last_welcome_time.get(member.guild.id)
            if last_time and now - last_time < timedelta(seconds=JOIN_COOLDOWN):
                return
            self.last_welcome_time[member.guild.id] = now

            channel = member.guild.get_channel(channel_id)
            if not channel:
                await WelcomeDatabase.update_settings(
                    member.guild.id,
                    False
                )
                return

            member_count = len(member.guild.members)
            remainder = member_count % increment

            if remainder == 0:
                message = WELCOME_MESSAGES["milestone"].format(
                    mention=member.mention,
                    member_count=member_count,
                    guild_name=member.guild.name
                )
            else:
                message = WELCOME_MESSAGES["normal"].format(
                    mention=member.mention,
                    member_count=member_count,
                    remaining=increment - remainder,
                    next_milestone=member_count + (increment - remainder)
                )

            await channel.send(message)

        except Exception as e:
            logger.error(
                "Error processing member join: %s", e,
                exc_info=True
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """メンバー退室時のイベントハンドラ"""
        try:
            is_enabled, channel_id = await LeaveDatabase.get_settings(
                member.guild.id
            )
            if not is_enabled:
                return

            channel = member.guild.get_channel(channel_id)
            if not channel:
                await LeaveDatabase.update_settings(
                    member.guild.id,
                    False
                )
                return

            member_count = len(member.guild.members)
            message = LEAVE_MESSAGES["leave"].format(
                mention=member.mention,
                member_count=member_count
            )

            await channel.send(message)

        except Exception as e:
            logger.error(
                "Error processing member leave: %s", e,
                exc_info=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemberWelcomeCog(bot))
