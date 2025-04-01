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
    
    @app_commands.command(name="auto-role", description="サーバー参加時に自動的に付与するロールを設定します")
    @app_commands.describe(
        human="人間のユーザーに付与するロール",
        bot="ボットに付与するロール"
    )
    @app_commands.default_permissions(administrator=True)
    async def auto_role(self, interaction: discord.Interaction, human: discord.Role = None, bot: discord.Role = None):
        """サーバー参加時に自動的に付与するロールを設定します"""
        if not human and not bot:
            await interaction.response.send_message("少なくとも一つのロールを指定してください。", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        
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
                if role:
                    await member.add_roles(role, reason="自動ロール付与: ボット")
            elif not member.bot and human_role_id:
                role = member.guild.get_role(human_role_id)
                if role:
                    await member.add_roles(role, reason="自動ロール付与: 人間")
        except Exception as e:
            logging.error(f"自動ロール付与中にエラーが発生しました: {e}")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))