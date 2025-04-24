import json
import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
import asyncpg  # 追加
from dotenv import load_dotenv  # 追加
from discord.app_commands import Transform  # 追加
from discord import Role  # 修正

logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = "role_panel"

class RolePanel(commands.Cog):
    """ユーザーがリアクションを通じてロールを取得できるパネルを管理するコグ"""

    def __init__(self, bot):
        self.bot = bot
        self.db_pool: Optional[asyncpg.Pool] = None  # データベース接続プール
        self.panels = {}

    async def cog_load(self):
        """Cogがロードされたときにデータベース接続プールを初期化"""
        self.db_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        await self._load_panels()

    async def cog_unload(self):
        """Cogがアンロードされたときにデータベース接続プールを閉じる"""
        if self.db_pool:
            await self.db_pool.close()

    async def _load_panels(self):
        """データベースからロールパネル情報を読み込む"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM role_panels")
                self.panels = {
                    row["panel_id"]: {
                        "title": row["title"],
                        "description": row["description"],
                        "channel_id": row["channel_id"],
                        "guild_id": row["guild_id"],
                        "roles": json.loads(row["roles"])
                    }
                    for row in rows
                }
        except Exception as e:
            logger.error(f"ロールパネルデータの読み込みに失敗しました: {e}")
            self.panels = {}

    async def _save_panels(self):
        """ロールパネル情報をデータベースに保存する"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("TRUNCATE TABLE role_panels")
                for panel_id, panel_data in self.panels.items():
                    await conn.execute(
                        """
                        INSERT INTO role_panels (panel_id, title, description, channel_id, guild_id, roles)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        panel_id,
                        panel_data["title"],
                        panel_data["description"],
                        panel_data["channel_id"],
                        panel_data["guild_id"],
                        json.dumps(panel_data["roles"])
                    )
        except Exception as e:
            logger.error(f"ロールパネルデータの保存に失敗しました: {e}")

    async def get_or_fetch_message(self, channel_id: int, message_id: int) -> Optional[discord.Message]:
        """チャンネルとメッセージIDからメッセージを取得する"""
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            return await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            logger.error("Failed to fetch message: %s", e)
            return None
            
    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """ユーザーがサーバー管理者権限を持っているか確認する"""
        if not interaction.guild:
            await interaction.response.send_message("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            return False
            
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドはサーバー管理者のみが使用できます。", ephemeral=True)
            return False
            
        return True

    role_panel_group = app_commands.Group(name="role-panel", description="ロールパネル関連のコマンド")

    @role_panel_group.command(name="create", description="新しいロールパネルを作成します")
    @app_commands.describe(
        title="パネルのタイトル",
        description="パネルの説明"
    )
    @app_commands.default_permissions(administrator=True)
    async def create_panel(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str
    ):
        """新しいロールパネルを作成する"""
        if not await self._check_admin(interaction):
            return
            
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )
        embed.set_footer(text="リアクションをクリックしてロールを取得できます")

        await interaction.response.send_message("ロールパネルを作成中...", ephemeral=True)
        message = await interaction.channel.send(embed=embed)

        # パネル情報を保存
        self.panels[message.id] = {
            "title": title,
            "description": description,
            "channel_id": interaction.channel_id,
            "guild_id": interaction.guild_id,
            "roles": {}
        }
        self._save_panels()

        await interaction.edit_original_response(
            content=f"ロールパネルが作成されました！\nパネルID: `{message.id}`\n"
                    f"このパネルは、メッセージ上のリアクションをクリックすると該当ロールが付与される仕組みです。\n"
                    f"ロールの追加、削除、更新はそれぞれ `/role-panel add`、`/role-panel remove`、`/role-panel refresh` コマンドを使用してください。"
        )

    @role_panel_group.command(name="add", description="ロールパネルにロールを追加します")
    @app_commands.describe(
        panel_id="ロールパネルのメッセージID",
        role="追加するロール（ロールが表示されない場合は、ロールIDを入力してください）",
        emoji="関連付けるリアクション絵文字",
        description="ロールの説明（任意）"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_role(
        self,
        interaction: discord.Interaction,
        panel_id: str,
        role: Role,  # 修正
        emoji: str,
        description: str = ""
    ):
        """ロールパネルに新しいロールを追加する"""
        try:
            panel_id = int(panel_id)
        except ValueError:
            await interaction.response.send_message("無効なパネルIDです。数字のみを入力してください。パネルIDは `/role-panel list` で確認できます。", ephemeral=True)
            return

        if panel_id not in self.panels:
            await interaction.response.send_message(f"ID: `{panel_id}` のパネルが見つかりません。\nパネル一覧は `/role-panel list` で確認してください。", ephemeral=True)
            return

        if interaction.guild_id != self.panels[panel_id]["guild_id"]:
            await interaction.response.send_message("このパネルは他のサーバーに属しています。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        panel_data = self.panels[panel_id]
        channel_id = panel_data["channel_id"]

        message = await self.get_or_fetch_message(channel_id, panel_id)
        if not message:
            await interaction.followup.send("パネルメッセージが見つかりませんでした。削除された可能性があります。", ephemeral=True)
            return

        # 絵文字をパネルに追加する
        try:
            await message.add_reaction(emoji)
        except (discord.HTTPException, TypeError, ValueError):
            await interaction.followup.send("無効な絵文字です。Discord上で使用できる絵文字を指定してください。", ephemeral=True)
            return

        # パネルデータに役割を追加
        panel_data["roles"][emoji] = {
            "role_id": role.id,
            "role_name": role.name,
            "description": description
        }
        self._save_panels()

        # パネルの埋め込みを更新
        embed = message.embeds[0]
        role_text = ""
        for e, r_data in panel_data["roles"].items():
            desc = f" - {r_data['description']}" if r_data['description'] else ""
            role_text += f"{e} <@&{r_data['role_id']}>{desc}\n"

        embed.description = panel_data["description"] + "\n\n" + role_text
        await message.edit(embed=embed)

        await interaction.followup.send(
            f"ロール {role.mention} が絵文字 {emoji} と共にパネルに追加されました！\n"
            f"このリアクションをクリックするとユーザーが自動でロールを取得できます。\n"
            f"パネルの詳細は `/role-panel list` で確認してください。",
            ephemeral=True
        )

    @role_panel_group.command(name="remove", description="ロールパネルからロールを削除します")
    @app_commands.describe(
        panel_id="ロールパネルのメッセージID",
        emoji="削除するロールに関連付けられた絵文字"
    )
    @app_commands.default_permissions(administrator=True)
    async def remove_role(
        self,
        interaction: discord.Interaction,
        panel_id: str,
        emoji: str
    ):
        """ロールパネルから特定のロールを削除する"""
        try:
            panel_id = int(panel_id)
        except ValueError:
            await interaction.response.send_message("無効なパネルIDです。数字のみを入力してください。パネルIDは `/role-panel list` で確認できます。", ephemeral=True)
            return

        if panel_id not in self.panels:
            await interaction.response.send_message(f"ID: `{panel_id}` のパネルが見つかりません。\nパネル一覧は `/role-panel list` で確認してください。", ephemeral=True)
            return

        if interaction.guild_id != self.panels[panel_id]["guild_id"]:
            await interaction.response.send_message("このパネルは他のサーバーに属しています。", ephemeral=True)
            return

        panel_data = self.panels[panel_id]
        if emoji not in panel_data["roles"]:
            await interaction.response.send_message(f"絵文字 {emoji} はパネル内に見つかりません。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # メッセージを取得してエンベッドを更新
        channel_id = panel_data["channel_id"]
        message = await self.get_or_fetch_message(channel_id, panel_id)

        if not message:
            await interaction.followup.send("パネルメッセージが見つかりませんでした。削除された可能性があります。", ephemeral=True)
            return

        # パネルからロールを削除
        del panel_data["roles"][emoji]
        self._save_panels()

        # リアクションを削除
        try:
            await message.clear_reaction(emoji)
        except discord.HTTPException:
            pass  # リアクションが既に削除されている場合は無視

        # エンベッドを更新
        embed = message.embeds[0]
        role_text = ""
        for e, r_data in panel_data["roles"].items():
            desc = f" - {r_data['description']}" if r_data['description'] else ""
            role_text += f"{e} <@&{r_data['role_id']}>{desc}\n"

        new_description = panel_data["description"]
        if role_text:
            new_description += "\n\n" + role_text

        embed.description = new_description
        await message.edit(embed=embed)

        await interaction.followup.send(
            f"絵文字 {emoji} に関連付けられたロールがパネルから削除されました！\n"
            f"パネルの表示とリアクションが更新されています。",
            ephemeral=True
        )

    @role_panel_group.command(name="delete", description="ロールパネルを削除します")
    @app_commands.describe(panel_id="削除するロールパネルのメッセージID")
    @app_commands.default_permissions(administrator=True)
    async def delete_panel(self, interaction: discord.Interaction, panel_id: str):
        """ロールパネルを完全に削除する"""
        try:
            panel_id = int(panel_id)
        except ValueError:
            await interaction.response.send_message("無効なパネルIDです。数字のみを入力してください。パネルIDは `/role-panel list` で確認できます。", ephemeral=True)
            return

        if panel_id not in self.panels:
            await interaction.response.send_message(f"ID: `{panel_id}` のパネルが見つかりません。\nパネル一覧は `/role-panel list` で確認してください。", ephemeral=True)
            return

        if interaction.guild_id != self.panels[panel_id]["guild_id"]:
            await interaction.response.send_message("このパネルは他のサーバーに属しています。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # メッセージを削除
        channel_id = self.panels[panel_id]["channel_id"]
        message = await self.get_or_fetch_message(channel_id, panel_id)

        if message:
            try:
                await message.delete()
            except discord.HTTPException:
                await interaction.followup.send("メッセージの削除に失敗しましたが、パネル設定は削除されます。", ephemeral=True)

        # パネルデータを削除
        del self.panels[panel_id]
        self._save_panels()

        await interaction.followup.send(f"ID: `{panel_id}` のロールパネルが削除されました。\n他のパネル管理には `/role-panel list` コマンドをご利用ください。", ephemeral=True)

    @role_panel_group.command(name="list", description="サーバー内のすべてのロールパネルを表示します")
    @app_commands.default_permissions(administrator=True)
    async def list_panels(self, interaction: discord.Interaction):
        """サーバー内のすべてのロールパネルを表示"""
        if not self.panels:
            await interaction.response.send_message("このサーバーにはロールパネルが作成されていません。", ephemeral=True)
            return

        embed = discord.Embed(
            title="ロールパネル一覧",
            color=discord.Color.blue()
        )

        for panel_id, panel_data in self.panels.items():
            if panel_data.get("guild_id") != interaction.guild_id:
                continue

            channel = self.bot.get_channel(panel_data["channel_id"])
            channel_mention = f"<# {panel_data['channel_id']}>" if channel else f"ID: {panel_data['channel_id']}"

            role_count = len(panel_data["roles"])
            value = f"チャンネル: {channel_mention}\nロール数: {role_count}\nパネルID: `{panel_id}`"
            embed.add_field(
                name=panel_data["title"],
                value=value,
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @role_panel_group.command(name="refresh", description="ロールパネルを再読み込みして更新します")
    @app_commands.describe(panel_id="更新するロールパネルのメッセージID")
    @app_commands.default_permissions(administrator=True)
    async def refresh_panel(self, interaction: discord.Interaction, panel_id: str):
        """ロールパネルを再読み込みして更新する"""
        try:
            panel_id = int(panel_id)
        except ValueError:
            await interaction.response.send_message("無効なパネルIDです。数字のみを入力してください。パネルIDは `/role-panel list` で確認できます。", ephemeral=True)
            return

        if panel_id not in self.panels:
            await interaction.response.send_message(f"ID: `{panel_id}` のパネルが見つかりません。\nパネル一覧は `/role-panel list` で確認してください。", ephemeral=True)
            return

        if interaction.guild_id != self.panels[panel_id]["guild_id"]:
            await interaction.response.send_message("このパネルは他のサーバーに属しています。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        panel_data = self.panels[panel_id]
        channel_id = panel_data["channel_id"]

        message = await self.get_or_fetch_message(channel_id, panel_id)
        if not message:
            await interaction.followup.send("パネルメッセージが見つかりませんでした。削除された可能性があります。", ephemeral=True)
            return

        # エンベッドを更新
        embed = discord.Embed(
            title=panel_data["title"],
            description=panel_data["description"],
            color=discord.Color.blue()
        )

        role_text = ""
        for emoji, role_data in panel_data["roles"].items():
            desc = f" - {role_data['description']}" if role_data['description'] else ""
            role_text += f"{emoji} <@&{role_data['role_id']}>{desc}\n"

        if role_text:
            embed.description += "\n\n" + role_text

        embed.set_footer(text="リアクションをクリックしてロールを取得できます")
        await message.edit(embed=embed)

        # すべてのリアクションを再追加
        try:
            await message.clear_reactions()
            for emoji in panel_data["roles"].keys():
                await message.add_reaction(emoji)
        except discord.HTTPException as e:
            await interaction.followup.send(f"リアクションの更新中にエラーが発生しました: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"ロールパネル (ID: `{panel_id}`) が正常に更新されました！\nパネル内ロール情報とリアクションが最新の状態に同期されました。", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """ユーザーがリアクションを追加したときの処理"""
        # ボット自身のリアクションは無視
        if payload.user_id == self.bot.user.id:
            return

        panel_id = payload.message_id
        if panel_id not in self.panels:
            return

        # 絵文字が Unicode か カスタム絵文字か確認
        emoji = payload.emoji.name
        if payload.emoji.id:
            emoji = f"<:{payload.emoji.name}:{payload.emoji.id}>"

        panel_data = self.panels[panel_id]
        if emoji not in panel_data["roles"]:
            return

        role_id = panel_data["roles"][emoji]["role_id"]
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException as e:
                logger.error("Failed to fetch member: %s", e)
                return

        role = guild.get_role(role_id)
        if not role:
            return

        # ロールを付与
        try:
            await member.add_roles(role, reason="ロールパネルからの自動ロール付与")
        except discord.HTTPException as e:
            logger.error("Failed to add role: %s", e)
            return

        # DMでフィードバックを送る (任意)
        try:
            await member.send(f"**{guild.name}** サーバーで **{role.name}** ロールを取得しました！")
        except discord.HTTPException:
            pass  # DMが無効になっている場合は無視


    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """ユーザーがリアクションを削除したときの処理"""
        # ボット自身のリアクションは無視
        if payload.user_id == self.bot.user.id:
            return

        panel_id = payload.message_id
        if panel_id not in self.panels:
            return

        # 絵文字が Unicode か カスタム絵文字か確認
        emoji = payload.emoji.name
        if payload.emoji.id:
            emoji = f"<:{payload.emoji.name}:{payload.emoji.id}>"

        panel_data = self.panels[panel_id]
        if emoji not in panel_data["roles"]:
            return

        role_id = panel_data["roles"][emoji]["role_id"]
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException as e:
                logger.error("Failed to fetch member: %s", e)
                return

        role = guild.get_role(role_id)
        if not role:
            return

        # ロールを削除
        try:
            await member.remove_roles(role, reason="ロールパネルからの自動ロール削除")
        except discord.HTTPException as e:
            logger.error("Failed to remove role: %s", e)
            return

        # DMでフィードバックを送る (任意)
        try:
            await member.send(f"**{guild.name}** サーバーで **{role.name}** ロールを削除しました。")
        except discord.HTTPException:
            pass  # DMが無効になっている場合は無視

async def setup(bot):
    await bot.add_cog(RolePanel(bot))
