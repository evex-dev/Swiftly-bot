import discord
from discord.ext import commands
from lib.miq import MakeItQuote
from PIL import Image
import requests
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class MakeItQuoteCog(commands.Cog):
    """MakeItQuoteコマンドを提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.miq = MakeItQuote()

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

            reference_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            quote = reference_message.content
            author = reference_message.author.display_name

            # アイコンを取得
            avatar_url = reference_message.author.avatar.url
            response = requests.get(avatar_url, timeout=10)
            avatar_image = Image.open(BytesIO(response.content))

            # Make It Quoteを作成
            quote_image = self.miq.create_quote(
                quote=quote,
                author=author,
                background_image=avatar_image
            )

            # 画像を一時ファイルに保存
            with BytesIO() as image_binary:
                quote_image.save(image_binary, 'PNG')
                image_binary.seek(0)
                await ctx.send(file=discord.File(fp=image_binary, filename='quote.png'))

        except Exception as e:
            logger.error("Error in make_it_quote command: %s", e, exc_info=True)
            await ctx.send(f"エラーが発生しました: {str(e)}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MakeItQuoteCog(bot))
