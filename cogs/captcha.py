import base64
from io import BytesIO
from typing import Final, Optional
import logging

import aiohttp
import discord
from discord.ext import commands
from discord import ui


API_BASE_URL: Final[str] = "https://captcha.evex.land/api/captcha"
TIMEOUT_SECONDS: Final[int] = 30
MIN_DIFFICULTY: Final[int] = 1
MAX_DIFFICULTY: Final[int] = 10

ERROR_MESSAGES: Final[dict] = {
    "invalid_difficulty": "難易度は1から10の間で指定してください。",
    "fetch_failed": "CAPTCHAの取得に失敗しました。",
    "http_error": "HTTP エラーが発生しました: {}",
    "unexpected_error": "予期せぬエラーが発生しました: {}"
}

SUCCESS_MESSAGES: Final[dict] = {
    "correct": "✅ 正解です！CAPTCHAの認証に成功しました。",
    "incorrect": "❌ 不正解です。正解は `{}` でした。",
    "timeout": "⏰ 時間切れです。もう一度試してください。"
}

logger = logging.getLogger(__name__)

class CaptchaModal(ui.Modal):
    """CAPTCHA回答用のモーダル"""

    def __init__(self, answer: str) -> None:
        super().__init__(title="CAPTCHA 認証")
        self.answer = answer
        self.answer_input = ui.TextInput(
            label="画像に表示されている文字を入力してください",
            placeholder="ここに文字を入力",
            required=True,
            max_length=10
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """
        回答の検証を行う

        Parameters
        ----------
        interaction : discord.Interaction
            インタラクションコンテキスト
        """
        is_correct = self.answer_input.value.lower() == self.answer.lower()
        message = SUCCESS_MESSAGES["correct"] if is_correct else SUCCESS_MESSAGES["incorrect"].format(self.answer)
        await interaction.response.send_message(message, ephemeral=True)

class CaptchaButton(ui.Button):
    """CAPTCHA回答ボタン"""

    def __init__(self, answer: str) -> None:
        super().__init__(
            label="回答する",
            style=discord.ButtonStyle.primary,
            custom_id="captcha_answer"
        )
        self.answer = answer

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        ボタンクリック時の処理

        Parameters
        ----------
        interaction : discord.Interaction
            インタラクションコンテキスト
        """
        modal = CaptchaModal(self.answer)
        await interaction.response.send_modal(modal)

class CaptchaView(ui.View):
    """CAPTCHA表示用のビュー"""

    def __init__(self, answer: str) -> None:
        super().__init__(timeout=TIMEOUT_SECONDS)
        self.add_item(CaptchaButton(answer))
        self.message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        """タイムアウト時の処理"""
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
                await self.message.reply(
                    SUCCESS_MESSAGES["timeout"],
                    ephemeral=True
                )
        except Exception as e:
            logger.error("Error in captcha timeout: %s", e, exc_info=True)

class Captcha(commands.Cog):
    """CAPTCHA機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _create_captcha_embed(
        self,
        difficulty: int
    ) -> discord.Embed:
        return discord.Embed(
            title="CAPTCHA チャレンジ",
            description=(
                f"難易度: {difficulty}\n\n"
                "下のボタンを押して回答してください。\n"
                f"制限時間: {TIMEOUT_SECONDS}秒\n\n"
                f"APIエンドポイント: {API_BASE_URL}"
            ),
            color=discord.Color.blue()
        ).set_image(url="attachment://captcha.png")

    async def _fetch_captcha(
        self,
        difficulty: int
    ) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            async with self._session.get(
                f"{API_BASE_URL}?difficulty={difficulty}"
            ) as response:
                if response.status != 200:
                    return None, None, ERROR_MESSAGES["fetch_failed"]

                data = await response.json()
                image_data = data["image"].split(",")[1]
                image_bytes = base64.b64decode(image_data)
                return image_bytes, data["answer"], None

        except aiohttp.ClientError as e:
            logger.error("HTTP error in captcha fetch: %s", e, exc_info=True)
            return None, None, ERROR_MESSAGES["http_error"].format(str(e))
        except Exception as e:
            logger.error("Unexpected error in captcha fetch: %s", e, exc_info=True)
            return None, None, ERROR_MESSAGES["unexpected_error"].format(str(e))

    @discord.app_commands.command(
        name="captcha",
        description="CAPTCHA画像を生成し、解答を検証します"
    )
    @discord.app_commands.describe(
        difficulty="CAPTCHAの難易度 (1-10)"
    )
    async def captcha(
        self,
        interaction: discord.Interaction,
        difficulty: int = MIN_DIFFICULTY
    ) -> None:
        if not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
            await interaction.response.send_message(
                ERROR_MESSAGES["invalid_difficulty"],
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        image_bytes, answer, error = await self._fetch_captcha(difficulty)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        image_file = discord.File(
            BytesIO(image_bytes),
            filename="captcha.png"
        )
        embed = self._create_captcha_embed(difficulty)
        view = CaptchaView(answer)

        message = await interaction.followup.send(
            embed=embed,
            file=image_file,
            view=view
        )
        view.message = message


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Captcha(bot))
