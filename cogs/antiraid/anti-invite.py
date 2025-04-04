import discord
from discord.ext import commands
import aiosqlite
import os
import asyncio
import re
from typing import Final, Optional, Set, Dict, Any, List
import aiohttp
from urllib.parse import urlparse
from pathlib import Path
from collections import deque
import json


INVITE_PATTERNS: Final[Set[str]] = {
    "discord.gg/",
    "discordapp.com/invite/",
    "discord.com/invite/"
}

URL_SHORTENERS: Final[Set[str]] = {
    "x.gd", "bit.ly", "tinyurl.com",
    "goo.gl", "is.gd", "ow.ly",
    "buff.ly", "00m.in"
}

ADMIN_ONLY_MESSAGE: Final[str] = "このコマンドはサーバー管理者のみ実行可能です。"
GUILD_ONLY_MESSAGE: Final[str] = "このコマンドはサーバー内でのみ使用可能です。"
INVITE_WARNING: Final[str] = "Discord招待リンクは禁止です。メッセージは削除されました。"

class AntiInvite(commands.Cog):
    """招待リンク自動削除機能"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.data_dir = Path(os.getcwd()) / "data"
        self.data_dir.mkdir(exist_ok=True)

        self.db_path = self.data_dir / "anti_invite.db"
        self.db_exempt_path = self.data_dir / "anti_invite_exempt.db"

        self._session: Optional[aiohttp.ClientSession] = None
        self._url_cache: deque[str] = deque(maxlen=1000)  # キャッシュの最大サイズを1000に設定
        
        # Automodルールの保存用データ
        self.automod_rules: Dict[int, str] = {}  # guild_id -> rule_id

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

        # メインDB
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    guild_id INTEGER PRIMARY KEY,
                    anti_invite_enabled INTEGER NOT NULL DEFAULT 0,
                    automod_rule_id TEXT
                )
            """)
            await db.commit()

        # 除外リストDB
        async with aiosqlite.connect(self.db_exempt_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, channel_id)
                )
            """)
            await db.commit()
            
        # 既存のAutomodルールIDを読み込む
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT guild_id, automod_rule_id FROM settings WHERE automod_rule_id IS NOT NULL") as cursor:
                async for row in cursor:
                    if row[1]:  # automod_rule_idが存在する場合
                        self.automod_rules[row[0]] = row[1]

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def set_setting(self, guild_id: int, enabled: bool, rule_id: Optional[str] = None) -> None:
        """サーバーごとの設定を保存"""
        async with aiosqlite.connect(self.db_path) as db:
            if rule_id is not None:
                await db.execute(
                    "INSERT OR REPLACE INTO settings (guild_id, anti_invite_enabled, automod_rule_id) VALUES (?, ?, ?)",
                    (guild_id, int(enabled), rule_id)
                )
                if rule_id:
                    self.automod_rules[guild_id] = rule_id
                elif guild_id in self.automod_rules:
                    del self.automod_rules[guild_id]
            else:
                await db.execute(
                    "INSERT OR REPLACE INTO settings (guild_id, anti_invite_enabled) VALUES (?, ?)",
                    (guild_id, int(enabled))
                )
            await db.commit()

    async def get_setting(self, guild_id: int) -> bool:
        """サーバーごとの設定を取得"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT anti_invite_enabled FROM settings WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row else False

    async def get_automod_rule(self, guild_id: int) -> Optional[str]:
        """サーバーに設定されているAutomodルールIDを取得"""
        if guild_id in self.automod_rules:
            return self.automod_rules[guild_id]
            
        # メモリにない場合はDBから読み込む
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT automod_rule_id FROM settings WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    self.automod_rules[guild_id] = row[0]
                    return row[0]
        return None

    async def get_exempt_channels(self, guild_id: int) -> List[int]:
        """除外チャンネルのリストを取得"""
        exempt_channels = []
        async with aiosqlite.connect(self.db_exempt_path) as db:
            async with db.execute(
                "SELECT channel_id FROM whitelist WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                async for row in cursor:
                    exempt_channels.append(row[0])
        return exempt_channels

    async def contains_invite(self, content: str) -> bool:
        # 直接の招待リンクチェック
        if any(pattern in content.lower() for pattern in INVITE_PATTERNS):
            return True

        # URLの抽出
        urls = re.findall(r"(https?://\S+)", content)
        if not urls:
            return False

        if not self._session:
            self._session = aiohttp.ClientSession()

        for url in urls:
            try:
                parsed = urlparse(url)
                if not parsed.hostname:
                    continue

                hostname = parsed.hostname.lower()
                if hostname not in URL_SHORTENERS:
                    continue

                # キャッシュチェック
                if url in self._url_cache:
                    return True

                # 短縮URLの展開
                try:
                    async with self._session.head(
                        url,
                        allow_redirects=True,
                        timeout=5
                    ) as response:
                        final_url = str(response.url)
                except Exception:
                    async with self._session.get(
                        url,
                        allow_redirects=True,
                        timeout=5
                    ) as response:
                        final_url = str(response.url)

                if any(pattern in final_url.lower() for pattern in INVITE_PATTERNS):
                    self._url_cache.append(url)  # キャッシュに追加
                    return True

            except Exception:
                continue

        return False

    @discord.app_commands.command(
        name="anti-invite",
        description="Discord招待リンクの自動削除を設定します。（デフォルトはdisable）"
    )
    @discord.app_commands.describe(action="設定する値（enable または disable）")
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="enable", value="enable"),
        discord.app_commands.Choice(name="disable", value="disable")
    ])
    async def anti_invite(self, interaction: discord.Interaction, action: str) -> None:
        """招待リンク自動削除の有効/無効を設定"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(ADMIN_ONLY_MESSAGE, ephemeral=True)
            return

        if not interaction.guild:
            await interaction.response.send_message(GUILD_ONLY_MESSAGE, ephemeral=True)
            return

        enabled = action.lower() == "enable"
        
        # Automodルールを作成/削除
        if enabled:
            rule_id = await self.create_automod_rule(interaction.guild.id)
            if not rule_id:
                await interaction.response.send_message("Automodルールの設定に失敗しました。", ephemeral=True)
                return
        else:
            # 既存のルールがあれば削除
            existing_rule_id = await self.get_automod_rule(interaction.guild.id)
            if existing_rule_id:
                await self.delete_automod_rule(interaction.guild.id, existing_rule_id)
            rule_id = None
        
        # 設定を保存
        await self.set_setting(interaction.guild.id, enabled, rule_id)

        embed = discord.Embed(
            title="Anti-Invite設定",
            description=f"このサーバーでの招待リンク自動削除は **{'有効' if enabled else '無効'}** になりました。",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(
        name="anti-invite-setting",
        description="禁止対象としないチャンネル（ホワリス）を設定します（複数指定可、最大10件）。"
    )
    async def anti_invite_setting(
        self,
        interaction: discord.Interaction,
        channel_1: Optional[discord.TextChannel] = None,
        channel_2: Optional[discord.TextChannel] = None,
        channel_3: Optional[discord.TextChannel] = None,
        channel_4: Optional[discord.TextChannel] = None,
        channel_5: Optional[discord.TextChannel] = None,
        channel_6: Optional[discord.TextChannel] = None,
        channel_7: Optional[discord.TextChannel] = None,
        channel_8: Optional[discord.TextChannel] = None,
        channel_9: Optional[discord.TextChannel] = None,
        channel_10: Optional[discord.TextChannel] = None
    ) -> None:
        """ホワリスチャンネルの設定"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(ADMIN_ONLY_MESSAGE, ephemeral=True)
            return

        if not interaction.guild:
            await interaction.response.send_message(GUILD_ONLY_MESSAGE, ephemeral=True)
            return

        channels = [
            ch.id for ch in [
                channel_1, channel_2, channel_3, channel_4, channel_5,
                channel_6, channel_7, channel_8, channel_9, channel_10
            ]
            if ch and ch.guild.id == interaction.guild.id
        ]

        async with aiosqlite.connect(self.db_exempt_path) as db:
            await db.execute(
                "DELETE FROM whitelist WHERE guild_id = ?",
                (interaction.guild.id,)
            )
            if channels:
                await db.executemany(
                    "INSERT INTO whitelist (guild_id, channel_id) VALUES (?, ?)",
                    [(interaction.guild.id, ch_id) for ch_id in channels]
                )
            await db.commit()

        # Automodルールの除外チャンネルを更新
        rule_id = await self.get_automod_rule(interaction.guild.id)
        if rule_id:
            await self.update_automod_rule_exempt_channels(interaction.guild.id, rule_id, channels)

        if channels:
            desc = "以下のチャンネルで招待リンクの自動削除が無効化されました。\n" + \
                "\n".join([f"<#{ch_id}>" for ch_id in channels])
            title = "ホワリス設定完了"
        else:
            desc = "全てのチャンネルの無効化設定を解除しました。"
            title = "ホワリス解除完了"

        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        # 設定を確認
        if not await self.get_setting(message.guild.id):
            return
            
        # 除外チャンネルの確認
        exempt_channels = await self.get_exempt_channels(message.guild.id)
        if message.channel.id in exempt_channels:
            return

        # 短縮リンクの検出処理（Automodでは検出できない部分のみ）
        urls = re.findall(r"(https?://\S+)", message.content)
        if not urls:
            return
            
        # 短縮URLがないか確認
        has_shortener = False
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.hostname and parsed.hostname.lower() in URL_SHORTENERS:
                    has_shortener = True
                    break
            except Exception:
                continue
                
        if not has_shortener:
            return
            
        # 短縮リンクを検出した場合のみcontains_inviteを実行
        if await self.contains_invite(message.content):
            try:
                await message.delete()
                warning = await message.channel.send(INVITE_WARNING)
                await asyncio.sleep(5)
                await warning.delete()
            except (discord.errors.Forbidden, Exception):
                pass

    async def create_automod_rule(self, guild_id: int) -> Optional[str]:
        """Automodルールを作成"""
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
        if not bot_token:
            print("Botトークンが設定されていません。")
            return None

        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
            "X-Audit-Log-Reason": "Anti-Invite自動設定"
        }

        # 除外チャンネルを取得
        exempt_channels = await self.get_exempt_channels(guild_id)

        # Automodルール設定
        invite_patterns = [f"*{pattern}*" for pattern in INVITE_PATTERNS]
        payload = {
            "name": "Anti-Invite Rule",
            "event_type": 1,  # message_send
            "trigger_type": 1,  # keyword
            "trigger_metadata": {
                "keyword_filter": invite_patterns
            },
            "actions": [
                {
                    "type": 1  # block_message
                }
            ],
            "enabled": True,
            "exempt_channels": exempt_channels
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"https://discord.com/api/v10/guilds/{guild_id}/auto-moderation/rules",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 201:
                        data = await response.json()
                        print(f"Automodルールがサーバー {guild_id} に作成されました。ID: {data['id']}")
                        return data["id"]
                    else:
                        error_text = await response.text()
                        print(f"Automodルール作成に失敗しました: {response.status}")
                        print(error_text)
                        return None
            except Exception as e:
                print(f"Automodルールの作成中にエラーが発生しました: {e}")
                return None

    async def delete_automod_rule(self, guild_id: int, rule_id: str) -> bool:
        """Automodルールを削除"""
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
        if not bot_token:
            print("Botトークンが設定されていません。")
            return False

        headers = {
            "Authorization": f"Bot {bot_token}",
            "X-Audit-Log-Reason": "Anti-Invite無効化"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.delete(
                    f"https://discord.com/api/v10/guilds/{guild_id}/auto-moderation/rules/{rule_id}",
                    headers=headers
                ) as response:
                    if response.status == 204:
                        print(f"Automodルールがサーバー {guild_id} から削除されました。")
                        # キャッシュから削除
                        if guild_id in self.automod_rules:
                            del self.automod_rules[guild_id]
                        return True
                    else:
                        error_text = await response.text()
                        print(f"Automodルール削除に失敗しました: {response.status}")
                        print(error_text)
                        return False
            except Exception as e:
                print(f"Automodルールの削除中にエラーが発生しました: {e}")
                return False

    async def update_automod_rule_exempt_channels(self, guild_id: int, rule_id: str, exempt_channels: List[int]) -> bool:
        """Automodルールの除外チャンネルを更新"""
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
        if not bot_token:
            print("Botトークンが設定されていません。")
            return False

        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
            "X-Audit-Log-Reason": "Anti-Invite除外チャンネル更新"
        }

        payload = {
            "exempt_channels": exempt_channels
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.patch(
                    f"https://discord.com/api/v10/guilds/{guild_id}/auto-moderation/rules/{rule_id}",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        print(f"Automodルールの除外チャンネルが更新されました。サーバー: {guild_id}")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"Automodルール更新に失敗しました: {response.status}")
                        print(error_text)
                        return False
            except Exception as e:
                print(f"Automodルールの更新中にエラーが発生しました: {e}")
                return False

    async def get_existing_automod_rules(self, guild_id: int) -> List[Dict[str, Any]]:
        """サーバーの既存Automodルールを取得"""
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
        if not bot_token:
            print("Botトークンが設定されていません。")
            return []

        headers = {
            "Authorization": f"Bot {bot_token}"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"https://discord.com/api/v10/guilds/{guild_id}/auto-moderation/rules",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"Automodルール取得に失敗しました: {response.status}")
                        print(error_text)
                        return []
            except Exception as e:
                print(f"Automodルールの取得中にエラーが発生しました: {e}")
                return []

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Botが起動した際の処理"""
        for guild in self.bot.guilds:
            # 設定を確認
            if await self.get_setting(guild.id):
                # ルールIDを確認
                rule_id = await self.get_automod_rule(guild.id)
                if not rule_id:
                    # 既存のAutomodルールを確認
                    rules = await self.get_existing_automod_rules(guild.id)
                    anti_invite_rule = next((rule for rule in rules if rule["name"] == "Anti-Invite Rule"), None)
                    
                    if anti_invite_rule:
                        # 既存のルールIDを保存
                        await self.set_setting(guild.id, True, anti_invite_rule["id"])
                    else:
                        # 新しくルールを作成
                        new_rule_id = await self.create_automod_rule(guild.id)
                        if new_rule_id:
                            await self.set_setting(guild.id, True, new_rule_id)
                            print(f"サーバー {guild.name} にAutomodルールを作成しました。")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Botが新しいサーバーに参加した際の処理"""
        # デフォルトでは無効に設定
        await self.set_setting(guild.id, False, None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiInvite(bot))
