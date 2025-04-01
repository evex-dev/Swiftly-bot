import asyncio
import random
import copy
from typing import Final, Optional, List, Tuple, Dict, Any
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands


BOARD_WIDTH: Final[int] = 10
BOARD_HEIGHT: Final[int] = 15
HIDDEN_ROWS: Final[int] = 2  # 上部に隠し行（見えない領域）として確保
EMPTY: Final[str] = "⬛"
AUTO_DROP_DELAY: Final[float] = 3.0
GAME_TIMEOUT: Final[int] = 120
RATE_LIMIT_SECONDS: Final[int] = 30

# 各テトリミノに対応する色（emoji）
COLOR_MAP: Final[Dict[int, str]] = {
    0: "🟦",  # I
    1: "🟨",  # O
    2: "🟪",  # T
    3: "🟩",  # S
    4: "🟥",  # Z
    5: "🟧",  # J
    6: "🟫"   # L
}

# テトリミノの定義（各座標は原点からの相対座標）
TETRIS_SHAPES: Final[List[List[Tuple[int, int]]]] = [
    [(0, 0), (0, 1), (0, 2), (0, 3)],          # I
    [(0, 0), (1, 0), (0, 1), (1, 1)],          # O
    [(0, 0), (-1, 1), (0, 1), (1, 1)],         # T
    [(0, 0), (1, 0), (0, 1), (-1, 1)],         # S
    [(0, 0), (-1, 0), (0, 1), (1, 1)],         # Z
    [(0, 0), (0, 1), (0, 2), (-1, 2)],         # J
    [(0, 0), (0, 1), (0, 2), (1, 2)]           # L
]

ERROR_MESSAGES: Final[dict] = {
    "not_your_game": "このゲームはあなたの操作ではありません。",
    "rate_limit": "レート制限中です。{}秒後にお試しください。",
    "game_over": "Game Over!"
}

logger = logging.getLogger(__name__)

class TetrisGame:
    """テトリスゲームのロジックを管理するクラス"""

    def __init__(self) -> None:
        self.board = [[0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.current_piece: Optional[Dict[str, Any]] = None
        self.game_over = False
        self.score = 0
        self.lines_cleared = 0
        self.spawn_piece()

    def is_cell_empty(self, x: int, y: int) -> bool:
        """
        指定されたセルが空かどうかを判定

        Parameters
        ----------
        x : int
            X座標
        y : int
            Y座標

        Returns
        -------
        bool
            セルが空ならTrue
        """
        if y < 0:
            return True
        if not (0 <= x < BOARD_WIDTH and y < BOARD_HEIGHT):
            return False
        return self.board[y][x] == 0

    def spawn_piece(self) -> None:
        """新しいテトリミノを生成"""
        spawn_x = BOARD_WIDTH // 2
        spawn_y = HIDDEN_ROWS
        type_index = random.randint(0, len(TETRIS_SHAPES) - 1)
        shape = copy.deepcopy(TETRIS_SHAPES[type_index])
        piece = {
            "x": spawn_x,
            "y": spawn_y,
            "shape": shape,
            "type": type_index
        }

        # 新規ピースの配置可能判定
        for dx, dy in piece["shape"]:
            x = spawn_x + dx
            y = spawn_y + dy
            if y >= 0 and not self.is_cell_empty(x, y):
                self.game_over = True
                return
        self.current_piece = piece

    def current_piece_positions(self) -> List[Tuple[int, int]]:
        """現在のテトリミノの座標リストを取得"""
        if not self.current_piece:
            return []
        x = self.current_piece["x"]
        y = self.current_piece["y"]
        return [(x + dx, y + dy) for dx, dy in self.current_piece["shape"]]

    def fix_piece(self) -> None:
        """現在のテトリミノを固定"""
        if not self.current_piece:
            return

        # ゲームオーバー判定
        for x, y in self.current_piece_positions():
            if y < 0:
                self.game_over = True
                break

        # 固定ブロックをボードに設定
        for x, y in self.current_piece_positions():
            if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT:
                self.board[y][x] = self.current_piece["type"] + 1

        self.current_piece = None
        self.remove_complete_lines()

        # visible top rowのチェック
        if any(cell != 0 for cell in self.board[HIDDEN_ROWS]):
            self.game_over = True
        else:
            self.spawn_piece()

    def remove_complete_lines(self) -> None:
        """完成したラインを削除してスコアを更新"""
        new_board = [
            row for row in self.board
            if not all(cell != 0 for cell in row)
        ]
        lines_cleared = BOARD_HEIGHT - len(new_board)

        if lines_cleared > 0:
            self.lines_cleared += lines_cleared
            self.score += lines_cleared * 100 * (lines_cleared + 1) // 2

        # 新しい空の行を追加
        for _ in range(lines_cleared):
            new_board.insert(0, [0 for _ in range(BOARD_WIDTH)])
        self.board = new_board

    def can_move(
        self,
        dx: int,
        dy: int,
        new_shape: Optional[List[Tuple[int, int]]] = None
    ) -> bool:
        """
        指定された移動が可能かどうかを判定

        Parameters
        ----------
        dx : int
            X方向の移動量
        dy : int
            Y方向の移動量
        new_shape : Optional[List[Tuple[int, int]]], optional
            新しい形状, by default None

        Returns
        -------
        bool
            移動可能ならTrue
        """
        if not self.current_piece:
            return False

        shape = new_shape if new_shape is not None else self.current_piece["shape"]
        new_x = self.current_piece["x"] + dx
        new_y = self.current_piece["y"] + dy

        for offset_x, offset_y in shape:
            x = new_x + offset_x
            y = new_y + offset_y
            if y >= 0 and not self.is_cell_empty(x, y):
                return False
        return True

    def move(self, dx: int, dy: int) -> bool:
        """
        テトリミノを移動

        Parameters
        ----------
        dx : int
            X方向の移動量
        dy : int
            Y方向の移動量

        Returns
        -------
        bool
            移動が成功したらTrue
        """
        if not self.current_piece or not self.can_move(dx, dy):
            return False
        self.current_piece["x"] += dx
        self.current_piece["y"] += dy
        return True

    def move_left(self) -> bool:
        """左に移動"""
        return self.move(-1, 0)

    def move_right(self) -> bool:
        """右に移動"""
        return self.move(1, 0)

    def move_down(self) -> bool:
        """
        下に移動

        Returns
        -------
        bool
            移動が成功したらTrue、固定されたらFalse
        """
        if self.move(0, 1):
            return True
        self.fix_piece()
        return False

    def drop(self) -> None:
        """テトリミノを一番下まで落とす"""
        while self.move_down():
            pass

    def rotate(self) -> bool:
        """
        テトリミノを回転

        Returns
        -------
        bool
            回転が成功したらTrue
        """
        if not self.current_piece:
            return False

        old_shape = self.current_piece["shape"]
        rotated_shape = [(-dy, dx) for dx, dy in old_shape]

        # 回転の中心を計算
        old_cx = sum(x for x, _ in old_shape) / len(old_shape)
        old_cy = sum(y for _, y in old_shape) / len(old_shape)
        new_cx = sum(x for x, _ in rotated_shape) / len(rotated_shape)
        new_cy = sum(y for _, y in rotated_shape) / len(rotated_shape)

        # オフセットを計算して適用
        offset_x = round(old_cx - new_cx)
        offset_y = round(old_cy - new_cy)
        adjusted_shape = [
            (x + offset_x, y + offset_y)
            for x, y in rotated_shape
        ]

        if self.can_move(0, 0, new_shape=adjusted_shape):
            self.current_piece["shape"] = adjusted_shape
            return True
        return False

    def render(self) -> str:
        """
        ゲーム画面を文字列として生成

        Returns
        -------
        str
            ゲーム画面の文字列表現
        """
        display = [
            [EMPTY for _ in range(BOARD_WIDTH)]
            for _ in range(BOARD_HEIGHT - HIDDEN_ROWS)
        ]

        # 固定ブロックの描画
        for y in range(HIDDEN_ROWS, BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                if self.board[y][x] != 0:
                    color_index = self.board[y][x] - 1
                    display[y - HIDDEN_ROWS][x] = COLOR_MAP[color_index]

        # 落下中のブロックの描画
        if self.current_piece:
            piece_color = COLOR_MAP[self.current_piece["type"]]
            for x, y in self.current_piece_positions():
                if (HIDDEN_ROWS <= y < BOARD_HEIGHT and
                    0 <= x < BOARD_WIDTH):
                    display[y - HIDDEN_ROWS][x] = piece_color

        return "\n".join("".join(row) for row in display)

class TetrisView(discord.ui.View):
    """テトリスゲームのUIを管理するクラス"""

    def __init__(
        self,
        game: TetrisGame,
        interaction: discord.Interaction
    ) -> None:
        super().__init__(timeout=GAME_TIMEOUT)
        self.game = game
        self.interaction = interaction
        self.auto_drop_task: Optional[asyncio.Task] = None

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        """インタラクションの権限チェック"""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message(
                ERROR_MESSAGES["not_your_game"],
                ephemeral=True
            )
            return False
        return True

    async def update_message(self, new_interaction: Optional[discord.Interaction] = None) -> None:
        """ゲーム画面を更新"""
        embed = discord.Embed(
            title="Tetris",
            description=self.game.render(),
            color=discord.Color.blue()
        )

        # スコア情報を追加
        embed.add_field(
            name="スコア",
            value=str(self.game.score),
            inline=True
        )
        embed.add_field(
            name="消去ライン数",
            value=str(self.game.lines_cleared),
            inline=True
        )

        content = None
        if self.game.game_over:
            content = ERROR_MESSAGES["game_over"]
            for child in self.children:
                child.disabled = True
            if self.auto_drop_task:
                self.auto_drop_task.cancel()

        try:
            # 新しいインタラクションがある場合はそれを使用
            if new_interaction:
                await new_interaction.edit_original_response(
                    embed=embed,
                    content=content,
                    view=self
                )
            else:
                await self.interaction.edit_original_response(
                    embed=embed,
                    content=content,
                    view=self
                )
        except discord.errors.HTTPException as e:
            if e.code == 50027:  # Invalid Webhook Token
                logger.warning("Interaction token expired, cannot update message")
                # インタラクションが期限切れの場合、フォローアップメッセージを送信
                await self.send_interaction_expired_message(new_interaction)
            else:
                # その他のHTTPエラーは再スロー
                raise

    async def send_interaction_expired_message(self, interaction: Optional[discord.Interaction]) -> None:
        if not interaction:
            return

        try:
            # フォローアップメッセージを送信
            await interaction.followup.send(
                "インタラクションの有効期限が切れたよ。もう一度ゲームを作り直してね。",
                ephemeral=True
            )
        except Exception as e:
            logger.error("Failed to send interaction expired message: %s", e, exc_info=True)

    @discord.ui.button(label="←", style=discord.ButtonStyle.primary)
    async def left(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        """左移動ボタン"""
        await interaction.response.defer()
        if not self.game.game_over:
            self.game.move_left()
            await self.update_message(interaction)

    @discord.ui.button(label="→", style=discord.ButtonStyle.primary)
    async def right(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        """右移動ボタン"""
        await interaction.response.defer()
        if not self.game.game_over:
            self.game.move_right()
            await self.update_message(interaction)

    @discord.ui.button(label="↓", style=discord.ButtonStyle.primary)
    async def down(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        """下移動ボタン"""
        await interaction.response.defer()
        if not self.game.game_over:
            self.game.move_down()
            await self.update_message(interaction)

    @discord.ui.button(label="⏬", style=discord.ButtonStyle.primary)
    async def drop(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        """ハードドロップボタン"""
        await interaction.response.defer()
        if not self.game.game_over:
            self.game.drop()
            await self.update_message(interaction)

    @discord.ui.button(label="↻", style=discord.ButtonStyle.secondary)
    async def rotate_button(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button
    ) -> None:
        """回転ボタン"""
        await interaction.response.defer()
        if not self.game.game_over:
            self.game.rotate()
            await self.update_message(interaction)

class Tetri(commands.Cog):
    """テトリスゲーム機能を提供"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_uses = {}

    def _check_rate_limit(
        self,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        """
        レート制限をチェック

        Parameters
        ----------
        user_id : int
            ユーザーID

        Returns
        -------
        tuple[bool, Optional[int]]
            (制限中かどうか, 残り秒数)
        """
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    async def auto_drop(self, view: TetrisView) -> None:
        try:
            await asyncio.sleep(AUTO_DROP_DELAY)
            while not view.game.game_over:
                await asyncio.sleep(AUTO_DROP_DELAY)
                if (view.game.current_piece and
                    view.game.can_move(0, 1)):
                    view.game.move_down()
                    try:
                        await view.update_message()
                    except discord.errors.HTTPException as e:
                        if e.code == 50027:  # Invalid Webhook Token
                            logger.warning("Auto-drop: Interaction token expired")
                            # 自動落下ではフォローアップメッセージを送信できないので、
                            # ここでは処理を停止する
                            return
                        else:
                            raise
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Error in auto_drop: %s", e, exc_info=True)

    @app_commands.command(
        name="tetri",
        description="Discord上でテトリスを遊びます"
    )
    async def tetri(
        self,
        interaction: discord.Interaction
    ) -> None:
        """
        テトリスゲームを開始するコマンド

        Parameters
        ----------
        interaction : discord.Interaction
            インタラクションコンテキスト
        """
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

            # ゲームの初期化
            game = TetrisGame()
            view = TetrisView(game, interaction)

            embed = discord.Embed(
                title="Tetris",
                description=game.render(),
                color=discord.Color.blue()
            )
            embed.add_field(
                name="スコア",
                value="0",
                inline=True
            )
            embed.add_field(
                name="消去ライン数",
                value="0",
                inline=True
            )

            await interaction.response.send_message(
                embed=embed,
                view=view
            )

            # レート制限の更新
            self._last_uses[interaction.user.id] = datetime.now()

            # 自動落下処理の開始
            view.auto_drop_task = self.bot.loop.create_task(
                self.auto_drop(view)
            )

        except Exception as e:
            logger.error("Error in tetri command: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["unexpected"].format(str(e)),
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tetri(bot))
