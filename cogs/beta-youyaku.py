import discord
from discord.ext import commands
from transformers import pipeline

class BetaYouyaku(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        try:
            self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        except Exception as e:
            self.summarizer = None
            print(f"Error loading summarizer model: {str(e)}")

    @discord.app_commands.command(name="beta-youyaku", description="指定したチャンネルの過去のメッセージを要約します")
    @discord.app_commands.describe(channel="要約するチャンネル")
    async def beta_youyaku(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not self.summarizer:
            await interaction.response.send_message("サマライザーモデルの読み込みに失敗しました。管理者に連絡してください。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        try:
            messages = []
            async for message in channel.history(limit=100):
                if message.content:
                    messages.append(message.content)
            text = "\n".join(messages)
            summary = self.summarizer(text, max_length=130, min_length=30, do_sample=False)
            await interaction.followup.send(summary[0]['summary_text'], ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BetaYouyaku(bot))
