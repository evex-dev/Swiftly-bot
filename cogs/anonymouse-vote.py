import discord
from discord.ext import commands
from typing import Final, Optional
import logging
from datetime import datetime
import sqlite3

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
                f"選択肢は2個以上{MAX_OPTIONS}個以下で指定してください。",
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

        await interaction.response.send_message(
            f"投票が開始されました。セッションID: {session_id}",
            ephemeral=True
        )

    @discord.app_commands.command(
        name="anony-answer",
        description="匿名で投票に回答します"
    )
    async def anony_answer(
        self,
        interaction: discord.Interaction,
        session_id: str,
        answer: str
    ) -> None:
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

        await interaction.response.send_message(
            "投票に回答しました。",
            ephemeral=True
        )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnonyVote(bot))
