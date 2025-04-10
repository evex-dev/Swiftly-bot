import discord
from discord.ext import commands
import re

class MessageLink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # メッセージリンクの正規表現
        link_pattern = r"https://(?:canary\.|ptb\.)?discord\.com/channels/(\d+)/(\d+)/(\d+)"
        match = re.search(link_pattern, message.content)
        if match:
            guild_id, channel_id, message_id = map(int, match.groups())
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    return
                channel = guild.get_channel(channel_id)
                if not channel:
                    return
                target_message = await channel.fetch_message(message_id)
                embed = discord.Embed(
                    description=target_message.content,
                    color=discord.Color.blue()
                )
                embed.set_author(
                    name=target_message.author.display_name,
                    icon_url=target_message.author.avatar.url if target_message.author.avatar else None
                )
                embed.set_footer(
                    text=f"Sent on {target_message.created_at.strftime('%Y-%m-%d %H:%M:%S')} in {guild.name}"
                )
                await message.channel.send(embed=embed)
            except Exception as e:
                print(f"Error fetching message: {e}")

async def setup(bot):
    await bot.add_cog(MessageLink(bot))