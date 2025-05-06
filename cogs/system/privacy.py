import discord
from discord.ext import commands
import sqlite3
import os

class Privacy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.private_users = set()
        self._original_dispatch = bot.dispatch

        # データベースの初期化
        self.db_path = 'data/privacymode.db'
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        # データベースからプライバシーユーザーをロード
        self._load_private_users()

        async def dispatch(event_name, *args, **kwargs):
            if event_name == 'on_message':
                message = args[0]
                if message.author.id in self.private_users:
                    return  # イベントを破棄
            await self._original_dispatch(event_name, *args, **kwargs)

        bot.dispatch = dispatch

    def _init_db(self):
        """データベースを初期化します。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS private_users (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            conn.commit()

    def _load_private_users(self):
        """データベースからプライバシーユーザーをロードします。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM private_users')
            rows = cursor.fetchall()
            self.private_users = {row[0] for row in rows}

    def _add_private_user(self, user_id: int):
        """プライバシーユーザーをデータベースに追加します。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO private_users (user_id) VALUES (?)', (user_id,))
            conn.commit()

    def _remove_private_user(self, user_id: int):
        """プライバシーユーザーをデータベースから削除します。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM private_users WHERE user_id = ?', (user_id,))
            conn.commit()

    @commands.slash_command(name='privacy', description='プライバシーモードを切り替えます。')
    async def privacy(self, ctx: discord.ApplicationContext):
        """自身をプライバシーモードにして以降のイベントを一切受け付けなくします。再度実行で解除されます。"""
        uid = ctx.author.id
        if uid in self.private_users:
            self.private_users.remove(uid)
            self._remove_private_user(uid)
            await ctx.respond('プライバシーモードを解除しました。', ephemeral=True)
        else:
            self.private_users.add(uid)
            self._add_private_user(uid)
            try:
                await ctx.author.send('プライバシーモードが有効になりました。以降一切のコマンドやメッセージを受け取りません。そのため、botの仕様が不可能になります。\nしかし、荒らし対策系は安全のため引き続き検知します。')
            except discord.Forbidden:
                pass
            await ctx.respond('プライバシーモードを有効化しました。', ephemeral=True)


    def is_private_user(self, user_id: int) -> bool:
        """指定されたユーザーIDがプライバシーモードかどうかを確認します。
        他のコグからもこのメソッドを使用してプライバシーモードを確認できます。
        """
        return user_id in self.private_users

async def setup(bot: commands.Bot):
    await bot.add_cog(Privacy(bot))
