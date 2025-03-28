from typing import Final, List
from enum import Enum
import logging
import sqlite3
import uuid

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button


ADMIN_USER_ID: Final[int] = 1241397634095120438
SERVERS_PER_PAGE: Final[int] = 10
EMBED_COLORS: Final[dict] = {
    "error": discord.Color.red(),
    "success": discord.Color.green(),
    "info": discord.Color.blue()
}
ERROR_MESSAGES: Final[dict] = {
    "no_permission": "このコマンドを使用する権限がありません。",
    "invalid_option": "無効なオプションです。"
}

logger = logging.getLogger(__name__)

class AdminOption(str, Enum):
    """管理コマンドのオプション"""
    SERVERS = "servers"
    DEBUG = "debug"

class PaginationView(View):
    """ページネーション用のカスタムビュー"""

    def __init__(
        self,
        embeds: List[discord.Embed],
        timeout: float = 180.0
    ) -> None:
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0

        # ボタンの設定
        self.previous_button = Button(
            label="前へ",
            style=discord.ButtonStyle.primary,
            disabled=True,
            custom_id="previous_page"
        )
        self.next_button = Button(
            label="次へ",
            style=discord.ButtonStyle.primary,
            custom_id="next_page"
        )

        self.previous_button.callback = self.previous_callback
        self.next_button.callback = self.next_callback

        self.add_item(self.previous_button)
        self.add_item(self.next_button)

    async def update_buttons(self) -> None:
        """ボタンの状態を更新"""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1

    async def previous_callback(
        self,
        interaction: discord.Interaction
    ) -> None:
        """前のページへ移動"""
        self.current_page = max(0, self.current_page - 1)
        await self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )

    async def next_callback(
        self,
        interaction: discord.Interaction
    ) -> None:
        """次のページへ移動"""
        self.current_page = min(
            len(self.embeds) - 1,
            self.current_page + 1
        )
        await self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )

class RequestPaginationView(View):
    """リクエストページネーション用のカスタムビュー"""

    def __init__(
        self,
        embeds: List[discord.Embed],
        timeout: float = 180.0
    ) -> None:
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0

        # ボタンの設定
        self.previous_button = Button(
            label="前へ",
            style=discord.ButtonStyle.primary,
            disabled=True,
            custom_id="previous_page"
        )
        self.next_button = Button(
            label="次へ",
            style=discord.ButtonStyle.primary,
            custom_id="next_page"
        )

        self.previous_button.callback = self.previous_callback
        self.next_button.callback = self.next_callback

        self.add_item(self.previous_button)
        self.add_item(self.next_button)

    async def update_buttons(self) -> None:
        """ボタンの状態を更新"""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1

    async def previous_callback(
        self,
        interaction: discord.Interaction
    ) -> None:
        """前のページへ移動"""
        self.current_page = max(0, self.current_page - 1)
        await self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )

    async def next_callback(
        self,
        interaction: discord.Interaction
    ) -> None:
        """次のページへ移動"""
        self.current_page = min(
            len(self.embeds) - 1,
            self.current_page + 1
        )
        await self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=self
        )

class BotAdmin(commands.Cog):
    """ボット管理機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def is_admin(self, user_id: int) -> bool:
        return user_id == ADMIN_USER_ID

    async def create_server_embeds(self) -> List[discord.Embed]:
        embeds = []
        current_embed = discord.Embed(
            title="参加中のサーバー",
            color=EMBED_COLORS["info"]
        )

        for i, guild in enumerate(self.bot.guilds, 1):
            member_count = len(guild.members)
            owner = guild.owner
            created_at = guild.created_at.strftime("%Y-%m-%d")

            value = (
                f"ID: {guild.id}\n"
                f"オーナー: {owner}\n"
                f"メンバー数: {member_count}\n"
                f"作成日: {created_at}"
            )
            current_embed.add_field(
                name=guild.name,
                value=value,
                inline=False
            )

            if i % SERVERS_PER_PAGE == 0 or i == len(self.bot.guilds):
                embeds.append(current_embed)
                current_embed = discord.Embed(
                    title="参加中のサーバー (続き)",
                    color=EMBED_COLORS["info"]
                )

        return embeds

    async def create_debug_embed(self) -> discord.Embed:
        cogs = ", ".join(self.bot.cogs.keys())
        shard_info = (
            f"Shard ID: {self.bot.shard_id}\n"
            f"Shard Count: {self.bot.shard_count}\n"
        ) if self.bot.shard_id is not None else "Sharding is not enabled."

        debug_info = (
            f"Bot Name: {self.bot.user.name}\n"
            f"Bot ID: {self.bot.user.id}\n"
            f"Latency: {self.bot.latency * 1000:.2f} ms\n"
            f"Guild Count: {len(self.bot.guilds)}\n"
            f"Loaded Cogs: {cogs}\n"
            f"{shard_info}"
        )

        return discord.Embed(
            title="デバッグ情報",
            description=debug_info,
            color=EMBED_COLORS["success"]
        )

    async def create_request_embeds(self) -> List[discord.Embed]:
        conn = sqlite3.connect("data/request.db")
        c = conn.cursor()
        c.execute("SELECT user_id, date, message FROM requests ORDER BY date DESC")
        requests = c.fetchall()
        conn.close()

        embeds = []
        current_embed = discord.Embed(
            title="リクエスト一覧",
            color=EMBED_COLORS["info"]
        )

        for i, (user_id, date, message) in enumerate(requests, 1):
            value = (
                f"ユーザーID: {user_id}\n"
                f"日時: {date}\n"
                f"メッセージ: {message}"
            )
            current_embed.add_field(
                name=f"リクエスト {i}",
                value=value,
                inline=False
            )

            if i % SERVERS_PER_PAGE == 0 or i == len(requests):
                embeds.append(current_embed)
                current_embed = discord.Embed(
                    title="リクエスト一覧 (続き)",
                    color=EMBED_COLORS["info"]
                )

        return embeds

    async def generate_premium_token(self, user_id: int) -> str:
        """指定したユーザーにプレミアムトークンを発行し、DMを送信"""
        from cogs.premium import PremiumDatabase
        db = PremiumDatabase()
        user_data = db.get_user(user_id)

        if user_data:
            return user_data[0]  # 既存のトークンを返す

        token = str(uuid.uuid4())
        db.add_user(user_id, token)
        return token

    @app_commands.command(
        name="botadmin",
        description="Bot管理コマンド"
    )
    async def botadmin_command(
        self,
        interaction: discord.Interaction,
        option: str
    ) -> None:
        if not self.is_admin(interaction.user.id):
            embed = discord.Embed(
                title="エラー",
                description=ERROR_MESSAGES["no_permission"],
                color=EMBED_COLORS["error"]
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            return

        try:
            if option == AdminOption.SERVERS:
                embeds = await self.create_server_embeds()
                view = PaginationView(embeds)
                await interaction.response.send_message(
                    embed=embeds[0],
                    view=view,
                    ephemeral=True
                )

            elif option == AdminOption.DEBUG:
                embed = await self.create_debug_embed()
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True
                )

            elif option == "viewreq":
                embeds = await self.create_request_embeds()
                view = RequestPaginationView(embeds)
                await interaction.response.send_message(
                    embed=embeds[0],
                    view=view,
                    ephemeral=True
                )

            elif option.startswith("premium:"):
                try:
                    user_id = int(option.split(":")[1])
                    token = await self.generate_premium_token(user_id)
                    user = await self.bot.fetch_user(user_id)

                    if user:
                        await user.send(
                            f"🎉 **Swiftlyのプレミアムトークンが発行されました！** 🎉\n\n"
                            f"🔑 `{token}`\n\n"
                            "プレミアム機能を有効にするには、以下の手順をお試しください:\n"
                            "1️⃣ `/premium` コマンドを使用してトークンを登録\n"
                            "2️⃣ プレミアム機能を有効化\n\n"
                            "✨ **プレミアム特典:**\n"
                            "🔹 VC読み上げボイスの変更が可能\n"
                            "🔹 ボイスは `/set_voice` コマンドで設定できます\n\n"
                            "これからもSwiftlyをよろしくお願いします！"
                        )
                        await interaction.response.send_message(
                            f"ユーザー {user_id} にプレミアムトークンを発行し、DMを送信しました。",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            f"ユーザー {user_id} を見つけることができませんでした。",
                            ephemeral=True
                        )
                except Exception as e:
                    logger.error("Error in premium token generation: %s", e, exc_info=True)
                    await interaction.response.send_message(
                        f"エラーが発生しました: {e}",
                        ephemeral=True
                    )

            else:
                embed = discord.Embed(
                    title="エラー",
                    description=ERROR_MESSAGES["invalid_option"],
                    color=EMBED_COLORS["error"]
                )
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True
                )

        except Exception as e:
            logger.error("Error in botadmin command: %s", e, exc_info=True)
            embed = discord.Embed(
                title="エラー",
                description=f"予期せぬエラーが発生しました: {e}",
                color=EMBED_COLORS["error"]
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotAdmin(bot))
