# Copied from the v2 source code.
# https://github.com/evex-dev/Swiftly-v2/blob/main/src/commands/sandbox.py
import asyncio
import json
import time
from typing import Final, Optional, Tuple, Dict, Any
import logging
from datetime import datetime, timedelta

import aiohttp
import discord
from discord.ext import commands


API_BASE_URLS: Final[dict] = {
    "python": "https://py-sandbox.evex.land/",
    "javascript": "https://js-sandbox.evex.land/"
}
SUPPORT_FOOTER: Final[str] = "API Powered by EvexDevelopers"
# RATE_LIMIT_SECONDS: Final[int] = 30  # 削除
MAX_CODE_LENGTH: Final[int] = 2000
EXECUTION_TIMEOUT: Final[int] = 30

ERROR_MESSAGES: Final[dict] = {
    "no_code": "実行するコードを入力してください。",
    "code_too_long": f"コードは{MAX_CODE_LENGTH}文字以内で指定してください。",
    # "rate_limit": "レート制限中です。{}秒後にお試しください。",  # 削除
    "execution_failed": "コードの実行に失敗しました。",
    "api_error": "API通信エラー: {}",
    "parse_error": "APIからの応答の解析に失敗しました。",
    "timeout": "実行がタイムアウトしました。",
    "unexpected": "予期せぬエラー: {}"
}

EMBED_COLORS: Final[dict] = {
    "success": discord.Color.green(),
    "error": discord.Color.red(),
    "warning": discord.Color.orange()
}

logger = logging.getLogger(__name__)

class CodeExecutor:
    """コードの実行を管理するクラス"""

    def __init__(self, code: str, language: str) -> None:
        self.code = code
        self.language = language
        self._validate_code()

    def _validate_code(self) -> None:
        """コードのバリデーション"""
        if len(self.code) > MAX_CODE_LENGTH:
            raise ValueError(ERROR_MESSAGES["code_too_long"])

        # 危険な操作のチェック
        dangerous_keywords = {
            "python": [
                "import os", "import sys", "import subprocess",
                "__import__", "eval(", "exec(", "open("
            ],
            "javascript": [
                "require(", "process.", "global.",
                "__dirname", "__filename", "module."
            ]
        }

        for keyword in dangerous_keywords.get(self.language, []):
            if keyword in self.code:
                self.code = f"# 安全性の理由で{keyword}は使用できません\n{self.code}" if self.language == "python" else f"// 安全性の理由で{keyword}は使用できません\n{self.code}"

    async def execute(
        self,
        session: aiohttp.ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], float]:
        headers = {"Content-Type": "application/json"}
        payload = {"code": self.code}

        try:
            start_time = time.monotonic()
            async with session.post(
                API_BASE_URLS[self.language],
                json=payload,
                headers=headers,
                timeout=EXECUTION_TIMEOUT
            ) as response:
                end_time = time.monotonic()
                elapsed_time = end_time - start_time

                if response.status == 200:
                    result = await response.text()
                    return json.loads(result), None, elapsed_time

                logger.warning(
                    "API error: %d - %s", response.status, await response.text()
                )
                return None, ERROR_MESSAGES["execution_failed"], elapsed_time

        except aiohttp.ClientError as e:
            logger.error("API communication error: %s", e, exc_info=True)
            return None, ERROR_MESSAGES["api_error"].format(str(e)), 0.0
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s", e, exc_info=True)
            return None, ERROR_MESSAGES["parse_error"], 0.0
        except asyncio.TimeoutError:
            logger.warning("Execution timeout")
            return None, ERROR_MESSAGES["timeout"], EXECUTION_TIMEOUT
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            return None, ERROR_MESSAGES["unexpected"].format(str(e)), 0.0

class Sandbox(commands.Cog):
    """コードサンドボックス機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def create_result_embed(
        self,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        elapsed_time: float = 0.0,
        language: str = ""
    ) -> discord.Embed:
        if error:
            embed = discord.Embed(
                title="エラー",
                description=error,
                color=EMBED_COLORS["error"]
            )
        else:
            embed = discord.Embed(
                title="実行結果",
                color=EMBED_COLORS["success"]
            )
            if result:
                # 終了コードに応じて色を変更
                exit_code = result.get("exitcode", 0)
                if exit_code != 0:
                    embed.color = EMBED_COLORS["warning"]

                embed.add_field(
                    name="終了コード",
                    value=str(exit_code),
                    inline=False
                )

                # 出力の整形
                output = result.get("message", "").strip()
                if output:
                    # 長すぎる出力を切り詰める
                    if len(output) > 1000:
                        output = output[:997] + "..."
                    embed.add_field(
                        name="出力",
                        value=f"```{language}\n{output}\n```",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="出力",
                        value="(出力なし)",
                        inline=False
                    )

        embed.add_field(
            name="実行時間",
            value=f"{elapsed_time:.2f} 秒",
            inline=False
        )
        embed.set_footer(text=SUPPORT_FOOTER)
        return embed

    @discord.app_commands.command(
        name="sandbox",
        description="コードをサンドボックスで実行し、結果を返します。"
    )
    @discord.app_commands.describe(
        language="コードの言語 (python または javascript)",
        code="実行するコード"
    )
    async def sandbox(
        self,
        interaction: discord.Interaction,
        language: str,
        code: str
    ) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return
        try:
            # 言語のバリデーション
            if language not in API_BASE_URLS:
                await interaction.response.send_message(
                    "サポートされていない言語です。python または javascript を指定してください。",
                    ephemeral=True
                )
                return

            await interaction.response.defer(thinking=True)

            # コードの実行
            executor = CodeExecutor(code, language)
            if not self._session:
                self._session = aiohttp.ClientSession()

            result, error, elapsed_time = await executor.execute(
                self._session
            )

            # 結果の送信
            embed = await self.create_result_embed(
                result,
                error,
                elapsed_time,
                language
            )
            await interaction.followup.send(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(
                str(e),
                ephemeral=True
            )
        except Exception as e:
            logger.error("Error in sandbox command: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Sandbox(bot))