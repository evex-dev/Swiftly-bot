import discord
from discord.ext import commands
import sqlite3
from datetime import datetime

class RequestModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="リクエストを送信")
        self.add_item(discord.ui.TextInput(label="リクエスト内容", style=discord.TextStyle.long))

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        message = self.children[0].value
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_request(user_id, date, message)
        await interaction.response.send_message("リクエストが送信されました。", ephemeral=True)

class RequestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect('data/request.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS requests
                     (user_id INTEGER, date TEXT, message TEXT)''')
        conn.commit()
        conn.close()

    @discord.app_commands.command(name="request", description="機能やbotについてのリクエストを送信します。")
    async def request(self, interaction: discord.Interaction):
        modal = RequestModal()
        await interaction.response.send_modal(modal)

def save_request(user_id: int, date: str, message: str):
    conn = sqlite3.connect('data/request.db')
    c = conn.cursor()
    c.execute("INSERT INTO requests (user_id, date, message) VALUES (?, ?, ?)", (user_id, date, message))
    conn.commit()
    conn.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(RequestCog(bot))