import asyncpg
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import logging
from datetime import datetime, timedelta

load_dotenv()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = "premium"
CONN_STR = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class PremiumDatabase:
    # 非同期初期化用のファクトリメソッド
    @classmethod
    async def create(cls):
        self = cls.__new__(cls)
        self.pool = await asyncpg.create_pool(CONN_STR)
        await self._create_table()
        return self

    async def _create_table(self):
        await self.pool.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id BIGINT PRIMARY KEY,
                voice TEXT DEFAULT 'ja-JP-NanamiNeural'
            )
            """
        )

    async def add_user(self, user_id: int):
        await self.pool.execute(
            "INSERT INTO premium_users (user_id, voice) VALUES ($1, 'ja-JP-NanamiNeural') ON CONFLICT (user_id) DO UPDATE SET voice = EXCLUDED.voice",
            user_id
        )

    async def get_user(self, user_id: int):
        return await self.pool.fetchrow(
            "SELECT voice FROM premium_users WHERE user_id = $1",
            user_id
        )

    async def update_voice(self, user_id: int, voice: str):
        await self.pool.execute(
            "UPDATE premium_users SET voice = $1 WHERE user_id = $2",
            voice, user_id
        )

    async def remove_user(self, user_id: int):
        await self.pool.execute(
            "DELETE FROM premium_users WHERE user_id = $1",
            user_id
        )

class Premium(commands.Cog):
    """プレミアム機能を管理するクラス"""

    def __init__(self, bot: commands.Bot, db: PremiumDatabase):
        self.bot = bot
        self.db = db

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        owner = guild.owner
        if owner is None:
            try:
                owner = await self.bot.fetch_user(guild.owner_id)
            except Exception as e:
                logger.error("Failed to fetch guild owner: %s", e, exc_info=True)
                return

        await self.db.add_user(owner.id)
        try:
            await owner.send(
                "🎉 **Swiftlyの導入ありがとうございます！** 🎉\n\n"
                "導入の感謝として、**プレミアム機能**を有効化しました！\n\n"
                "✨ **プレミアム特典:**\n"
                "🔹 NSFW画像判定機能(sw!nsfwdetect)が利用可能\n"
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
            await self.db.remove_user(owner_id)
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
    async def set_voice(self, interaction: discord.Interaction):
        options = [
            discord.SelectOption(label="Keita", value="ja-JP-KeitaNeural", description="男性ボイス"),
            discord.SelectOption(label="Nanami", value="ja-JP-NanamiNeural", description="女性ボイス")
        ]

        class VoiceSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="ボイスを選択してください",
                    min_values=1,
                    max_values=1,
                    options=options
                )

            async def callback(self, interaction: discord.Interaction):
                selected_voice = self.values[0]
                user_id = interaction.user.id
                user_data = await self.view.cog.db.get_user(user_id)
                if not user_data:
                    await interaction.response.send_message(
                        "プレミアムユーザーのみがこの機能を使用できます。\n"
                        "Swiftlyを自分のサーバーに導入することでプレミアム機能が使用できるようになります。\n"
                        "すでに導入済みの場合は開発者(techfish_1)にお問い合わせください。",
                        ephemeral=True
                    )
                    return

                await self.view.cog.db.update_voice(user_id, selected_voice)
                await interaction.response.send_message(f"ボイスを {selected_voice} に設定しました。", ephemeral=True)

        class VoiceSelectView(discord.ui.View):
            def __init__(self, cog):
                super().__init__()
                self.cog = cog
                self.add_item(VoiceSelect())

        await interaction.response.send_message(
            "以下からボイスを選択してください。",
            view=VoiceSelectView(self),
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    db = await PremiumDatabase.create()
    await bot.add_cog(Premium(bot, db))