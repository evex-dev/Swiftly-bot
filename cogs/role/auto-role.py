import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import logging

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'data/autorole.db'
        self._ensure_database()
    
    def _ensure_database(self):
        """データベースとテーブルの存在を確認し、なければ作成する"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS autoroles (
            guild_id INTEGER PRIMARY KEY,
            human_role_id INTEGER,
            bot_role_id INTEGER
        )
        ''')
        conn.commit()
        conn.close()
    
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
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 現在の設定を取得
        cursor.execute("SELECT human_role_id, bot_role_id FROM autoroles WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        
        human_id = human.id if human else (result[0] if result else None)
        bot_id = bot.id if bot else (result[1] if result else None)
        
        # 設定を更新または挿入
        if result:
            cursor.execute(
                "UPDATE autoroles SET human_role_id = ?, bot_role_id = ? WHERE guild_id = ?",
                (human_id, bot_id, guild_id)
            )
        else:
            cursor.execute(
                "INSERT INTO autoroles (guild_id, human_role_id, bot_role_id) VALUES (?, ?, ?)",
                (guild_id, human_id, bot_id)
            )
        
        conn.commit()
        conn.close()
        
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
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """メンバーがサーバーに参加したときに適切なロールを付与"""
        try:
            guild_id = member.guild.id
            
            # Botにロール管理権限があるか確認
            if not member.guild.me.guild_permissions.manage_roles:
                logging.warning(f"サーバー {member.guild.name} でロール管理権限がありません")
                return
                
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT human_role_id, bot_role_id FROM autoroles WHERE guild_id = ?", (guild_id,))
            result = cursor.fetchone()
            conn.close()
            
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