import discord
from discord.ext import commands

class MinecraftSkin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="skin", description="Minecraftのスキンを取得します。Java版のみ。")
    async def skin(self, interaction: discord.Interaction, username: str) -> None:
        skin_url = f"https://mineskin.eu/armor/body/{username}/100.png"

        embed = discord.Embed(
            title=f"{username}'s Minecraft Skin",
            description=f"Here is the skin for {username}",
            color=discord.Color.blue()
        )
        embed.set_image(url=skin_url)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(MinecraftSkin(bot))
