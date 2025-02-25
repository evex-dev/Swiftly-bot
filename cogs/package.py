import aiohttp
import discord
from discord.ext import commands

class PackageSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="search_package", description="npmまたはpipのパッケージを検索します")
    async def search_package(self, interaction: discord.Interaction, manager: str, package: str) -> None:
        await interaction.response.defer(thinking=True)
        if manager not in ["npm", "pip"]:
            await interaction.followup.send("無効なパッケージマネージャーです。'npm'または'pip'を使用してください。", ephemeral=True)
            return

        url = f"https://registry.npmjs.org/{package}" if manager == "npm" else f"https://pypi.org/pypi/{package}/json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if manager == "npm":
                        name = data.get("name")
                        version = data.get("dist-tags", {}).get("latest")
                        description = data.get("description")
                        homepage = data.get("homepage")
                    else:
                        info = data.get("info", {})
                        name = info.get("name")
                        version = info.get("version")
                        description = info.get("summary")
                        homepage = info.get("home_page")

                    embed = discord.Embed(
                        title=f"{name} ({manager})",
                        description=description,
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="バージョン", value=version, inline=True)
                    embed.add_field(name="ホームページ", value=homepage, inline=True)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"{manager}でパッケージ'{package}'が見つかりませんでした。", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PackageSearch(bot))
