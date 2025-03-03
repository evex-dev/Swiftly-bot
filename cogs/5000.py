import aiohttp
import discord
import io
from typing import Final
from discord.ext import commands


API_URL: Final[str] = "https://gsapi.cbrx.io/image"
ERROR_MESSAGE: Final[str] = "画像の生成に失敗しました。"
TITLE: Final[str] = "5000兆円ジェネレーター"
DESCRIPTION: Final[str] = "生成された画像はこちらです。"
FILE_NAME: Final[str] = "5000yen.jpeg"


class Yen5000(commands.Cog):
    """5000兆円ジェネレーター"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    @discord.app_commands.command(name="5000", description="5000兆円ジェネレーター")
    async def yen5000(self, interaction: discord.Interaction, top: str, bottom: str) -> None:
        await interaction.response.defer(thinking=True)

        try:
            if not self._session:
                self._session = aiohttp.ClientSession()

            params = {"top": top, "bottom": bottom}
            async with self._session.get(API_URL, params=params) as response:
                if response.status != 200:
                    await interaction.followup.send(
                        f"{ERROR_MESSAGE} (Status: {response.status})",
                        ephemeral=True
                    )
                    return

                image_data = await response.read()
                file = discord.File(
                    fp=io.BytesIO(image_data),
                    filename=FILE_NAME
                )

                embed = discord.Embed(
                    title=TITLE,
                    description=DESCRIPTION,
                    color=discord.Color.green()
                )
                embed.set_image(url=f"attachment://{FILE_NAME}")

                await interaction.followup.send(embed=embed, file=file)

        except aiohttp.ClientError as e:
            await interaction.followup.send(
                f"{ERROR_MESSAGE} (Error: {e})",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"予期せぬエラーが発生しました。(Error: {e})",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Yen5000(bot))
