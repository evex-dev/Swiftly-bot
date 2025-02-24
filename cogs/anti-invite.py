# coding: utf-8
import discord
from discord.ext import commands
import sqlite3
import os
import asyncio  # 追加: asyncioをインポート

class AntiInvite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Ensure the data directory exists
        data_dir = os.path.join(os.getcwd(), 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        db_path = os.path.join(data_dir, 'anti_invite.db')
        self.db = sqlite3.connect(db_path)
        cursor = self.db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                anti_invite_enabled INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.db.commit()

    def set_setting(self, guild_id: int, enabled: bool):
        cursor = self.db.cursor()
        cursor.execute("SELECT anti_invite_enabled FROM settings WHERE guild_id = ?", (guild_id,))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO settings(guild_id, anti_invite_enabled) VALUES(?,?)", (guild_id, int(enabled)))
        else:
            cursor.execute("UPDATE settings SET anti_invite_enabled = ? WHERE guild_id = ?", (int(enabled), guild_id))
        self.db.commit()

    def get_setting(self, guild_id: int) -> bool:
        cursor = self.db.cursor()
        cursor.execute("SELECT anti_invite_enabled FROM settings WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else False

    # アプリケーションコマンドとしての設定コマンドに変更
    @discord.app_commands.command(name="anti-invite", description="Discord招待リンクの自動削除を設定します。（デフォルトはdisable）")
    @discord.app_commands.describe(action="設定する値（enable または disable）")
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="enable", value="enable"),
        discord.app_commands.Choice(name="disable", value="disable")
    ])
    async def anti_invite(self, interaction: discord.Interaction, action: str):
        if interaction.guild is None:
            await interaction.response.send_message('このコマンドはサーバー内でのみ使用可能です。', ephemeral=True)
            return
        enabled = action.lower() == 'enable'
        self.set_setting(interaction.guild.id, enabled)
        state = '有効' if enabled else '無効'
        embed = discord.Embed(title="Anti-Invite設定", description=f'このサーバーでの招待リンク自動削除は **{state}** になりました。', color=0x00ff00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return
        # サーバーごとにanti-inviteが有効かどうかをチェック
        if self.get_setting(message.guild.id):
            content = message.content.lower()
            if 'discord.gg/' in content or 'discordapp.com/invite/' in content or 'discord.com/invite/' in content:
                try:
                    await message.delete()
                    warning = await message.channel.send("Discord招待リンクは禁止です。メッセージは削除されました。")
                    await asyncio.sleep(5)
                    await warning.delete()
                except discord.errors.Forbidden:
                    pass
                except Exception:
                    pass

def setup(bot):
    bot.add_cog(AntiInvite(bot))
