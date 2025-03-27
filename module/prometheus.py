import discord
from discord.ext import commands, tasks
from prometheus_client import Counter, Gauge, start_http_server

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

        self._unique_users_set = set()

        # Start Prometheus HTTP server on port 8000
        start_http_server(8000)

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

        # Update unique user gauge if necessary
        if user_id not in self._unique_users_set:
            self._unique_users_set.add(user_id)
            self.unique_users.set(len(self._unique_users_set))

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if not ctx.command:
            return

        command_name = ctx.command.qualified_name
        # Increment error counter for the command
        self.error_count.labels(command_name=command_name).inc()

    @tasks.loop(seconds=60)
    async def update_gauges(self):
        # Update server count gauge every 60 seconds
        self.server_count.set(len(self.bot.guilds))

    @update_gauges.before_loop
    async def before_update_gauges(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(PrometheusCog(bot))