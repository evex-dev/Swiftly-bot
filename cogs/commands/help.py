import discord
from discord.ext import commands
from typing import Final, Dict, List
import logging
from collections import defaultdict
from discord.ui import View, Button

EMBED_COLOR: Final[int] = discord.Color.blue().value
WEBSITE_URL: Final[str] = "https://sakana11.org/swiftly/commands.html"
FOOTER_TEXT: Final[str] = "Hosted by TechFish_Lab"

COMMAND_CATEGORIES: Final[Dict[str, str]] = {
    "予測": "AIを使用した予測機能",
    "ユーティリティ": "便利な機能",
    "検索": "情報検索機能",
    "AI機能": "AI関連の機能",
    "サーバー管理": "サーバー管理用機能",
    "エンターテイメント": "遊び系の機能",
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
    },
    "imagegen": {
        "category": "AI機能",
        "name": "/imagegen",
        "description": "AIによる画像生成",
        "features": [
            "テキストから画像を生成",
            "高品質な画像出力",
            "様々なスタイルに対応"
        ]
    },
    "youyaku": {
        "category": "ユーティリティ", 
        "name": "/youyaku",
        "description": "チャンネルのメッセージを要約",
        "features": [
            "指定チャンネルのメッセージを分析",
            "最大1000メッセージまで処理可能",
            "会話の要点をまとめて提供"
        ]
    },
    "antiraid": {
        "category": "サーバー管理",
        "name": "/antiraid_enable",
        "description": "サーバーの荒らし対策機能",
        "features": [
            "自動荒らし検出と対応",
            "カスタマイズ可能な保護設定",
            "/antiraid_disable で無効化可能"
        ]
    },
    "role_panel": {
        "category": "サーバー管理",
        "name": "/role-panel",
        "description": "リアクションでロール付与パネルを作成",
        "features": [
            "カスタムロールパネルの作成",
            "絵文字リアクションでロール管理",
            "ユーザーが自分でロールを取得可能"
        ]
    },
    "poll": {
        "category": "ユーティリティ",
        "name": "/poll",
        "description": "匿名投票の作成と管理",
        "features": [
            "複数選択肢の投票作成",
            "投票期間の設定",
            "結果の自動集計"
        ]
    },
    "sandbox": {
        "category": "エンターテイメント",
        "name": "/sandbox",
        "description": "JavaScriptコード実行環境",
        "features": [
            "コードをサンドボックスで実行",
            "結果をすぐに表示",
            "?sandbox としても使用可能"
        ]
    },
    "pysandbox": {
        "category": "エンターテイメント",
        "name": "/pysandbox",
        "description": "Pythonコード実行環境",
        "features": [
            "Pythonコードをサンドボックスで実行",
            "結果をすぐに表示",
            "?pysandbox としても使用可能"
        ]
    },
    "tetri": {
        "category": "エンターテイメント",
        "name": "/tetri",
        "description": "テトリスゲーム",
        "features": [
            "Discordでテトリスをプレイ",
            "リアクションで操作",
            "スコアの記録"
        ]
    },
    "join": {
        "category": "ユーティリティ",
        "name": "/join",
        "description": "ボイスチャンネル読み上げ機能",
        "features": [
            "テキストチャンネルのメッセージを読み上げ",
            "/leave でVCから退出",
            "/dictionary_add で読み上げ辞書を編集可能"
        ]
    }
}

logger = logging.getLogger(__name__)

class HelpPaginator(View):
    def __init__(self, embeds: List[discord.Embed], user: discord.User):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.current_page = 0
        self.user = user
        self.update_buttons()

    def update_buttons(self):
        # 生成済みのボタンのdisabled状態を更新
        for child in self.children:
            if child.custom_id == "prev":
                child.disabled = self.current_page <= 0
            elif child.custom_id == "next":
                child.disabled = self.current_page >= len(self.embeds) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("この操作はコマンドを実行したユーザーのみが使用できます。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="前へ", style=discord.ButtonStyle.primary, custom_id="prev")
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = max(self.current_page - 1, 0)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = min(self.current_page + 1, len(self.embeds) - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

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

            commandss = categories[category]
            value = f"**{description}**\n\n"

            for cmd in commandss:
                value += f"**{cmd['name']}**\n{cmd['description']}\n"
                value += "特徴:\n" + "\n".join(f"- {feature}" for feature in cmd["features"]) + "\n\n"

            fields.append({
                "name": f"【{category}】",
                "value": value.strip(),
                "inline": False
            })

        return fields

    def _create_paginated_embeds(self) -> List[discord.Embed]:
        fields = self._create_category_fields()
        embeds = []

        for field in fields:  # 1ページに1つのカテゴリを表示
            embed = discord.Embed(
                title="Swiftlyヘルプ",
                description=(
                    "Swiftlyのコマンドの使い方と特徴を説明します。\n"
                    "各コマンドは目的に応じてカテゴリ分けされています。"
                ),
                color=EMBED_COLOR
            )
            embed.add_field(**field)
            embed.set_footer(text=FOOTER_TEXT)
            embeds.append(embed)

        return embeds

    @discord.app_commands.command(
        name="help",
        description="Swiftlyのヘルプを表示します。"
    )
    async def help_command(self, interaction: discord.Interaction) -> None:
        try:
            embeds = self._create_paginated_embeds()
            view = HelpPaginator(embeds, interaction.user)
            await interaction.response.send_message(embed=embeds[0], view=view)
        except Exception as e:
            logger.error("Error in help command: %s", e, exc_info=True)
            await interaction.response.send_message(
                f"ヘルプの表示中にエラーが発生しました: {e}",
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
