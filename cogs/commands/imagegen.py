import discord
from discord.ext import commands
import aiohttp
import io
from typing import Final, Optional
import logging
import re
from datetime import datetime, timedelta


API_BASE_URL: Final[str] = "https://image-ai.evex.land"
MAX_PROMPT_LENGTH: Final[int] = 1000

ERROR_MESSAGES: Final[dict] = {
    "generation_failed": "画像の生成に失敗しました。時間をおいて再度お試しください。",
    "prompt_too_long": f"プロンプトは{MAX_PROMPT_LENGTH}文字以内で指定してください。",
    "invalid_prompt": "プロンプトに不適切な文字が含まれています。",
    "api_error": "APIエラーが発生しました: {}"
}

EMBED_COLORS: Final[dict] = {
    "success": discord.Color.blue(),
    "error": discord.Color.red()
}

logger = logging.getLogger(__name__)

class ImageGen(commands.Cog):
    """画像生成機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _validate_prompt(self, prompt: str) -> tuple[bool, Optional[str]]:
        if len(prompt) > MAX_PROMPT_LENGTH:
            return False, ERROR_MESSAGES["prompt_too_long"]

        # 不適切な文字や文字列のチェック
        invalid_patterns = [
            r"[<>{}[\]\\]",  # 特殊文字
            r"(?:https?://|www\.)\S+"  # URL
        ]

        for pattern in invalid_patterns:
            if re.search(pattern, prompt):
                return False, ERROR_MESSAGES["invalid_prompt"]

        return True, None

    def _create_image_embed(
        self,
        prompt: str
    ) -> discord.Embed:
        return discord.Embed(
            title="生成された画像",
            description=f"プロンプト: {prompt}",
            color=EMBED_COLORS["success"]
        ).set_image(
            url="attachment://generated_image.png"
        ).set_footer(
            text="API Powered by Evex"
        )

    async def _generate_image(
        self,
        prompt: str
    ) -> Optional[bytes]:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            async with self._session.get(
                f"{API_BASE_URL}/?prompt={prompt}"
            ) as response:
                if response.status == 200:
                    return await response.read()
                logger.warning(
                    "Image generation failed with status %d", response.status
                )
                return None
        except Exception as e:
            logger.error("Error generating image: %s", e, exc_info=True)
            return None

    @discord.app_commands.command(
        name="imagegen",
        description="与えられたプロンプトに基づいて画像を生成します"
    )
    @discord.app_commands.describe(
        prompt="生成する画像の説明（プロンプト）"
    )
    async def imagegen(
        self,
        interaction: discord.Interaction,
        prompt: str
    ) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return
        try:
            # プロンプトのバリデーション
            is_valid, error_message = self._validate_prompt(prompt)
            if not is_valid:
                await interaction.response.send_message(
                    error_message,
                    ephemeral=True
                )
                return

            await interaction.response.defer(thinking=True)

            # 画像の生成
            image_data = await self._generate_image(prompt)
            if not image_data:
                await interaction.followup.send(
                    ERROR_MESSAGES["generation_failed"],
                    ephemeral=True
                )
                return

            # 結果の送信
            file = discord.File(
                io.BytesIO(image_data),
                filename="generated_image.png"
            )
            embed = self._create_image_embed(prompt)
            await interaction.followup.send(embed=embed, file=file)

        except Exception as e:
            logger.error("Error in imagegen command: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["api_error"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageGen(bot))
