import aiohttp
import discord
from discord.ext import commands
from typing import Final, Optional, Dict, Literal
import logging
from datetime import datetime, timedelta


PACKAGE_MANAGERS: Final[Dict[str, str]] = {
    "npm": "https://registry.npmjs.org/{}",
    "pip": "https://pypi.org/pypi/{}/json"
}

RATE_LIMIT_SECONDS: Final[int] = 10

ERROR_MESSAGES: Final[dict] = {
    "invalid_manager": "無効なパッケージマネージャーです。'npm'または'pip'を使用してください。",
    "package_not_found": "{}でパッケージ'{}'が見つかりませんでした。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "network_error": "ネットワークエラーが発生しました: {}",
    "api_error": "APIエラーが発生しました: {}"
}

EMBED_COLORS: Final[dict] = {
    "npm": discord.Color.red(),
    "pip": discord.Color.blue()
}

logger = logging.getLogger(__name__)

class PackageInfo:
    """パッケージ情報を管理するクラス"""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        homepage: str,
        manager: Literal["npm", "pip"]
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.homepage = homepage
        self.manager = manager

    @classmethod
    def from_npm_data(cls, data: dict) -> "PackageInfo":
        return cls(
            name=data.get("name", "Unknown"),
            version=data.get("dist-tags", {}).get("latest", "Unknown"),
            description=data.get("description", "No description"),
            homepage=data.get("homepage", "No homepage"),
            manager="npm"
        )

    @classmethod
    def from_pip_data(cls, data: dict) -> "PackageInfo":
        info = data.get("info", {})
        return cls(
            name=info.get("name", "Unknown"),
            version=info.get("version", "Unknown"),
            description=info.get("summary", "No description"),
            homepage=info.get("home_page", "No homepage"),
            manager="pip"
        )

class PackageSearch(commands.Cog):
    """パッケージ検索機能を提供"""

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

    def _create_package_embed(
        self,
        package: PackageInfo
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{package.name} ({package.manager})",
            description=package.description,
            color=EMBED_COLORS[package.manager],
            url=package.homepage
        )

        fields = {
            "バージョン": package.version,
            "ホームページ": package.homepage,
            "インストール": f"`{package.manager} install {package.name}`"
        }

        for name, value in fields.items():
            if value and value != "No homepage":
                embed.add_field(
                    name=name,
                    value=value,
                    inline=True
                )

        return embed

    async def _fetch_package_info(
        self,
        manager: Literal["npm", "pip"],
        package: str
    ) -> Optional[PackageInfo]:
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            url = PACKAGE_MANAGERS[manager].format(package)
            async with self._session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                return (
                    PackageInfo.from_npm_data(data)
                    if manager == "npm"
                    else PackageInfo.from_pip_data(data)
                )

        except Exception as e:
            logger.error("Error fetching package info: %s", e, exc_info=True)
            return None

    @discord.app_commands.command(
        name="search_package",
        description="npmまたはpipのパッケージを検索します"
    )
    @discord.app_commands.describe(
        manager="パッケージマネージャー（npm/pip）",
        package="検索するパッケージ名"
    )
    @discord.app_commands.choices(manager=[
        discord.app_commands.Choice(name=m, value=m)
        for m in PACKAGE_MANAGERS
    ])
    async def search_package(
        self,
        interaction: discord.Interaction,
        manager: str,
        package: str
    ) -> None:
        try:
            if manager not in PACKAGE_MANAGERS:
                await interaction.response.send_message(
                    ERROR_MESSAGES["invalid_manager"],
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

            # パッケージ情報の取得
            package_info = await self._fetch_package_info(
                manager,
                package
            )
            if not package_info:
                await interaction.followup.send(
                    ERROR_MESSAGES["package_not_found"].format(
                        manager,
                        package
                    ),
                    ephemeral=True
                )
                return

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            embed = self._create_package_embed(package_info)
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as e:
            logger.error("Network error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["network_error"].format(str(e)),
                ephemeral=True
            )
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["api_error"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PackageSearch(bot))
