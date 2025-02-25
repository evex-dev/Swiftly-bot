import discord
from discord.ext import commands
from typing import Final, Dict, Tuple
import logging

# 定数定義
EMBED_COLOR: Final[int] = discord.Color.blue().value

COMMAND_INFO: Final[Dict[str, dict]] = {
    "growth": {
        "name": "/growth",
        "description": "サーバーの成長を3次多項式回帰モデルで予測します。",
        "features": [
            "適度なデータポイント数が必要です。",
            "短期的な予測に適しています。",
            "データの傾向を滑らかに捉えることができます。"
        ],
        "parameters": [
            "target: 目標とするメンバー数",
            "show_graph: グラフを表示するかどうか（デフォルト: True）"
        ]
    },
    "prophet_growth": {
        "name": "/prophet_growth",
        "description": "サーバーの成長をProphetモデルで予測します。",
        "features": [
            "大規模なデータセットに適しています。",
            "季節性や休日の影響を考慮できます。",
            "長期的な予測に強いです。"
        ],
        "parameters": [
            "target: 目標とするメンバー数",
            "show_graph: グラフを表示するかどうか（デフォルト: True）"
        ]
    },
    "arima_growth": {
        "name": "/arima_growth",
        "description": "サーバーの成長をARIMAモデルで予測します。",
        "features": [
            "時系列データに適しています。",
            "データの自己相関を考慮します。",
            "短期から中期の予測に適しています。"
        ],
        "parameters": [
            "target: 目標とするメンバー数",
            "show_graph: グラフを表示するかどうか（デフォルト: True）"
        ]
    }
}

FOOTER_TEXT: Final[str] = (
    "この予測は統計モデルに基づくものであり、"
    "実際の結果を保証するものではありません。"
)

logger = logging.getLogger(__name__)

class GrowthHelp(commands.Cog):
    """成長予測コマンドのヘルプを提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _create_command_field(
        self,
        command_info: dict
    ) -> Tuple[str, str, bool]:
        value = (
            f"{command_info['description']}\n\n"
            "**特徴:**\n" +
            "\n".join(f"- {feature}" for feature in command_info["features"]) +
            "\n\n**パラメータ:**\n" +
            "\n".join(f"- {param}" for param in command_info["parameters"])
        )
        return command_info["name"], value, False

    def _create_help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="成長予測コマンドのヘルプ",
            description=(
                "サーバーの成長を予測するためのコマンドの使い方と特徴を説明します。\n"
                "各コマンドは異なる予測モデルを使用しており、"
                "用途に応じて使い分けることができます。"
            ),
            color=EMBED_COLOR
        )

        # 各コマンドの情報を追加
        for command_info in COMMAND_INFO.values():
            name, value, inline = self._create_command_field(command_info)
            embed.add_field(
                name=name,
                value=value,
                inline=inline
            )

        # 使用上の注意を追加
        embed.add_field(
            name="使用上の注意",
            value=(
                "- 予測の精度はデータ量に大きく依存します。\n"
                "- 急激な変化があった場合、予測が不正確になる可能性があります。\n"
                "- 定期的に予測を更新することをお勧めします。"
            ),
            inline=False
        )

        embed.set_footer(text=FOOTER_TEXT)
        return embed

    @discord.app_commands.command(
        name="growth-help",
        description="成長予測コマンドのヘルプを表示します。"
    )
    async def growth_help(
        self,
        interaction: discord.Interaction
    ) -> None:
        try:
            embed = self._create_help_embed()
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in growth_help command: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"ヘルプの表示中にエラーが発生しました: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GrowthHelp(bot))
