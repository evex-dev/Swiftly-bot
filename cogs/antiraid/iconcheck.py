import discord
from discord.ext import commands
from discord.ui import View
from datetime import datetime, timezone, timedelta
import aiosqlite
from pathlib import Path
from typing import Final, Optional
import logging


JST: Final[timezone] = timezone(timedelta(hours=9))
DB_PATH: Final[Path] = Path("data/anticheat.db")
BUTTON_TIMEOUT: Final[int] = 60
WARNING_DELETE_DELAY: Final[int] = 5

EMBED_COLORS: Final[dict] = {
    "error": discord.Color.red(),
    "warning": discord.Color.orange(),
    "success": discord.Color.green(),
    "info": discord.Color.blue()
}

ERROR_MESSAGES: Final[dict] = {
    "guild_only": "このコマンドはサーバー内でのみ使用できます。",
    "admin_only": "このコマンドはサーバーの管理者のみ実行できます。",
    "no_permission": "Botにメッセージ削除の権限がありません。登録できません。",
    "already_enabled": "荒らし対策は既に有効です。",
    "already_disabled": "荒らし対策は既に無効です。",
    "interaction_failed": "インタラクションに失敗しました: {}"
}

SUCCESS_MESSAGES: Final[dict] = {
    "enabled": "荒らし対策を有効にしました。",
    "disabled": "荒らし対策を無効にしました。"
}

FEATURE_DESCRIPTION: Final[str] = (
    "この機能は、デフォルトアバターかつ本日作成されたアカウントによる"
    "メッセージ送信を制限することで、荒らし対策をします。\n"
    "登録ボタンを押すことで、荒らし対策を有効にします。"
)

logger = logging.getLogger(__name__)

class AntiRaidDatabase:
    """荒らし対策のDB操作を管理"""

    @staticmethod
    async def init_db() -> None:
        """DBを初期化"""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS enabled_servers
                (guild_id TEXT PRIMARY KEY)
                """
            )
            await db.commit()

    @staticmethod
    async def is_enabled(guild_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM enabled_servers WHERE guild_id = ?",
                (str(guild_id),)
            ) as cursor:
                return await cursor.fetchone() is not None

    @staticmethod
    async def enable(guild_id: int) -> None:
        """サーバーの機能を有効化"""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO enabled_servers (guild_id) VALUES (?)",
                (str(guild_id),)
            )
            await db.commit()

    @staticmethod
    async def disable(guild_id: int) -> None:
        """サーバーの機能を無効化"""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM enabled_servers WHERE guild_id = ?",
                (str(guild_id),)
            )
            await db.commit()

class EnableAnticheatView(View):
    """荒らし対策有効化用のビュー"""

    def __init__(self, guild_id: int) -> None:
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.guild_id = guild_id

    @discord.ui.button(
        label="登録",
        style=discord.ButtonStyle.green,
        custom_id="confirm_enable"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        """登録ボタンのコールバック"""
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.guild:
                await interaction.followup.send(
                    ERROR_MESSAGES["guild_only"],
                    ephemeral=True
                )
                return

            if not interaction.channel.permissions_for(
                interaction.guild.me
            ).manage_messages:
                await interaction.followup.send(
                    ERROR_MESSAGES["no_permission"],
                    ephemeral=True
                )
                return

            if await AntiRaidDatabase.is_enabled(self.guild_id):
                await interaction.followup.send(
                    ERROR_MESSAGES["already_enabled"],
                    ephemeral=True
                )
                return

            await AntiRaidDatabase.enable(self.guild_id)
            await interaction.edit_original_response(
                content=SUCCESS_MESSAGES["enabled"]
            )

        except Exception as e:
            logger.error("Error in enable confirmation: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["interaction_failed"].format(str(e)),
                ephemeral=True
            )
        finally:
            self.stop()

class IconCheck(commands.Cog):
    """荒らし対策機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Cogのロード時にDBを初期化"""
        await AntiRaidDatabase.init_db()

    def _create_embed(
        self,
        title: str,
        description: str,
        color_key: str
    ) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=description,
            color=EMBED_COLORS[color_key]
        )

    async def _check_command_context(
        self,
        interaction: discord.Interaction
    ) -> Optional[discord.Embed]:
        if not interaction.guild:
            return self._create_embed(
                "エラー",
                ERROR_MESSAGES["guild_only"],
                "error"
            )

        if not interaction.user.guild_permissions.administrator:
            return self._create_embed(
                "エラー",
                ERROR_MESSAGES["admin_only"],
                "error"
            )

        return None

    @discord.app_commands.command(
        name="antiraid_enable",
        description="荒らし対策を有効にします"
    )
    async def anticheat_enable(
        self,
        interaction: discord.Interaction
    ) -> None:
        """荒らし対策を有効化するコマンド"""
        if error_embed := await self._check_command_context(interaction):
            await interaction.response.send_message(
                embed=error_embed,
                ephemeral=True
            )
            return

        if await AntiRaidDatabase.is_enabled(interaction.guild_id):
            await interaction.response.send_message(
                embed=self._create_embed(
                    "情報",
                    ERROR_MESSAGES["already_enabled"],
                    "warning"
                ),
                ephemeral=True
            )
            return

        embed = self._create_embed(
            "説明",
            FEATURE_DESCRIPTION,
            "info"
        )
        view = EnableAnticheatView(interaction.guild_id)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @discord.app_commands.command(
        name="antiraid_disable",
        description="荒らし対策を無効にします"
    )
    async def anticheat_disable(
        self,
        interaction: discord.Interaction
    ) -> None:
        """荒らし対策を無効化するコマンド"""
        if error_embed := await self._check_command_context(interaction):
            await interaction.response.send_message(
                embed=error_embed,
                ephemeral=True
            )
            return

        if not await AntiRaidDatabase.is_enabled(interaction.guild_id):
            await interaction.response.send_message(
                embed=self._create_embed(
                    "情報",
                    ERROR_MESSAGES["already_disabled"],
                    "warning"
                ),
                ephemeral=True
            )
            return

        await AntiRaidDatabase.disable(interaction.guild_id)
        await interaction.response.send_message(
            embed=self._create_embed(
                "完了",
                SUCCESS_MESSAGES["disabled"],
                "success"
            ),
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """メッセージ送信時の処理"""
        if message.author.bot or not message.guild:
            return

        try:
            if await AntiRaidDatabase.is_enabled(message.guild.id):
                user = message.author
                is_default_avatar = user.avatar is None
                created_at_utc = user.created_at.replace(tzinfo=timezone.utc)
                is_new_account = (
                    created_at_utc.date() ==
                    datetime.now(timezone.utc).date()
                )

                if is_default_avatar and is_new_account:
                    await message.delete()
                    logger.info(f"Deleted message from {user} in {message.guild.name} ({message.guild.id})")
                    warning_embed = self._create_embed(
                        "警告",
                        f"{user.mention}、デフォルトのアバターかつ"
                        "本日作成されたアカウントではメッセージを送信できません。",
                        "error"
                    )
                    warning_message = await message.channel.send(
                        embed=warning_embed
                    )
                    await warning_message.delete(delay=WARNING_DELETE_DELAY)

        except Exception as e:
            logger.error(
                "Error processing message in anti-raid: %s", e,
                exc_info=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IconCheck(bot))
