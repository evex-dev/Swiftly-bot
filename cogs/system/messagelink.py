import discord
from discord.ext import commands
import re

class DeleteButtonView(discord.ui.View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="削除", style=discord.ButtonStyle.danger, custom_id="delete_embed_button")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class MessageLink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(message.author.id):
            return

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
                view = DeleteButtonView()
                await message.channel.send(embed=embed, view=view)
            except Exception as e:
                print(f"Error fetching message: {e}")

async def setup(bot):
    await bot.add_cog(MessageLink(bot))