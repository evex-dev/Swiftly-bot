import discord
from discord.ext import commands
from transformers import pipeline
import logging
from datetime import datetime, timedelta
from typing import Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification, LukeConfig
import torch

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
        self.tokenizer = AutoTokenizer.from_pretrained("Mizuiro-sakura/luke-japanese-large-sentiment-analysis-wrime")
        self.config = LukeConfig.from_pretrained("Mizuiro-sakura/luke-japanese-large-sentiment-analysis-wrime", output_hidden_states=True)
        self.model = AutoModelForSequenceClassification.from_pretrained("Mizuiro-sakura/luke-japanese-large-sentiment-analysis-wrime", config=self.config)
        self.url_tokenizer = AutoTokenizer.from_pretrained("r3ddkahili/final-complete-malicious-url-model")
        self.url_model = AutoModelForSequenceClassification.from_pretrained("r3ddkahili/final-complete-malicious-url-model")

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
            async with ctx.typing():
                # レート制限のチェック
                is_limited, remaining = self._check_rate_limit(ctx.author.id)
                if is_limited:
                    await ctx.send(ERROR_MESSAGES["rate_limit"].format(remaining))
                    return

                # 返信先のメッセージを取得
                if not ctx.message.reference or not ctx.message.reference.resolved:
                    await ctx.send("返信先のメッセージが見つかりません。")
                    return

                referenced_message = ctx.message.reference.resolved
                text = referenced_message.content

                # テキストをトークン化
                max_seq_length = 512
                tokenized = self.tokenizer(text, truncation=True, max_length=max_seq_length, padding="max_length")
                input_ids = torch.tensor(tokenized['input_ids']).unsqueeze(0)  # バッチ次元追加
                attention_mask = torch.tensor(tokenized['attention_mask']).unsqueeze(0)

                # モデル実行
                output = self.model(input_ids, attention_mask=attention_mask)
                max_index = torch.argmax(output.logits, dim=1).item()

                # ラベルに対応する感情
                if max_index == 0:
                    sentiment_label = 'うれしい'
                elif max_index == 1:
                    sentiment_label = '悲しい'
                elif max_index == 2:
                    sentiment_label = '期待'
                elif max_index == 3:
                    sentiment_label = '驚き'
                elif max_index == 4:
                    sentiment_label = '怒り'
                elif max_index == 5:
                    sentiment_label = '恐れ'
                elif max_index == 6:
                    sentiment_label = '嫌悪'
                elif max_index == 7:
                    sentiment_label = '信頼'
                else:
                    sentiment_label = '不明'

                # レート制限の更新
                self._last_uses[ctx.author.id] = datetime.now()

                # 結果の送信
                embed = discord.Embed(
                    title="感情予測結果",
                    description=f"メッセージ: {text}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="感情", value=sentiment_label)
                embed.add_field(name="予測クラス", value=str(max_index))
                embed.set_footer(text="この結果はAIによる予測です。実際の結果とは異なる場合があります。")
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Error in mind command: %s", e, exc_info=True)
            await ctx.send(ERROR_MESSAGES["unexpected"].format(str(e)))

    @commands.command(
        name="url",
        description="指定されたURLの分類を行います"
    )
    async def url(self, ctx: commands.Context, url: str) -> None:
        try:
            async with ctx.typing():
                # レート制限のチェック
                is_limited, remaining = self._check_rate_limit(ctx.author.id)
                if is_limited:
                    await ctx.send(ERROR_MESSAGES["rate_limit"].format(remaining))
                    return
                # URLをトークン化して予測
                inputs = self.url_tokenizer(url, return_tensors="pt", truncation=True, padding=True, max_length=128)
                with torch.no_grad():
                    outputs = self.url_model(**inputs)
                    prediction = torch.argmax(outputs.logits).item()
                # ラベルマッピング
                label_map = {0: "Benign", 1: "Defacement", 2: "Phishing", 3: "Malware"}
                result = label_map.get(prediction, "Unknown")
                # レート制限の更新
                self._last_uses[ctx.author.id] = datetime.now()
                # 結果の送信
                embed = discord.Embed(
                    title="URL分類結果",
                    description=f"URL: {url}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="分類", value=result)
                embed.set_footer(text="この結果はAIによる予測です。実際の結果とは異なる場合があります。")
                await ctx.send(embed=embed)
        except Exception as e:
            logger.error("Error in url command: %s", e, exc_info=True)
            await ctx.send(ERROR_MESSAGES["unexpected"].format(str(e)))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Mind(bot))
