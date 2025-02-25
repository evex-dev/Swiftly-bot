import discord
from discord.ext import commands
from typing import Final, Optional
import logging
from datetime import datetime
import sqlite3
import matplotlib.pyplot as plt
import io
import matplotlib
import japanize_matplotlib
matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']

# 定数定義
MAX_OPTIONS: Final[int] = 10
DB_PATH: Final[str] = 'data/votes.db'

logger = logging.getLogger(__name__)

class AnonyVote(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self._create_table()

    def _create_table(self) -> None:
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS votes (
                    session_id TEXT PRIMARY KEY,
                    channel_id INTEGER,
                    topic TEXT,
                    options TEXT
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS answers (
                    session_id TEXT,
                    user_id INTEGER,
                    answer TEXT,
                    PRIMARY KEY (session_id, user_id)
                )
            ''')

    @discord.app_commands.command(
        name="anony-vote",
        description="匿名で投票を開始します"
    )
    async def anony_vote(
        self,
        interaction: discord.Interaction,
        topic: str,
        options: str
    ) -> None:
        options_list = options.split(',')
        if len(options_list) < 2 or len(options_list) > MAX_OPTIONS:
            await interaction.response.send_message(
                f"選択肢は2個以上{MAX_OPTIONS}個以下で指定してください。「,」で区切ってください。",
                ephemeral=True
            )
            return

        session_id = str(datetime.now().timestamp())
        options_str = ",".join(options_list)
        with self.conn:
            self.conn.execute(
                'INSERT INTO votes (session_id, channel_id, topic, options) VALUES (?, ?, ?, ?)',
                (session_id, interaction.channel_id, topic, options_str)
            )

        embed = discord.Embed(
            title="匿名投票が開始されました",
            description=f"トピック: {topic}\n選択肢: {', '.join(options_list)}\nセッションID: {session_id}",
            color=discord.Color.blue()
        )

        view = discord.ui.View()
        for option in options_list:
            button = discord.ui.Button(label=option, style=discord.ButtonStyle.primary)
            button.callback = self.create_button_callback(session_id, option)
            view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    def create_button_callback(self, session_id: str, answer: str):
        async def button_callback(interaction: discord.Interaction):
            vote = self.conn.execute(
                'SELECT channel_id FROM votes WHERE session_id = ?',
                (session_id,)
            ).fetchone()

            if not vote:
                await interaction.response.send_message(
                    "無効なセッションIDです。",
                    ephemeral=True
                )
                return

            if vote[0] != interaction.channel_id:
                await interaction.response.send_message(
                    "このチャンネルでは投票に回答できません。",
                    ephemeral=True
                )
                return

            existing_answer = self.conn.execute(
                'SELECT answer FROM answers WHERE session_id = ? AND user_id = ?',
                (session_id, interaction.user.id)
            ).fetchone()

            if existing_answer:
                await interaction.response.send_message(
                    "既に投票済みです。",
                    ephemeral=True
                )
                return

            with self.conn:
                self.conn.execute(
                    'INSERT INTO answers (session_id, user_id, answer) VALUES (?, ?, ?)',
                    (session_id, interaction.user.id, answer)
                )

            embed = discord.Embed(
                title="投票に回答しました",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        return button_callback

    @discord.app_commands.command(
        name="anony-end",
        description="投票を終了し、結果を表示します"
    )
    async def anony_end(
        self,
        interaction: discord.Interaction,
        session_id: str
    ) -> None:
        vote = self.conn.execute(
            'SELECT topic, options FROM votes WHERE session_id = ?',
            (session_id,)
        ).fetchone()

        if not vote:
            await interaction.response.send_message(
                "無効なセッションIDです。",
                ephemeral=True
            )
            return

        answers = self.conn.execute(
            'SELECT answer, COUNT(*) FROM answers WHERE session_id = ? GROUP BY answer',
            (session_id,)
        ).fetchall()

        if not answers:
            await interaction.response.send_message(
                "投票がありません。",
                ephemeral=True
            )
            return

        topic, options_str = vote
        options_list = options_str.split(',')
        answer_counts = {option: 0 for option in options_list}
        for answer, count in answers:
            answer_counts[answer] = count

        # 結果を文字で表示
        result_str = f"投票結果: {topic}\n"
        for option, count in answer_counts.items():
            result_str += f"{option}: {'█' * count} ({count}票)\n"

        embed = discord.Embed(
            title="投票結果",
            description=result_str,
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

        # セッションをDBから削除
        with self.conn:
            self.conn.execute('DELETE FROM votes WHERE session_id = ?', (session_id,))
            self.conn.execute('DELETE FROM answers WHERE session_id = ?', (session_id,))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnonyVote(bot))
