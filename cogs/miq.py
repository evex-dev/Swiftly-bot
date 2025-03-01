import discord
from discord.ext import commands
from lib.miq import MakeItQuote
from PIL import Image
import aiohttp
from io import BytesIO
import logging
import asyncio

logger = logging.getLogger(__name__)


class MakeItQuoteCog(commands.Cog):
    """MakeItQuoteコマンドを提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.miq = MakeItQuote()
        self.session = None
        self.avatar_cache = {}  # Cache for avatar images

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self.session:
            await self.session.close()

    @commands.command(
        name="miq",
        description="返信先のメッセージとその人のアイコンでMake It Quoteを作成します"
    )
    async def make_it_quote(
        self,
        ctx: commands.Context
    ) -> None:
        try:
            # 返信先のメッセージを取得
            if not ctx.message.reference:
                await ctx.send("返信先のメッセージが必要です。")
                return

            async with ctx.typing():
                reference_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                quote = reference_message.content
                author = reference_message.author.display_name

                # アイコンを取得、キャッシュを利用
                avatar_url = reference_message.author.avatar.url
                if avatar_url in self.avatar_cache:
                    avatar_image = self.avatar_cache[avatar_url]
                else:
                    async with self.session.get(avatar_url) as response:
                        if response.status != 200:
                            raise Exception(f"アバター画像の取得に失敗しました: {response.status}")
                        avatar_bytes = await response.read()
                        avatar_image = await asyncio.to_thread(Image.open, BytesIO(avatar_bytes))
                        self.avatar_cache[avatar_url] = avatar_image

                # Make It Quoteを作成 using asynchronous thread for blocking operation
                quote_image = await asyncio.to_thread(self.miq.create_quote, quote=quote, author=author, background_image=avatar_image)

                # 画像を一時ファイルに保存
                with BytesIO() as image_binary:
                    await asyncio.to_thread(quote_image.save, image_binary, "PNG")
                    image_binary.seek(0)
                    await ctx.send(file=discord.File(fp=image_binary, filename="quote.png"))

        except Exception as e:
            logger.error("Error in make_it_quote command: %s", e, exc_info=True)
            await ctx.send(f"エラーが発生しました: {str(e)}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MakeItQuoteCog(bot))
