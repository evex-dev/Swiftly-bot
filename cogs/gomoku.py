import discord
from discord.ext import commands
import sqlite3
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 定数
BOARD_SIZE = 15
EMPTY = 0
PLAYER1 = 1
PLAYER2 = 2

# 絵文字
EMOJI_MAP = {
    EMPTY: "▫️",
    PLAYER1: "🔴",
    PLAYER2: "🔵"
}

DB_PATH = r"/data/gomoku.db"

def create_empty_board():
    return [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

def render_board(board):
    rows = []
    header = "   " + " ".join(f"{i:2d}" for i in range(1, BOARD_SIZE+1))
    rows.append(header)
    for idx, row in enumerate(board):
        line = f"{idx+1:2d} " + " ".join(EMOJI_MAP[cell] for cell in row)
        rows.append(line)
    return "\n".join(rows)

def check_win(board, x, y, player):
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    for dx, dy in directions:
        count = 1
        nx, ny = x + dx, y + dy
        while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == player:
            count += 1
            nx += dx
            ny += dy
        nx, ny = x - dx, y - dy
        while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == player:
            count += 1
            nx -= dx
            ny -= dy
        if count >= 5:
            return True
    return False

class Gomoku(commands.Cog):
    """五目並べのセッションと対局を管理します"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    player1 INTEGER NOT NULL,
                    player2 INTEGER NOT NULL,
                    current_turn INTEGER NOT NULL,
                    board TEXT NOT NULL,
                    moves TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ended_at TEXT,
                    winner INTEGER
                )
            """)

    def _create_session(self, p1: int, p2: int, channel_id: int) -> int:
        board = create_empty_board()
        moves = []
        now = datetime.utcnow().isoformat()
        with self.conn:
            cur = self.conn.execute("""
                INSERT INTO sessions (channel_id, player1, player2, current_turn, board, moves, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (channel_id, p1, p2, p1, json.dumps(board), json.dumps(moves), now))
            return cur.lastrowid

    def _update_session(self, session_id: int, board, moves, current_turn, ended_at=None, winner=None):
        with self.conn:
            self.conn.execute("""
                UPDATE sessions 
                SET board = ?, moves = ?, current_turn = ?, ended_at = ?, winner = ?
                WHERE id = ?
            """, (json.dumps(board), json.dumps(moves), current_turn, ended_at, winner, session_id))

    def _get_active_session_for_channel(self, channel_id: int):
        cur = self.conn.execute("""
            SELECT * FROM sessions 
            WHERE ended_at IS NULL AND channel_id = ?
        """, (channel_id,))
        return cur.fetchone()

    def _get_active_session_for_user_channel(self, user_id: int, channel_id: int):
        cur = self.conn.execute("""
            SELECT * FROM sessions 
            WHERE ended_at IS NULL AND channel_id = ? AND (player1 = ? OR player2 = ?)
        """, (channel_id, user_id, user_id))
        return cur.fetchone()

    @discord.app_commands.command(
        name="gomoku",
        description="五目並べの対局を開始します。/gomoku opponent: @相手"
    )
    async def gomoku(self, interaction: discord.Interaction, opponent: discord.User) -> None:
        p1 = interaction.user.id
        p2 = opponent.id
        channel_id = interaction.channel.id

        if p1 == p2:
            await interaction.response.send_message("自分自身とは対局できません。", ephemeral=True)
            return

        # 既にこのチャンネルで進行中の対局があるか確認
        if self._get_active_session_for_channel(channel_id):
            await interaction.response.send_message("このチャンネルではすでに進行中の対局があります。", ephemeral=True)
            return

        session_id = self._create_session(p1, p2, channel_id)
        board = create_empty_board()
        board_str = render_board(board)
        embed = discord.Embed(
            title="🎮 Gomoku 対局開始",
            description=f"<@{p1}> vs <@{p2}>\n先手: <@{p1}> (🔴)\n後手: <@{p2}> (🔵)"
        )
        embed.add_field(name="盤面", value=f"```\n{board_str}\n```", inline=False)
        embed.set_footer(text=f"対局ID: {session_id} | /move x y で手を打ってください。座標は1～{BOARD_SIZE}で指定。")
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="move",
        description="五目並べの手を打ちます。/move x:座標 y:座標"
    )
    async def move(self, interaction: discord.Interaction, x: int, y: int) -> None:
        user_id = interaction.user.id
        channel_id = interaction.channel.id
        session = self._get_active_session_for_user_channel(user_id, channel_id)
        if not session:
            await interaction.response.send_message("このチャンネルで進行中の対局が見つかりません。", ephemeral=True)
            return

        if not (1 <= x <= BOARD_SIZE and 1 <= y <= BOARD_SIZE):
            await interaction.response.send_message(f"座標は1から{BOARD_SIZE}の間で指定してください。", ephemeral=True)
            return

        x_idx = x - 1
        y_idx = y - 1

        if user_id != session["current_turn"]:
            await interaction.response.send_message("今はあなたの手番ではありません。", ephemeral=True)
            return

        board = json.loads(session["board"])
        moves = json.loads(session["moves"])
        if board[y_idx][x_idx] != EMPTY:
            await interaction.response.send_message("そのマスはすでに埋まっています。", ephemeral=True)
            return

        if user_id == session["player1"]:
            player = PLAYER1
            other = session["player2"]
        else:
            player = PLAYER2
            other = session["player1"]

        board[y_idx][x_idx] = player
        moves.append({"x": x_idx, "y": y_idx, "player": player, "time": datetime.utcnow().isoformat()})

        if check_win(board, x_idx, y_idx, player):
            ended_at = datetime.utcnow().isoformat()
            self._update_session(session["id"], board, moves, current_turn=0, ended_at=ended_at, winner=user_id)
            board_str = render_board(board)
            embed = discord.Embed(
                title="🏆 対局終了",
                description=f"<@{user_id}> の勝利！"
            )
            embed.add_field(name="最終盤面", value=f"```\n{board_str}\n```", inline=False)
            await interaction.response.send_message(embed=embed)
            return

        if all(cell != EMPTY for row in board for cell in row):
            ended_at = datetime.utcnow().isoformat()
            self._update_session(session["id"], board, moves, current_turn=0, ended_at=ended_at, winner=0)
            board_str = render_board(board)
            embed = discord.Embed(
                title="🤝 引き分け",
                description="盤面が埋まりました。引き分けです。"
            )
            embed.add_field(name="最終盤面", value=f"```\n{board_str}\n```", inline=False)
            await interaction.response.send_message(embed=embed)
            return

        next_turn = other
        self._update_session(session["id"], board, moves, current_turn=next_turn)
        board_str = render_board(board)
        embed = discord.Embed(
            title="⏳ 次の一手",
            description=f"現在の手番: <@{next_turn}>"
        )
        embed.add_field(name="盤面", value=f"```\n{board_str}\n```", inline=False)
        embed.set_footer(text=f"対局ID: {session['id']}")
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gomoku(bot))
