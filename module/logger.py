import logging

import discord
from discord.ext import commands

class LoggingCog(commands.Cog):
    """Botの動作をログ出力するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("bot")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.logger.info("Bot is ready. Logged in as %s", self.bot.user)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.info("Joined guild: %s (ID: %s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.logger.info("Removed from guild: %s (ID: %s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        self.logger.info("Member joined: %s (ID: %s) in guild: %s", member.name, member.id, member.guild.name)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        self.logger.info("Member left: %s (ID: %s) from guild: %s", member.name, member.id, member.guild.name)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        self.logger.info("Command executed: %s by %s (ID: %s) in guild: %s", ctx.command, ctx.author.name, ctx.author.id, guild_name)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        self.logger.error("Command error: %s by %s (ID: %s) in guild: %s - %s", ctx.command, ctx.author.name, ctx.author.id, guild_name, error)

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command) -> None:
        guild_name = interaction.guild.name if interaction.guild else "DM"
        self.logger.info("Command executed: %s by %s (ID: %s) in guild: %s", command.name, interaction.user.name, interaction.user.id, guild_name)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        guild_name = interaction.guild.name if interaction.guild else "DM"
        command_name = interaction.command.name if interaction.command else "Unknown"
        self.logger.error("Command error: %s by %s (ID: %s) in guild: %s - %s", command_name, interaction.user.name, interaction.user.id, guild_name, error)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))
