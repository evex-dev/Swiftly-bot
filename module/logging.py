import discord
from discord.ext import commands
import logging

# Set up logging
logging.basicConfig(filename='logging.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

class LoggingCog(commands.Cog):
    """Botの動作をログ出力するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logging.info(f"Bot is ready. Logged in as {self.bot.user}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        logging.info(f"Joined guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logging.info(f"Removed from guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        logging.info(f"Member joined: {member.name} (ID: {member.id}) in guild: {member.guild.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        logging.info(f"Member left: {member.name} (ID: {member.id}) from guild: {member.guild.name}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        logging.info(f"Command executed: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {guild_name}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        logging.error(f"Command error: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {guild_name} - {error}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))