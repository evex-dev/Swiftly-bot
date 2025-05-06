import asyncio
import re
from functools import lru_cache
from typing import Final, Optional, List, Tuple, Dict
import logging
from datetime import datetime, timedelta

import wikipedia
from wikipedia.exceptions import DisambiguationError, PageError

import discord
from discord import app_commands
from discord.ext import commands


WIKIPEDIA_LANG: Final[str] = "ja"
CACHE_SIZE: Final[int] = 100
SEARCH_RESULTS_LIMIT: Final[int] = 3
DISAMBIGUATION_LIMIT: Final[int] = 5
SUMMARY_SENTENCES: Final[int] = 3
RATE_LIMIT_SECONDS: Final[int] = 10

PATTERNS: Final[Dict[str, str]] = {
    "mention": r"@",
    "everyone_here": r"@(everyone|here)"
}

ERROR_MESSAGES: Final[dict] = {
    "no_results": "**'{}'** に該当する結果はありませんでした。",
    "page_not_found": "**'{}'** に該当するページが見つかりませんでした。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "unexpected": "エラーが発生しました: {}"
}

EMBED_COLORS: Final[dict] = {
    "normal": discord.Color.blue(),
    "warning": discord.Color.orange(),
    "error": discord.Color.red()
}

logger = logging.getLogger(__name__)

class WikipediaAPI:
    """Wikipedia APIを管理するクラス"""

    def __init__(self) -> None:
        wikipedia.set_lang(WIKIPEDIA_LANG)

    @lru_cache(maxsize=CACHE_SIZE)
    def search(self, query: str) -> List[str]:
        return wikipedia.search(query, results=SEARCH_RESULTS_LIMIT)

    async def get_page_info(
        self,
        title: str
    ) -> Tuple[str, str, str]:
        loop = asyncio.get_event_loop()
        try:
            page, summary = await asyncio.gather(
                loop.run_in_executor(None, wikipedia.page, title),
                loop.run_in_executor(
                    None,
                    wikipedia.summary,
                    title,
                    SUMMARY_SENTENCES
                )
            )
            return page.title, summary, page.url
        except Exception as e:
            logger.error("Error getting page info: %s", e, exc_info=True)
            raise

    async def get_random_page(self) -> Tuple[str, str, str]:
        loop = asyncio.get_event_loop()
        try:
            page = await loop.run_in_executor(None, wikipedia.random)
            page_info = await self.get_page_info(page)
            return page_info
        except Exception as e:
            logger.error("Error getting random page: %s", e, exc_info=True)
            raise

class MessageProcessor:
    """メッセージ処理を行うクラス"""

    @staticmethod
    def sanitize_input(content: str) -> str:
        result = content
        # メンションを全角に変換
        result = re.sub(PATTERNS["mention"], "＠", result)
        # @everyone, @hereを無効化
        result = re.sub(PATTERNS["everyone_here"], "＠\\1", result)
        return result

class WikipediaCog(commands.Cog):
    """Wikipedia検索機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.api = WikipediaAPI()
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

    def _create_search_embed(
        self,
        title: str,
        summary: str,
        url: str
    ) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=summary,
            url=url,
            color=EMBED_COLORS["normal"]
        ).set_footer(
            text="情報はWikipediaより取得されました。"
        )

    def _create_disambiguation_embed(
        self,
        options: List[str]
    ) -> discord.Embed:
        return discord.Embed(
            title="曖昧な検索結果",
            description="\n".join(
                f"{i+1}. {option}"
                for i, option in enumerate(options[:DISAMBIGUATION_LIMIT])
            ),
            color=EMBED_COLORS["warning"]
        ).set_footer(
            text="もう一度詳しいキーワードで検索してください。"
        )

    @app_commands.command(
        name="wikipedia",
        description="Wikipediaで検索します"
    )
    @app_commands.describe(
        query="検索するキーワード"
    )
    async def wikipedia_search(
        self,
        interaction: discord.Interaction,
        query: str
    ) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return
        try:
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

            await interaction.response.defer()

            # 入力のサニタイズ
            query = MessageProcessor.sanitize_input(query)

            # 検索の実行
            search_results = self.api.search(query)
            if not search_results:
                await interaction.followup.send(
                    ERROR_MESSAGES["no_results"].format(query)
                )
                return

            # ページ情報の取得
            title, summary, url = await self.api.get_page_info(
                search_results[0]
            )

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_search_embed(title, summary, url)
            await interaction.followup.send(embed=embed)
        except DisambiguationError as e:
            logger.info("Disambiguation for query '%s': %s", query, e.options)
            return
        except PageError:
            logger.warning("Page not found for query '%s'", query)
            return
        except Exception as e:
            logger.error("Error in wikipedia search: %s", e, exc_info=True)
            return

    @app_commands.command(
        name="random_wikipedia",
        description="Wikipediaのおまかせページを表示します"
    )
    async def random_wikipedia(
        self,
        interaction: discord.Interaction
    ) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return
        try:
            await interaction.response.defer()

            # ランダムページ情報の取得
            title, summary, url = await self.api.get_random_page()

            # 結果の送信
            embed = self._create_search_embed(title, summary, url)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error("Error in random wikipedia: %s", e, exc_info=True)
            return


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WikipediaCog(bot))
