from discord.ext import commands
import discord
import whois
from typing import Final, Optional, Dict, Any
import logging
import re
from datetime import datetime, timedelta


RATE_LIMIT_SECONDS: Final[int] = 30
DOMAIN_PATTERN: Final[str] = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"

ERROR_MESSAGES: Final[dict] = {
    "invalid_domain": "無効なドメイン名です。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "whois_error": "Whois情報の取得に失敗しました: {}",
    "unexpected": "予期せぬエラーが発生しました: {}"
}

FIELD_MAPPINGS: Final[Dict[str, str]] = {
    "Domain Name": "domain_name",
    "Registrar": "registrar",
    "Creation Date": "creation_date",
    "Expiration Date": "expiration_date",
    "Updated Date": "updated_date",
    "Name Servers": "name_servers",
    "Status": "status",
    "Registrant": "registrant",
    "Admin Email": "admin_email"
}

logger = logging.getLogger(__name__)

class WhoisInfo:
    """Whois情報を管理するクラス"""

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self.info: Optional[whois.WhoisEntry] = None

    def _validate_domain(self) -> bool:
        return bool(re.match(DOMAIN_PATTERN, self.domain))

    def _format_date(
        self,
        date: Any
    ) -> Optional[str]:
        if isinstance(date, list):
            date = date[0]
        if isinstance(date, datetime):
            return date.strftime("%Y-%m-%d %H:%M:%S")
        return str(date) if date else None

    def _format_list(
        self,
        items: Any
    ) -> Optional[str]:
        if isinstance(items, list):
            return "\n".join(str(item) for item in items)
        return str(items) if items else None

    async def fetch(self) -> bool:
        try:
            if not self._validate_domain():
                raise ValueError(ERROR_MESSAGES["invalid_domain"])

            self.info = whois.whois(self.domain)
            return True

        except Exception as e:
            logger.error("Error fetching whois info: %s", e, exc_info=True)
            raise

    def get_formatted_info(self) -> Dict[str, str]:
        if not self.info:
            return {}

        formatted = {}
        for display_name, attr_name in FIELD_MAPPINGS.items():
            value = getattr(self.info, attr_name, None)
            if not value:
                continue

            if "date" in attr_name.lower():
                formatted_value = self._format_date(value)
            elif isinstance(value, list):
                formatted_value = self._format_list(value)
            else:
                formatted_value = str(value)

            if formatted_value:
                formatted[display_name] = formatted_value

        return formatted

class Whois(commands.Cog):
    """Whois情報取得機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_uses = {}

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

    def _create_whois_embed(
        self,
        domain: str,
        info: Dict[str, str]
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"Whois情報: {domain}",
            color=discord.Color.blue()
        )

        for field_name, value in info.items():
            embed.add_field(
                name=field_name,
                value=value,
                inline=False
            )

        embed.set_footer(
            text="データ提供: Python-Whois"
        )

        return embed

    @discord.app_commands.command(
        name="whois",
        description="ドメインのwhois情報を返します"
    )
    @discord.app_commands.describe(
        domain="Whois情報を取得するドメイン名"
    )
    async def whois(
        self,
        interaction: discord.Interaction,
        domain: str
    ) -> None:
        try:
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

            # Whois情報の取得
            whois_info = WhoisInfo(domain)
            await whois_info.fetch()

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 結果の送信
            formatted_info = whois_info.get_formatted_info()
            if not formatted_info:
                await interaction.followup.send(
                    ERROR_MESSAGES["whois_error"].format("情報が取得できません"),
                    ephemeral=True
                )
                return

            embed = self._create_whois_embed(domain, formatted_info)
            await interaction.followup.send(embed=embed)

        except ValueError as e:
            await interaction.followup.send(
                str(e),
                ephemeral=True
            )
        except Exception as e:
            logger.error("Error in whois command: %s", e, exc_info=True)
            await interaction.followup.send(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Whois(bot))
