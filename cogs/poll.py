import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import datetime
import pytz
import asyncio
from typing import Optional
from datetime import datetime, timedelta


RATE_LIMIT_SECONDS = 5  # コマンドのレート制限
VOTE_RATE_LIMIT_SECONDS = 2  # 投票アクションのレート制限
CLEANUP_DAYS = 1  # 終了した投票を保持する日数

DURATION_CHOICES = [
    app_commands.Choice(name="30分", value=30),
    app_commands.Choice(name="1時間", value=60),
    app_commands.Choice(name="12時間", value=720),
    app_commands.Choice(name="1日", value=1440),
    app_commands.Choice(name="3日", value=4320),
    app_commands.Choice(name="1週間", value=10080)
]


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
                remaining = VOTE_RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
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

        async with aiosqlite.connect('./data/poll.db') as db:
            # 投票が有効かチェック
            async with db.execute('SELECT is_active FROM polls WHERE id = ?', (self.poll_id,)) as cursor:
                poll = await cursor.fetchone()
                if not poll or not poll[0]:
                    await interaction.response.send_message("この投票はもう終了しているよ", ephemeral=True)
                    return

            # ユーザーが既に投票しているかチェック
            async with db.execute('SELECT 1 FROM votes WHERE poll_id = ? AND user_id = ?', (self.poll_id, interaction.user.id)) as cursor:
                if await cursor.fetchone():
                    await interaction.response.send_message("既に投票済みだよ", ephemeral=True)
                    return

            # 新しい投票を登録
            await db.execute('INSERT INTO votes (poll_id, user_id, choice) VALUES (?, ?, ?)', (self.poll_id, interaction.user.id, self.option_id))
            await db.commit()

            # 現在の投票数を取得
            async with db.execute('SELECT COUNT(*) FROM votes WHERE poll_id = ?', (self.poll_id,)) as cursor:
                total_votes = await cursor.fetchone()
                total_votes = total_votes[0] if total_votes else 0

        # レート制限を更新
        self._last_uses[interaction.user.id] = datetime.now()
        await interaction.response.send_message(f"投票を受け付けたよ（現在の投票数: {total_votes}票）", ephemeral=True)


class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_uses = {}
        self.bot.loop.create_task(self.init_db())
        self.bot.loop.create_task(self.cleanup_old_polls())
        self.bot.loop.create_task(self.check_ended_polls())

    def _check_rate_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        now = datetime.now()
        if user_id in self._last_uses:
            time_diff = now - self._last_uses[user_id]
            if time_diff < timedelta(seconds=RATE_LIMIT_SECONDS):
                remaining = RATE_LIMIT_SECONDS - int(time_diff.total_seconds())
                return True, remaining
        return False, None

    async def init_db(self):
        async with aiosqlite.connect('./data/poll.db') as db:
            # polls
            await db.execute('''
                CREATE TABLE IF NOT EXISTS polls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    creator_id INTEGER NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    options TEXT NOT NULL
                )
            ''')

            # votes
            await db.execute('''
                CREATE TABLE IF NOT EXISTS votes (
                    poll_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    choice INTEGER NOT NULL,
                    UNIQUE(poll_id, user_id)
                )
            ''')
            await db.commit()

    async def cleanup_old_polls(self):
        """終了した古い投票を定期的に削除"""
        while True:
            try:
                async with aiosqlite.connect('./data/poll.db') as db:
                    # CLEANUP_DAYS日以上前に終了した投票を削除
                    cleanup_time = datetime.now() - timedelta(days=CLEANUP_DAYS)
                    # 関連する投票データを削除
                    await db.execute('''
                        DELETE FROM votes WHERE poll_id IN (
                            SELECT id FROM polls
                            WHERE is_active = 0
                            AND end_time < ?
                        )
                    ''', (cleanup_time.timestamp(),))
                    # 投票自体を削除
                    await db.execute('''
                        DELETE FROM polls
                        WHERE is_active = 0
                        AND end_time < ?
                    ''', (cleanup_time.timestamp(),))
                    await db.commit()
            except Exception as e:
                print(f"Error in cleanup_old_polls: {e}")
            await asyncio.sleep(86400)  # 24時間ごとに実行

    async def check_ended_polls(self):
        """終了時間を過ぎた投票を自動的に終了する"""
        while True:
            try:
                current_time = datetime.now().timestamp()
                async with aiosqlite.connect('./data/poll.db') as db:
                    # 終了時間が過ぎているがまだアクティブな投票を検索
                    async with db.execute('''
                        SELECT id, title, options, end_time
                        FROM polls
                        WHERE is_active = 1
                        AND end_time < ?
                    ''', (current_time,)) as cursor:
                        ended_polls = await cursor.fetchall()

                    # 終了した投票ごとに処理
                    for poll in ended_polls:
                        poll_id, title, options_str, end_time = poll

                        # 投票を終了状態に更新
                        await db.execute('UPDATE polls SET is_active = 0 WHERE id = ?', (poll_id,))

                        # 投票結果を集計
                        async with db.execute('''
                            SELECT choice, COUNT(*) as votes
                            FROM votes
                            WHERE poll_id = ?
                            GROUP BY choice
                        ''', (poll_id,)) as cursor:
                            results = await cursor.fetchall()

                        await db.commit()

                        # 結果を集計
                        options = options_str.split(',')
                        vote_counts = {i: 0 for i in range(len(options))}
                        total_votes = 0

                        for choice, votes in results:
                            if choice is not None:
                                vote_counts[choice] = votes
                                total_votes += votes

                        # 結果表示用のEmbed作成
                        embed = discord.Embed(
                            title=f"📊 投票結果: {title} (自動終了)",
                            color=discord.Color.green()
                        )

                        max_votes_count = max(vote_counts.values()) if vote_counts else 0
                        for i, option in enumerate(options):
                            votes = vote_counts.get(i, 0)
                            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                            bar_length = int(percentage / 5 * total_votes / max_votes_count) if max_votes_count > 0 else 0
                            progress_bar = '█' * bar_length + '▁' * (20 - bar_length)
                            embed.add_field(
                                name=option,
                                value=f"{progress_bar} {votes}票 ({percentage:.1f}%)",
                                inline=False
                            )

                        embed.set_footer(text=f"総投票数: {total_votes}票")

                        # 投票が作成されたチャンネルを特定して結果を送信
                        # 注意: これはメッセージ履歴から投票メッセージを見つける必要があるため、
                        # 全てのチャンネルで投票結果を表示できない場合があります
                        for guild in self.bot.guilds:
                            for channel in guild.text_channels:
                                try:
                                    # 過去のメッセージから投票IDを含むメッセージを検索
                                    async for message in channel.history(limit=100):
                                        if message.embeds and len(message.embeds) > 0:
                                            footer_text = message.embeds[0].footer.text
                                            if footer_text and f"投票ID: {poll_id}" in footer_text:
                                                await channel.send("投票の終了時間になったよ", embed=embed)
                                                break
                                except (discord.Forbidden, discord.HTTPException):
                                    continue

            except Exception as e:
                print(f"Error in check_ended_polls: {e}")

            await asyncio.sleep(55)  # 1分ごとに実行

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
    async def poll(
        self,
        interaction: discord.Interaction,
        action: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        duration: Optional[app_commands.Choice[int]] = None,
        options: Optional[str] = None
    ):
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
                await interaction.response.send_message(
                    "タイトルと選択肢は必須だよ", ephemeral=True)
                return

            option_list = [opt.strip() for opt in options.split(',')]
            if len(option_list) < 2:
                await interaction.response.send_message(
                    "選択肢は2つ以上必要だよ", ephemeral=True)
                return

            jst = pytz.timezone('Asia/Tokyo')
            duration_minutes = duration.value if duration else 1440  # デフォルト24時間
            end_time = datetime.now(jst) + timedelta(minutes=duration_minutes)

            async with aiosqlite.connect('./data/poll.db') as db:
                cursor = await db.execute(
                    'INSERT INTO polls (title, description, creator_id, end_time, options) VALUES (?, ?, ?, ?, ?)',
                    (title, description or "", interaction.user.id, end_time.timestamp(), options)
                )
                poll_id = cursor.lastrowid
                await db.commit()

            embed = discord.Embed(
                title=f"📊 {title}",
                description=description or "投票を開始するよ",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="終了時刻",
                value=f"{end_time.strftime('%Y/%m/%d %H:%M')} (JST)\n<t:{int(end_time.timestamp())}:R>",
                inline=False
            )
            embed.add_field(
                name="投票数",
                value="0",
                inline=False
            )
            embed.set_footer(text=f"投票ID: {poll_id}")

            view = PollView(option_list, poll_id)
            await interaction.response.send_message(embed=embed, view=view)

            # レート制限を更新
            self._last_uses[interaction.user.id] = datetime.now()

        elif action == "end":
            async with aiosqlite.connect('./data/poll.db') as db:
                # ユーザーが作成した有効な投票を取得
                async with db.execute(
                    'SELECT id, title, options FROM polls WHERE creator_id = ? AND is_active = 1',
                    (interaction.user.id,)
                ) as cursor:
                    polls = await cursor.fetchall()

            if not polls:
                await interaction.response.send_message(
                    "終了可能な投票が見つからないよ", ephemeral=True)
                return

            # 投票選択用のセレクトメニューを作成
            options = [
                discord.SelectOption(
                    label=f"ID: {poll[0]} - {poll[1]}",
                    value=str(poll[0])
                ) for poll in polls
            ]

            select_menu = discord.ui.Select(
                placeholder="終了する投票を選択してね",
                options=options
            )

            async def select_callback(interaction: discord.Interaction):
                poll_id = int(select_menu.values[0])
                async with aiosqlite.connect('./data/poll.db') as db:
                    # 投票を終了状態に更新
                    await db.execute('UPDATE polls SET is_active = 0 WHERE id = ?', (poll_id,))

                    # 投票結果を集計
                    async with db.execute('''
                        SELECT p.title, p.options,
                               v.choice, COUNT(*) as votes
                        FROM polls p
                        LEFT JOIN votes v ON p.id = v.poll_id
                        WHERE p.id = ?
                        GROUP BY v.choice
                    ''', (poll_id,)) as cursor:
                        results = await cursor.fetchall()
                    await db.commit()

                if not results:
                    await interaction.response.send_message("エラーが発生したよ", ephemeral=True)
                    return

                title = results[0][0]
                options = results[0][1].split(',')

                # 結果を集計
                vote_counts = {i: 0 for i in range(len(options))}
                total_votes = 0
                for result in results:
                    if result[2] is not None:  # None check for LEFT JOIN
                        vote_counts[result[2]] = result[3]
                        total_votes += result[3]

                # 結果表示用のEmbed作成
                embed = discord.Embed(
                    title=f"📊 投票結果: {title}",
                    color=discord.Color.green()
                )

                max_votes_count = max(vote_counts.values()) if vote_counts else 0
                for i, option in enumerate(options):
                    votes = vote_counts.get(i, 0)
                    percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                    bar_length = int(percentage / 5 * total_votes / max_votes_count) if max_votes_count > 0 else 0
                    progress_bar = '█' * bar_length + '▁' * (20 - bar_length)
                    embed.add_field(
                        name=option,
                        value=f"{progress_bar} {votes}票 ({percentage:.1f}%)",
                        inline=False
                    )

                embed.set_footer(text=f"総投票数: {total_votes}票")

                await interaction.response.send_message("投票を終了したよ", ephemeral=True)

                await interaction.channel.send(embed=embed)

            select_menu.callback = select_callback
            view = discord.ui.View()
            view.add_item(select_menu)
            await interaction.response.send_message("終了する投票を選択してね: ", view=view, ephemeral=True)

            # レート制限を更新
            self._last_uses[interaction.user.id] = datetime.now()

        else:
            # ここには基本的に来ない
            await interaction.response.send_message(
                "無効なアクションです。'create' または 'end' を指定してね",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Poll(bot))
