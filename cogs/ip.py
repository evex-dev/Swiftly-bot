import discord
from discord.ext import commands
import aiohttp
import asyncio
import json


class IP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="ip", description="IP情報を取得します")
    async def ip(self, interaction: discord.Interaction, ip_addr: str) -> None:
        await interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://ip-api.com/json/{ip_addr}") as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if data.get("status") == "success":
                                embed = discord.Embed(
                                    title="IP Information",
                                    description=f"IP: {ip_addr}",
                                    color=discord.Color.blue()
                                )
                                fields = [
                                    ("Country", f"{data.get('country')} ({data.get('countryCode')})"),
                                    ("Region", f"{data.get('regionName')} ({data.get('region')})"),
                                    ("City", data.get("city")),
                                    ("ZIP Code", data.get("zip")),
                                    ("Coordinates", f"Lat: {data.get('lat')}, Lon: {data.get('lon')}"),
                                    ("Timezone", data.get("timezone")),
                                    ("ISP", data.get("isp")),
                                    ("Organization", data.get("org")),
                                    ("AS", data.get("as"))
                                ]
                                for name, value in fields:
                                    if value and value != "None (None)":
                                        embed.add_field(name=name, value=value, inline=True)
                                await interaction.followup.send(embed=embed)
                            else:
                                await interaction.followup.send("IPアドレスの情報取得に失敗しました。", ephemeral=True)
                        except (json.JSONDecodeError, aiohttp.ContentTypeError):
                            await interaction.followup.send("JSONの解析に失敗しました。", ephemeral=True)
                    else:
                        await interaction.followup.send(f"APIエラー: ステータスコード {response.status}", ephemeral=True)
        except aiohttp.ClientError as e:
            await interaction.followup.send(f"ネットワークエラーが発生しました: {e}", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("リクエストがタイムアウトしました。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(IP(bot))
