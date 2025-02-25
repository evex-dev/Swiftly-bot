import discord
from discord.ext import commands

class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="avatar", description="ユーザーのアイコンを表示します")
    async def avatar(self, interaction: discord.Interaction, user: discord.User) -> None:
        if not user.avatar:
            await interaction.response.send_message("アイコンが設定されてないよ")
        else:
            embed = discord.Embed(
                title=f"{user.name}のアイコン",
                color=discord.Color.blue()
            )
            embed.set_image(url=user.avatar.url)
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Avatar(bot))
