import sqlite3
import uuid
from discord.ext import commands
import discord

DB_PATH = "data/premium.db"

class PremiumDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._create_table()

    def _create_table(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS premium_users (
                    user_id INTEGER PRIMARY KEY,
                    token TEXT NOT NULL,
                    voice TEXT DEFAULT 'ja-JP-NanamiNeural'
                )
                """
            )

    def add_user(self, user_id: int, token: str):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO premium_users (user_id, token) VALUES (?, ?)",
                (user_id, token)
            )

    def get_user(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT token, voice FROM premium_users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()

    def update_voice(self, user_id: int, voice: str):
        with self.conn:
            self.conn.execute(
                "UPDATE premium_users SET voice = ? WHERE user_id = ?",
                (voice, user_id)
            )

class Premium(commands.Cog):
    """プレミアム機能を管理するクラス"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PremiumDatabase()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        owner = guild.owner
        user_data = self.db.get_user(owner.id)
        if user_data:
            # プレミアム機能が既に有効な場合は何もしない
            return
        else:
            token = str(uuid.uuid4())
            self.db.add_user(owner.id, token)
            await owner.send(
                f"🎉 **Swiftlyの導入ありがとうございます！** 🎉\n\n"
                f"導入の感謝として、**プレミアムトークン**を発行しました:\n"
                f"🔑 `{token}`\n\n"
                "プレミアム機能を有効にするには、以下の手順をお試しください:\n"
                "1️⃣ `/premium` コマンドを使用してトークンを登録\n"
                "2️⃣ プレミアム機能を有効化\n\n"
                "✨ **プレミアム特典:**\n"
                "🔹 VC読み上げボイスの変更が可能\n"
                "🔹 ボイスは `/set_voice` コマンドで設定できます\n\n"
                "これからもSwiftlyをよろしくお願いします！\n\n"
                "🌐 **Swiftlyの共有もお願いします！**\n"
                "🔗 [公式サイト](https://sakana11.org/swiftly/)\n"
                "🔗 [Discordアプリページ](https://discord.com/discovery/applications/1310198598213963858)"
            )

    @discord.app_commands.command(
        name="premium",
        description="プレミアムトークンを登録します"
    )
    async def premium(self, interaction: discord.Interaction, token: str):
        user_id = interaction.user.id
        user_data = self.db.get_user(user_id)
        if user_data and user_data[0] == token:
            await interaction.response.send_message("プレミアム機能が有効になりました！導入ありがとうございます。Swiftlyの共有もお願いします！", ephemeral=True)
        else:
            await interaction.response.send_message("無効なトークンです。", ephemeral=True)

    @discord.app_commands.command(
        name="set_voice",
        description="読み上げボイスを設定します (プレミアムユーザーのみ)"
    )
    async def set_voice(self, interaction: discord.Interaction, voice: str):
        if voice not in ["ja-JP-KeitaNeural", "ja-JP-NanamiNeural"]:
            await interaction.response.send_message("無効なボイスです。", ephemeral=True)
            return

        user_id = interaction.user.id
        user_data = self.db.get_user(user_id)
        if not user_data:
            await interaction.response.send_message("プレミアムユーザーのみがこの機能を使用できます。\nプレミアムユーザーになるには、自分のサーバーにSwiftlyを導入するとトークンが発行され、プレミアムユーザーになることができます。\nすでに導入済みの場合は開発者(techfish_1)にお問い合わせください。", ephemeral=True)
            return

        self.db.update_voice(user_id, voice)
        await interaction.response.send_message(f"ボイスを {voice} に設定しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Premium(bot))