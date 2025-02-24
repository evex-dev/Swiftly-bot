import json
import os
import discord
from discord.ext import commands

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="set_prohibited_channel", 
        description="特定のチャンネルでのコマンドの利用を禁止する（チャンネルのIDを指定）"
    )
    async def set_prohibited_channel(self, ctx, channel_id: str):
        # コマンド実行ごとに最新のJSONファイルをロードする
        prohibited_channels = {}
        if os.path.exists("prohibited_channels.json"):
            with open("prohibited_channels.json", "r", encoding="utf-8") as f:
                prohibited_channels = json.load(f)
        
        guild_id = str(ctx.guild.id)

        if guild_id not in prohibited_channels:
            prohibited_channels[guild_id] = []

        if channel_id not in prohibited_channels[guild_id]:
            prohibited_channels[guild_id].append(channel_id)
            await ctx.response.send_message(f"<#{channel_id}> をコマンド実行禁止チャンネルに追加しました。")
        else:
            prohibited_channels[guild_id].remove(channel_id)
            await ctx.response.send_message(f"<#{channel_id}> をコマンド実行禁止チャンネルから削除しました。")

        with open("prohibited_channels.json", "w", encoding="utf-8") as f:
            json.dump(prohibited_channels, f, ensure_ascii=False, indent=4)

async def setup(bot):
    await bot.add_cog(Ping(bot))