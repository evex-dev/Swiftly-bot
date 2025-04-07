import datetime
from pathlib import Path
from typing import Final, Optional, Tuple
import logging
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks


DB_PATH: Final[Path] = Path("data/server_board.db")
UP_DB_PATH: Final[Path] = Path("data/server_board_up.db")
UP_COOLDOWN: Final[int] = 7200  # 2時間（秒）
REMINDER_MESSAGE: Final[str] = "2時間経ちました！/upしてね！"
ERROR_MESSAGES: Final[dict] = {
    "already_registered": "このサーバーは既に登録されています。",
    "db_error": "DBエラーが発生しました。時間をおいて再度お試しください。\nエラー: {}",
    "no_invite_channel": "招待リンクを作成できるチャンネルがありません。ボットの権限を確認してください。",
    "no_invite_permission": "招待リンクを作成する権限がありません。ボットに「招待リンクの作成」権限があることを確認してください。",
    "invite_error": "招待リンクの作成中にエラーが発生しました。時間をおいて再度お試しください。\nエラー: {}",
    "not_registered": "このサーバーは登録されていません。",
    "register_first": "このサーバーは登録されていません。先に/registerコマンドで登録してください。",
    "unexpected_error": "予期せぬエラーが発生しました。時間をおいて再度お試しください。\nエラー: {}"
}

logger = logging.getLogger(__name__)

class DescriptionModal(discord.ui.Modal):
    """サーバー説明文設定用のモーダル"""

    def __init__(self, default_description: Optional[str] = None) -> None:
        super().__init__(title="サーバー説明文の設定")
        self.description = discord.ui.TextInput(
            label="サーバーの説明",
            placeholder="あなたのサーバーの説明を入力してください",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=default_description
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute(
                    "UPDATE servers SET description = ? WHERE server_id = ?",
                    (str(self.description), interaction.guild.id)
                )
                await conn.commit()
            await interaction.response.send_message("サーバーの説明文を更新しました！", ephemeral=True)
        except Exception as e:
            pass

class ConfirmView(discord.ui.View):
    """登録確認用のビュー"""

    def __init__(self, guild: discord.Guild, invite: discord.Invite) -> None:
        super().__init__(timeout=180.0)
        self.guild = guild
        self.invite = invite

    @discord.ui.button(style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute(
                    """
                    INSERT INTO servers (server_id, server_name, icon_url, invite_url)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        self.guild.id,
                        self.guild.name,
                        self.guild.icon.url if self.guild.icon else None,
                        self.invite.url
                    )
                )
                await conn.commit()
            await interaction.followup.send("サーバーを登録しました！", ephemeral=True)
            await interaction.message.delete()
        except Exception as e:
            pass
    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self.invite.delete()
            await interaction.followup.send("登録をキャンセルしました。", ephemeral=True)
            await interaction.message.delete()
        except Exception as e:
            pass
    async def on_timeout(self) -> None:
        try:
            await self.invite.delete()
        except Exception as e:
            pass

class UnregisterView(discord.ui.View):
    """登録削除確認用のビュー"""

    def __init__(self, guild_id: int) -> None:
        super().__init__(timeout=180.0)
        self.guild_id = guild_id

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                cursor = await conn.execute(
                    "DELETE FROM servers WHERE server_id = ?",
                    (self.guild_id,)
                )
                deleted = cursor.rowcount > 0
                await conn.commit()

            if deleted:
                await interaction.followup.send("サーバーの登録を削除しました。", ephemeral=True)
            else:
                await interaction.followup.send(ERROR_MESSAGES["not_registered"], ephemeral=True)
            await interaction.message.delete()
        except Exception as e:
            pass
    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("登録削除をキャンセルしました。", ephemeral=True)
        await interaction.message.delete()

class ServerBoard(commands.Cog):
    """サーバー掲示板機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.setup_database.start()
        self.check_up_reminder.start()

    async def cog_unload(self) -> None:
        self.setup_database.cancel()
        self.check_up_reminder.cancel()

    @tasks.loop(count=1)
    async def setup_database(self) -> None:
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS servers (
                        server_id INTEGER PRIMARY KEY,
                        server_name TEXT NOT NULL,
                        icon_url TEXT,
                        description TEXT,
                        rank_points INTEGER DEFAULT 0,
                        last_up_time TIMESTAMP,
                        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        invite_url TEXT
                    )
                """)
                await conn.commit()

            async with aiosqlite.connect(UP_DB_PATH) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS up_channels (
                        server_id INTEGER PRIMARY KEY,
                        channel_id INTEGER,
                        last_up_time TIMESTAMP
                    )
                """)
                await conn.commit()
        except Exception as e:
            pass

    @tasks.loop(minutes=1)
    async def check_up_reminder(self) -> None:
        try:
            current_time = datetime.datetime.now()
            async with aiosqlite.connect(UP_DB_PATH) as conn:
                async with conn.execute(
                    "SELECT server_id, channel_id, last_up_time FROM up_channels"
                ) as cursor:
                    async for server_id, channel_id, last_up_time in cursor:
                        last_up = datetime.datetime.fromisoformat(last_up_time)
                        if (current_time - last_up).total_seconds() >= UP_COOLDOWN:
                            if guild := self.bot.get_guild(server_id):
                                if channel := guild.get_channel(channel_id):
                                    await channel.send(REMINDER_MESSAGE)
                            await conn.execute(
                                "DELETE FROM up_channels WHERE server_id = ?",
                                (server_id,)
                            )
                await conn.commit()
        except Exception as e:
            pass

    async def create_server_invite(
        self,
        guild: discord.Guild
    ) -> Tuple[Optional[discord.Invite], Optional[str]]:
        """サーバーの招待リンクを作成"""
        try:
            invite_channel = guild.system_channel or next(
                (ch for ch in guild.text_channels
                 if ch.permissions_for(guild.me).create_instant_invite),
                None
            )
            if not invite_channel:
                return None, ERROR_MESSAGES["no_invite_channel"]

            try:
                invite = await invite_channel.create_invite(
                    max_age=0,
                    max_uses=0,
                    reason="サーバー掲示板用の永続的な招待リンク"
                )
                return invite, None
            except discord.Forbidden:
                return None, ERROR_MESSAGES["no_invite_permission"]
            except discord.HTTPException as e:
                return None, ERROR_MESSAGES["invite_error"].format(str(e))

        except Exception as e:
            pass

    @app_commands.command(
        name="register",
        description="サーバーを掲示板に登録します"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def register(self, interaction: discord.Interaction) -> None:
        """サーバーを掲示板に登録"""
        await interaction.response.defer(ephemeral=True)
        try:
            # 既存の登録をチェック
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute(
                    "SELECT 1 FROM servers WHERE server_id = ?",
                    (interaction.guild.id,)
                ) as cursor:
                    if await cursor.fetchone():
                        await interaction.followup.send(
                            ERROR_MESSAGES["already_registered"],
                            ephemeral=True
                        )
                        return

            # 招待リンクを作成
            invite, error = await self.create_server_invite(interaction.guild)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return

            # 確認用Embedを作成
            embed = discord.Embed(
                title="サーバー掲示板への登録",
                description="以下の情報でサーバーを登録します。よろしければ✅を押してください。\n"
                          "キャンセルする場合は❌を押してください。",
                color=discord.Color.blue()
            )
            embed.add_field(name="サーバー名", value=interaction.guild.name)
            embed.add_field(
                name="アイコン",
                value="設定済み" if interaction.guild.icon else "未設定"
            )
            embed.add_field(name="招待リンク", value=invite.url, inline=False)

            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            view = ConfirmView(interaction.guild, invite)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            pass

    @app_commands.command(
        name="up",
        description="サーバーの表示順位を上げます"
    )
    async def up_rank(self, interaction: discord.Interaction) -> None:
        """サーバーの表示順位を上げる"""
        await interaction.response.defer(ephemeral=False)
        try:
            # DMでコマンドが使用された場合のチェック
            if not interaction.guild:
                await interaction.followup.send(
                    "このコマンドはサーバー内でのみ使用できます。",
                    ephemeral=True
                )
                return
                
            current_time = datetime.datetime.now()

            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute(
                    "SELECT last_up_time FROM servers WHERE server_id = ?",
                    (interaction.guild.id,)
                ) as cursor:
                    result = await cursor.fetchone()

                    if not result:
                        await interaction.followup.send(
                            ERROR_MESSAGES["not_registered"],
                            ephemeral=False
                        )
                        return

                    if result[0]:
                        last_up = datetime.datetime.fromisoformat(result[0])
                        if (current_time - last_up).total_seconds() < UP_COOLDOWN:
                            remaining_time = datetime.timedelta(
                                seconds=UP_COOLDOWN
                            ) - (current_time - last_up)
                            await interaction.followup.send(
                                f"upコマンドは2時間に1回のみ使用できます。\n"
                                f"残り時間: {int(remaining_time.total_seconds())}秒",
                                ephemeral=True
                            )
                            return

                await conn.execute(
                    """
                    UPDATE servers
                    SET rank_points = rank_points + 1,
                        last_up_time = ?
                    WHERE server_id = ?
                    """,
                    (current_time.isoformat(), interaction.guild.id)
                )
                await conn.commit()

            async with aiosqlite.connect(UP_DB_PATH) as conn:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO up_channels
                    (server_id, channel_id, last_up_time)
                    VALUES (?, ?, ?)
                    """,
                    (
                        interaction.guild.id,
                        interaction.channel.id,
                        current_time.isoformat()
                    )
                )
                await conn.commit()

            await interaction.followup.send(
                "サーバーの表示順位を上げました！2時間後にこの場所で/upを通知します。",
                ephemeral=False
            )

        except Exception as e:
            pass

    @app_commands.command(
        name="board-setting",
        description="サーバーの説明文を設定します"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def board_setting(self, interaction: discord.Interaction) -> None:
        """サーバーの説明文を設定"""
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                async with conn.execute(
                    "SELECT description FROM servers WHERE server_id = ?",
                    (interaction.guild.id,)
                ) as cursor:
                    result = await cursor.fetchone()

                    if not result:
                        await interaction.response.send_message(
                            ERROR_MESSAGES["register_first"],
                            ephemeral=True
                        )
                        return

                    modal = DescriptionModal(result[0] if result[0] else None)
                    await interaction.response.send_modal(modal)

        except Exception as e:
            pass

    @app_commands.command(
        name="unregister",
        description="サーバーの登録を削除します"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def unregister(self, interaction: discord.Interaction) -> None:
        """サーバーの登録を削除"""
        try:
            embed = discord.Embed(
                title="サーバー掲示板からの登録削除",
                description="本当にこのサーバーの登録を削除しますか？\n"
                          "この操作は取り消せません。",
                color=discord.Color.red()
            )
            view = UnregisterView(interaction.guild.id)
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )

        except Exception as e:
            pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerBoard(bot))
