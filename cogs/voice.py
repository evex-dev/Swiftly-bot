import asyncio
import os
import re
import tempfile

import edge_tts
import discord
from discord.ext import commands

VOICE = "ja-JP-NanamiNeural"  # Predefined voice


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}  # Track voice clients per guild and channel
        self.locks = {}  # Locks for each guild to prevent race conditions
        self.monitored_channels = {}  # Track monitored text channels per guild
        self.tts_queues = {}  # Queues for TTS messages per guild

    def sanitize_message(self, text: str) -> str:
        # Replace any URL with "URL省略"
        text = re.sub(r"http[s]?://\S+", "URL省略", text)
        # Replace any user mention with "メンション省略"
        text = re.sub(r"<@!?[0-9]+>", "メンション省略", text)
        # Replace role and channel mentions if needed
        text = re.sub(r"<@&[0-9]+>", "メンション省略", text)
        text = re.sub(r"<#[0-9]+>", "メンション省略", text)
        return text

    def limit_message(self, message: str) -> str:
        # 75文字を超える場合は、最初の75文字と「省略」とする
        if len(message) > 75:
            return message[:75] + "省略"
        return message

    async def play_tts(self, guild_id, channel_id, message):
        voice_client = self.voice_clients[guild_id][channel_id]

        # Generate TTS audio using edge_tts
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
            temp_filename = temp_audio_file.name

        tts = edge_tts.Communicate(message, VOICE)
        await tts.save(temp_filename)

        def after_playing(error):
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            # Play next message in the queue
            if self.tts_queues[guild_id][channel_id]:
                next_message = self.tts_queues[guild_id][channel_id].pop(0)
                asyncio.run_coroutine_threadsafe(self.play_tts(guild_id, channel_id, next_message), self.bot.loop)

        # Play the audio with volume reduced by 6%
        voice_client.play(discord.FFmpegPCMAudio(temp_filename, options="-filter:a 'volume=0.6'"), after=after_playing)

    @discord.app_commands.command(name="join", description="ボイスチャンネルに参加します")
    async def join(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not member.voice:
            embed = discord.Embed(
                description="先にボイスチャンネルに参加してください。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        voice_channel = member.voice.channel
        guild_id = interaction.guild.id
        channel_id = voice_channel.id

        try:
            if guild_id in self.voice_clients and channel_id in self.voice_clients[guild_id]:
                await self.voice_clients[guild_id][channel_id].move_to(voice_channel)
            else:
                voice_client = await voice_channel.connect()
                if guild_id not in self.voice_clients:
                    self.voice_clients[guild_id] = {}
                self.voice_clients[guild_id][channel_id] = voice_client

            # Mute the bot
            voice_client = self.voice_clients[guild_id][channel_id]
            await voice_client.guild.change_voice_state(channel=voice_client.channel, self_deaf=True)

            # Monitor the text channel where the join command was issued
            self.monitored_channels[guild_id] = interaction.channel.id

            # Initialize TTS queue for the guild and channel
            if guild_id not in self.tts_queues:
                self.tts_queues[guild_id] = {}
            self.tts_queues[guild_id][channel_id] = []

            embed = discord.Embed(
                description=f"✅ {voice_channel.name} に参加しました。",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
        except Exception as e:
            embed = discord.Embed(
                description=f"エラーが発生しました: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)

    @discord.app_commands.command(name="leave", description="ボイスチャンネルから退出します")
    async def leave(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not member.voice:
            embed = discord.Embed(
                description="ボイスチャンネルに参加していません。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        guild_id = interaction.guild.id
        voice_channel = member.voice.channel
        channel_id = voice_channel.id

        if guild_id not in self.voice_clients or channel_id not in self.voice_clients[guild_id]:
            embed = discord.Embed(
                description="ボイスチャンネルに参加していません。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        try:
            await self.voice_clients[guild_id][channel_id].disconnect()
            del self.voice_clients[guild_id][channel_id]
            if not self.voice_clients[guild_id]:
                del self.voice_clients[guild_id]

            # Stop monitoring the text channel
            if guild_id in self.monitored_channels:
                del self.monitored_channels[guild_id]

            # Clear TTS queue for the guild and channel
            if guild_id in self.tts_queues and channel_id in self.tts_queues[guild_id]:
                del self.tts_queues[guild_id][channel_id]
                if not self.tts_queues[guild_id]:
                    del self.tts_queues[guild_id]

            embed = discord.Embed(
                description="👋 ボイスチャンネルから退出しました。",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
        except Exception as e:
            embed = discord.Embed(
                description=f"エラーが発生しました: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)

    @discord.app_commands.command(name="vc-tts", description="メッセージを読み上げます")
    async def vc_tts(self, interaction: discord.Interaction, message: str):
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not member.voice:
            embed = discord.Embed(
                description="先にボイスチャンネルに参加してください。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        voice_channel = member.voice.channel
        guild_id = interaction.guild.id
        channel_id = voice_channel.id

        if guild_id not in self.voice_clients or channel_id not in self.voice_clients[guild_id]:
            embed = discord.Embed(
                description="ボイスチャンネルに参加していません。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        # Sanitize the message to replace URLs and mentions
        sanitized_message = self.sanitize_message(message)
        #75文字を超える場合は、先頭75文字と「省略」に変更
        sanitized_message = self.limit_message(sanitized_message)

        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()

        async with self.locks[guild_id]:
            try:
                # Add message to the queue
                self.tts_queues[guild_id][channel_id].append(sanitized_message)

                # If not currently playing, start playing
                if not self.voice_clients[guild_id][channel_id].is_playing():
                    next_message = self.tts_queues[guild_id][channel_id].pop(0)
                    await self.play_tts(guild_id, channel_id, next_message)

                embed = discord.Embed(
                    description=f"📢 メッセージを読み上げました: {sanitized_message}",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=False)
            except Exception as e:
                embed = discord.Embed(
                    description=f"エラーが発生しました: {e}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=False)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        voice_client = member.guild.voice_client
        if voice_client:
            if len(voice_client.channel.members) == 1:  # ボットだけが残っている場合
                await voice_client.disconnect()

        # 新しく参加したメンバーがいる場合
        if before.channel is None and after.channel is not None:
            guild_id = member.guild.id
            channel_id = after.channel.id
            if guild_id in self.voice_clients and channel_id in self.voice_clients[guild_id]:
                message = f"{member.display_name}が参加しました。"
                sanitized_message = self.sanitize_message(message)
                sanitized_message = self.limit_message(sanitized_message)
                if guild_id not in self.locks:
                    self.locks[guild_id] = asyncio.Lock()
                async with self.locks[guild_id]:
                    try:
                        self.tts_queues[guild_id][channel_id].append(sanitized_message)
                        if not self.voice_clients[guild_id][channel_id].is_playing():
                            next_message = self.tts_queues[guild_id][channel_id].pop(0)
                            await self.play_tts(guild_id, channel_id, next_message)
                    except Exception as e:
                        print(f"エラーが発生しました: {e}")
        # 退出したメンバーがいる場合
        elif before.channel is not None and after.channel is None:
            guild_id = member.guild.id
            channel_id = before.channel.id
            if guild_id in self.voice_clients and channel_id in self.voice_clients[guild_id]:
                message = f"{member.display_name}が退出しました。"
                sanitized_message = self.sanitize_message(message)
                sanitized_message = self.limit_message(sanitized_message)
                if guild_id not in self.locks:
                    self.locks[guild_id] = asyncio.Lock()
                async with self.locks[guild_id]:
                    try:
                        self.tts_queues[guild_id][channel_id].append(sanitized_message)
                        if not self.voice_clients[guild_id][channel_id].is_playing():
                            next_message = self.tts_queues[guild_id][channel_id].pop(0)
                            await self.play_tts(guild_id, channel_id, next_message)
                    except Exception as e:
                        print(f"エラーが発生しました: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        guild_id = message.guild.id
        if guild_id in self.monitored_channels and message.channel.id == self.monitored_channels[guild_id]:
            if not message.author.voice:
                return
            voice_channel = message.author.voice.channel
            channel_id = voice_channel.id

            if guild_id in self.voice_clients and channel_id in self.voice_clients[guild_id]:
                if guild_id not in self.locks:
                    self.locks[guild_id] = asyncio.Lock()

                # Sanitize the message to replace URLs and mentions
                sanitized_message = self.sanitize_message(message.content)
                # 75文字を超える場合は、先頭75文字と「省略」に変更
                sanitized_message = self.limit_message(sanitized_message)

                # 画像が含まれている場合、画像の枚数を追加
                if message.attachments:
                    image_count = len(message.attachments)
                    sanitized_message += f" {image_count}枚の画像"

                async with self.locks[guild_id]:
                    try:
                        # Add message to the queue
                        self.tts_queues[guild_id][channel_id].append(sanitized_message)

                        # If not currently playing, start playing
                        if not self.voice_clients[guild_id][channel_id].is_playing():
                            next_message = self.tts_queues[guild_id][channel_id].pop(0)
                            await self.play_tts(guild_id, channel_id, next_message)
                    except Exception as e:
                        print(f"エラーが発生しました: {e}")


async def setup(bot):
    await bot.add_cog(Voice(bot))
