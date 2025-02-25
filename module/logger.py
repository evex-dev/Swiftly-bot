import logging

import discord
from discord.ext import commands

class LoggingCog(commands.Cog):
    """Botの動作をログ出力するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # ロガーを取得
        self.logger = logging.getLogger('bot')
        # コマンド完了イベントと失敗イベントのリスナーを明示的に追加
        self.bot.add_listener(self.on_command_completion, "on_command_completion")
        self.bot.add_listener(self.on_command_error, "on_command_error")
        # スラッシュコマンド完了イベントとエラーイベントのリスナーを明示的に追加
        self.bot.add_listener(self.on_app_command_completion, "on_app_command_completion")
        self.bot.add_listener(self.on_app_command_error, "on_app_command_error")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.logger.info(f"Bot is ready. Logged in as {self.bot.user}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.logger.info(f"Removed from guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        self.logger.info(f"Member joined: {member.name} (ID: {member.id}) in guild: {member.guild.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        self.logger.info(f"Member left: {member.name} (ID: {member.id}) from guild: {member.guild.name}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        self.logger.info(f"Command executed: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {guild_name}")
        # デバッグ用に標準出力にも出力
        print(f"Command executed: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {guild_name}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        guild_name = ctx.guild.name if ctx.guild else "DM"
        self.logger.error(f"Command error: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {guild_name} - {error}")
        # デバッグ用に標準出力にも出力
        print(f"Command error: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {guild_name} - {error}")
    
    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command) -> None:
        guild_name = interaction.guild.name if interaction.guild else "DM"
        self.logger.info(f"Command executed: {command.name} by {interaction.user.name} (ID: {interaction.user.id}) in guild: {guild_name}")
        # デバッグ用に標準出力にも出力
        print(f"Command executed: {command.name} by {interaction.user.name} (ID: {interaction.user.id}) in guild: {guild_name}")
    
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        guild_name = interaction.guild.name if interaction.guild else "DM"
        command_name = interaction.command.name if interaction.command else "Unknown"
        self.logger.error(f"Command error: {command_name} by {interaction.user.name} (ID: {interaction.user.id}) in guild: {guild_name} - {error}")
        # デバッグ用に標準出力にも出力
        print(f"Command error: {command_name} by {interaction.user.name} (ID: {interaction.user.id}) in guild: {guild_name} - {error}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))