import os
import sqlite3
import discord
from discord.ext import commands

# DBの初期化
DB_PATH = "prohibited_channels.db"
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prohibited_channels (
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            PRIMARY KEY (guild_id, channel_id)
        )
    """)
    conn.commit()

class Prohibited(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="set_prohibited_channel", 
        description="特定のチャンネルでのコマンドの利用を禁止する"
    )
    async def set_prohibited_channel(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        channel_id = str(channel.id)
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM prohibited_channels WHERE guild_id = ? AND channel_id = ?", 
                (guild_id, channel_id)
            )
            exists = cursor.fetchone()
            if not exists:
                cursor.execute(
                    "INSERT INTO prohibited_channels (guild_id, channel_id) VALUES (?, ?)",
                    (guild_id, channel_id)
                )
                message = f"{channel.mention} をコマンド実行禁止チャンネルに追加しました。"
            else:
                cursor.execute(
                    "DELETE FROM prohibited_channels WHERE guild_id = ? AND channel_id = ?",
                    (guild_id, channel_id)
                )
                message = f"{channel.mention} をコマンド実行禁止チャンネルから削除しました。"
            conn.commit()
        await ctx.response.send_message(message)

async def setup(bot):
    await bot.add_cog(Prohibited(bot))