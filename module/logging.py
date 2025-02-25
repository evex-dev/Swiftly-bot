import discord
from discord.ext import commands

class LoggingCog(commands.Cog):
    """Botの動作をログ出力するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        print(f"Bot is ready. Logged in as {self.bot.user}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        print(f"Joined guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        print(f"Removed from guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        print(f"Member joined: {member.name} (ID: {member.id}) in guild: {member.guild.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        print(f"Member left: {member.name} (ID: {member.id}) from guild: {member.guild.name}")

    # これは無くても良いが、一応。
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return
        print(f"Message from {message.author.name} (ID: {message.author.id}) in guild: {message.guild.name} - {message.content}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        print(f"Command executed: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {ctx.guild.name}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        print(f"Command error: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {ctx.guild.name} - {error}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))