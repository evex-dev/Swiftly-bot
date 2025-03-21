import discord
from discord.ext import commands
import torch
from PIL import Image
from transformers import AutoModelForImageClassification, ViTImageProcessor
import io
import sqlite3

class NSFWdetectionImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.model = AutoModelForImageClassification.from_pretrained("Falconsai/nsfw_image_detection")
        self.processor = ViTImageProcessor.from_pretrained('Falconsai/nsfw_image_detection')
        self.conn = sqlite3.connect('data/nsfw-settings.db')
        self.create_table_if_not_exists()

    def create_table_if_not_exists(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                nsfw_detection_enabled BOOLEAN NOT NULL
            )
        ''')
        self.conn.commit()

    def is_nsfw(self, image_bytes):
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        with torch.no_grad():
            inputs = self.processor(images=img, return_tensors="pt")
            outputs = self.model(**inputs)
            logits = outputs.logits
        predicted_label = logits.argmax(-1).item()
        return self.model.config.id2label[predicted_label] == 'nsfw'

    def get_nsfw_detection_status(self, guild_id):
        cursor = self.conn.execute('SELECT nsfw_detection_enabled FROM settings WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        return row[0] if row else False

    def set_nsfw_detection_status(self, guild_id, status):
        cursor = self.conn.execute('SELECT nsfw_detection_enabled FROM settings WHERE guild_id = ?', (guild_id,))
        if cursor.fetchone():
            self.conn.execute('UPDATE settings SET nsfw_detection_enabled = ? WHERE guild_id = ?', (status, guild_id))
        else:
            self.conn.execute('INSERT INTO settings (guild_id, nsfw_detection_enabled) VALUES (?, ?)', (guild_id, status))
        self.conn.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.get_nsfw_detection_status(message.guild.id):
            return

        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                    image_bytes = await attachment.read()
                    if self.is_nsfw(image_bytes):
                        await message.add_reaction('🚫')
                        alert = await message.channel.send(f"{message.author.mention} NSFW画像が検出されました。\nこのメッセージは5秒後に削除されます。")
                        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=5))
                        await alert.delete()
                        await message.delete()
                        self.bot.logger.info(f"NSFW image detected and removed in guild {message.guild.id} by user {message.author.id}.")
                    else:
                        await message.add_reaction('✅')
                        self.bot.logger.info(f"Safe image detected in guild {message.guild.id} by user {message.author.id}.")

    @discord.app_commands.command(name='sentry', description="NSFWコンテンツの検出設定を管理します")
    async def sentry(self, interaction: discord.Interaction, action: str, function: str):
        if function != 'imagedetect':
            await interaction.response.send_message("無効な機能です。")
            return

        if action == 'enable':
            self.set_nsfw_detection_status(interaction.guild_id, True)
            await interaction.response.send_message("NSFW画像検知が有効になりました。")
        elif action == 'disable':
            self.set_nsfw_detection_status(interaction.guild_id, False)
            await interaction.response.send_message("NSFW画像検知が無効になりました。")
        else:
            await interaction.response.send_message("無効なアクションです。")

async def setup(bot):
    await bot.add_cog(NSFWdetectionImageCog(bot))
