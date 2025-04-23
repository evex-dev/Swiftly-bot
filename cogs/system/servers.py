import json
import os
from pathlib import Path
from discord.ext import commands, tasks

class ServerCountCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.server_count_file = Path("data/server_count.json")
        self.update_server_count.start()

    def cog_unload(self):
        self.update_server_count.cancel()

    @tasks.loop(minutes=1)
    async def update_server_count(self):
        """定期的にサーバー数をJSONファイルに書き込む"""
        server_count = len(self.bot.guilds)
        data = {"server_count": server_count}

        # ディレクトリが存在しない場合は作成
        if not self.server_count_file.parent.exists():
            os.makedirs(self.server_count_file.parent)

        # JSONファイルにサーバー数を書き込む
        with open(self.server_count_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @update_server_count.before_loop
    async def before_update_server_count(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerCountCog(bot))