import discord
from discord.ext import commands, tasks
import json
import os

class LatencyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.latency_file = "data/latency.json"
        self.update_latency.start()

    def cog_unload(self):
        self.update_latency.cancel()

    @tasks.loop(minutes=1)
    async def update_latency(self):
        latency = round(self.bot.latency * 1000, 2)  # Convert to milliseconds
        data = {"latency_ms": latency}

        os.makedirs(os.path.dirname(self.latency_file), exist_ok=True)
        with open(self.latency_file, "w") as f:
            json.dump(data, f, indent=4)

    @update_latency.before_loop
    async def before_update_latency(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(LatencyCog(bot))