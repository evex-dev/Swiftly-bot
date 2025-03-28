import sqlite3
import uuid
from discord.ext import commands
import discord
import logging
DB_PATH = "data/premium.db"

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

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

    def validate_and_consume_token(self, token: str):
        """トークンを検証し、使用済みとして無効化する"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT user_id FROM premium_users WHERE token = ? AND token IS NOT NULL",
            (token,)
        )
        result = cursor.fetchone()
        if result:
            user_id = result[0]
            with self.conn:
                self.conn.execute(
                    "UPDATE premium_users SET token = NULL WHERE user_id = ?",
                    (user_id,)
                )
            return user_id
        return None

class Premium(commands.Cog):
    """プレミアム機能を管理するクラス"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PremiumDatabase()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        owner = guild.owner
        if owner is None:
            try:
                owner = await self.bot.fetch_user(guild.owner_id)  # fetch_userでオーナーを取得
            except Exception as e:
                logger.error("Failed to fetch guild owner: %s", e, exc_info=True)
                return  # オーナーが取得できない場合は処理をスキップ

        user_data = self.db.get_user(owner.id)
        if user_data:
            return  # プレミアム機能が既に有効な場合は何もしない

        token = str(uuid.uuid4())
        self.db.add_user(owner.id, token)
        try:
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
        except Exception as e:
            logger.error("Failed to send DM to guild owner: %s", e, exc_info=True)

    @discord.app_commands.command(
        name="premium",
        description="プレミアムトークンを登録します"
    )
    async def premium(self, interaction: discord.Interaction, token: str):
        user_id = self.db.validate_and_consume_token(token)
        if user_id == interaction.user.id:
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
            await interaction.response.send_message("プレミアムユーザーのみがこの機能を使用できます。\nプレミアムユーザーになるには、自分のサーバーにSwiftlyを導入するとトークンが発行され、プレミアムユーザーになることができます。\nすでに導入済みの場合やDMが送信されない場合は開発者(techfish_1)にお問い合わせください。", ephemeral=True)
            return

        self.db.update_voice(user_id, voice)
        await interaction.response.send_message(f"ボイスを {voice} に設定しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Premium(bot))