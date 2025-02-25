import discord
from discord.ext import commands
import math
from typing import Final, List, Optional
import logging
from collections import defaultdict

# 定数定義
ITEMS_PER_PAGE: Final[int] = 10
TIMEOUT_SECONDS: Final[int] = 180
DEFAULT_COLOR: Final[int] = discord.Color.green().value

EMBED_TITLES: Final[dict] = {
    "main": "Swiftlyのコマンド一覧",
    "category": "カテゴリ: {}"
}

logger = logging.getLogger(__name__)

class CommandListView(discord.ui.View):
    """コマンド一覧表示用のカスタムビュー"""

    def __init__(
        self,
        commands_list: List[discord.app_commands.Command],
        timeout: int = TIMEOUT_SECONDS
    ) -> None:
        super().__init__(timeout=timeout)
        self.commands_list = commands_list
        self.current_page = 0
        self.items_per_page = ITEMS_PER_PAGE
        self.max_pages = math.ceil(len(commands_list) / self.items_per_page)
        self.current_category: Optional[str] = None
        self.categories = self._categorize_commands()

        # ボタンの初期状態を設定
        self.update_button_states()

    def _categorize_commands(self) -> dict:
        categories = defaultdict(list)
        for cmd in self.commands_list:
            # コグ名をカテゴリとして使用
            category = getattr(cmd.callback, "__cog_name__", "その他")
            categories[category].append(cmd)
        return dict(categories)

    def update_button_states(self) -> None:
        """ページネーションボタンの状態を更新"""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "previous":
                    child.disabled = self.current_page <= 0
                elif child.custom_id == "next":
                    child.disabled = self.current_page >= self.max_pages - 1

    def get_current_commands(self) -> List[discord.app_commands.Command]:
        if self.current_category:
            commands_to_show = self.categories[self.current_category]
        else:
            commands_to_show = self.commands_list

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        return commands_to_show[start_idx:end_idx]

    def create_embed(self) -> discord.Embed:
        title = (
            EMBED_TITLES["category"].format(self.current_category)
            if self.current_category
            else EMBED_TITLES["main"]
        )

        embed = discord.Embed(
            title=title,
            description=f"ページ {self.current_page + 1}/{self.max_pages}",
            color=DEFAULT_COLOR
        )

        for command in self.get_current_commands():
            name = f"/{command.name}"
            if command.description:
                value = command.description
                if hasattr(command, "parameters") and command.parameters:
                    value += "\n\n**パラメータ:**"
                    for param in command.parameters:
                        value += f"\n• {param.name}: {param.description}"
            else:
                value = "説明なし"

            embed.add_field(
                name=name,
                value=value,
                inline=False
            )

        if self.categories:
            categories_text = "**カテゴリ一覧:**\n" + "\n".join(
                f"• {category}" for category in self.categories.keys()
            )
            embed.add_field(
                name="カテゴリ",
                value=categories_text,
                inline=False
            )

        return embed

    @discord.ui.button(
        label="前へ",
        style=discord.ButtonStyle.gray,
        custom_id="previous"
    )
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """前のページに移動"""
        try:
            if self.current_page > 0:
                self.current_page -= 1
                self.update_button_states()
                await interaction.response.edit_message(
                    embed=self.create_embed(),
                    view=self
                )
            else:
                await interaction.response.defer()
        except Exception as e:
            logger.error("Error in previous button: %s", e, exc_info=True)
            await interaction.response.defer()

    @discord.ui.button(
        label="次へ",
        style=discord.ButtonStyle.gray,
        custom_id="next"
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """次のページに移動"""
        try:
            if self.current_page < self.max_pages - 1:
                self.current_page += 1
                self.update_button_states()
                await interaction.response.edit_message(
                    embed=self.create_embed(),
                    view=self
                )
            else:
                await interaction.response.defer()
        except Exception as e:
            logger.error("Error in next button: %s", e, exc_info=True)
            await interaction.response.defer()

    @discord.ui.select(
        placeholder="カテゴリを選択",
        custom_id="category_select",
        min_values=1,
        max_values=1
    )
    async def category_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ) -> None:
        """カテゴリを選択"""
        try:
            category = select.values[0]
            if category == "すべて":
                self.current_category = None
                self.commands_list = [
                    cmd for cmds in self.categories.values()
                    for cmd in cmds
                ]
            else:
                self.current_category = category
                self.commands_list = self.categories[category]

            self.current_page = 0
            self.max_pages = math.ceil(
                len(self.commands_list) / self.items_per_page
            )
            self.update_button_states()

            await interaction.response.edit_message(
                embed=self.create_embed(),
                view=self
            )
        except Exception as e:
            logger.error("Error in category select: %s", e, exc_info=True)
            await interaction.response.defer()

    async def on_timeout(self) -> None:
        """タイムアウト時の処理"""
        try:
            for child in self.children:
                child.disabled = True
            # メッセージを更新して全てのボタンを無効化
            if hasattr(self, "message"):
                await self.message.edit(view=self)
        except Exception as e:
            logger.error("Error in timeout handling: %s", e, exc_info=True)

class CommandList(commands.Cog):
    """コマンド一覧を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.app_commands.command(
        name="help-command",
        description="Swiftlyが提供するすべてのコマンドを表示します。"
    )
    async def command_list(self, interaction: discord.Interaction) -> None:
        try:
            commands_list = list(self.bot.tree.get_commands())
            view = CommandListView(commands_list)

            # カテゴリ選択オプションを追加
            categories = ["すべて"] + list(view.categories.keys())
            view.category_select.options = [
                discord.SelectOption(
                    label=category,
                    value=category
                ) for category in categories
            ]

            message = await interaction.response.send_message(
                embed=view.create_embed(),
                view=view
            )
            if isinstance(message, discord.Message):
                view.message = message
        except Exception as e:
            logger.error("Error in command_list: %s", e, exc_info=True)
            await interaction.response.send_message(
                "コマンド一覧の取得中にエラーが発生しました。",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandList(bot))
