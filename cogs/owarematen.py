import discord
from discord.ext import commands
import sqlite3
import uuid
import os
import asyncio


class DiscowaremaTen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # ディレクトリに対して正しいパスを設定
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "owarematen_session.db")
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                channel_id INTEGER,
                guild_id INTEGER,
                theme TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_id INTEGER,
                user_name TEXT,
                answer TEXT,
                UNIQUE(session_id, user_id)
            )
        """)
        conn.commit()
        conn.close()

    async def auto_open(self, session_id: str, channel_id: int, guild_id: int):
        # 1時間待機
        await asyncio.sleep(60 * 60)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT session_id, theme FROM sessions WHERE session_id = ?", (session_id,))
        session = c.fetchone()
        if not session:
            conn.close()
            return
        theme = session[1]
        embed = discord.Embed(title="自動終了: 終われまテン", description="V1.0 by K-Nana", color=discord.Color.green())
        embed.add_field(name="お題", value=theme, inline=False)
        c.execute("SELECT user_name, answer FROM answers WHERE session_id = ?", (session_id,))
        answers = c.fetchall()
        if len(answers) == 0:
            embed.add_field(name="おっと。", value="誰も答えていないようです...", inline=False)
        else:
            for user_name, answer in answers:
                embed.add_field(name=f"{user_name}の回答", value=answer, inline=False)
        c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM answers WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)

    @discord.app_commands.command(name="owarematen-start-custom", description="終われまテンをカスタムお題で開始します。")
    async def start_custom(self, ctx, theme: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM sessions WHERE channel_id = ? AND guild_id = ?", (ctx.channel.id, ctx.guild_id))
        session = c.fetchone()
        if session:
            embed = discord.Embed(title="終われまテン", description="V1.0 by K-Nana", color=discord.Color.red())
            embed.add_field(name="他のゲームが進行中です", value="先に/owarematen-open-answersでゲームを終了してください。", inline=False)
            embed.set_footer(text=f"セッションID: {session[0]}")
            await ctx.response.send_message(embed=embed)
            conn.close()
            return
        session_id = uuid.uuid4().hex
        c.execute("INSERT INTO sessions (session_id, channel_id, guild_id, theme) VALUES (?, ?, ?, ?)",
                  (session_id, ctx.channel.id, ctx.guild_id, theme))
        conn.commit()
        conn.close()

        # セッション開始時のメッセージにタイムアウトの情報を追加
        embed = discord.Embed(title="終われまテン", description="V1.0 by K-Nana", color=discord.Color.blurple())
        embed.add_field(name="お題", value=theme, inline=False)
        embed.add_field(name="回答方法", value="/owarematen-answerで回答できます。", inline=False)
        embed.add_field(name="注意", value="このセッションは1時間後に自動で終了し回答が公開されます。", inline=False)
        embed.set_footer(text=f"セッションID: {session_id}")
        await ctx.response.send_message(embed=embed)

        # 1時間後に自動で回答を公開するタスクをスケジュール
        self.bot.loop.create_task(self.auto_open(session_id, ctx.channel.id, ctx.guild_id))

    @discord.app_commands.command(name="owarematen-open-answers", description="全員の回答を開きます。終われまテンの終了コマンドも兼ねています。")
    async def open_answers(self, ctx):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT session_id, theme FROM sessions WHERE channel_id = ? AND guild_id = ?", (ctx.channel.id, ctx.guild_id))
        session = c.fetchone()
        if session:
            session_id, theme = session
            embed = discord.Embed(title="終われまテン", description="V1.0 by K-Nana", color=discord.Color.green())
            embed.add_field(name="お題", value=theme, inline=False)
            embed.set_footer(text=f"セッションID: {session_id}")
            c.execute("SELECT user_name, answer FROM answers WHERE session_id = ?", (session_id,))
            answers = c.fetchall()
            if len(answers) == 0:
                embed.add_field(name="おっと。", value="誰も答えていないようです...", inline=False)
            else:
                for user_name, answer in answers:
                    embed.add_field(name=f"{user_name}の回答", value=answer, inline=False)
            c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            c.execute("DELETE FROM answers WHERE session_id = ?", (session_id,))
            conn.commit()
            conn.close()
            await ctx.response.send_message(embed=embed)
        else:
            conn.close()
            embed = discord.Embed(title="終われまテン", description="V1.0 by K-Nana", color=discord.Color.red())
            embed.add_field(name="ゲームが開始されていません", value="先に/owarematen-start-customでゲームを開始してください。", inline=False)
            await ctx.response.send_message(embed=embed)

    @discord.app_commands.command(name="owarematen-answer", description="終われまテンに回答します。")
    async def answer(self, ctx, answer: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT session_id FROM sessions WHERE channel_id = ? AND guild_id = ?", (ctx.channel.id, ctx.guild_id))
        session = c.fetchone()
        if not session:
            conn.close()
            await ctx.response.send_message("ゲームが開始されていません。/owarematen-start-customで開始してください。", ephemeral=True)
            return

        session_id = session[0]

        # 既に回答済みかチェック
        c.execute("SELECT * FROM answers WHERE session_id = ? AND user_id = ?", (session_id, ctx.user.id))
        if c.fetchone():
            conn.close()
            await ctx.response.send_message("既に回答済みです。一人一回のみ回答できます。", ephemeral=True)
            return

        try:
            c.execute("INSERT INTO answers (session_id, user_id, user_name, answer) VALUES (?, ?, ?, ?)",
                     (session_id, ctx.user.id, ctx.user.name, answer))
            conn.commit()
            c.execute("SELECT COUNT(*) FROM answers WHERE session_id = ?", (session_id,))
            count = c.fetchone()[0]
            conn.close()

            await ctx.response.send_message(f"{answer}で回答しました", ephemeral=True)
            notify_embed = discord.Embed(title="回答受付", description=f"{ctx.user.name}が回答しました。", color=discord.Color.orange())
            notify_embed.add_field(name="現在の回答数", value=str(count), inline=False)
            notify_embed.set_footer(text=f"セッションID: {session_id}")
            await ctx.channel.send(embed=notify_embed)

        except sqlite3.IntegrityError:
            conn.close()
            await ctx.response.send_message("既に回答済みです。一人一回のみ回答できます。", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DiscowaremaTen(bot))
