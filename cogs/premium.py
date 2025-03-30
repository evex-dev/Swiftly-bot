import sqlite3
import uuid
from discord.ext import commands
import discord
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

DB_PATH = "data/premium.db"
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")  # .envから読み込み、デフォルト値を設定

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
                    voice TEXT DEFAULT 'ja-JP-NanamiNeural'
                )
                """
            )

    def add_user(self, user_id: int):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO premium_users (user_id) VALUES (?)",
                (user_id,)
            )

    def get_user(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT voice FROM premium_users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()

    def update_voice(self, user_id: int, voice: str):
        with self.conn:
            self.conn.execute(
                "UPDATE premium_users SET voice = ? WHERE user_id = ?",
                (voice, user_id)
            )

    def remove_user(self, user_id: int):
        with self.conn:
            self.conn.execute(
                "DELETE FROM premium_users WHERE user_id = ?",
                (user_id,)
            )

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

        self.db.add_user(owner.id)  # オーナーをプレミアムユーザーとして登録
        try:
            await owner.send(
                "🎉 **Swiftlyの導入ありがとうございます！** 🎉\n\n"
                "導入の感謝として、**プレミアム機能**を有効化しました！\n\n"
                "✨ **プレミアム特典:**\n"
                "🔹 VC読み上げボイスの変更が可能\n"
                "🔹 ボイスは `/set_voice` コマンドで設定できます\n他にもたくさんの特典を追加する予定です！\n"
                "これからもSwiftlyをよろしくお願いします！\n\n"
                "🌐 **Swiftlyの共有もお願いします！**\n"
                "🔗 [公式サイト](https://sakana11.org/swiftly/)\n"
                "🔗 [Discordアプリページ](https://discord.com/discovery/applications/1310198598213963858)\n\n"
                "(プレミアム機能は完全無料です。有料ではありません。)"
            )
        except Exception as e:
            logger.error("Failed to send DM to guild owner: %s", e, exc_info=True)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        owner_id = guild.owner_id
        if owner_id:
            self.db.remove_user(owner_id)  # サーバー脱退時にオーナーのプレミアムを剥奪
            logger.info(f"Removed premium status for user {owner_id} as the guild was removed.")
            try:
                owner = await self.bot.fetch_user(owner_id)
                await owner.send(
                    "⚠️ **Swiftlyのサーバーからの削除を確認しました。** ⚠️\n\n"
                    "これに伴い、プレミアム機能が無効化されました。\n\n"
                    "再度Swiftlyを導入することで、プレミアム機能を再び有効化できます。\n"
                    "Swiftlyをご利用いただきありがとうございました！"
                )
            except Exception as e:
                logger.error("Failed to send DM to guild owner: %s", e, exc_info=True)

    @discord.app_commands.command(
        name="set_voice",
        description="読み上げボイスを設定します (プレミアムユーザーのみ)"
    )
    async def set_voice(self, interaction: discord.Interaction, voice: str):
        if voice not in ["ja-JP-KeitaNeural", "ja-JP-NanamiNeural"]:
            await interaction.response.send_message("無効なボイスです。\nボイスは以下から選べます。\n- ja-JP-KeitaNeural\n- ja-JP-NanamiNeural", ephemeral=True)
            return

        user_id = interaction.user.id
        user_data = self.db.get_user(user_id)
        if not user_data:
            await interaction.response.send_message("プレミアムユーザーのみがこの機能を使用できます。\nSwiftlyを自分のサーバーに導入することでプレミアム機能が使用できるようになります。\nすでに導入済みの場合は開発者(techfish_1)にお問い合わせください。", ephemeral=True)
            return

        self.db.update_voice(user_id, voice)
        await interaction.response.send_message(f"ボイスを {voice} に設定しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Premium(bot))