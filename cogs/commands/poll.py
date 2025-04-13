import asyncio
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands
import hashlib
import json
import os
import pytz
import asyncpg
from dotenv import load_dotenv
from typing import Optional


RATE_LIMIT_SECONDS = 5  # コマンドのレート制限
VOTE_RATE_LIMIT_SECONDS = 2  # 投票アクションのレート制限
CLEANUP_DAYS = 1  # 終了した投票を保持する日数
MAX_OPTIONS = 5  # 最大選択肢数（Discordの制限に合わせる）
RECOVER = False  # BOT再起動時にアクティブな投票を復元するかどうか(レートリミット注意)


DURATION_CHOICES = [
    app_commands.Choice(name="30分", value=30),
    app_commands.Choice(name="1時間", value=60),
    app_commands.Choice(name="12時間", value=720),
    app_commands.Choice(name="1日", value=1440),
    app_commands.Choice(name="3日", value=4320),
    app_commands.Choice(name="1週間", value=10080)
]


def encrypt_user_id(user_id: int) -> str:
    """ユーザーIDを暗号化"""
    # 暗号化は行わず、そのまま返す
    return str(user_id)


def get_vote_hash(poll_id: int, user_id: int) -> str:
    """投票確認用のハッシュを生成"""
    data = f"{poll_id}:{user_id}".encode()
    return hashlib.sha256(data).hexdigest()


class PollView(discord.ui.View):
    def __init__(self, options: list, poll_id: int):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        for i, option in enumerate(options):
            self.add_item(PollButton(option, i, poll_id))


class PollButton(discord.ui.Button):
    def __init__(self, label: str, option_id: int, poll_id: int):
        super().__init__(style=discord.ButtonStyle.primary, label=label, custom_id=f"poll_{poll_id}_{option_id}")
        self.option_id = option_id
        self.poll_id = poll_id
        self._last_uses = {}

    def _check_rate_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=VOTE_RATE_LIMIT_SECONDS):
                remaining = VOTE_RATE_LIMIT_SECONDS - \
                    int(time_diff.total_seconds())
                return True, remaining
        return False, None

    async def callback(self, interaction: discord.Interaction):
        # レート制限
        is_limited, remaining = self._check_rate_limit(interaction.user.id)
        if is_limited:
            await interaction.response.send_message(
                f"投票が早すぎます。{remaining}秒後に試してね",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            async with self.db_pool.acquire() as db:
                async with db.transaction():
                    # 投票が有効かチェック
                    async with db.execute("SELECT is_active FROM polls WHERE id = ?", (self.poll_id,)) as cursor:
                        poll = await cursor.fetchone()
                        if not poll or not poll[0]:
                            await interaction.followup.send("この投票はもう終了しているよ", ephemeral=True)
                            return

                    # ユーザーが既に投票しているかチェック
                    vote_hash = get_vote_hash(
                        self.poll_id, interaction.user.id)
                    async with db.execute("SELECT 1 FROM vote_checks WHERE vote_hash = ?", (vote_hash,)) as cursor:
                        if await cursor.fetchone():
                            await interaction.followup.send("既に投票済みだよ", ephemeral=True)
                            return

                    # 暗号化されたユーザーIDと投票データを保存
                    encrypted_user_id = encrypt_user_id(interaction.user.id)
                    await db.execute("""
                        INSERT INTO votes (poll_id, encrypted_user_id, choice)
                        VALUES (?, ?, ?)
                    """, (self.poll_id, encrypted_user_id, self.option_id))

                    # 投票チェック用のハッシュを保存
                    await db.execute("INSERT INTO vote_checks (vote_hash) VALUES (?)", (vote_hash,))

                    # 投票数を更新
                    await db.execute("""
                        UPDATE polls
                        SET total_votes = (
                            SELECT COUNT(*)
                            FROM votes
                            WHERE poll_id = ?
                        )
                        WHERE id = ?
                    """, (self.poll_id, self.poll_id))

                    await db.commit()

                # 現在の投票数を取得
                async with db.execute("SELECT total_votes FROM polls WHERE id = ?", (self.poll_id,)) as cursor:
                    result = await cursor.fetchone()
                    total_votes = result[0] if result else 0

        except Exception as e:
            print(f"データベース接続エラー: {e}")
            await interaction.followup.send("システムエラーが発生したよ。もう一度試してね", ephemeral=True)
            return

        # レート制限を更新
        self._last_uses[interaction.user.id] = datetime.now()

        # 投票メッセージを更新
        try:
            async with self.db_pool.acquire() as db:
                async with db.execute("SELECT channel_id, message_id FROM polls WHERE id = ?", (self.poll_id,)) as cursor:
                    poll_location = await cursor.fetchone()

            if poll_location and poll_location[0] and poll_location[1]:
                channel_id, message_id = poll_location
                channel = interaction.guild.get_channel(channel_id)

                if channel:
                    try:
                        message = await channel.fetch_message(message_id)
                        if message.embeds and len(message.embeds) > 0:
                            embed = message.embeds[0]
                            for i, field in enumerate(embed.fields):
                                if field.name == "🗳️ 投票数":
                                    embed.set_field_at(
                                        i,
                                        name="🗳️ 投票数",
                                        value=str(total_votes),
                                        inline=False
                                    )
                                    await message.edit(embed=embed)
                                    break
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                        print(f"投票メッセージの更新中にエラーが発生しました: {e}")
        except Exception as e:
            print(f"投票数の更新中にエラーが発生しました: {e}")

        await interaction.followup.send(f"投票を受け付けたよ（現在の投票数: {total_votes}票）", ephemeral=True)


class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        load_dotenv()  # 環境変数をロード
        self.bot.loop.create_task(self.init_db_pool())
        self._last_uses = {}
        self.bot.loop.create_task(self.cleanup_old_polls())
        self.bot.loop.create_task(self.check_ended_polls())
        if RECOVER:
            self.bot.loop.create_task(self.recover_active_polls())

    async def init_db_pool(self):
        host = os.environ.get("DB_HOST")
        port = os.environ.get("DB_PORT")
        user = os.environ.get("DB_USER")
        password = os.environ.get("DB_PASSWORD")
        self.db_pool = await asyncpg.create_pool(user=user, password=password, database="poll", host=host, port=port)

    async def init_db(self):
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # pollsテーブル（AUTOINCREMENT→SERIALに変更）
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS polls (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT,
                        creator_id INTEGER NOT NULL,
                        end_time DOUBLE PRECISION NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT true,
                        options TEXT NOT NULL,
                        channel_id INTEGER,
                        message_id BIGINT,
                        total_votes INTEGER DEFAULT 0
                    )
                """)

                # 投票テーブル
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS votes (
                        poll_id INTEGER NOT NULL,
                        encrypted_user_id TEXT NOT NULL,
                        choice INTEGER NOT NULL
                    )
                """)

                # 投票チェック用
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS vote_checks (
                        vote_hash TEXT PRIMARY KEY
                    )
                """)

    async def recover_active_polls(self):
        """アクティブな投票の状態を復元"""
        await self.bot.wait_until_ready()
        try:
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    rows = await conn.fetch("""
                        SELECT id, title, options, channel_id, message_id, total_votes
                        FROM polls
                        WHERE is_active = true
                    """)
                    active_polls = rows

                for poll in active_polls:
                    poll_id = poll["id"]
                    title = poll["title"]
                    options_str = poll["options"]
                    channel_id = poll["channel_id"]
                    message_id = poll["message_id"]
                    total_votes = poll["total_votes"]
                    options = options_str.split(",")

                    # チャンネルとメッセージを取得
                    for guild in self.bot.guilds:
                        channel = guild.get_channel(channel_id)
                        if channel:
                            try:
                                # 古いメッセージを削除
                                if message_id:
                                    try:
                                        message = await channel.fetch_message(message_id)
                                        await message.delete()
                                    except:
                                        pass

                                # 新しい投票メッセージを作成
                                embed = discord.Embed(
                                    title=f"📊 {title}",
                                    description="🔒 **匿名投票**\n\n(BOTの再起動により再作成されました)",
                                    color=discord.Color.blue()
                                )
                                embed.add_field(
                                    name="🗳️ 投票数",
                                    value=str(total_votes),
                                    inline=False
                                )

                                view = PollView(options, poll_id)
                                message = await channel.send(embed=embed, view=view)

                                # 新しいメッセージIDを保存
                                await conn.execute(
                                    "UPDATE polls SET message_id = $1 WHERE id = $2",
                                    (message.id, poll_id)
                                )
                                break
                            except Exception as e:
                                print(f"投票の復元中にエラーが発生: {e}")
        except Exception as e:
            print(f"アクティブな投票の復元中にエラーが発生: {e}")

    async def cleanup_old_polls(self):
        """終了した古い投票を定期的に削除"""
        while True:
            try:
                async with self.db_pool.acquire() as conn:
                    async with conn.transaction():
                        cleanup_time = datetime.now() - timedelta(days=CLEANUP_DAYS)
                        # 関連する投票データを削除
                        await conn.execute("""
                            DELETE FROM votes WHERE poll_id IN (
                                SELECT id FROM polls
                                WHERE is_active = false
                                AND end_time < $1
                            )
                        """, cleanup_time.timestamp())
                        # 投票チェックデータを削除
                        await conn.execute("""
                            DELETE FROM vote_checks WHERE vote_hash IN (
                                SELECT vote_hash FROM vote_checks
                                WHERE vote_hash LIKE $1
                            )
                        """, f"%{cleanup_time.timestamp()}%")
                        # 投票自体を削除
                        await conn.execute("""
                            DELETE FROM polls
                            WHERE is_active = false
                            AND end_time < $1
                        """, cleanup_time.timestamp())
            except Exception as e:
                print(f"Error in cleanup_old_polls: {e}")
            await asyncio.sleep(86400)  # 24時間ごとに実行

    async def check_ended_polls(self):
        """終了時間を過ぎた投票を自動的に終了する"""
        while True:
            try:
                current_time = datetime.now().timestamp()
                async with self.db_pool.acquire() as conn:
                    async with conn.transaction():
                        rows = await conn.fetch("""
                            SELECT id, title, options, end_time, channel_id, message_id
                            FROM polls
                            WHERE is_active = true
                            AND end_time < $1
                        """, current_time)
                        ended_polls = rows
                        for poll in ended_polls:
                            poll_id = poll["id"]
                            title = poll["title"]
                            options = poll["options"].split(",")
                            # 投票を終了状態に更新
                            await conn.execute("UPDATE polls SET is_active = false WHERE id = $1", poll_id)
                            # 投票結果集計
                            vote_counts = {i: 0 for i in range(len(options))}
                            total_votes = 0
                            results = await conn.fetch("""
                                SELECT choice, COUNT(*) as votes
                                FROM votes
                                WHERE poll_id = $1
                                GROUP BY choice
                            """, poll_id)
                            for r in results:
                                vote_counts[r["choice"]] = r["votes"]
                                total_votes += r["votes"]

                            # 結果表示用のEmbed作成
                            embed = discord.Embed(
                                title=f"📊 投票結果: {title} (自動終了)",
                                description="🔒 この投票は匿名で実施されました",
                                color=discord.Color.green()
                            )

                            max_votes = max(vote_counts.values()
                                            ) if vote_counts else 0
                            for i, option in enumerate(options):
                                votes = vote_counts.get(i, 0)
                                percentage = (
                                    votes / total_votes * 100) if total_votes > 0 else 0
                                bar_length = int(
                                    percentage / 5 * total_votes / max_votes) if max_votes > 0 else 0
                                progress_bar = "█" * bar_length + \
                                    "▁" * (20 - bar_length)
                                embed.add_field(
                                    name=option,
                                    value=f"{progress_bar} {votes}票 ({percentage:.1f}%)",
                                    inline=False
                                )

                            embed.set_footer(
                                text=f"総投票数: {total_votes}票")

                            # チャンネルを取得して結果を送信
                            if poll[4]:
                                for guild in self.bot.guilds:
                                    channel = guild.get_channel(poll[3])
                                    if channel:
                                        try:
                                            await channel.send("投票の終了時間になったよ", embed=embed)

                                            if poll[5]:
                                                try:
                                                    original_message = await channel.fetch_message(poll[5])
                                                    await original_message.delete()
                                                except:
                                                    pass

                                            break
                                        except Exception as e:
                                            print(f"投票結果の送信中にエラーが発生しました: {e}")

            except Exception as e:
                print(f"Error in check_ended_polls: {e}")

            await asyncio.sleep(10)

    @app_commands.command(name="poll", description="匿名投票の作成・管理")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="投票を作成", value="create"),
            app_commands.Choice(name="投票を終了", value="end")
        ],
        duration=DURATION_CHOICES
    )
    @app_commands.describe(
        action="実行するアクション",
        title="投票のタイトル",
        description="投票の説明",
        duration="投票の期間",
        options="投票の選択肢（カンマ区切り）"
    )
    async def poll(self, interaction: discord.Interaction, action: str,
                   title: Optional[str] = None,
                   description: Optional[str] = None,
                   duration: Optional[app_commands.Choice[int]] = None,
                   options: Optional[str] = None):
        # レート制限チェック
        is_limited, remaining = self._check_rate_limit(interaction.user.id)
        if is_limited:
            await interaction.response.send_message(
                f"コマンドの実行が早すぎます。{remaining}秒後に試してね",
                ephemeral=True
            )
            return

        if action == "create":
            if not all([title, options]):
                await interaction.response.send_message("タイトルと選択肢は必須だよ", ephemeral=True)
                return

            option_list = [opt.strip() for opt in options.split(",")]
            if len(option_list) < 2:
                await interaction.response.send_message(
                    "選択肢は2つ以上必要だよ", ephemeral=True)
                return

            if len(option_list) > MAX_OPTIONS:
                await interaction.response.send_message(
                    f"選択肢は最大{MAX_OPTIONS}個までだよ", ephemeral=True)
                return

            # 先に応答を遅延させる
            await interaction.response.defer()

            try:
                jst = pytz.timezone("Asia/Tokyo")
                duration_minutes = duration.value if duration else 1440  # デフォルト24時間
                end_time = datetime.now(
                    jst) + timedelta(minutes=duration_minutes)

                async with self.db_pool.acquire() as conn:
                    async with conn.transaction():
                        row = await conn.fetchrow("""
                            INSERT INTO polls (title, description, creator_id, end_time, options, channel_id)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            RETURNING id
                        """, title, description or "", interaction.user.id, end_time.timestamp(), options, interaction.channel_id)
                        poll_id = row["id"]

                embed = discord.Embed(
                    title=f"📊 {title}",
                    description=f"🔒 **匿名投票**\n\n{description or '投票を開始するよ'}",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="⏰ 終了時刻",
                    value=f"{end_time.strftime('%Y/%m/%d %H:%M')} (JST)\n<t:{int(end_time.timestamp())}:R>",
                    inline=False
                )
                embed.add_field(
                    name="🗳️ 投票数",
                    value="0",
                    inline=False
                )

                view = PollView(option_list, poll_id)
                message = await interaction.followup.send(embed=embed, view=view)

                # 保存したメッセージIDの更新（例）
                async with self.db_pool.acquire() as conn:
                    await conn.execute("UPDATE polls SET message_id = $1 WHERE id = $2", message.id, poll_id)

                self._last_uses[interaction.user.id] = datetime.now()

            except Exception as e:
                print(f"投票作成中にエラーが発生: {e}")
                await interaction.followup.send("システムエラーが発生したよ", ephemeral=True)

        elif action == "end":
            try:
                async with self.db_pool.acquire() as conn:
                    polls = await conn.fetch("""
                        SELECT id, title FROM polls
                        WHERE creator_id = $1 AND is_active = true
                    """, interaction.user.id)

                if not polls:
                    await interaction.response.send_message("終了可能な投票が見つからないよ", ephemeral=True)
                    return

                options_menu = [
                    discord.SelectOption(label=f"ID: {r['id']} - {r['title']}", value=str(r["id"]))
                    for r in polls
                ]
                select_menu = discord.ui.Select(placeholder="終了する投票を選択してね", options=options_menu)

                async def select_callback(select_interaction: discord.Interaction):
                    poll_id = int(select_menu.values[0])
                    try:
                        async with self.db_pool.acquire() as conn:
                            async with conn.transaction():
                                await conn.execute("UPDATE polls SET is_active = false WHERE id = $1", poll_id)
                                results = await conn.fetch("""
                                    SELECT p.title, p.options, v.choice, COUNT(*) as votes
                                    FROM polls p
                                    LEFT JOIN votes v ON p.id = v.poll_id
                                    WHERE p.id = $1
                                    GROUP BY p.title, p.options, v.choice
                                """, poll_id)

                        if not results:
                            await select_interaction.response.send_message("エラーが発生したよ", ephemeral=True)
                            return

                        title = results[0]["title"]
                        options_list = results[0]["options"].split(",")
                        vote_counts = {i: 0 for i in range(len(options_list))}
                        total_votes = 0
                        for r in results:
                            if r["choice"] is not None:
                                vote_counts[r["choice"]] = r["votes"]
                                total_votes += r["votes"]

                        embed = discord.Embed(
                            title=f"📊 投票結果: {title}",
                            description="🔒 この投票は匿名で実施されたよ",
                            color=discord.Color.green()
                        )

                        max_votes = max(vote_counts.values()
                                        ) if vote_counts else 0
                        for i, option in enumerate(options_list):
                            votes = vote_counts.get(i, 0)
                            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                            bar_length = int(
                                percentage / 5 * total_votes / max_votes) if max_votes > 0 else 0
                            progress_bar = "█" * bar_length + \
                                "▁" * (20 - bar_length)
                            embed.add_field(
                                name=option,
                                value=f"{progress_bar} {votes}票 ({percentage:.1f}%)",
                                inline=False
                            )

                        embed.set_footer(text=f"総投票数: {total_votes}票")

                        await select_interaction.response.send_message("投票を終了したよ", ephemeral=True)
                        await interaction.channel.send(embed=embed)

                    except Exception as e:
                        print(f"投票終了中にエラーが発生: {e}")
                        await select_interaction.response.send_message("システムエラーが発生したよ", ephemeral=True)

                select_menu.callback = select_callback
                view = discord.ui.View()
                view.add_item(select_menu)
                await interaction.response.send_message("終了する投票を選択してね: ", view=view, ephemeral=True)

                self._last_uses[interaction.user.id] = datetime.now()

            except Exception as e:
                print(f"投票終了選択中にエラーが発生: {e}")
                await interaction.response.send_message("システムエラーが発生したよ", ephemeral=True)

        else:
            await interaction.response.send_message('無効なアクションです。"create" または "end" を指定してね',
                                                    ephemeral=True
                                                    )


async def setup(bot: commands.Bot):
    await bot.add_cog(Poll(bot))
