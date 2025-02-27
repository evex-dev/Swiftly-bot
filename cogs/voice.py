import asyncio
import os
import re
import tempfile
from typing import Final, Optional, Dict, List
import logging
from pathlib import Path
from datetime import datetime, timedelta

import edge_tts
import discord
from discord.ext import commands


VOICE: Final[str] = "ja-JP-NanamiNeural"
MAX_MESSAGE_LENGTH: Final[int] = 75
RATE_LIMIT_SECONDS: Final[int] = 10
VOLUME_LEVEL: Final[float] = 0.6
TEMP_DIR: Final[Path] = Path(tempfile.gettempdir()) / "voice_tts"

PATTERNS: Final[Dict[str, str]] = {
    "url": r"http[s]?://\S+",
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
        for file in self.temp_files:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    self.temp_files.remove(file)
                except Exception as e:
                    logger.error("Error removing temp file: %s", e, exc_info=True)

    async def generate_audio(
        self,
        message: str
    ) -> Optional[str]:
        try:
            temp_file = TEMP_DIR / f"{hash(message)}.mp3"
            temp_path = str(temp_file)
            self.temp_files.append(temp_path)

            tts = edge_tts.Communicate(message, VOICE)
            await tts.save(temp_path)
            return temp_path

        except Exception as e:
            logger.error("Error generating audio: %s", e, exc_info=True)
            return None

class MessageProcessor:
    """メッセージの処理を行うクラス"""

    @staticmethod
    def sanitize_message(text: str) -> str:
        result = text
        for pattern in PATTERNS.values():
            result = re.sub(pattern, "メンション省略", result)
        return result

    @staticmethod
    def limit_message(message: str) -> str:
        """メッセージを制限長に収める"""
        if len(message) > MAX_MESSAGE_LENGTH:
            return message[:MAX_MESSAGE_LENGTH] + "省略"
        return message

    @staticmethod
    def process_message(
        message: str,
        attachments: List[discord.Attachment] = None
    ) -> str:
        result = MessageProcessor.sanitize_message(message)
        result = MessageProcessor.limit_message(result)

        if attachments:
            image_count = len(attachments)
            result += f" {image_count}枚の画像"

        return result

class VoiceState:
    """ボイスの状態を管理するクラス"""

    def __init__(self) -> None:
        self.voice_clients: Dict[int, Dict[int, discord.VoiceClient]] = {}
        self.monitored_channels: Dict[int, int] = {}
        self.tts_queues: Dict[int, Dict[int, List[str]]] = {}
        self.locks: Dict[int, asyncio.Lock] = {}
        self.tts_manager = TTSManager()

    def get_lock(self, guild_id: int) -> asyncio.Lock:
        """ギルドのロックを取得"""
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    async def play_tts(
        self,
        guild_id: int,
        channel_id: int,
        message: str
    ) -> None:
        logger.info(f"Playing TTS in guild {guild_id}, channel {channel_id}: {message}")
        voice_client = self.voice_clients[guild_id][channel_id]
        temp_path = await self.tts_manager.generate_audio(message)
        if not temp_path:
            return

        def after_playing(error: Optional[Exception]) -> None:
            if error:
                logger.error("Error playing audio: %s", error, exc_info=True)

            # 次のメッセージを再生
            if (guild_id in self.tts_queues and
                channel_id in self.tts_queues[guild_id] and
                self.tts_queues[guild_id][channel_id]):
                next_message = self.tts_queues[guild_id][channel_id].pop(0)
                asyncio.run_coroutine_threadsafe(
                    self.play_tts(guild_id, channel_id, next_message),
                    voice_client.loop
                )

        voice_client.play(
            discord.FFmpegPCMAudio(
                temp_path,
                options=f"-filter:a 'volume={VOLUME_LEVEL}'"
            ),
            after=after_playing
        )

class Voice(commands.Cog):
    """音声機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.state = VoiceState()
        self._last_uses = {}

    def _check_rate_limit(
        self,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        """レート制限をチェック"""
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    @discord.app_commands.command(
        name="join",
        description="ボイスチャンネルに参加します"
    )
    async def join(
        self,
        interaction: discord.Interaction
    ) -> None:
        """ボイスチャンネル参加コマンド"""
        try:
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not member.voice:
                await interaction.response.send_message(
                    ERROR_MESSAGES["not_in_voice"],
                    ephemeral=True
                )
                return

            voice_channel = member.voice.channel
            guild_id = interaction.guild.id
            channel_id = voice_channel.id

            # レート制限のチェック
            is_limited, remaining = self._check_rate_limit(
                interaction.user.id
            )
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            # ボイスチャンネルに接続
            if (guild_id in self.state.voice_clients and
                channel_id in self.state.voice_clients[guild_id]):
                await self.state.voice_clients[guild_id][channel_id].move_to(
                    voice_channel
                )
            else:
                voice_client = await voice_channel.connect()
                if guild_id not in self.state.voice_clients:
                    self.state.voice_clients[guild_id] = {}
                self.state.voice_clients[guild_id][channel_id] = voice_client

            # ボットをミュート
            voice_client = self.state.voice_clients[guild_id][channel_id]
            await voice_client.guild.change_voice_state(
                channel=voice_client.channel,
                self_deaf=True
            )

            # チャンネルの監視を開始
            self.state.monitored_channels[guild_id] = interaction.channel.id

            # TTSキューを初期化
            if guild_id not in self.state.tts_queues:
                self.state.tts_queues[guild_id] = {}
            self.state.tts_queues[guild_id][channel_id] = []

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            await interaction.response.send_message(
                SUCCESS_MESSAGES["joined"].format(voice_channel.name)
            )

        except Exception as e:
            logger.error("Error in join command: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )

    @discord.app_commands.command(
        name="leave",
        description="ボイスチャンネルから退出します"
    )
    async def leave(
        self,
        interaction: discord.Interaction
    ) -> None:
        """ボイスチャンネル退出コマンド"""
        try:
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not member.voice:
                await interaction.response.send_message(
                    ERROR_MESSAGES["not_in_voice"],
                    ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            channel_id = member.voice.channel.id

            if (guild_id not in self.state.voice_clients or
                channel_id not in self.state.voice_clients[guild_id]):
                await interaction.response.send_message(
                    ERROR_MESSAGES["bot_not_in_voice"],
                    ephemeral=True
                )
                return

            # レート制限のチェック
            is_limited, remaining = self._check_rate_limit(
                interaction.user.id
            )
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            # ボイスチャンネルから切断
            await self.state.voice_clients[guild_id][channel_id].disconnect()
            del self.state.voice_clients[guild_id][channel_id]
            if not self.state.voice_clients[guild_id]:
                del self.state.voice_clients[guild_id]

            # 監視を停止
            if guild_id in self.state.monitored_channels:
                del self.state.monitored_channels[guild_id]

            # TTSキューをクリア
            if guild_id in self.state.tts_queues:
                if channel_id in self.state.tts_queues[guild_id]:
                    del self.state.tts_queues[guild_id][channel_id]
                if not self.state.tts_queues[guild_id]:
                    del self.state.tts_queues[guild_id]

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            await interaction.response.send_message(
                SUCCESS_MESSAGES["left"]
            )

        except Exception as e:
            logger.error("Error in leave command: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )

    @discord.app_commands.command(
        name="vc-tts",
        description="メッセージを読み上げます"
    )
    async def vc_tts(
        self,
        interaction: discord.Interaction,
        message: str
    ) -> None:
        try:
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not member.voice:
                await interaction.response.send_message(
                    ERROR_MESSAGES["not_in_voice"],
                    ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            channel_id = member.voice.channel.id

            if (guild_id not in self.state.voice_clients or
                channel_id not in self.state.voice_clients[guild_id]):
                await interaction.response.send_message(
                    ERROR_MESSAGES["bot_not_in_voice"],
                    ephemeral=True
                )
                return

            # レート制限のチェック
            is_limited, remaining = self._check_rate_limit(
                interaction.user.id
            )
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            # メッセージを処理
            processed_message = MessageProcessor.process_message(message)

            async with self.state.get_lock(guild_id):
                # キューにメッセージを追加
                self.state.tts_queues[guild_id][channel_id].append(
                    processed_message
                )

                # 再生中でなければ再生開始
                if not self.state.voice_clients[guild_id][channel_id].is_playing():
                    next_message = self.state.tts_queues[guild_id][channel_id].pop(0)
                    await self.state.play_tts(
                        guild_id,
                        channel_id,
                        next_message
                    )

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            await interaction.response.send_message(
                SUCCESS_MESSAGES["tts_played"].format(processed_message)
            )

        except Exception as e:
            logger.error("Error in vc_tts command: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ) -> None:
        """ボイスチャンネルの状態変更イベントハンドラ"""
        try:
            # ボットだけになった場合は切断
            if voice_client := member.guild.voice_client:
                if len(voice_client.channel.members) == 1:
                    await voice_client.disconnect()
                    return

            guild_id = member.guild.id

            # 参加時の処理
            if before.channel is None and after.channel is not None:
                channel_id = after.channel.id
                if (guild_id in self.state.voice_clients and
                    channel_id in self.state.voice_clients[guild_id]):
                    message = f"{member.display_name}が参加しました。"
                    processed_message = MessageProcessor.process_message(message)

                    async with self.state.get_lock(guild_id):
                        self.state.tts_queues[guild_id][channel_id].append(
                            processed_message
                        )
                        if not self.state.voice_clients[guild_id][channel_id].is_playing():
                            next_message = self.state.tts_queues[guild_id][channel_id].pop(0)
                            await self.state.play_tts(
                                guild_id,
                                channel_id,
                                next_message
                            )

            # 退出時の処理
            elif before.channel is not None and after.channel is None:
                channel_id = before.channel.id
                if (guild_id in self.state.voice_clients and
                    channel_id in self.state.voice_clients[guild_id]):
                    message = f"{member.display_name}が退出しました。"
                    processed_message = MessageProcessor.process_message(message)

                    async with self.state.get_lock(guild_id):
                        self.state.tts_queues[guild_id][channel_id].append(
                            processed_message
                        )
                        if not self.state.voice_clients[guild_id][channel_id].is_playing():
                            next_message = self.state.tts_queues[guild_id][channel_id].pop(0)
                            await self.state.play_tts(
                                guild_id,
                                channel_id,
                                next_message
                            )

        except Exception as e:
            logger.error(
                "Error in voice state update: %s",
                e,
                exc_info=True
            )

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ) -> None:
        """メッセージイベントハンドラ"""
        try:
            if message.author.bot:
                return

            guild_id = message.guild.id
            if (guild_id not in self.state.monitored_channels or
                message.channel.id != self.state.monitored_channels[guild_id]):
                return

            if not message.author.voice:
                return

            channel_id = message.author.voice.channel.id
            if (guild_id not in self.state.voice_clients or
                channel_id not in self.state.voice_clients[guild_id]):
                return

            processed_message = MessageProcessor.process_message(
                message.content,
                message.attachments
            )

            async with self.state.get_lock(guild_id):
                self.state.tts_queues[guild_id][channel_id].append(
                    processed_message
                )
                if not self.state.voice_clients[guild_id][channel_id].is_playing():
                    next_message = self.state.tts_queues[guild_id][channel_id].pop(0)
                    await self.state.play_tts(
                        guild_id,
                        channel_id,
                        next_message
                    )

        except Exception as e:
            logger.error(
                "Error in message handler: %s",
                e,
                exc_info=True
            )

    async def cog_unload(self) -> None:
        """Cogのアンロード時の処理"""
        # 一時ファイルの削除
        self.state.tts_manager.cleanup_temp_files()

        # ボイスクライアントの切断
        for guild_clients in self.state.voice_clients.values():
            for client in guild_clients.values():
                if client.is_connected():
                    await client.disconnect()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Voice(bot))
