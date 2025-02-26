import re
from collections import Counter
from typing import Final, Optional, List, Tuple
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands


MAX_MESSAGES: Final[int] = 1000
DEFAULT_MESSAGES: Final[int] = 100
TOP_WORDS_COUNT: Final[int] = 10
RATE_LIMIT_SECONDS: Final[int] = 30
MIN_WORD_LENGTH: Final[int] = 2

JAPANESE_STOP_WORDS: Final[List[str]] = [
    "の", "に", "は", "を", "た", "が", "で", "て", "と", "し",
    "れ", "さ", "ある", "いる", "も", "する", "から", "な", "こと",
    "として", "い", "や", "れる", "など", "なっ", "ない", "この",
    "ため", "その", "あっ", "よう", "また", "もの", "という", "あり",
    "まで", "られ", "なる", "へ", "か", "だ", "これ", "によって",
    "により", "おり", "より", "による", "ず", "なり", "られる", "において",
    "です", "ます"
]


ERROR_MESSAGES: Final[dict] = {
    "max_messages": "メッセージ数の上限は{}件です。",
    "no_messages": "要約するメッセージが見つかりませんでした。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "discord_error": "Discordでエラーが発生しました: {}",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

logger = logging.getLogger(__name__)

class MessageAnalyzer:
    """メッセージ分析を行うクラス"""

    @staticmethod
    def extract_words(text: str) -> List[str]:
        words = re.findall(r"\b\w+\b", text)
        return [
            word for word in words
            if (len(word) >= MIN_WORD_LENGTH and
                word not in JAPANESE_STOP_WORDS)
        ]

    @staticmethod
    def analyze_frequency(
        words: List[str]
    ) -> List[Tuple[str, int]]:
        word_counts = Counter(words)
        return word_counts.most_common(TOP_WORDS_COUNT)

    @staticmethod
    def format_summary(
        word_counts: List[Tuple[str, int]]
    ) -> str:
        if not word_counts:
            return "頻出単語が見つかりませんでした。"

        total_count = sum(count for _, count in word_counts)
        summary_lines = []

        for word, count in word_counts:
            percentage = (count / total_count) * 100
            summary_lines.append(
                f"・{word}: {count}回 ({percentage:.1f}%)"
            )

        return "\n".join(summary_lines)

class Youyaku(commands.Cog):
    """メッセージ要約機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.analyzer = MessageAnalyzer()
        self._last_uses = {}

    def _check_rate_limit(
        self,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    def _create_summary_embed(
        self,
        channel: discord.TextChannel,
        num_messages: int,
        summary: str
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"メッセージ要約: #{channel.name}",
            description=f"直近{num_messages}件のメッセージを分析しました。",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="頻出単語",
            value=summary,
            inline=False
        )

        embed.set_footer(
            text="単語の出現頻度に基づく分析結果です。"
        )

        return embed

    @discord.app_commands.command(
        name="youyaku",
        description="指定したチャンネルのメッセージを要約します。"
    )
    @discord.app_commands.describe(
        channel="要約するチャンネル",
        num_messages="分析するメッセージ数（デフォルト: 100、最大: 1000）"
    )
    async def youyaku(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        num_messages: int = DEFAULT_MESSAGES
    ) -> None:
        try:
            # メッセージ数の制限チェック
            if num_messages > MAX_MESSAGES:
                await interaction.response.send_message(
                    ERROR_MESSAGES["max_messages"].format(MAX_MESSAGES),
                    ephemeral=True
                )
                return

            # レート制限のチェック
            is_limited, remaining = self._check_rate_limit(
                interaction.user.id
            )
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            await interaction.response.defer(thinking=True)

            # メッセージの取得
            messages = [
                message async for message in channel.history(
                    limit=num_messages
                )
            ]
            message_contents = [
                message.content
                for message in messages
                if message.content
            ]

            if not message_contents:
                await interaction.followup.send(
                    ERROR_MESSAGES["no_messages"]
                )
                return

            # テキストの解析
            combined_text = " ".join(message_contents)
            words = self.analyzer.extract_words(combined_text)
            word_counts = self.analyzer.analyze_frequency(words)
            summary = self.analyzer.format_summary(word_counts)

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_summary_embed(
                channel,
                num_messages,
                summary
            )
            await interaction.followup.send(embed=embed)

        except discord.DiscordException as e:
            logger.error("Discord error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["discord_error"].format(str(e))
            )
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["unexpected"].format(str(e))
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Youyaku(bot))
