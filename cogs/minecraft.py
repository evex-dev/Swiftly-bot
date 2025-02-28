import logging
from datetime import datetime, timedelta
from typing import Final, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS: Final[int] = 30

class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self._last_uses = {}

    def _check_rate_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    @app_commands.command(name='minecraft', description='Get the status of a Minecraft server')
    async def minecraft(self, interaction: discord.Interaction, address: str):
        # レート制限のチェック
        is_limited, remaining = self._check_rate_limit(interaction.user.id)
        if is_limited:
            await interaction.response.send_message(
                f"レート制限中です。{remaining}秒後にお試しください。",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)
        url = f'https://api.mcsrvstat.us/3/{address}'
        icon_url = f'https://api.mcsrvstat.us/icon/{address}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    # レート制限の更新
                    self._last_uses[interaction.user.id] = datetime.now()

                    logger.debug("Request URL: %s", url)
                    logger.debug("Response status: %s", response.status)
                    if response.status != 200:
                        raise aiohttp.ClientError(f"HTTP Error: {response.status}")
                    data = await response.json()
                    logger.debug("Response data: %s", data)

                    if data['online']:
                        embed = discord.Embed(title=f"Server Status for {address}", color=discord.Color.green())
                        embed.set_thumbnail(url=icon_url)
                        embed.add_field(name="IP", value=data.get('ip', 'N/A'), inline=False)
                        embed.add_field(name="Port", value=data.get('port', 'N/A'), inline=False)
                        embed.add_field(name="Version", value=data.get('version', 'N/A'), inline=False)
                        embed.add_field(name="Players Online", value=f"{data['players']['online']}/{data['players']['max']}", inline=False)
                        if 'hostname' in data:
                            embed.add_field(name="Hostname", value=data['hostname'], inline=False)
                        if 'motd' in data:
                            embed.add_field(name="MOTD", value="\n".join(data['motd']['clean']), inline=False)
                        if 'plugins' in data:
                            plugins = ", ".join([plugin['name'] for plugin in data['plugins']])
                            embed.add_field(name="Plugins", value=plugins, inline=False)
                        if 'mods' in data:
                            mods = ", ".join([mod['name'] for mod in data['mods']])
                            embed.add_field(name="Mods", value=mods, inline=False)
                    else:
                        embed = discord.Embed(title=f"Server Status for {address}", color=discord.Color.red())
                        embed.set_thumbnail(url=icon_url)
                        embed.add_field(name="Status", value="Offline", inline=False)

                    await interaction.followup.send(embed=embed)
        except aiohttp.ClientError as e:
            logger.error("ClientError: %s", e)
            await interaction.followup.send(f"Failed to retrieve server status: {e}", ephemeral=True)
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Minecraft(bot))
