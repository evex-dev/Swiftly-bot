import discord
from discord.ext import commands
from transformers import pipeline
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 5
ERROR_MESSAGES = {
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

class Mind(commands.Cog):
    """Mindコマンドを提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_uses = {}
        self.sentiment_analyzer = pipeline("sentiment-analysis", model="cl-tohoku/bert-base-japanese")

    def _check_rate_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    @commands.command(
        name="mind",
        description="返信先のメッセージの感情予測を行います"
    )
    async def mind(self, ctx: commands.Context) -> None:
        try:
            # レート制限のチェック
            is_limited, remaining = self._check_rate_limit(ctx.author.id)
            if is_limited:
                await ctx.send(
                    ERROR_MESSAGES["rate_limit"].format(remaining)
                )
                return

            # 返信先のメッセージを取得
            if not ctx.message.reference or not ctx.message.reference.resolved:
                await ctx.send(
                    "返信先のメッセージが見つかりません。"
                )
                return

            referenced_message = ctx.message.reference.resolved

            # 感情予測
            sentiment = self.sentiment_analyzer(referenced_message.content)
            sentiment_label = sentiment[0]['label']
            sentiment_score = sentiment[0]['score']

            # レート制限の更新
            self._last_uses[ctx.author.id] = datetime.now()

            # 結果の送信
            embed = discord.Embed(
                title="感情予測結果",
                description=f"メッセージ: {referenced_message.content}",
                color=discord.Color.blue()
            )
            embed.add_field(name="感情", value=sentiment_label)
            embed.add_field(name="スコア", value=f"{sentiment_score:.2f}")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error in mind command: %s", e, exc_info=True)
            await ctx.send(
                ERROR_MESSAGES["unexpected"].format(str(e))
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Mind(bot))
