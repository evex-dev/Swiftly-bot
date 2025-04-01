import discord
from discord.ext import commands
import aiohttp
import asyncio
import re
from typing import Final, Optional, Dict, List, Tuple
import logging
from datetime import datetime, timedelta


API_BASE_URL: Final[str] = "http://ip-api.com/json"
RATE_LIMIT_SECONDS: Final[int] = 60
REQUEST_TIMEOUT: Final[int] = 10

ERROR_MESSAGES: Final[dict] = {
    "invalid_ip": "無効なIPアドレスです。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "api_error": "APIエラー: ステータスコード {}",
    "json_error": "JSONの解析に失敗しました。",
    "network_error": "ネットワークエラーが発生しました: {}",
    "timeout": "リクエストがタイムアウトしました。",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

FIELD_MAPPINGS: Final[List[Tuple[str, str]]] = [
    ("Country", "country"),
    ("Region", "regionName"),
    ("City", "city"),
    ("ZIP Code", "zip"),
    ("Coordinates", "coordinates"),
    ("Timezone", "timezone"),
    ("ISP", "isp"),
    ("Organization", "org"),
    ("AS", "as")
]

logger = logging.getLogger(__name__)

class IP(commands.Cog):
    """IP情報を取得する機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_uses: Dict[int, datetime] = {}

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _validate_ip(self, ip_addr: str) -> bool:
        ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        ipv6_pattern = r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"

        if re.match(ipv4_pattern, ip_addr):
            # IPv4の各オクテットが0-255の範囲内かチェック
            return all(0 <= int(octet) <= 255 for octet in ip_addr.split('.'))
        elif re.match(ipv6_pattern, ip_addr):
            return True
        return False

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

    def _create_ip_embed(
        self,
        ip_addr: str,
        data: dict
    ) -> discord.Embed:
        embed = discord.Embed(
            title="IP情報",
            description=f"IP: {ip_addr}",
            color=discord.Color.blue()
        )

        for display_name, key in FIELD_MAPPINGS:
            value = None
            if key == "coordinates":
                value = f"Lat: {data.get('lat')}, Lon: {data.get('lon')}"
            elif key == "country":
                value = f"{data.get('country')} ({data.get('countryCode')})"
            elif key == "regionName":
                value = f"{data.get('regionName')} ({data.get('region')})"
            else:
                value = data.get(key)

            if value and value != "None (None)":
                embed.add_field(
                    name=display_name,
                    value=value,
                    inline=True
                )

        return embed

    async def _fetch_ip_info(self, ip_addr: str) -> Optional[dict]:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            async with self._session.get(
                f"{API_BASE_URL}/{ip_addr}",
                timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "API error for IP %s: %d", ip_addr, response.status
                    )
                    return None

                data = await response.json()
                if data.get("status") != "success":
                    return None

                return data

        except Exception as e:
            logger.error("Error fetching IP info: %s", e, exc_info=True)
            return None

    @discord.app_commands.command(
        name="ip",
        description="IP情報を取得します"
    )
    @discord.app_commands.describe(
        ip_addr="情報を取得するIPアドレス"
    )
    async def ip(
        self,
        interaction: discord.Interaction,
        ip_addr: str
    ) -> None:
        try:
            # IPアドレスのバリデーション
            if not self._validate_ip(ip_addr):
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_ip"],
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

            await interaction.response.defer()

            # IP情報の取得
            data = await self._fetch_ip_info(ip_addr)
            if not data:
                await interaction.followup.send(
                    ERROR_MESSAGES["api_error"].format("データ取得失敗"),
                    ephemeral=True
                )
                return

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_ip_embed(ip_addr, data)
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as e:
            logger.error("Network error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["network_error"].format(str(e)),
                ephemeral=True
            )
        except asyncio.TimeoutError:
            logger.warning("Request timeout for IP %s", ip_addr)
            await interaction.followup.send(
                ERROR_MESSAGES["timeout"],
                ephemeral=True
            )
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IP(bot))
