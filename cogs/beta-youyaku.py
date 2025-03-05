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
        if not channel.permissions_for(interaction.guild.me).read_message_history:
            await interaction.response.send_message("メッセージ履歴を読む権限がありません。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        try:
            # メッセージの取得を修正
            messages = [
                message async for message in channel.history(limit=100)
            ]
            
            # メッセージ内容を抽出
            message_contents = [
                message.content
                for message in messages
                if message.content and len(message.content.strip()) > 0
            ]
            
            if not message_contents:
                await interaction.followup.send("要約するメッセージが見つかりませんでした。", ephemeral=True)
                return
            
            # スペースを使用してメッセージを結合（改行よりも要約モデルに適している）
            text = " ".join(message_contents)
            
            # デバッグ情報を追加（長さを確認用）
            print(f"Messages found: {len(message_contents)}, Total text length: {len(text)}")
            
            summary = self.summarizer(text, max_length=130, min_length=30, do_sample=False)
            await interaction.followup.send(summary[0]['summary_text'], ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BetaYouyaku(bot))
