import discord
from discord.ext import commands
import asyncpg
import os
from dotenv import load_dotenv
from typing import Final, Optional, List, Tuple
import logging
import uuid
import asyncio

VERSION: Final[str] = "V1.0 by K-Nana"
SESSION_TIMEOUT: Final[int] = 3600  # 1時間（秒）

CREATE_SESSIONS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    channel_id INTEGER,
    guild_id INTEGER,
    theme TEXT
)
"""

CREATE_ANSWERS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    user_id INTEGER,
    answer TEXT,
    UNIQUE(session_id, user_id)
)
"""

EMBED_COLORS: Final[dict] = {
    "start": discord.Color.blurple(),
    "success": discord.Color.green(),
    "error": discord.Color.red(),
    "notify": discord.Color.orange()
}

ERROR_MESSAGES: Final[dict] = {
    "game_in_progress": "他のゲームが進行中です。先に/owarematen-open-answersでゲームを終了してください。",
    "no_game": "ゲームが開始されていません。/owarematen-start-customで開始してください。",
    "already_answered": "既に回答済みです。一人一回のみ回答できます。",
    "db_error": "DBエラーが発生しました: {}"
}

logger = logging.getLogger(__name__)

class GameSession:
    """ゲームセッションを管理するクラス"""

    def __init__(
        self,
        session_id: str,
        channel_id: int,
        guild_id: int,
        theme: str
    ) -> None:
        self.session_id = session_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.theme = theme

class DiscowaremaTen(commands.Cog):
    """終われまテン機能を提供"""

    def _create_game_embed(
        self,
        title: str,
        session: Optional[GameSession] = None,
        answers: Optional[List[Tuple[int, str]]] = None,
        color_key: str = "success",
        error_message: Optional[str] = None
    ) -> discord.Embed:
        """ゲーム用の埋め込みメッセージを作成"""
        embed = discord.Embed(title=title, color=EMBED_COLORS[color_key])
        if session:
            embed.add_field(name="お題", value=session.theme, inline=False)
            embed.set_footer(text=f"セッションID: {session.session_id}")
        if answers:
            answer_text = "\n".join([f"<@{user_id}>: {answer}" for user_id, answer in answers])
            embed.add_field(name="回答一覧", value=answer_text or "なし", inline=False)
        if error_message:
            embed.add_field(name="エラー", value=error_message, inline=False)
        return embed

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db_pool = None

    async def cog_load(self) -> None:
        load_dotenv()
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")

        if not all([db_host, db_port, db_user, db_password]):
            raise ValueError("One or more database environment variables are missing or invalid.")
        self.db_pool = await asyncpg.create_pool(
            dsn=f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/owarematen"
        )
        await self._init_db()

    async def _init_db(self) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(CREATE_SESSIONS_TABLE)
            await conn.execute(CREATE_ANSWERS_TABLE)

    async def _get_session(self, channel_id: int, guild_id: int) -> Optional[GameSession]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT session_id, theme FROM sessions WHERE channel_id = $1 AND guild_id = $2",
                channel_id, guild_id
            )
            if row:
                return GameSession(row["session_id"], channel_id, guild_id, row["theme"])
        return None

    async def _get_answers(self, session_id: str) -> List[Tuple[int, str]]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, answer FROM answers WHERE session_id = $1",
                session_id
            )
            return [(r["user_id"], r["answer"]) for r in rows]

    async def _clear_session(self, session_id: str) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE session_id = $1", session_id)
            await conn.execute("DELETE FROM answers WHERE session_id = $1", session_id)

    async def auto_open(self, session_id: str, channel_id: int, guild_id: int) -> None:
        await asyncio.sleep(SESSION_TIMEOUT)
        try:
            session = GameSession(session_id, channel_id, guild_id, "Unknown Theme")
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT theme FROM sessions WHERE session_id = $1", session_id
                )
                if row:
                    session.theme = row["theme"]
                else:
                    return
            answers = await self._get_answers(session_id)
            await self._clear_session(session_id)
            if channel := self.bot.get_channel(channel_id):
                embed = self._create_game_embed("自動終了: 終われまテン", session, answers)
                await channel.send(embed=embed)
        except Exception as e:
            logger.error("Error in auto_open: %s", e, exc_info=True)

    @discord.app_commands.command(
        name="owarematen-start-custom",
        description="終われまテンをカスタムお題で開始します。"
    )
    async def start_custom(self, interaction: discord.Interaction, theme: str) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return
        try:
            if session := await self._get_session(interaction.channel_id, interaction.guild_id):
                embed = self._create_game_embed(
                    "終われまテン", session,
                    color_key="error",
                    error_message=ERROR_MESSAGES["game_in_progress"]
                )
                await interaction.response.send_message(embed=embed)
                return

            session_id = uuid.uuid4().hex
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO sessions (session_id, channel_id, guild_id, theme) VALUES ($1, $2, $3, $4)",
                    session_id, interaction.channel_id, interaction.guild_id, theme
                )

            session = GameSession(session_id, interaction.channel_id, interaction.guild_id, theme)
            embed = self._create_game_embed("終われまテン", session, color_key="start")
            embed.add_field(name="回答方法", value="/owarematen-answerで回答できます。", inline=False)
            embed.add_field(name="注意", value="このセッションは1時間後に自動で終了し回答が公開されます。", inline=False)
            await interaction.response.send_message(embed=embed)

            self.bot.loop.create_task(self.auto_open(session_id, interaction.channel_id, interaction.guild_id))

        except Exception as e:
            logger.error("Error in start_custom: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["db_error"].format(str(e)), ephemeral=True
            )

    @discord.app_commands.command(
        name="owarematen-open-answers",
        description="全員の回答を開きます。終われまテンの終了コマンドも兼ねています。"
    )
    async def open_answers(self, interaction: discord.Interaction) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return
        try:
            if session := await self._get_session(interaction.channel_id, interaction.guild_id):
                answers = await self._get_answers(session.session_id)
                await self._clear_session(session.session_id)
                embed = self._create_game_embed("終われまテン", session, answers)
                await interaction.response.send_message(embed=embed)
            else:
                embed = self._create_game_embed(
                    "終われまテン",
                    color_key="error",
                    error_message=ERROR_MESSAGES["no_game"]
                )
                await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error("Error in open_answers: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["db_error"].format(str(e)), ephemeral=True
            )

    @discord.app_commands.command(
        name="owarematen-answer",
        description="終われまテンに回答します。"
    )
    async def answer(self, interaction: discord.Interaction, answer: str) -> None:
        # プライバシーモードのユーザーを無視
        privacy_cog = self.bot.get_cog("Privacy")
        if privacy_cog and privacy_cog.is_private_user(interaction.user.id):
            return
        try:
            if not (session := await self._get_session(interaction.channel_id, interaction.guild_id)):
                await interaction.response.send_message(ERROR_MESSAGES["no_game"], ephemeral=True)
                return

            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM answers WHERE session_id = $1 AND user_id = $2",
                    session.session_id, interaction.user.id
                )
                if row:
                    await interaction.response.send_message(ERROR_MESSAGES["already_answered"], ephemeral=True)
                    return

                await conn.execute(
                    "INSERT INTO answers (session_id, user_id, answer) VALUES ($1, $2, $3)",
                    session.session_id, interaction.user.id, answer
                )
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM answers WHERE session_id = $1",
                    session.session_id
                )

            await interaction.response.send_message(f"{answer}で回答しました", ephemeral=True)

            notify_embed = discord.Embed(
                title="回答受付",
                description=f"ユーザーID: {interaction.user.id}が回答しました。",
                color=EMBED_COLORS["notify"]
            )
            notify_embed.add_field(name="現在の回答数", value=str(count), inline=False)
            notify_embed.set_footer(text=f"セッションID: {session.session_id}")
            await interaction.channel.send(embed=notify_embed)

        except asyncpg.UniqueViolationError:
            await interaction.response.send_message(ERROR_MESSAGES["already_answered"], ephemeral=True)
        except Exception as e:
            logger.error("Error in answer: %s", e, exc_info=True)
            await interaction.response.send_message(
                ERROR_MESSAGES["db_error"].format(str(e)), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DiscowaremaTen(bot))
