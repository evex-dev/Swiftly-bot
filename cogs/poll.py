import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import datetime
import pytz
from typing import Optional

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

    async def callback(self, interaction: discord.Interaction):
        async with aiosqlite.connect('./data/poll.db') as db:
            # 投票が有効かチェック
            async with db.execute('SELECT is_active FROM polls WHERE id = ?', (self.poll_id,)) as cursor:
                poll = await cursor.fetchone()
                if not poll or not poll[0]:
                    await interaction.response.send_message("この投票は終了しています。", ephemeral=True)
                    return

            # 既存の投票を削除
            await db.execute('DELETE FROM votes WHERE poll_id = ? AND user_id = ?',
                           (self.poll_id, interaction.user.id))

            # 新しい投票を登録
            await db.execute('INSERT INTO votes (poll_id, user_id, choice) VALUES (?, ?, ?)',
                           (self.poll_id, interaction.user.id, self.option_id))
            await db.commit()

        await interaction.response.send_message("投票を受け付けました。", ephemeral=True)

class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.init_db())

    async def init_db(self):
        async with aiosqlite.connect('./data/poll.db') as db:
            # polls テーブルの作成
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

            # votes テーブルの作成
            await db.execute('''
                CREATE TABLE IF NOT EXISTS votes (
                    poll_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    choice INTEGER NOT NULL,
                    UNIQUE(poll_id, user_id)
                )
            ''')
            await db.commit()

    @app_commands.command(name="poll", description="投票の作成・管理を行います")
    @app_commands.describe(
        action="実行するアクション（create/end）",
        title="投票のタイトル",
        description="投票の説明",
        duration="投票の期間（時間）デフォルト24時間",
        options="投票の選択肢（カンマ区切り）"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        action: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        duration: Optional[int] = 24,
        options: Optional[str] = None
    ):
        if action == "create":
            if not all([title, options]):
                await interaction.response.send_message(
                    "タイトルと選択肢は必須です。", ephemeral=True)
                return

            option_list = [opt.strip() for opt in options.split(',')]
            if len(option_list) < 2:
                await interaction.response.send_message(
                    "選択肢は2つ以上必要です。", ephemeral=True)
                return

            jst = pytz.timezone('Asia/Tokyo')
            end_time = datetime.datetime.now(jst) + datetime.timedelta(hours=duration)

            async with aiosqlite.connect('./data/poll.db') as db:
                cursor = await db.execute(
                    'INSERT INTO polls (title, description, creator_id, end_time, options) VALUES (?, ?, ?, ?, ?)',
                    (title, description or "", interaction.user.id, end_time.timestamp(), options)
                )
                poll_id = cursor.lastrowid
                await db.commit()

            embed = discord.Embed(
                title=f"📊 {title}",
                description=description or "投票を開始します。",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="終了時刻",
                value=f"{end_time.strftime('%Y/%m/%d %H:%M')} (JST)",
                inline=False
            )
            embed.set_footer(text=f"投票ID: {poll_id}")

            view = PollView(option_list, poll_id)
            await interaction.response.send_message(embed=embed, view=view)

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
                    "終了可能な投票が見つかりません。", ephemeral=True)
                return

            # 投票選択用のセレクトメニューを作成
            options = [
                discord.SelectOption(
                    label=f"ID: {poll[0]} - {poll[1]}",
                    value=str(poll[0])
                ) for poll in polls
            ]

            select_menu = discord.ui.Select(
                placeholder="終了する投票を選択してください",
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
                    await interaction.response.send_message("エラーが発生しました。", ephemeral=True)
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

                for i, option in enumerate(options):
                    votes = vote_counts.get(i, 0)
                    percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                    bar_length = int(percentage / 5)  # 20文字を最大とする
                    bar = '█' * bar_length + '░' * (20 - bar_length)
                    embed.add_field(
                        name=option,
                        value=f"{bar} {votes}票 ({percentage:.1f}%)",
                        inline=False
                    )

                embed.set_footer(text=f"総投票数: {total_votes}票")
                await interaction.response.send_message(embed=embed)

            select_menu.callback = select_callback
            view = discord.ui.View()
            view.add_item(select_menu)
            await interaction.response.send_message("終了する投票を選択してください：", view=view, ephemeral=True)

        else:
            await interaction.response.send_message(
                "無効なアクションです。'create' または 'end' を指定してください。",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Poll(bot))