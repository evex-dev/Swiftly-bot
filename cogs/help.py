import discord
from discord.ext import commands
from typing import Final, Dict, List
import logging
from collections import defaultdict

# 定数定義
EMBED_COLOR: Final[int] = discord.Color.blue().value
WEBSITE_URL: Final[str] = "https://sakana11.org/swiftly/commands.html"
FOOTER_TEXT: Final[str] = "Hosted by TechFish_Lab"

COMMAND_CATEGORIES: Final[Dict[str, str]] = {
    "予測": "AIを使用した予測機能",
    "ユーティリティ": "便利な機能",
    "検索": "情報検索機能",
    "その他": "その他の機能"
}

COMMAND_INFO: Final[Dict[str, dict]] = {
    "growth": {
        "category": "予測",
        "name": "/growth",
        "description": "サーバーの成長を3次多項式回帰で予測",
        "features": [
            "3次多項式回帰を使用",
            "サーバーの目標人数達成日を予測",
            "グラフによる視覚化"
        ]
    },
    "prophet_growth": {
        "category": "予測",
        "name": "/prophet-growth",
        "description": "サーバーの成長をProphetで予測",
        "features": [
            "Prophetモデルを使用",
            "季節性を考慮した予測",
            "長期的な予測に強い"
        ]
    },
    "arima_growth": {
        "category": "予測",
        "name": "/arima-growth",
        "description": "サーバーの成長をARIMAで予測",
        "features": [
            "ARIMAモデルを使用",
            "時系列データに適している",
            "短中期の予測に適している"
        ]
    },
    "base64": {
        "category": "ユーティリティ",
        "name": "/base64",
        "description": "Base64のエンコード・デコード",
        "features": [
            "文字列のエンコード/デコード",
            "荒らし対策機能付き",
            "セキュリティ考慮済み"
        ]
    },
    "first_comment": {
        "category": "ユーティリティ",
        "name": "/first-comment",
        "description": "チャンネルの最初のメッセージを取得",
        "features": [
            "最初のメッセージへのリンクを提供",
            "キャッシュ機能で高速化",
            "簡単な履歴確認"
        ]
    },
    "wikipedia": {
        "category": "検索",
        "name": "/wikipedia",
        "description": "Wikipedia検索",
        "features": [
            "記事の検索と表示",
            "曖昧さ回避ページの対応",
            "要約表示機能"
        ]
    }
}

logger = logging.getLogger(__name__)

class Help(commands.Cog):
    """Swiftlyのヘルプ機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _create_category_fields(self) -> List[Dict[str, str]]:
        categories = defaultdict(list)
        for cmd_info in COMMAND_INFO.values():
            categories[cmd_info["category"]].append(cmd_info)

        fields = []
        for category, description in COMMAND_CATEGORIES.items():
            if category not in categories:
                continue

            commands = categories[category]
            value = f"**{description}**\n\n"

            for cmd in commands:
                value += f"**{cmd['name']}**\n{cmd['description']}\n"
                value += "特徴:\n" + "\n".join(
                    f"- {feature}" for feature in cmd["features"]
                ) + "\n\n"

            fields.append({
                "name": f"【{category}】",
                "value": value.strip(),
                "inline": False
            })

        return fields

    def _create_help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Swiftlyヘルプ",
            description=(
                "Swiftlyのコマンドの使い方と特徴を説明します。\n"
                "各コマンドは目的に応じてカテゴリ分けされています。"
            ),
            color=EMBED_COLOR
        )

        # カテゴリごとのフィールドを追加
        for field in self._create_category_fields():
            embed.add_field(**field)

        # 追加情報
        embed.add_field(
            name="その他のコマンド",
            value=(
                f"すべてのコマンドは {WEBSITE_URL} "
                "で確認できます。"
            ),
            inline=False
        )

        embed.set_footer(text=FOOTER_TEXT)
        return embed

    @discord.app_commands.command(
        name="help",
        description="Swiftlyのヘルプを表示します。"
    )
    async def help_command(
        self,
        interaction: discord.Interaction
    ) -> None:
        try:
            embed = self._create_help_embed()
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in help command: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"ヘルプの表示中にエラーが発生しました: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
