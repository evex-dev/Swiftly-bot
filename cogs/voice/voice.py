import asyncio
import os
import re
import tempfile
import uuid
from typing import Final, Optional, Dict, List
import logging
from pathlib import Path
from datetime import datetime, timedelta
import asyncpg
from dotenv import load_dotenv

import edge_tts
import discord
from discord.ext import commands
from discord import ClientException, ConnectionClosed  # ConnectionClosedをインポート

from cogs.premium.premium import PremiumDatabase

# .envファイルから環境変数を読み込む
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": "dictionary",
    "max_size": 10  # 最大接続数を10に制限
}

VOICE: Final[str] = "ja-JP-NanamiNeural"
MAX_MESSAGE_LENGTH: Final[int] = 75
RATE_LIMIT_SECONDS: Final[int] = 10
VOLUME_LEVEL: Final[float] = 0.6
TEMP_DIR: Final[Path] = Path(tempfile.gettempdir()) / "voice_tts"
RECONNECT_ATTEMPTS: Final[int] = 3  # 再接続試行回数
RECONNECT_DELAY: Final[int] = 5  # 再接続の間隔（秒）

PATTERNS: Final[Dict[str, str]] = {
    "url": r"http[s]?://[^\s<>]+",
    "user_mention": r"<@!?[0-9]+>",
    "role_mention": r"<@&[0-9]+>",
    "channel_mention": r"<#[0-9]+>"
}

ERROR_MESSAGES: Final[dict] = {
    "not_in_voice": "先にボイスチャンネルに参加してください。",
    "bot_not_in_voice": "ボイスチャンネルに参加していません。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "unexpected": "エラーが発生しました: {}"
}

SUCCESS_MESSAGES: Final[dict] = {
    "joined": "✅ {} に参加しました。",
    "left": "👋 ボイスチャンネルから退出しました。",
    "tts_played": "📢 メッセージを読み上げました: {}"
}

logger = logging.getLogger(__name__)

class TTSManager:
    """TTSの管理を行うクラス"""

    def __init__(self) -> None:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.temp_files: List[str] = []

    def cleanup_temp_files(self) -> None:
        """一時ファイルを削除"""
        for file in self.temp_files.copy():
            if os.path.exists(file):
                try:
                    os.remove(file)
                    self.temp_files.remove(file)
                except Exception as e:
                    logger.error("Error removing temp file: %s", e, exc_info=True)

    async def generate_audio(
        self,
        message: str,
        guild_id: int,
        voice: str
    ) -> Optional[str]:
        try:
            # メッセージが空か空白のみの場合は処理しない
            if not message or message.isspace():
                logger.warning("Empty message received for TTS, skipping audio generation")
                return None
                
            # 文字列が有効であることを確認（制御文字などを除去）
            message = ''.join(char for char in message if char.isprintable() or char.isspace())
            if not message:
                logger.warning("Message contains only non-printable characters, skipping audio generation")
                return None

            # guild_idとuuidをファイル名に含める
            unique_id = uuid.uuid4().hex
            temp_file = TEMP_DIR / f"{guild_id}_{unique_id}.mp3"
            temp_path = str(temp_file)
            self.temp_files.append(temp_path)

            # 最大試行回数を設定
            max_attempts = 2
            for attempt in range(max_attempts):
                try:
                    tts = edge_tts.Communicate(message, voice)
                    await tts.save(temp_path)
                    return temp_path
                except Exception as e:
                    if attempt < max_attempts - 1:
                        logger.warning(f"TTS generation failed on attempt {attempt+1}, retrying: {e}")
                        await asyncio.sleep(1)  # 少し待ってからリトライ
                    else:
                        raise  # 最大試行回数に達したら例外を再度投げる
        except Exception as e:
            logger.error(f"Error generating audio: {e}", exc_info=True)
            # 一時ファイルが作成されていたら削除
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    self.temp_files.remove(temp_path)
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up temp file after failed TTS: {cleanup_error}")
            return None

class DictionaryManager:
    """辞書管理クラス"""

    def __init__(self) -> None:
        self.pool = None

    async def initialize(self) -> None:
        """データベース接続プールを初期化"""
        self.pool = await asyncpg.create_pool(**DB_CONFIG)
        await self._create_table()

    async def _create_table(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS dictionary (word TEXT PRIMARY KEY, reading TEXT)"
            )

    async def add_word(self, word: str, reading: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO dictionary (word, reading) VALUES ($1, $2) ON CONFLICT (word) DO UPDATE SET reading = $2",
                word, reading
            )

    async def remove_word(self, word: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM dictionary WHERE word = $1",
                word
            )

    async def get_reading(self, word: str) -> Optional[str]:
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT reading FROM dictionary WHERE word = $1",
                word
            )
            return result["reading"] if result else None

    async def list_words(self, limit: int, offset: int) -> List[tuple]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT word, reading FROM dictionary LIMIT $1 OFFSET $2",
                limit, offset
            )
            return [(row["word"], row["reading"]) for row in rows]

    async def close(self) -> None:
        """接続プールを閉じる"""
        if self.pool:
            await self.pool.close()

class MessageProcessor:
    """メッセージの処理を行うクラス"""

    @staticmethod
    def sanitize_message(text: str) -> str:
        result = text
        
        # 絵文字・スタンプのパターン (<:name:id> または <a:name:id>)
        emoji_pattern = r"<a?:[a-zA-Z0-9_]+:[0-9]+>"
        result = re.sub(emoji_pattern, "スタンプ", result)
        
        # その他のパターン処理
        for pattern_name, pattern in PATTERNS.items():
            if pattern_name == "url":
                result = re.sub(pattern, "URL省略", result)
            else:
                result = re.sub(pattern, "メンション省略", result)
        return result

    @staticmethod
    def limit_message(message: str) -> str:
        if len(message) > MAX_MESSAGE_LENGTH:
            return message[:MAX_MESSAGE_LENGTH] + "省略"
        return message

    @staticmethod
    async def process_message(
        message: str,
        attachments: List[discord.Attachment] = None,
        dictionary: DictionaryManager = None
    ) -> str:
        result = MessageProcessor.sanitize_message(message)
        result = MessageProcessor.limit_message(result)
        if dictionary:
            for word in result.split():
                reading = await dictionary.get_reading(word)
                if reading:
                    result = result.replace(word, reading)
        if attachments:
            result += f" {len(attachments)}枚の画像"
        return result

class GuildTTS:
    """Guildごとの音声再生状態を管理するクラス"""

    def __init__(self, channel_id: int, voice_client: discord.VoiceClient, text_channel_id: int) -> None:
        self.channel_id = channel_id
        self.voice_client = voice_client
        self.text_channel_id = text_channel_id    # 追加: /joinが実行されたテキストチャンネルID
        self.tts_queue: List[Dict[str, any]] = []  # メッセージだけでなく、ユーザーIDとボイス情報も格納
        self.lock = asyncio.Lock()
        self.reconnecting = False  # 再接続中かどうかのフラグ

class VoiceState:
    """複数ギルド・複数チャンネルに対応した状態管理クラス"""

    def __init__(self) -> None:
        self.guilds: Dict[int, GuildTTS] = {}
        self.tts_manager = TTSManager()
        self.premium_db = None  # PremiumDatabaseのインスタンス (非同期初期化)

    async def initialize(self) -> None:
        """状態管理の初期化"""
        self.premium_db = await PremiumDatabase.create()  # 非同期でPremiumDatabaseを作成

    async def reconnect_voice(self, guild_id: int, bot) -> bool:
        """ボイス接続が切断された場合に再接続を試みる"""
        guild_state = self.guilds.get(guild_id)
        if not guild_state or guild_state.reconnecting:
            return False

        guild_state.reconnecting = True
        
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                logger.error(f"Guild {guild_id} not found during reconnection attempt")
                return False
                
            voice_channel = guild.get_channel(guild_state.channel_id)
            if not voice_channel:
                logger.error(f"Voice channel {guild_state.channel_id} not found during reconnection attempt")
                return False
                
            for attempt in range(RECONNECT_ATTEMPTS):
                try:
                    logger.info(f"Attempting to reconnect to voice channel in guild {guild_id} (attempt {attempt+1}/{RECONNECT_ATTEMPTS})")
                    
                    # 古い接続をクリーンアップ
                    old_voice_client = guild_state.voice_client
                    if old_voice_client and old_voice_client.is_connected():
                        try:
                            await old_voice_client.disconnect(force=True)
                        except Exception as e:
                            logger.warning(f"Error disconnecting old voice client: {e}")
                    
                    # 新しい接続を確立
                    new_voice_client = await voice_channel.connect()
                    
                    # 自己ミュート状態に設定
                    await new_voice_client.guild.change_voice_state(
                        channel=new_voice_client.channel,
                        self_deaf=True
                    )
                    
                    # 状態を更新
                    guild_state.voice_client = new_voice_client
                    
                    logger.info(f"Successfully reconnected to voice channel in guild {guild_id}")
                    return True
                    
                except (ClientException, ConnectionClosed) as e:
                    logger.warning(f"Reconnection attempt {attempt+1} failed: {e}")
                    if attempt < RECONNECT_ATTEMPTS - 1:
                        await asyncio.sleep(RECONNECT_DELAY)
                    else:
                        logger.error(f"All reconnection attempts failed for guild {guild_id}")
                        # 再接続に失敗した場合は状態をクリーンアップ
                        del self.guilds[guild_id]
                        return False
        except Exception as e:
            logger.error(f"Unexpected error during voice reconnection: {e}", exc_info=True)
            return False
        finally:
            if guild_id in self.guilds:
                self.guilds[guild_id].reconnecting = False
        
        return False

    async def play_tts(
        self,
        guild_id: int,
        message: str,
        user_id: Optional[int] = None,
        voice: Optional[str] = None
    ) -> None:
        guild_state = self.guilds.get(guild_id)
        if not guild_state:
            return

        voice_client = guild_state.voice_client
        
        # ボイスクライアントが接続されていない場合は処理しない
        if not voice_client or not voice_client.is_connected():
            return

        # ボイスが指定されていない場合は、プレミアムユーザーのボイスまたはデフォルトボイスを使用
        if voice is None:
            user_data = await self.premium_db.get_user(user_id) if user_id else None
            voice = user_data[0] if user_data and len(user_data) > 0 else VOICE

        temp_path = await self.tts_manager.generate_audio(message, guild_id, voice)
        if not temp_path:
            return

        def after_playing(error: Optional[Exception]) -> None:
            if error:
                logger.error("Error playing audio: %s", error, exc_info=True)
                # ConnectionClosedエラーを検出して再接続ロジックをトリガー
                if isinstance(error, ConnectionClosed):
                    # guild_idがまだ有効か確認してから再接続
                    if guild_id in self.guilds:
                        try:
                            asyncio.create_task(self._handle_connection_closed(guild_id))
                        except Exception as e:
                            logger.error(f"Error scheduling reconnection: {e}", exc_info=True)
            
            async def play_next():
                # guild_idがまだ有効か確認
                if guild_id in self.guilds and self.guilds[guild_id].voice_client.is_connected():
                    async with guild_state.lock:
                        if guild_state.tts_queue:
                            next_item = guild_state.tts_queue.pop(0)
                            next_message = next_item["message"]
                            next_user_id = next_item.get("user_id")
                            next_voice = next_item.get("voice")
                            await self.play_tts(guild_id, next_message, next_user_id, next_voice)
            
            try:
                asyncio.run_coroutine_threadsafe(play_next(), voice_client.loop)
            except Exception as e:
                logger.error(f"Error running play_next coroutine: {e}", exc_info=True)

        try:
            voice_client.play(
                discord.FFmpegPCMAudio(
                    temp_path,
                    options=f"-filter:a 'volume={VOLUME_LEVEL}'"
                ),
                after=after_playing
            )
        except Exception as e:
            logger.error(f"Error starting voice playback: {e}", exc_info=True)
            # 再生中にエラーが発生した場合も再接続を試みる
            if isinstance(e, ConnectionClosed):
                if guild_id in self.guilds:
                    try:
                        asyncio.create_task(self._handle_connection_closed(guild_id))
                    except Exception as ex:
                        logger.error(f"Error scheduling reconnection: {ex}", exc_info=True)

    async def _handle_connection_closed(self, guild_id: int):
        """ConnectionClosedエラーを処理し、必要に応じて再接続を試みる"""
        logger.warning(f"Voice connection closed unexpectedly for guild {guild_id}, attempting to reconnect")
        # guild_idがまだ有効か確認
        if guild_id not in self.guilds:
            logger.warning(f"Guild {guild_id} not found in self.guilds during reconnection handling")
            return
        # Voice.botへの参照を取得するため、一時的な回避策としてcogからbotを取得
        for cog in self.guilds[guild_id].voice_client.client.cogs.values():
            if isinstance(cog, Voice):
                success = await self.reconnect_voice(guild_id, cog.bot)
                if success and guild_id in self.guilds:
                    # 再接続に成功した場合、キューに残っているメッセージを処理
                    guild_state = self.guilds[guild_id]
                    async with guild_state.lock:
                        if guild_state.tts_queue:
                            next_item = guild_state.tts_queue[0]  # キューから削除せずに次のアイテムを取得
                            guild_state.tts_queue.pop(0)  # キューから削除
                            await self.play_tts(
                                guild_id, 
                                next_item["message"], 
                                next_item.get("user_id"),
                                next_item.get("voice")
                            )
                break

class Voice(commands.Cog):
    """音声機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.state = VoiceState()
        self._last_uses: Dict[int, datetime] = {}
        self.dictionary = DictionaryManager()

    async def cog_load(self) -> None:
        """Cogがロードされたときに呼び出される"""
        await self.dictionary.initialize()
        await self.state.initialize()

    async def cog_unload(self) -> None:
        """Cogがアンロードされたときに呼び出される"""
        self.state.tts_manager.cleanup_temp_files()
        for guild_state in self.state.guilds.values():
            if guild_state.voice_client.is_connected():
                await guild_state.voice_client.disconnect()
        await self.dictionary.close()  # 接続プールを閉じる

    def _check_rate_limit(
        self,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            diff = now - self._last_uses[user_id]
            if diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(diff.total_seconds())
                return True, remaining
        return False, None

    async def _send_migration_message(self, interaction: discord.Interaction) -> None:
        """機能移行メッセージを送信"""
        await interaction.response.send_message(
            "この機能はSwiftly読み上げ専用botに移行しました。読み上げ機能を使用するにはこのbotを導入してください。"
            "https://discord.com/oauth2/authorize?client_id=1371465579780767824",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="join",
        description="ボイスチャンネルに参加します"
    )
    async def join(
        self,
        interaction: discord.Interaction
    ) -> None:
        await self._send_migration_message(interaction)

    @discord.app_commands.command(
        name="leave",
        description="ボイスチャンネルから退出します"
    )
    async def leave(
        self,
        interaction: discord.Interaction
    ) -> None:
        await self._send_migration_message(interaction)

    @discord.app_commands.command(
        name="vc-tts",
        description="メッセージを読み上げます"
    )
    async def vc_tts(
        self,
        interaction: discord.Interaction,
        message: str
    ) -> None:
        await self._send_migration_message(interaction)

    @discord.app_commands.command(
        name="dictionary_add",
        description="辞書に単語を追加します"
    )
    async def dictionary_add(
        self,
        interaction: discord.Interaction,
        word: str,
        reading: str
    ) -> None:
        await self._send_migration_message(interaction)

    @discord.app_commands.command(
        name="dictionary_remove",
        description="辞書から単語を削除します"
    )
    async def dictionary_remove(
        self,
        interaction: discord.Interaction,
        word: str
    ) -> None:
        await self._send_migration_message(interaction)

    @discord.app_commands.command(
        name="dictionary_list",
        description="辞書の単語をリストします"
    )
    async def dictionary_list(
        self,
        interaction: discord.Interaction,
        page: int = 1
    ) -> None:
        await self._send_migration_message(interaction)

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ) -> None:
        # メッセージ処理を無効化
        pass

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ) -> None:
        # ボイス状態更新処理を無効化
        pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Voice(bot))
