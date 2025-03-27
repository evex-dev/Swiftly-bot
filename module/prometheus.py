import discord
from discord.ext import commands, tasks
from prometheus_client import Counter, Gauge, start_http_server
import json
import os
from asyncio import Lock

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
        self.message_count_per_minute = Gauge(
            'discord_bot_messages_received_per_minute',
            'Number of messages received per minute'
        )
        self.vc_join_count = Counter(
            'discord_bot_vc_joins_total',
            'Total number of voice channel joins'
        )
        self.vc_active_count = Gauge(
            'discord_bot_vc_active_count',
            'Number of active voice channels the bot is currently in'
        )

        # Temporary message counter
        self._message_count_temp = 0
        self._message_count_lock = Lock()

        # Track active voice channels
        self._active_vcs = set()

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
        # Increment temporary message counter
        if not message.author.bot:  # Ignore bot messages
            async with self._message_count_lock:
                self._message_count_temp += 1

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Check if the user joined a voice channel
        if before.channel is None and after.channel is not None:
            self.vc_join_count.inc()

        # Check if the bot joined or left a voice channel
        bot_id = self.bot.user.id
        if member.id == bot_id:
            if before.channel is None and after.channel is not None:
                self._active_vcs.add(after.channel.id)
            elif before.channel is not None and after.channel is None:
                self._active_vcs.discard(before.channel.id)

            # Update the active VC count gauge
            self.vc_active_count.set(len(self._active_vcs))

    @tasks.loop(seconds=60)
    async def update_gauges(self):
        # Update server count gauge every 60 seconds
        self.server_count.set(len(self.bot.guilds))

        # Update unique user count from JSON file
        user_count = self.get_unique_user_count()
        self.unique_users.set(user_count)

        # Update message count per minute
        async with self._message_count_lock:
            self.message_count_per_minute.set(self._message_count_temp)
            self._message_count_temp = 0

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
