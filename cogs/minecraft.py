import logging
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from typing import Final, Optional, Dict, List
import re
from datetime import datetime, timedelta

# 定数定義
API_BASE_URL: Final[str] = "https://api.mcsrvstat.us/3"
ICON_BASE_URL: Final[str] = "https://api.mcsrvstat.us/icon"
RATE_LIMIT_SECONDS: Final[int] = 30
ADDRESS_PATTERN: Final[str] = r"^[a-zA-Z0-9][a-zA-Z0-9-\.]{1,61}[a-zA-Z0-9]\:[0-9]{1,5}$|^[a-zA-Z0-9][a-zA-Z0-9-\.]{1,61}[a-zA-Z0-9]$"

ERROR_MESSAGES: Final[dict] = {
    "invalid_address": "無効なサーバーアドレスです。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "api_error": "サーバーステータスの取得に失敗しました: {}",
    "network_error": "ネットワークエラーが発生しました: {}"
}

EMBED_COLORS: Final[dict] = {
    "online": discord.Color.green(),
    "offline": discord.Color.red()
}

logger = logging.getLogger(__name__)

class MinecraftServer:
    """Minecraftサーバー情報を管理するクラス"""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.online = data.get("online", False)
        self.address = data.get("hostname") or data.get("ip", "N/A")
        self.port = data.get("port", "N/A")
        self.version = data.get("version", "N/A")
        self.players = self._get_players()
        self.motd = self._get_motd()
        self.plugins = self._get_plugins()
        self.mods = self._get_mods()

    def _get_players(self) -> str:
        """プレイヤー情報を取得"""
        if "players" not in self.data:
            return "N/A"
        return f"{self.data['players']['online']}/{self.data['players']['max']}"

    def _get_motd(self) -> Optional[str]:
        """MOTDを取得"""
        if "motd" in self.data and "clean" in self.data["motd"]:
            return "\n".join(self.data["motd"]["clean"])
        return None

    def _get_plugins(self) -> Optional[str]:
        """プラグイン情報を取得"""
        if "plugins" in self.data:
            return ", ".join(
                plugin["name"] for plugin in self.data["plugins"]
            )
        return None

    def _get_mods(self) -> Optional[str]:
        """MOD情報を取得"""
        if "mods" in self.data:
            return ", ".join(
                mod["name"] for mod in self.data["mods"]
            )
        return None

class Minecraft(commands.Cog):
    """Minecraftサーバー情報を取得する機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_uses = {}

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _validate_address(self, address: str) -> bool:
        return bool(re.match(ADDRESS_PATTERN, address))

    def _check_rate_limit(
        self,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    def _create_server_embed(
        self,
        server: MinecraftServer,
        address: str
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"サーバーステータス: {address}",
            color=EMBED_COLORS["online" if server.online else "offline"]
        )
        embed.set_thumbnail(url=f"{ICON_BASE_URL}/{address}")

        if server.online:
            fields = {
                "IP": server.address,
                "ポート": server.port,
                "バージョン": server.version,
                "プレイヤー数": server.players
            }

            if server.motd:
                fields["MOTD"] = server.motd
            if server.plugins:
                fields["プラグイン"] = server.plugins
            if server.mods:
                fields["MOD"] = server.mods

            for name, value in fields.items():
                embed.add_field(
                    name=name,
                    value=value,
                    inline=False
                )
        else:
            embed.add_field(
                name="ステータス",
                value="オフライン",
                inline=False
            )

        return embed

    async def _fetch_server_info(
        self,
        address: str
    ) -> Optional[dict]:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            async with self._session.get(
                f"{API_BASE_URL}/{address}"
            ) as response:
                if response.status != 200:
                    logger.warning(
                        f"API error for server {address}: {response.status}"
                    )
                    return None
                return await response.json()

        except Exception as e:
            logger.error(f"Error fetching server info: {e}", exc_info=True)
            return None

    @app_commands.command(
        name="minecraft",
        description="Minecraft サーバーのステータスを取得する"
    )
    @app_commands.describe(
        address="サーバーアドレス（例: example.com または example.com:25565）"
    )
    async def minecraft(
        self,
        interaction: discord.Interaction,
        address: str
    ) -> None:
        try:
            # アドレスのバリデーション
            if not self._validate_address(address):
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_address"],
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

            await interaction.response.defer(thinking=True)

            # サーバー情報の取得
            data = await self._fetch_server_info(address)
            if not data:
                await interaction.followup.send(
                    ERROR_MESSAGES["api_error"].format("データ取得失敗"),
                    ephemeral=True
                )
                return

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            server = MinecraftServer(data)
            embed = self._create_server_embed(server, address)
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}", exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["network_error"].format(str(e)),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["api_error"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Minecraft(bot))
