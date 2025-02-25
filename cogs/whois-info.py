from discord.ext import commands
import discord
import whois

class Whois(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="whois", description="ドメインのwhois情報を返します")
    async def whois(self, interaction: discord.Interaction, domain: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            domain_info = whois.whois(domain)
            embed = discord.Embed(
                title=f"Whois情報: {domain}",
                color=discord.Color.blue()
            )

            fields = {
                "Domain Name": domain_info.domain_name,
                "Registrar": domain_info.registrar,
                "Creation Date": domain_info.creation_date,
                "Expiration Date": domain_info.expiration_date,
                "Name Servers": domain_info.name_servers
            }

            for key, value in fields.items():
                if value:
                    embed.add_field(name=key, value=str(value), inline=False)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Whois(bot))