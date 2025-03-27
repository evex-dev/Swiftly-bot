import discord
from discord.ext import commands, tasks
from prometheus_client import Counter, Gauge, start_http_server
import json
import os

class PrometheusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Prometheus metrics
        self.command_count = Counter(
            'discord_bot_command_executions_total',
            'Total number of executed commands',
            ['command_name']
        )
        self.user_command_count = Counter(
            'discord_bot_user_commands_total',
            'Total number of commands executed per user',
            ['user_id']
        )
        self.error_count = Counter(
            'discord_bot_command_errors_total',
            'Total number of command errors',
            ['command_name']
        )
        self.server_count = Gauge(
            'discord_bot_server_count',
            'Number of servers the bot is connected to'
        )
        self.unique_users = Gauge(
            'discord_bot_unique_users',
            'Number of unique users who have executed commands'
        )
        self.message_count = Counter(
            'discord_bot_messages_received_total',
            'Total number of messages received'
        )
        self.vc_join_count = Counter(
            'discord_bot_vc_joins_total',
            'Total number of voice channel joins',
            ['user_id']
        )

        # Start Prometheus HTTP server on port 8000
        start_http_server(8491)

        # Task to update gauges periodically
        self.update_gauges.start()

    def cog_unload(self):
        self.update_gauges.cancel()

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        if not ctx.command:
            return

        command_name = ctx.command.qualified_name
        # Increment command execution counter per command
        self.command_count.labels(command_name=command_name).inc()

        # Track per-user command usage
        user_id = str(ctx.author.id)
        self.user_command_count.labels(user_id=user_id).inc()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if not ctx.command:
            return

        command_name = ctx.command.qualified_name
        # Increment error counter for the command
        self.error_count.labels(command_name=command_name).inc()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Increment message received counter
        if not message.author.bot:  # Ignore bot messages
            self.message_count.inc()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Check if the user joined a voice channel
        if before.channel is None and after.channel is not None:
            user_id = str(member.id)
            self.vc_join_count.labels(user_id=user_id).inc()

    @tasks.loop(seconds=60)
    async def update_gauges(self):
        # Update server count gauge every 60 seconds
        self.server_count.set(len(self.bot.guilds))

        # Update unique user count from JSON file
        user_count = self.get_unique_user_count()
        self.unique_users.set(user_count)

    @update_gauges.before_loop
    async def before_update_gauges(self):
        await self.bot.wait_until_ready()

    def get_unique_user_count(self):
        # Load unique user count from JSON file
        try:
            with open('data/user_count.json', 'r') as f:
                data = json.load(f)
                return data.get('total_users', 0)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0

async def setup(bot: commands.Bot):
    await bot.add_cog(PrometheusCog(bot))