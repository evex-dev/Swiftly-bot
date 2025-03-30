# Swiftly DiscordBot.
# Developed by: TechFish_1
# Standard library imports
import asyncio
import json
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Final, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import aiosqlite
import discord
import dotenv
from discord.ext import commands
from module.logger import LoggingCog
from module.prometheus import PrometheusCog


SHARD_COUNT: Final[int] = None
COMMAND_PREFIX: Final[str] = "sw!"
STATUS_UPDATE_COOLDOWN: Final[int] = 5
LOG_RETENTION_DAYS: Final[int] = 7

PATHS: Final[dict] = {
    "log_dir": Path("./log"),
    "db": Path("data/prohibited_channels.db"),
    "user_count": Path("data/user_count.json"),
    "cogs_dir": Path("./cogs")
}

ERROR_MESSAGES: Final[dict] = {
    "command_error": "エラーが発生しました",
    "prohibited_channel": "このチャンネルではコマンドの実行が禁止されています。",
    "db_error": "DBエラーが発生しました: {}"
}

LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logger = logging.getLogger(__name__)

class CogReloader(FileSystemEventHandler):
    """Cogファイルの変更を監視し、自動リロードを行うハンドラ"""

    def __init__(self, bot: 'SwiftlyBot') -> None:
        self.bot = bot
        self._reload_lock = asyncio.Lock()
        self._last_reload: Dict[str, float] = {}
        self.RELOAD_COOLDOWN = 2.0  # リロードのクールダウン時間（秒）

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.py'):
            file_path = Path(event.src_path)
            if file_path.parent.name == "cogs":
                future = asyncio.run_coroutine_threadsafe(
                    self._handle_cog_change(file_path),
                    self.bot.loop
                )
                try:
                    future.result()  # エラーハンドリングのため結果を待つ
                except Exception as e:
                    logger.error("Error in cog reload: %s", e, exc_info=True)

    async def _handle_cog_change(self, file_path: Path) -> None:
        cog_name = f"cogs.{file_path.stem}"
        current_time = time.time()

        # クールダウンチェック
        if cog_name in self._last_reload:
            if current_time - self._last_reload[cog_name] < self.RELOAD_COOLDOWN:
                return

        async with self._reload_lock:
            try:
                # 既存のCogをアンロード
                if cog_name in [ext for ext in self.bot.extensions]:
                    await self.bot.unload_extension(cog_name)

                # Cogを再読み込み
                await self.bot.load_extension(cog_name)
                self._last_reload[cog_name] = current_time
                logger.info("Reloaded: %s", cog_name)

                # コマンドを再同期
                await self.bot.tree.sync()
                logger.info("Commands synced after reloading: %s", cog_name)
            except Exception as e:
                logger.error("Failed to reload %s: %s", cog_name, e, exc_info=True)

class DatabaseManager:
    """DB操作を管理するクラス"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """DBを初期化"""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS prohibited_channels (
                guild_id TEXT,
                channel_id TEXT,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await self._connection.commit()

    async def cleanup(self) -> None:
        """DB接続を閉じる"""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def is_channel_prohibited(
        self,
        guild_id: int,
        channel_id: int
    ) -> bool:
        try:
            if not self._connection:
                await self.initialize()

            async with self._connection.execute(
                """
                SELECT 1 FROM prohibited_channels
                WHERE guild_id = ? AND channel_id = ?
                """,
                (str(guild_id), str(channel_id))
            ) as cursor:
                return bool(await cursor.fetchone())

        except Exception as e:
            logger.error("Database error: %s", e, exc_info=True)
            return False

class UserCountManager:
    """ユーザー数管理を行うクラス"""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_update = 0
        self._cache: Dict[str, Any] = {}

    def _read_count(self) -> int:
        """ファイルからユーザー数を読み込み"""
        try:
            if self.file_path.exists():
                data = json.loads(self.file_path.read_text(encoding="utf-8"))
                return data.get("total_users", 0)
            return 0
        except Exception as e:
            logger.error("Error reading user count: %s", e, exc_info=True)
            return 0

    def _write_count(self, count: int) -> None:
        """ユーザー数をファイルに書き込み"""
        try:
            self.file_path.write_text(
                json.dumps(
                    {"total_users": count},
                    ensure_ascii=False,
                    indent=4
                ),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error("Error writing user count: %s", e, exc_info=True)

    def get_count(self) -> int:
        """現在のユーザー数を取得"""
        return self._read_count()

    def update_count(self, count: int) -> None:
        self._write_count(count)
        self._last_update = time.time()

    def should_update(self) -> bool:
        """更新が必要かどうかを判定"""
        return time.time() - self._last_update >= STATUS_UPDATE_COOLDOWN

class SwiftlyBot(commands.AutoShardedBot):
    """Swiftlyボットのメインクラス"""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            shard_count=SHARD_COUNT
        )

        self.db = DatabaseManager(PATHS["db"])
        self.user_count = UserCountManager(PATHS["user_count"])
        self._setup_logging()

        # ファイル監視の設定
        self.cog_reloader = CogReloader(self)
        self.observer = Observer()

    def _setup_logging(self) -> None:
        """ロギングの設定"""
        PATHS["log_dir"].mkdir(exist_ok=True)

        # コンソール出力用のハンドラを追加
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S'))

        # 共通のログハンドラ設定
        handlers = []
        for name, level in [("logs", logging.INFO), ("commands", logging.INFO)]:
            handler = TimedRotatingFileHandler(
                PATHS["log_dir"] / f"{name}.log",
                when="midnight",
                interval=1,
                backupCount=LOG_RETENTION_DAYS,
                encoding="utf-8"
            )
            handler.setLevel(level)
            handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S'))
            handlers.append(handler)

        # ボットのロガー設定
        logger.setLevel(logging.INFO)
        for handler in handlers:
            logger.addHandler(handler)
        logger.addHandler(console_handler)

        # LoggingCog用のロガー設定
        bot_logger = logging.getLogger("bot")
        bot_logger.setLevel(logging.INFO)
        for handler in handlers:
            bot_logger.addHandler(handler)
        bot_logger.addHandler(console_handler)

        # Discordのロガー設定
        discord_logger = logging.getLogger("discord")
        discord_logger.setLevel(logging.INFO)
        for handler in handlers:
            discord_logger.addHandler(handler)
        discord_logger.addHandler(console_handler)

        # aiosqliteのロガーレベルをINFOに設定
        aiosqlite_logger = logging.getLogger("aiosqlite")
        aiosqlite_logger.setLevel(logging.INFO)
        for handler in handlers:
            aiosqlite_logger.addHandler(handler)
        aiosqlite_logger.addHandler(console_handler)

        # PILのロガーレベルをINFOに設定
        pil_logger = logging.getLogger("PIL")
        pil_logger.setLevel(logging.INFO)
        for handler in handlers:
            pil_logger.addHandler(handler)
        pil_logger.addHandler(console_handler)

    async def setup_hook(self) -> None:
        """ボットのセットアップ処理"""
        await self.db.initialize()
        await self._load_extensions()

        # ファイル監視を開始
        self.observer.schedule(self.cog_reloader, str(PATHS["cogs_dir"]), recursive=False)
        self.observer.start()
        logger.info("Started watching cogs directory for changes")

        await self.add_cog(LoggingCog(self))  # LoggingCogを追加
        await self.add_cog(PrometheusCog(self))
        await self.tree.sync()

    async def _load_extensions(self) -> None:
        """Cogを読み込み"""
        for file in PATHS["cogs_dir"].glob("*.py"):
            if file.stem == "__init__":
                continue

            try:
                await self.load_extension(f"cogs.{file.stem}")
                logger.info("Loaded: cogs.%s", file.stem)
            except Exception as e:
                logger.error("Failed to load: cogs.%s - %s", file.stem, e, exc_info=True)

    async def update_presence(self) -> None:
        """ステータスを更新"""
        while True:
            await self.change_presence(
                activity=discord.Game(
                    name=f"メンテナンス中...(詳しくは自己紹介欄を確認)",
                )
            )
            await asyncio.sleep(300)  # 5分ごとに更新


    async def count_unique_users(self) -> None:
        """ユニークユーザー数を集計"""
        unique_users: Set[int] = set()
        for guild in self.guilds:
            unique_users.update(member.id for member in guild.members)

        count = len(unique_users)
        logger.info("Unique user count: %s", count)
        self.user_count.update_count(count)

    async def on_ready(self) -> None:
        """準備完了時の処理"""
        logger.info("Logged in as %s", self.user)
        await self.count_unique_users()
        await self.update_presence()  # on_readyで一度だけ呼び出す

    async def on_member_join(self, _) -> None:
        """メンバー参加時の処理"""
        await self.count_unique_users()

    async def on_member_remove(self, _) -> None:
        """メンバー退出時の処理"""
        await self.count_unique_users()

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ) -> None:
        """アプリケーションコマンドエラー時の処理"""
        logger.error("App command error: %s", error, exc_info=True)
        await interaction.response.send_message(
            ERROR_MESSAGES["command_error"],
            ephemeral=True
        )

    async def check_command_permissions(
        self,
        ctx: commands.Context
    ) -> bool:
        if not ctx.guild:
            return True

        if ctx.command and ctx.command.name == "set_mute_channel":
            return True

        is_prohibited = await self.db.is_channel_prohibited(
            ctx.guild.id,
            ctx.channel.id
        )
        if is_prohibited:
            await ctx.send(ERROR_MESSAGES["prohibited_channel"])
            return False
        return True

    async def check_slash_command(
        self,
        interaction: discord.Interaction
    ) -> bool:
        # DEV_USER_IDが設定されている場合、そのユーザーのみコマンドを実行可能
        dev_user_id = os.getenv("DEV_USER_ID")
        if dev_user_id and str(interaction.user.id) != dev_user_id:
            await interaction.response.send_message(
                "このコマンドは開発者のみが実行できます。",
                ephemeral=True
            )
            return False

        if not interaction.guild:
            return True

        if (interaction.command and
            interaction.command.name == "set_mute_channel"):
            return True

        is_prohibited = await self.db.is_channel_prohibited(
            interaction.guild_id,
            interaction.channel_id
        )
        if is_prohibited:
            await interaction.response.send_message(
                ERROR_MESSAGES["prohibited_channel"],
                ephemeral=True
            )
            return False
        return True

def main() -> None:
    """メイン処理"""
    # 環境変数の読み込み
    dotenv.load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN not found in .env file")

    # ボットの起動
    bot = SwiftlyBot()
    bot.tree.interaction_check = bot.check_slash_command
    bot.check(bot.check_command_permissions)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(bot.start(token))
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error("Bot crashed: %s", e, exc_info=True)
    finally:
        # ファイル監視を停止
        bot.observer.stop()
        bot.observer.join()
        loop.run_until_complete(bot.db.cleanup())

if __name__ == "__main__":
    main()
