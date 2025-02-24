# coding: utf-8
import discord
from discord.ext import commands
import sqlite3
import os
import asyncio
import re
import aiohttp
from urllib.parse import urlparse

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
        
        # 新規: DB for whitelist（ホワリス）
        db_exempt_path = os.path.join(data_dir, 'anti_invite_exempt.db')
        self.db_exempt = sqlite3.connect(db_exempt_path)
        cursor_exempt = self.db_exempt.cursor()
        cursor_exempt.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                guild_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
        """
        )
        self.db_exempt.commit()

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

    async def contains_invite(self, content: str) -> bool:
        # 直接の招待リンクが含まれているかチェック
        if 'discord.gg/' in content or 'discordapp.com/invite/' in content or 'discord.com/invite/' in content:
            return True
        # メッセージ内のURLを抽出
        urls = re.findall(r'(https?://\S+)', content)
        if not urls:
            return False
        # 既知の短縮URLドメイン一覧
        shorteners = ["x.gd", "bit.ly", "tinyurl.com", "goo.gl", "is.gd", "ow.ly", "buff.ly", "00m.in"]
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.hostname and parsed.hostname.lower() in shorteners:
                    async with aiohttp.ClientSession() as session:
                        try:
                            async with session.head(url, allow_redirects=True, timeout=5) as response:
                                final_url = str(response.url)
                        except Exception:
                            # HEADリクエストが失敗した場合、GETリクエストで試す
                            async with session.get(url, allow_redirects=True, timeout=5) as response:
                                final_url = str(response.url)
                    if 'discord.gg/' in final_url or 'discordapp.com/invite/' in final_url or 'discord.com/invite/' in final_url:
                        return True
            except Exception:
                continue
        return False

    @discord.app_commands.command(name="anti-invite", description="Discord招待リンクの自動削除を設定します。（デフォルトはdisable）")
    @discord.app_commands.describe(action="設定する値（enable または disable）")
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="enable", value="enable"),
        discord.app_commands.Choice(name="disable", value="disable")
    ])
    async def anti_invite(self, interaction: discord.Interaction, action: str):
        # 管理者チェックを追加
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('このコマンドはサーバー管理者のみ実行可能です。', ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message('このコマンドはサーバー内でのみ使用可能です。', ephemeral=True)
            return
        enabled = action.lower() == 'enable'
        self.set_setting(interaction.guild.id, enabled)
        state = '有効' if enabled else '無効'
        embed = discord.Embed(title="Anti-Invite設定", description=f'このサーバーでの招待リンク自動削除は **{state}** になりました。', color=0x00ff00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 新規: ホワリス設定コマンド（禁止対象外のチャンネル設定）
    @discord.app_commands.command(name="anti-invite-setting", description="禁止対象としないチャンネル（ホワリス）を設定します（複数指定可、最大10件）。")
    @discord.app_commands.describe(
        channel_1="指定チャンネル1（任意）",
        channel_2="指定チャンネル2（任意）",
        channel_3="指定チャンネル3（任意）",
        channel_4="指定チャンネル4（任意）",
        channel_5="指定チャンネル5（任意）",
        channel_6="指定チャンネル6（任意）",
        channel_7="指定チャンネル7（任意）",
        channel_8="指定チャンネル8（任意）",
        channel_9="指定チャンネル9（任意）",
        channel_10="指定チャンネル10（任意）"
    )
    async def anti_invite_setting(self, interaction: discord.Interaction, 
                                   channel_1: discord.TextChannel = None,
                                   channel_2: discord.TextChannel = None,
                                   channel_3: discord.TextChannel = None,
                                   channel_4: discord.TextChannel = None,
                                   channel_5: discord.TextChannel = None,
                                   channel_6: discord.TextChannel = None,
                                   channel_7: discord.TextChannel = None,
                                   channel_8: discord.TextChannel = None,
                                   channel_9: discord.TextChannel = None,
                                   channel_10: discord.TextChannel = None):
        # 管理者チェックを追加
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('このコマンドはサーバー管理者のみ実行可能です。', ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message('このコマンドはサーバー内でのみ使用可能です。', ephemeral=True)
            return
        channels = []
        for ch in [channel_1, channel_2, channel_3, channel_4, channel_5, channel_6, channel_7, channel_8, channel_9, channel_10]:
            if ch and ch.guild.id == interaction.guild.id:
                channels.append(ch.id)
        cursor_exempt = self.db_exempt.cursor()
        cursor_exempt.execute("DELETE FROM whitelist WHERE guild_id = ?", (interaction.guild.id,))
        for ch_id in channels:
            cursor_exempt.execute("INSERT INTO whitelist (guild_id, channel_id) VALUES (?, ?)", (interaction.guild.id, ch_id))
        self.db_exempt.commit()
        if channels:
            desc = "以下のチャンネルで招待リンクの自動削除が無効化されました。\n" + "\n".join([f"<#{ch_id}>" for ch_id in channels])
            title = "ホワリス設定完了"
        else:
            desc = "全てのチャンネルの無効化設定を解除しました。"
            title = "ホワリス解除完了"
        embed = discord.Embed(title=title, description=desc, color=0x00ff00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return
        # サーバーごとにanti-inviteが有効かどうかをチェック
        if self.get_setting(message.guild.id):
            cursor_exempt = self.db_exempt.cursor()
            cursor_exempt.execute("SELECT channel_id FROM whitelist WHERE guild_id = ?", (message.guild.id,))
            whitelist_channels = [row[0] for row in cursor_exempt.fetchall()]
            if message.channel.id in whitelist_channels:
                return
            if await self.contains_invite(message.content):
                try:
                    await message.delete()
                    warning = await message.channel.send("Discord招待リンクは禁止です。メッセージは削除されました。")
                    await asyncio.sleep(5)
                    await warning.delete()
                except discord.errors.Forbidden:
                    pass
                except Exception:
                    pass

async def setup(bot):
    await bot.add_cog(AntiInvite(bot))
