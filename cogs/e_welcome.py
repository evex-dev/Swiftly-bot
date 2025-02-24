import os
import sqlite3
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands


class MemberWelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_welcome_time = {}
        self.db_path = "data/welcome.db"
        self._init_database()

    def _init_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS welcome_settings (
            guild_id INTEGER PRIMARY KEY,
            is_enabled INTEGER DEFAULT 0,
            member_increment INTEGER DEFAULT 100,
            channel_id INTEGER DEFAULT NULL
        )
        """)

        conn.commit()
        conn.close()

    def _get_guild_settings(self, guild_id: int) -> tuple:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT is_enabled, member_increment, channel_id FROM welcome_settings WHERE guild_id = ?",
            (guild_id,)
        )
        result = cursor.fetchone()
        conn.close()

        if result is None:
            return (False, 100, None)  # デフォルト100人ずつ
        return (bool(result[0]), result[1], result[2])

    def _update_guild_settings(self, guild_id: int, is_enabled: bool, member_increment: int = None, channel_id: int = None):
        """Update guild welcome settings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO welcome_settings (guild_id, is_enabled, member_increment, channel_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                is_enabled = excluded.is_enabled,
                member_increment = COALESCE(?, welcome_settings.member_increment),
                channel_id = COALESCE(?, welcome_settings.channel_id)
            """,
            (guild_id, is_enabled, member_increment, channel_id, member_increment, channel_id)
        )

        conn.commit()
        conn.close()

    @app_commands.command(
        name="welcome",
        description="参加メッセージの設定"
    )
    @app_commands.describe(
        action="on/off - 参加メッセージをON/OFFにします",
        increment="何人ごとにお祝いメッセージを送信するか設定 (デフォルト: 100)",
        channel="メッセージを送信するチャンネル"
    )
    async def welcome_command(
        self,
        interaction: discord.Interaction,
        action: str,
        increment: int = None,
        channel: discord.TextChannel = None
    ):
        # このあたりは適宜変更してね
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("コマンドを使用するにはサーバーの管理権限が必要だよ", ephemeral=True)
            return

        if action.lower() not in ["on", "off"]:
            await interaction.response.send_message("onまたはoffを指定してね", ephemeral=True)
            return

        is_enabled = action.lower() == "on"

        # OFFの時もincrementが指定されるかもだけどまぁ気になるならいじろう
        if not increment:
            increment = 100

        if increment and (increment < 5 or increment > 1000):
            await interaction.response.send_message("5～1000人の間で指定してね", ephemeral=True)
            return

        if is_enabled and channel is None:
            await interaction.response.send_message("ONにする場合はチャンネルを指定してね", ephemeral=True)
            return

        channel_id = channel.id if channel else None
        self._update_guild_settings(
            interaction.guild_id, is_enabled, increment, channel_id)

        settings = self._get_guild_settings(interaction.guild_id)
        if is_enabled:
            channel_mention = f"<#{settings[2]}>"
            await interaction.response.send_message(
                f"参加メッセージをONにしたよ!\n"
                f"{settings[1]}人ごとに{channel_mention}でお祝いメッセージを送信します",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("参加メッセージを無効にしたよ!", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        settings = self._get_guild_settings(member.guild.id)
        if not settings[0]:
            return

        # 参加マクロ対策
        now = datetime.now()
        last_time = self.last_welcome_time.get(member.guild.id)
        if last_time and now - last_time < timedelta(seconds=3):
            return
        self.last_welcome_time[member.guild.id] = now

        # 設定されたチャンネルを取得
        channel = member.guild.get_channel(settings[2])

        if channel is None:
            # チャンネルが見つからない場合は設定をOFFにする
            self._update_guild_settings(member.guild.id, False)
            return

        guild = self.bot.get_guild(member.guild.id)

        remainder = len(member.guild.members) % settings[1]  # member_increment
        if remainder == 0:
            message = (
                f"🎉🎉🎉 お祝い 🎉🎉🎉\n"
                f"{member.mention} さん、ようこそ！\n"
                f"{len(guild.members)}人達成！\n"
                f"{guild.name}のメンバーが{len(guild.members)}人になりました！皆さんありがとうございます！"
            )
        else:
            remaining_members = settings[1] - remainder
            message = (
                f"{member.mention} さん、ようこそ！\n"
                f"現在のメンバー数: {len(guild.members)}人\n"
                f"あと {remaining_members} 人で {len(guild.members) + remaining_members}人達成です！"
            )

        await channel.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberWelcomeCog(bot))
