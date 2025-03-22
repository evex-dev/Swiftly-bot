import asyncio
import os
import re
import tempfile
import uuid
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
        guild_id: int
    ) -> Optional[str]:
        try:
            # guild_idとuuidをファイル名に含める
            unique_id = uuid.uuid4().hex
            temp_file = TEMP_DIR / f"{guild_id}_{unique_id}.mp3"
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
            result += f" {len(attachments)}枚の画像"
        return result

class GuildTTS:
    """Guildごとの音声再生状態を管理するクラス"""

    def __init__(self, channel_id: int, voice_client: discord.VoiceClient) -> None:
        self.channel_id = channel_id
        self.voice_client = voice_client
        self.tts_queue: List[str] = []
        self.lock = asyncio.Lock()

class VoiceState:
    """複数ギルド・複数チャンネルに対応した状態管理クラス"""

    def __init__(self) -> None:
        self.guilds: Dict[int, GuildTTS] = {}
        self.tts_manager = TTSManager()

    async def play_tts(
        self,
        guild_id: int,
        message: str
    ) -> None:
        guild_state = self.guilds.get(guild_id)
        if not guild_state:
            return

        voice_client = guild_state.voice_client
        temp_path = await self.tts_manager.generate_audio(message, guild_id)
        if not temp_path:
            return

        def after_playing(error: Optional[Exception]) -> None:
            if error:
                logger.error("Error playing audio: %s", error, exc_info=True)
            async def play_next():
                if voice_client.is_connected():
                    async with guild_state.lock:
                        if guild_state.tts_queue:
                            next_message = guild_state.tts_queue.pop(0)
                            await self.play_tts(guild_id, next_message)
            asyncio.run_coroutine_threadsafe(play_next(), voice_client.loop)

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
        self._last_uses: Dict[int, datetime] = {}

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

    @discord.app_commands.command(
        name="join",
        description="ボイスチャンネルに参加します"
    )
    async def join(
        self,
        interaction: discord.Interaction
    ) -> None:
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

            is_limited, remaining = self._check_rate_limit(interaction.user.id)
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            if guild_id in self.state.guilds:
                # 既存の場合はチャンネル移動
                await self.state.guilds[guild_id].voice_client.move_to(voice_channel)
            else:
                voice_client = await voice_channel.connect()
                # ミュート状態に変更
                await voice_client.guild.change_voice_state(
                    channel=voice_client.channel,
                    self_deaf=True
                )
                self.state.guilds[guild_id] = GuildTTS(voice_channel.id, voice_client)

            self._last_uses[interaction.user.id] = datetime.now()
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
        try:
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not member.voice:
                await interaction.response.send_message(
                    ERROR_MESSAGES["not_in_voice"],
                    ephemeral=True
                )
                return

            guild_id = interaction.guild.id

            if guild_id not in self.state.guilds:
                await interaction.response.send_message(
                    ERROR_MESSAGES["bot_not_in_voice"],
                    ephemeral=True
                )
                return

            voice_client = self.state.guilds[guild_id].voice_client

            is_limited, remaining = self._check_rate_limit(interaction.user.id)
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            await voice_client.disconnect()
            del self.state.guilds[guild_id]
            self._last_uses[interaction.user.id] = datetime.now()

            await interaction.response.send_message(SUCCESS_MESSAGES["left"])

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
            if guild_id not in self.state.guilds:
                await interaction.response.send_message(
                    ERROR_MESSAGES["bot_not_in_voice"],
                    ephemeral=True
                )
                return

            is_limited, remaining = self._check_rate_limit(interaction.user.id)
            if is_limited:
                await interaction.response.send_message(
                    ERROR_MESSAGES["rate_limit"].format(remaining),
                    ephemeral=True
                )
                return

            processed_message = MessageProcessor.process_message(message)
            guild_state = self.state.guilds[guild_id]
            async with guild_state.lock:
                guild_state.tts_queue.append(processed_message)
                if not guild_state.voice_client.is_playing():
                    next_message = guild_state.tts_queue.pop(0)
                    await self.state.play_tts(guild_id, next_message)

            self._last_uses[interaction.user.id] = datetime.now()
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
    async def on_message(
        self,
        message: discord.Message
    ) -> None:
        try:
            if message.author.bot:
                return
            guild = message.guild
            if not guild or guild.id not in self.state.guilds:
                return
            processed_message = MessageProcessor.process_message(
                message.content,
                message.attachments
            )
            guild_state = self.state.guilds[guild.id]
            async with guild_state.lock:
                guild_state.tts_queue.append(processed_message)
                if not guild_state.voice_client.is_playing():
                    next_message = guild_state.tts_queue.pop(0)
                    await self.state.play_tts(guild.id, next_message)

        except Exception as e:
            logger.error("Error in message handler: %s", e, exc_info=True)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ) -> None:
        try:
            guild = member.guild
            guild_state = self.state.guilds.get(guild.id)
            if not guild_state:
                return

            voice_client = guild_state.voice_client
            # ボットのみになった場合は切断
            if voice_client and len(voice_client.channel.members) == 1:
                await voice_client.disconnect()
                del self.state.guilds[guild.id]
                return

            # 参加・退出時にTTSを再生
            if before.channel is None and after.channel is not None:
                msg = f"{member.display_name}が参加しました。"
            elif before.channel is not None and after.channel is None:
                msg = f"{member.display_name}が退出しました。"
            else:
                return

            processed_message = MessageProcessor.process_message(msg)
            async with guild_state.lock:
                guild_state.tts_queue.append(processed_message)
                if not voice_client.is_playing():
                    next_message = guild_state.tts_queue.pop(0)
                    await self.state.play_tts(guild.id, next_message)

        except Exception as e:
            logger.error("Error in voice state update: %s", e, exc_info=True)

    async def cog_unload(self) -> None:
        self.state.tts_manager.cleanup_temp_files()
        for guild_state in self.state.guilds.values():
            if guild_state.voice_client.is_connected():
                await guild_state.voice_client.disconnect()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Voice(bot))
