import base64
from io import BytesIO

import aiohttp
import discord
from discord.ext import commands
from discord import ui


class CaptchaModal(ui.Modal, title="CAPTCHA 認証"):
    def __init__(self, answer: str):
        super().__init__()
        self.answer = answer

    answer_input = ui.TextInput(
        label="画像に表示されている文字を入力してください",
        placeholder="ここに文字を入力",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        if self.answer_input.value.lower() == self.answer.lower():
            await interaction.response.send_message("✅ 正解です！CAPTCHAの認証に成功しました。", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 不正解です。正解は `{self.answer}` でした。", ephemeral=True)


class CaptchaButton(ui.Button):
    def __init__(self, answer: str):
        super().__init__(
            label="回答する",
            style=discord.ButtonStyle.primary,
            custom_id="captcha_answer"
        )
        self.answer = answer

    async def callback(self, interaction: discord.Interaction):
        modal = CaptchaModal(self.answer)
        await interaction.response.send_modal(modal)


class CaptchaView(ui.View):
    def __init__(self, answer: str):
        super().__init__(timeout=30)
        self.add_item(CaptchaButton(answer))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
            await self.message.reply("⏰ 時間切れです。もう一度試してください。", ephemeral=True)
        except:
            pass


class Captcha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    @discord.app_commands.command(name="captcha", description="CAPTCHA画像を生成し、解答を検証します")
    @discord.app_commands.describe(difficulty="CAPTCHAの難易度 (1-10)")
    async def captcha(self, ctx: discord.Interaction, difficulty: int = 1) -> None:
        if difficulty < 1 or difficulty > 10:
            await ctx.response.send_message("難易度は1から10の間で指定してください。", ephemeral=True)
            return

        await ctx.response.defer(thinking=True)

        try:
            async with self.session.get(f"https://captcha.evex.land/api/captcha?difficulty={difficulty}") as response:
                if response.status == 200:
                    data = await response.json()
                    image_data = data["image"].split(",")[1]
                    image_bytes = base64.b64decode(image_data)
                    image_file = discord.File(BytesIO(image_bytes), filename="captcha.png")
                    answer = data["answer"]

                    embed = discord.Embed(
                        title="CAPTCHA チャレンジ",
                        description=f"難易度: {difficulty}\n\n下のボタンを押して回答してください。\n制限時間: 30秒\n\nAPIエンドポイント: https://captcha.evex.land/api/captcha",
                        color=discord.Color.blue()
                    )
                    embed.set_image(url="attachment://captcha.png")

                    view = CaptchaView(answer)
                    message = await ctx.followup.send(embed=embed, file=image_file, view=view)
                    view.message = message

                else:
                    await ctx.followup.send("CAPTCHAの取得に失敗しました。", ephemeral=True)

        except aiohttp.ClientError as e:
            await ctx.followup.send(f"HTTP エラーが発生しました: {e}", ephemeral=True)
        except Exception as e:
            await ctx.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

    async def cog_unload(self):
        await self.session.close()


async def setup(bot):
    await bot.add_cog(Captcha(bot))
