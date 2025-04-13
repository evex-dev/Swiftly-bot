import discord
from discord import app_commands
from discord.ext import commands
import asyncpg
import os
import logging
from dotenv import load_dotenv

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_pool: asyncpg.Pool | None = None

    async def cog_load(self):
        """Cogがロードされたときにデータベース接続を初期化"""
        load_dotenv()
        self.db_pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database="autorole"
        )
        await self._ensure_database()

    async def cog_unload(self):
        """Cogがアンロードされたときにデータベース接続を閉じる"""
        if self.db_pool:
            await self.db_pool.close()

    async def _ensure_database(self):
        """データベースとテーブルの存在を確認し、なければ作成する"""
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS autoroles (
                guild_id BIGINT PRIMARY KEY,
                human_role_id BIGINT,
                bot_role_id BIGINT
            )
            ''')

    async def _check_admin_permission(self, interaction: discord.Interaction) -> bool:
        """ユーザーが管理者権限を持っているかチェックする"""
        if not interaction.guild:
            await interaction.response.send_message("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            return False
            
        if interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id:
            return True
            
        await interaction.response.send_message("このコマンドを使用するには管理者権限が必要です。", ephemeral=True)
        return False
    
    @app_commands.command(name="auto-role", description="サーバー参加時に自動的に付与するロールを設定します")
    @app_commands.describe(
        human="人間のユーザーに付与するロール",
        bot="ボットに付与するロール"
    )
    @app_commands.default_permissions(administrator=True)
    async def auto_role(self, interaction: discord.Interaction, human: discord.Role = None, bot: discord.Role = None):
        """サーバー参加時に自動的に付与するロールを設定します"""
        # 管理者権限チェック
        if not await self._check_admin_permission(interaction):
            return
            
        if not human and not bot:
            await interaction.response.send_message("少なくとも一つのロールを指定してください。", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        
        # ロールの管理権限チェック
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("Botにロールを管理する権限がありません。必要な権限を付与してください。", ephemeral=True)
            return
            
        # 指定されたロールがBotよりも上位ではないかチェック
        bot_top_role = interaction.guild.me.top_role
        if (human and human.position >= bot_top_role.position) or (bot and bot.position >= bot_top_role.position):
            await interaction.response.send_message("指定されたロールがBotの最上位ロールよりも上位にあるため、自動付与できません。", ephemeral=True)
            return
        
        async with self.db_pool.acquire() as conn:
            # 現在の設定を取得
            result = await conn.fetchrow("SELECT human_role_id, bot_role_id FROM autoroles WHERE guild_id = $1", guild_id)
            
            human_id = human.id if human else (result["human_role_id"] if result else None)
            bot_id = bot.id if bot else (result["bot_role_id"] if result else None)

            # 設定を更新または挿入
            if result:
                await conn.execute(
                    "UPDATE autoroles SET human_role_id = $1, bot_role_id = $2 WHERE guild_id = $3",
                    human_id, bot_id, guild_id
                )
            else:
                await conn.execute(
                    "INSERT INTO autoroles (guild_id, human_role_id, bot_role_id) VALUES ($1, $2, $3)",
                    guild_id, human_id, bot_id
                )
        
        # 応答メッセージの作成
        response = []
        if human:
            response.append(f"人間ユーザーへの自動ロール: {human.mention}")
        if bot:
            response.append(f"ボットへの自動ロール: {bot.mention}")
        
        await interaction.response.send_message(
            f"自動ロール設定を更新しました:\n" + "\n".join(response),
            ephemeral=True
        )
    
    @app_commands.command(name="auto-role-disable", description="自動ロール付与機能を無効にします")
    @app_commands.default_permissions(administrator=True)
    async def auto_role_disable(self, interaction: discord.Interaction):
        """サーバーの自動ロール付与機能を無効にします"""
        # 管理者権限チェック
        if not await self._check_admin_permission(interaction):
            return
            
        guild_id = interaction.guild.id
        
        async with self.db_pool.acquire() as conn:
            # 現在の設定を確認
            result = await conn.fetchrow("SELECT * FROM autoroles WHERE guild_id = $1", guild_id)
            if not result:
                await interaction.response.send_message("このサーバーでは自動ロール機能は既に設定されていません。", ephemeral=True)
                return
            
            # 設定を削除
            await conn.execute("DELETE FROM autoroles WHERE guild_id = $1", guild_id)
        
        await interaction.response.send_message("自動ロール機能を無効化しました。新しく参加するメンバーにはロールが自動付与されなくなります。", ephemeral=True)

    @app_commands.command(name="auto-role-settings", description="現在の自動ロール設定を表示します")
    @app_commands.default_permissions(administrator=True)
    async def auto_role_settings(self, interaction: discord.Interaction):
        """現在のサーバーの自動ロール設定を表示します"""
        # 管理者権限チェック
        if not await self._check_admin_permission(interaction):
            return
            
        guild_id = interaction.guild.id
        
        async with self.db_pool.acquire() as conn:
            # 現在の設定を取得
            result = await conn.fetchrow("SELECT human_role_id, bot_role_id FROM autoroles WHERE guild_id = $1", guild_id)
        
        if not result:
            await interaction.response.send_message("このサーバーでは自動ロール機能は設定されていません。", ephemeral=True)
            return
            
        human_role_id, bot_role_id = result
        
        # レスポンスメッセージの作成
        embed = discord.Embed(
            title="自動ロール設定",
            description="サーバーへの新規参加者に自動的に付与されるロール設定です",
            color=discord.Color.blue()
        )
        
        if human_role_id:
            human_role = interaction.guild.get_role(human_role_id)
            human_status = f"{human_role.mention}" if human_role else "設定されたロールが見つかりません"
            embed.add_field(name="人間ユーザー向けロール", value=human_status, inline=False)
        else:
            embed.add_field(name="人間ユーザー向けロール", value="設定されていません", inline=False)
            
        if bot_role_id:
            bot_role = interaction.guild.get_role(bot_role_id)
            bot_status = f"{bot_role.mention}" if bot_role else "設定されたロールが見つかりません"
            embed.add_field(name="ボット向けロール", value=bot_status, inline=False)
        else:
            embed.add_field(name="ボット向けロール", value="設定されていません", inline=False)
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """メンバーがサーバーに参加したときに適切なロールを付与"""
        try:
            guild_id = member.guild.id
            
            # Botにロール管理権限があるか確認
            if not member.guild.me.guild_permissions.manage_roles:
                logging.warning(f"サーバー {member.guild.name} でロール管理権限がありません")
                return
                
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchrow("SELECT human_role_id, bot_role_id FROM autoroles WHERE guild_id = $1", guild_id)
            
            if not result:
                return
            
            human_role_id, bot_role_id = result
            
            if member.bot and bot_role_id:
                role = member.guild.get_role(bot_role_id)
                if role and role.position < member.guild.me.top_role.position:
                    await member.add_roles(role, reason="自動ロール付与: ボット")
                else:
                    logging.warning(f"サーバー {member.guild.name} でボットロール付与に失敗: ロールが見つからないか、権限不足")
            elif not member.bot and human_role_id:
                role = member.guild.get_role(human_role_id)
                if role and role.position < member.guild.me.top_role.position:
                    await member.add_roles(role, reason="自動ロール付与: 人間")
                else:
                    logging.warning(f"サーバー {member.guild.name} で人間ロール付与に失敗: ロールが見つからないか、権限不足")
        except Exception as e:
            logging.error(f"自動ロール付与中にエラーが発生しました: {e}")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))