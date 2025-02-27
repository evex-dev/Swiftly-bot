import discord
from discord import app_commands
import aiohttp
import logging
from discord.ext import commands

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='minecraft', description='Get the status of a Minecraft server')
    async def minecraft(self, interaction: discord.Interaction, address: str):
        await interaction.response.defer(thinking=True)
        url = f'https://api.mcsrvstat.us/3/{address}'
        icon_url = f'https://api.mcsrvstat.us/icon/{address}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    logger.debug(f"Request URL: {url}")
                    logger.debug(f"Response status: {response.status}")
                    if response.status != 200:
                        raise aiohttp.ClientError(f"HTTP Error: {response.status}")
                    data = await response.json()
                    logger.debug(f"Response data: {data}")

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
            logger.error(f"ClientError: {e}")
            await interaction.followup.send(f"Failed to retrieve server status: {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Minecraft(bot))