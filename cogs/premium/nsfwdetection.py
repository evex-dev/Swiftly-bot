import os
import torch
import discord
from discord.ext import commands
from transformers import pipeline
from PIL import Image
import io
from cogs.premium.premium import PremiumDatabase

class NSFWDetection(commands.Cog):
    def __init__(self, bot):
        device_id = 0 if torch.cuda.is_available() else -1
        self.bot = bot
        self.classifier = pipeline(
            "image-classification",
            model="Falconsai/nsfw_image_detection",
            device=device_id
        )

    @commands.command(name="nsfwdetect")
    async def analyze_nsfw(self, ctx):
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(ctx.author.id):
            return

        user_id = ctx.author.id
        premium_db = PremiumDatabase()
        user_data = premium_db.get_user(user_id)
        if not user_data:
            return await ctx.send("このコマンドはプレミアムユーザー専用です。プレミアム機能を有効化するには、Swiftlyを自分のサーバーに導入してください。既にサーバーに導入済みの場合は、開発者(techfish_1)にお問い合わせください。\n(プレミアム機能は完全無料です。有料ではありません。)")

        if not (ctx.message.reference and ctx.message.reference.message_id):
            return await ctx.send("参照先のメッセージに画像を添付してください。")

        ref_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        analyzing_msg = await ctx.send("解析中...")

        valid_attachments = [att for att in ref_message.attachments
                             if att.filename.lower().endswith(('jpg','jpeg','png'))]
        if not valid_attachments:
            return await analyzing_msg.edit(content="画像が見つかりませんでした。")

        # Collect all images
        images = []
        for att in valid_attachments:
            image_bytes = await att.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # Convert to PNG if not already
            if not att.filename.lower().endswith('png'):
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                buffer.seek(0)
                image = Image.open(buffer)
            images.append(image)

        # Single batch inference
        results = self.classifier(images)

        final_label = 'SAFE'
        description_lines = []

        for idx, result in enumerate(results, start=1):
            # Directly check the label from the result
            label = 'NSFW' if result[0]['label'] == 'nsfw' else 'SAFE'
            if label == 'NSFW':
                final_label = 'NSFW'
            description_lines.append(
                f"画像 {idx}:\n"
                f"📄 ファイル名: {valid_attachments[idx-1].filename}\n"
                f"🔍 判定ラベル: {label} (信頼度: {result[0]['score']*100:.2f}%)\n\n"
            )

        embed = discord.Embed(
            title="NSFW コンテンツ判定結果",
            description=(
                "画像の内容を確認しました。\n\n"
                + "\n".join(description_lines)
                + "\n最終判定結果: " + final_label
            ),
            color=discord.Color.green() if final_label == 'SAFE' else discord.Color.red()
        )
        await analyzing_msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(NSFWDetection(bot))
