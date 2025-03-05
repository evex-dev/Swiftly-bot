import discord
from discord.ext import commands
from transformers import pipeline

class BetaYouyaku(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

    @discord.app_commands.command(name="beta-youyaku", description="過去のDiscordメッセージを要約します")
    async def beta_youyaku(self, interaction: discord.Interaction, text: str) -> None:
        try:
            summary = self.summarizer(text, max_length=130, min_length=30, do_sample=False)
            await interaction.response.send_message(summary[0]['summary_text'], ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BetaYouyaku(bot))
